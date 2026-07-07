# ResourceOwner — auto-release for backend-local resources

A `ResourceOwner` is a hierarchical container that tracks
backend-local resources (buffer pins, snapshots, plan caches,
file descriptors, AIO handles, lock-local references) and
releases them automatically when its owning context ends —
transaction commit/abort, subtransaction unwind, portal close,
or error unwind. Replaces error-prone manual cleanup.

Anchors:
- `source/src/include/utils/resowner.h` — public API
  [verified-by-code]
- `source/src/backend/utils/resowner/resowner.c` —
  implementation
- `knowledge/subsystems/utils-mmgr.md` — companion: memory
  contexts (which the ResourceOwner subsystem mirrors in
  shape, distinct in purpose)

## The opaque type

```c
typedef struct ResourceOwnerData *ResourceOwner;
extern PGDLLIMPORT ResourceOwner CurrentResourceOwner;
```

[verified-by-code `resowner.h:27-33`]

The struct is opaque — callers see only the typedef. Every
ResourceOwner has:

- A **parent** (or NULL if top-level).
- A list of child ResourceOwners.
- Per-resource-kind tables of currently-held resources.

`CurrentResourceOwner` is the thread-local "where to record new
resources." Backend code calls `ResourceOwnerRemember(...)` to
register a new resource against `CurrentResourceOwner`.

## The hierarchy

A backend creates a ResourceOwner per:

- **TopTransaction** — owns top-level transaction resources.
- **CurTransaction** — current subtransaction (chains to
  TopTransaction's owner).
- **Portal** — long-lived cursor; outlives the transaction
  that created it.
- **Each plan / planner invocation** — short-lived.
- **Auxiliary processes** — startup / bgwriter / walwriter
  have their own (`CreateAuxProcessResourceOwner()`
  [verified-by-code `resowner.h:159`]).

When a subtransaction commits, its ResourceOwner's children
get re-parented to the subtransaction's parent (resources
"escape" upward). When it aborts, the ResourceOwner is
released — every resource it holds is cleaned up via the
appropriate `ReleaseResource` callback.

## The two-phase release

[verified-by-code `resowner.h:139-142`]

```c
ResourceOwnerRelease(owner, phase, isCommit, isTopLevel);
```

Where `phase` is one of:

| Phase | When | What |
|---|---|---|
| `RESOURCE_RELEASE_BEFORE_LOCKS` | Pre-commit | Release plan caches, snapshots, buffers, files |
| `RESOURCE_RELEASE_LOCKS` | Lock release | Release relation / object locks |
| `RESOURCE_RELEASE_AFTER_LOCKS` | Post-commit | Release things that depended on locks (e.g. relcache pins) |

The phasing matters because some cleanup depends on locks
still being held (e.g. inspecting a relation to free its
relcache pin), and other cleanup must happen before locks are
released (e.g. releasing buffer pins must happen before the
lock on the buffer's relation is released).

[from-comment `resowner.h:88-89`]

> Note that the callbacks occur post-commit or post-abort, so
> the callback functions can only do noncritical cleanup and
> must not fail.

Cleanup callbacks **must not raise an error**. They run after
the transaction's success/failure is decided; failing here
would leave the backend in a corrupt state.

## The resource-kind descriptor

```c
typedef struct ResourceOwnerDesc
{
    const char *name;
    ResourceReleasePhase release_phase;
    ResourceReleasePriority release_priority;
    void (*ReleaseResource) (Datum res);
    char *(*DebugPrint) (Datum res);
} ResourceOwnerDesc;
```

[verified-by-code `resowner.h:91-120`]

Every resource kind (buffer pin, snapshot, locallock, ...) is
described by one of these. The `ReleaseResource` callback is
what runs on release.

`DebugPrint` produces a string used in `WARNING: <resource>
leaked: %s` when a resource isn't released by transaction end.
A NULL `DebugPrint` produces a generic format.

## Registration: the Remember/Forget pair

```c
ResourceOwnerEnlarge(owner);
ResourceOwnerRemember(owner, value, kind);
... use the resource ...
ResourceOwnerForget(owner, value, kind);
```

[verified-by-code `resowner.h:148-150`]

The pattern:

1. **Enlarge** — reserve space in the owner's table before
   the registration. Doing this BEFORE acquiring the resource
   means the registration cannot fail with the resource
   already acquired (which would leak).
2. **Remember** — register.
3. **Forget** — deregister on normal release.

If the code path between Remember and Forget raises an
ERROR, the longjmp unwinds to the closest error handler,
which calls `ResourceOwnerRelease`, which calls every
remembered resource's `ReleaseResource`. The resource is
freed.

## Special-purpose typed variants

[verified-by-code `resowner.h:164-170`]

For hot paths, type-specific wrappers exist:

- `ResourceOwnerRememberLock(owner, locallock)` /
  `ResourceOwnerForgetLock(owner, locallock)` — bypasses the
  Datum cast for the common lock-tracking case.
- `ResourceOwnerRememberAioHandle(owner, ioh_node)` /
  `ResourceOwnerForgetAioHandle(owner, ioh_node)` — for the
  AIO subsystem.

Built-in resource kinds have their own typed wrappers; one-off
extensions use the generic Remember/Forget + Datum.

## Module callbacks

[verified-by-code `resowner.h:122-129`]

```c
typedef void (*ResourceReleaseCallback) (
    ResourceReleasePhase phase,
    bool isCommit,
    bool isTopLevel,
    void *arg);

RegisterResourceReleaseCallback(callback, arg);
```

A loadable module can register a global callback that fires on
every ResourceOwnerRelease. Used by extensions that hold
backend-global resources (file descriptors to FDW remote
connections, etc.) without per-resource tracking.

## Common review-time concerns

- **`ResourceOwnerEnlarge` BEFORE acquiring the resource.**
  Reverse order = leak path on table-grow OOM.
- **Don't ERROR from `ReleaseResource`.** Use `PG_TRY`/
  `PG_CATCH` if a release step might fail; convert errors to
  `WARNING`s.
- **Per-kind descriptor is `const`.** Allocate once at module
  load; never modify.
- **`CurrentResourceOwner` save/restore.** Code that
  temporarily switches owners (e.g. for a sub-step) must save
  and restore in a PG_TRY/PG_CATCH to handle errors.

## Invariants

- **[INV-1]** Enlarge before Remember; Forget on normal
  release; ReleaseResource on error / commit / abort.
- **[INV-2]** Release callbacks MUST NOT fail; they run post-
  decision.
- **[INV-3]** Two-phase release (before-locks / locks /
  after-locks) preserves invariants about what's accessible
  during cleanup.
- **[INV-4]** Subtransaction commit re-parents children;
  abort releases.
- **[INV-5]** `ResourceOwnerDesc` is const; allocate once.

## Useful greps

- All resource kinds in the tree:
  `grep -RIn 'ResourceOwnerDesc' source/src/backend | head -20`
- Typed Remember/Forget pairs:
  `grep -n 'ResourceOwnerRemember\w*' source/src/include/utils/resowner.h`
- CurrentResourceOwner save/restore patterns:
  `grep -RIn 'CurrentResourceOwner =' source/src/backend | head -20`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/resowner/resowner.c`](../files/src/backend/utils/resowner/resowner.c.md) | — | implementation |
| `src/backend/utils/resowner/resowner_test.c` | — | small example using the API |
| [`src/include/utils/resowner.h`](../files/src/include/utils/resowner.md) | — | public API + descriptor type |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/subsystems/utils-mmgr.md` — memory contexts;
  parallel hierarchy + auto-release semantics, but distinct
  in scope.
- `.claude/skills/memory-contexts/SKILL.md` — companion
  cleanup mechanism; memory + ResourceOwners often pair.
- `.claude/skills/error-handling/SKILL.md` — ereport/longjmp
  unwinds; ResourceOwner is one of the unwind hooks.
- `.claude/skills/locking/SKILL.md` — `LOCALLOCK` is one of
  the typed resource kinds.
- `source/src/include/utils/resowner.h` — public API +
  descriptor type.
- `source/src/backend/utils/resowner/resowner.c` —
  implementation.
- `source/src/backend/utils/resowner/resowner_test.c` — small
  example using the API.
