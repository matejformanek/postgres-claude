---
name: resource-owners
description: PostgreSQL's ResourceOwner infrastructure — `src/backend/utils/resowner/resowner.c` — the tree of resource-tracking objects that release buffer pins, catcache refs, tuple descriptors, snapshots, plancache refs, DSM segments etc. automatically on transaction/subtransaction/portal boundaries. Loads when the user asks about `CurrentResourceOwner`, `ResourceOwnerCreate`/`ResourceOwnerRelease`, why a subtransaction cleanup didn't free a resource, the callback-based extension API (PG 17+), adding a new resource kind, or debugging "resource owner leak" WARNINGs. Skip when the ask is about MemoryContexts (parallel infrastructure but different lifecycle — see `memory-contexts`) or about locks (separate — `locking`).
when_to_load: Debug resource-owner-leak WARNINGs; add a new resource kind (extension or new core resource); understand PG 17+ callback API; work with subtransaction cleanup timing; investigate portal-owner vs transaction-owner boundary bugs.
companion_skills:
  - memory-contexts
  - locking
---

# resource-owners — automatic cleanup for reference-counted resources

Every backend has a tree of ResourceOwner objects. When a scope exits (subtransaction ends, transaction commits, portal closes), its ResourceOwner releases all resources it holds. This is how PG can safely leak buffers, syscache refs, snapshots, plans across many code paths — the cleanup is centralized.

Different from **MemoryContexts** — which manage `palloc`ed memory. Resowners manage **reference-counted or open resources** that need special release semantics (unpin a buffer, release a catcache ref, close a DSM handle).

## The file

Single-file subsystem:

- `src/backend/utils/resowner/resowner.c` (~1000 lines) — implementation.
- `src/include/utils/resowner.h` (~150 lines) — the callback-based public API (PG 17+).
- `src/backend/utils/resowner/README` — the definitive design doc; shorter than this skill.

## Two flavors — legacy and callback-based

### Legacy: per-resource-kind arrays (pre-PG-17)

Historically, resowner.c had hard-coded arrays for each resource kind (buffer pins, catcache refs, plancache refs, tupledesc refs, etc.). Each kind had `Resource<Kind>OwnerRemember` and `Resource<Kind>OwnerForget`; on release, the resowner scanned each array and released.

This required a code change in resowner.c whenever a new resource kind was added — problematic for extensions.

### PG 17+ callback-based API

Extensions and core resource kinds can now register their own release callback:

```c
static const ResourceOwnerDesc my_resource_desc = {
    "my resource",
    RELEASE_PRIO_FIRST,       /* release order */
    RESOURCE_RELEASE_BEFORE_LOCKS,
    my_release_callback,
    my_debug_print_callback,
};

/* At creation time */
ResourceOwnerRemember(owner, PointerGetDatum(my_resource), &my_resource_desc);

/* At normal release */
ResourceOwnerForget(owner, PointerGetDatum(my_resource), &my_resource_desc);
```

The callback receives the resource and does whatever release is appropriate. Callbacks are sorted by `release_prio` so ordering-sensitive resources release in a defined sequence.

## The tree structure

```
TopTransactionResourceOwner
    ├── SubtransactionResourceOwner_1 (savepoint 1)
    │       ├── PortalResourceOwner_A
    │       └── (short-lived scope resowner)
    ├── SubtransactionResourceOwner_2 (savepoint 2)
    │       └── ...
    └── CurTransactionResourceOwner (implicit)
```

Each resowner has:

- **Parent** — pointer.
- **Child list** — siblings + first-child pointer.
- **Resources** — the array/list of held resources per kind.
- **Callbacks** — per-resource `ResourceOwnerDesc *`.

`CurrentResourceOwner` — the global. `palloc` doesn't touch resowners; only resource-remembering functions do.

## The release cycle

`ResourceOwnerRelease(owner, phase, isCommit, isTopLevel)` runs in **three phases**:

1. **`RESOURCE_RELEASE_BEFORE_LOCKS`** — release resources that need to happen BEFORE locks are released (e.g. buffer pins so nobody starts a new scan on a page we still hold).
2. **`RESOURCE_RELEASE_LOCKS`** — release the heavyweight and lightweight locks themselves (via `LockReleaseAll` — separate machinery).
3. **`RESOURCE_RELEASE_AFTER_LOCKS`** — release resources whose cleanup is safe after locks are gone (e.g. catcache refs — the catcache entry's refcount).

The three-phase discipline is why callback registration takes a `phase` field.

## What a resource kind must have

For every kind:

- **Release order priority** — `RELEASE_PRIO_FIRST` / `LAST` — nudges when in the release loop.
- **Phase** — before-locks vs after-locks.
- **Release callback** — what to do with each remembered resource on release.
- **Debug print callback** — for `WARNING: leaked resource` messages during development.

## Legacy resource kinds (still hard-coded)

Some resources predate the callback API and remain hard-coded in resowner.c:

- **Buffer pins** — released before locks.
- **Snapshots** — active snapshots decremented.
- **DSM segments** — detached.
- **Files** — closed via fd.c.
- **JIT contexts** — deleted.

Newer resources (starting PG 17) use the callback API — including plancache, tupledesc, some smgr handles.

## Common patch shapes

### Add a new callback-based resource kind

- Define a `ResourceOwnerDesc` struct with your release callback.
- At resource-acquisition: `ResourceOwnerRemember(CurrentResourceOwner, ptr, &desc)`.
- At normal release: `ResourceOwnerForget`.
- Test: create the resource inside a subtransaction, ROLLBACK, verify the callback fires.
- No changes to resowner.c required — the callback API is the extension point.

### Debug "WARNING: xxx leaked"

- Log identifies the resource kind and the resowner name.
- Common cause: a code path takes a resource but early-exits without calling `ResourceOwnerForget`.
- Fix: use PG_TRY/CATCH or ensure release is in a cleanup block.
- Sometimes: the resource is legitimately held past the reporting resowner's scope — need to re-parent or hand-off.

### Add a new resource-owner phase

Very rare. Would require:
- Adding phase enum value.
- Reorganizing the three-phase release loop.
- Auditing every existing callback for correct phase assignment.

Not done since the current three-phase design has held up.

## Pitfalls

- **`CurrentResourceOwner` changes on subtransaction entry** — code that captures `CurrentResourceOwner` in a local variable needs to be sure the captured resowner outlives the resource's expected lifetime.
- **`ResourceOwnerForget` on a non-existent resource silently succeeds** — but sets a warning-level `elog` in debug builds. Double-forgetting is silent — indicates a logic error somewhere.
- **Callbacks run in error paths too** — during transaction abort, callbacks fire while `elog(ERROR)` state is set. Callbacks must be reentrant-safe and can't themselves ereport.
- **PortalResourceOwner is a snapshot of its creating scope** — a cursor holds resources under a resowner created at cursor DECLARE time. If that resowner is a subtransaction's, the cursor dies on subtransaction rollback.
- **Extension-registered resource kinds need to survive extension unload** — if an extension's callback function pointer becomes invalid, release on a subsequent transaction crashes.
- **Resource-owner leaks are LOG level in production, WARNING in dev** — production may silently accumulate leaks (usually LWLocks or pins) until an eventual PANIC. Watch for the leak warnings in dev.
- **JIT context reuse depends on resowner** — a query with JIT has its context tied to a resowner. Recompiling on error paths can spuriously double-JIT.
- **`ResourceOwnerNewParent`** — rare API for re-parenting. Very tricky; only makes sense for handoff scenarios like moving a portal to a longer-lived owner.

## Related corpus

- **Idiom**: `subtransaction-stack` (savepoint accounting — layered atop resowner tree).
- **Subsystem**: `utils-cache` (typcache is a caller — its refcount management ties to resowner).
- **Data structure**: `resourceowner` (the struct definitions).
- **README**: `source/src/backend/utils/resowner/README` — authoritative + shorter than this skill.
- **Past planning**: `planning/jsonpath_leak/` + `planning/pgstat_progress_leak/` — both dealt with resource-lifecycle bugs at the boundary of memory contexts + resowners.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/utils/resowner/resowner.c
```

Single-file neighborhood.

## Boundary

**Use this skill** for `resowner.c` + the callback-based API + resource-kind additions.

**Don't use** for:
- **`MemoryContext`** — sibling infrastructure but for `palloc`ed memory. See `memory-contexts`.
- **Heavyweight or LWLock release** — that's `storage/lmgr/` — released as part of the resowner cycle but implemented separately.
- **Portal cleanup** — Portals HAVE resowners; portal lifecycle itself is in `utils/mmgr/portalmem.c`.
- **Subtransaction bookkeeping** — see `subtransaction-stack` idiom; resowner is one layer, xact.c is the outer scaffold.
