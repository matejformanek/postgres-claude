# Snapshots — ActiveSnapshot stack and RegisteredSnapshots heap

A live PG backend can hold many snapshots at once: one or more
on the **ActiveSnapshot stack** (the executor's notion of
"current snapshot for this query/portal/savepoint"), plus zero
or more in **RegisteredSnapshots** (a pairing heap ordered by
xmin, holding snapshots whose lifetime is tied to a
`ResourceOwner`).  A single `SnapshotData` can live in both —
the `regd_count` and `active_count` reference counters track
each side independently, and the snapshot is freed only when
both reach zero.

This doc covers the two refcount structures, how `Push`/`Pop`
and `Register`/`Unregister` interact, and how
`SnapshotResetXmin` recomputes the global xmin contribution.
For the static `CurrentSnapshot`/`SecondarySnapshot`/
`CatalogSnapshot` slots see
[[snapshot-static-and-current]].  For exported / historic /
parallel-shared snapshots see
[[snapshot-export-historic-parallel]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/utils/time/snapmgr.c` — the stack + heap + refcount logic
- `source/src/include/utils/snapshot.h` — `active_count`, `regd_count`, `ph_node`
- `source/src/backend/utils/resowner/resowner.c` — `ResourceOwner` integration

## The two reference counts

Every `SnapshotData` has two refcounts (in `snapshot.h`):

```c
int active_count;       /* refcount on ActiveSnapshot stack */
int regd_count;         /* refcount on RegisteredSnapshots heap + others */
```

`copied` flags whether the snapshot is a heap allocation
(eligible for `FreeSnapshot`) or a pointer to a static slot
(must not be freed).  A snapshot is freed when **both
counters are zero** AND `copied = true`.

The two counts answer different questions:

- **`active_count`** — how many `ActiveSnapshotElt` entries
  on the stack point at me?  Bumped by `PushActiveSnapshot`,
  decremented by `PopActiveSnapshot`.
- **`regd_count`** — how many `ResourceOwner` references +
  `RegisteredSnapshots` heap entries point at me?  Bumped by
  `RegisterSnapshot`, decremented by `UnregisterSnapshot`.
  Catalog snapshot increments it but uses neither — see
  [[snapshot-static-and-current]] §Catalog snapshot.

## ActiveSnapshot — a singly-linked stack

`snapmgr.c:173-181` [verified-by-code]:

```c
typedef struct ActiveSnapshotElt
{
    Snapshot                 as_snap;
    int                      as_level;
    struct ActiveSnapshotElt *as_next;
} ActiveSnapshotElt;

static ActiveSnapshotElt *ActiveSnapshot = NULL;
```

Three fields:

- **`as_snap`** — the snapshot itself.  Each element accounts
  for exactly one `as_snap->active_count`.
- **`as_level`** — the subtransaction nest level that "owns"
  this stack element.  Used by `AtSubAbort_Snapshot` to pop
  elements when a savepoint rolls back.
- **`as_next`** — the singly-linked next pointer.

The invariant from `snapmgr.c:170-171` [from-comment]:

> NB: the code assumes that elements in this list are in
> non-increasing order of as_level; also, the list must be
> NULL-terminated.

So newer (deeper subxact) entries are on top, with
monotonically non-decreasing `as_level` from top to bottom.

The stack lives in `TopTransactionContext`
(`MemoryContextAlloc(TopTransactionContext, ...)` at line 703)
so all `ActiveSnapshotElt`s evaporate at xact end.

## `PushActiveSnapshot` — the standard pattern

`snapmgr.c:681-721` [verified-by-code]:

```c
void
PushActiveSnapshot(Snapshot snapshot)
{
    PushActiveSnapshotWithLevel(snapshot, GetCurrentTransactionNestLevel());
}

void
PushActiveSnapshotWithLevel(Snapshot snapshot, int snap_level)
{
    ActiveSnapshotElt *newactive;

    Assert(snapshot != InvalidSnapshot);
    Assert(ActiveSnapshot == NULL || snap_level >= ActiveSnapshot->as_level);

    newactive = MemoryContextAlloc(TopTransactionContext, sizeof(ActiveSnapshotElt));

    if (snapshot == CurrentSnapshot || snapshot == SecondarySnapshot ||
        !snapshot->copied)
        newactive->as_snap = CopySnapshot(snapshot);
    else
        newactive->as_snap = snapshot;

    newactive->as_next = ActiveSnapshot;
    newactive->as_level = snap_level;

    newactive->as_snap->active_count++;

    ActiveSnapshot = newactive;
}
```

Three details to know:

### 1. Static-slot snapshots get copied

```c
if (snapshot == CurrentSnapshot || snapshot == SecondarySnapshot ||
    !snapshot->copied)
    newactive->as_snap = CopySnapshot(snapshot);
```

This is the auto-promotion that lets the typical
`PushActiveSnapshot(GetTransactionSnapshot())` work safely.
`GetTransactionSnapshot` returns a pointer to
`CurrentSnapshotData`, which gets clobbered by the next call;
`PushActiveSnapshot` `CopySnapshot`s it first, so the version
on the stack is stable.

The `!snapshot->copied` check catches the case where the
caller passed a snapshot that's still pointing at a static
slot but isn't one of the well-known ones — also forced-copy.

### 2. The `as_level` invariant

`Assert(ActiveSnapshot == NULL || snap_level >= ActiveSnapshot->as_level)`

— the new top must be at *the same or deeper* nest level
than the current top.  This is what makes subxact abort
cleanup work in stack order.

### 3. `active_count` increments by 1 per push

Per the comment at lines 167-168 [from-comment]:

> Each element here accounts for exactly one active_count on
> SnapshotData.

So if you `PushActiveSnapshot(snap)` twice, `active_count`
becomes 2 — even though there's one snapshot pointer shared
by two stack elements.  The two `Pop`s drop it back to 0.

## `PopActiveSnapshot` — refcount + free

`snapmgr.c:774-793` [verified-by-code]:

```c
void
PopActiveSnapshot(void)
{
    ActiveSnapshotElt *newstack;

    newstack = ActiveSnapshot->as_next;

    Assert(ActiveSnapshot->as_snap->active_count > 0);

    ActiveSnapshot->as_snap->active_count--;

    if (ActiveSnapshot->as_snap->active_count == 0 &&
        ActiveSnapshot->as_snap->regd_count == 0)
        FreeSnapshot(ActiveSnapshot->as_snap);

    pfree(ActiveSnapshot);
    ActiveSnapshot = newstack;

    SnapshotResetXmin();
}
```

Four steps:

1. Decrement `active_count`.
2. If both refcounts are now zero, free the snapshot heap
   memory.
3. Free the `ActiveSnapshotElt`.
4. Call `SnapshotResetXmin` to maybe advance PGPROC->xmin.

The "both refcounts zero" check is the **double-counted
freedom guard** — a snapshot held by both a `RegisterSnapshot`
and a `PushActiveSnapshot` shouldn't be freed by the `Pop`
because the `Register` side is still holding it.

## `UpdateActiveSnapshotCommandId` — mutating the top

`snapmgr.c:743-766` [verified-by-code]:

```c
void
UpdateActiveSnapshotCommandId(void)
{
    CommandId save_curcid, curcid;

    Assert(ActiveSnapshot != NULL);
    Assert(ActiveSnapshot->as_snap->active_count == 1);
    Assert(ActiveSnapshot->as_snap->regd_count == 0);

    save_curcid = ActiveSnapshot->as_snap->curcid;
    curcid = GetCurrentCommandId(false);
    if (IsInParallelMode() && save_curcid != curcid)
        elog(ERROR, "cannot modify commandid in active snapshot during a parallel operation");
    ActiveSnapshot->as_snap->curcid = curcid;
}
```

The two Asserts are the **safety contract** for in-place
mutation:

- `active_count == 1` — exactly one reference, so no other
  code path is reading this snapshot.
- `regd_count == 0` — nobody has registered it, so we're not
  going to confuse RegisteredSnapshots' invariants.

If the caller wants to mutate but doesn't satisfy this
contract, they must use `PushCopiedSnapshot` (`snapmgr.c:731-735`)
[verified-by-code] which forces a fresh `CopySnapshot`:

```c
void
PushCopiedSnapshot(Snapshot snapshot)
{
    PushActiveSnapshot(CopySnapshot(snapshot));
}
```

The parallel-mode error: workers share the leader's snapshot
via DSM, so silently changing `curcid` would create
inconsistencies.  The workers' guard catches it.

## `RegisteredSnapshots` — a pairing heap ordered by xmin

`snapmgr.c:190` [verified-by-code]:

```c
static pairingheap RegisteredSnapshots = {&xmin_cmp, NULL, NULL};
```

The comparator at lines 909-921 [verified-by-code]:

```c
static int
xmin_cmp(const pairingheap_node *a, const pairingheap_node *b, void *arg)
{
    const SnapshotData *asnap = pairingheap_const_container(SnapshotData, ph_node, a);
    const SnapshotData *bsnap = pairingheap_const_container(SnapshotData, ph_node, b);

    if (TransactionIdPrecedes(asnap->xmin, bsnap->xmin))
        return 1;
    else if (TransactionIdFollows(asnap->xmin, bsnap->xmin))
        return -1;
    else
        return 0;
}
```

PG pairing heaps are **max-heaps** in the comparator sense; the
comparator returns +1 when `a` should be "earlier" in the
heap.  The above returns +1 when `a->xmin` precedes
`b->xmin`, so the smallest xmin is at the top.

That's the property `SnapshotResetXmin` relies on:
`pairingheap_first(&RegisteredSnapshots)` returns the entry
with the **lowest** xmin, which is exactly what
PGPROC->xmin should be set to.

## `RegisterSnapshot` — refcount on a ResourceOwner

`snapmgr.c:818-856` [verified-by-code]:

```c
Snapshot
RegisterSnapshotOnOwner(Snapshot snapshot, ResourceOwner owner)
{
    Snapshot snap;

    if (snapshot == InvalidSnapshot)
        return InvalidSnapshot;

    /* Static snapshot?  Create a persistent copy */
    snap = snapshot->copied ? snapshot : CopySnapshot(snapshot);

    ResourceOwnerEnlarge(owner);
    snap->regd_count++;
    ResourceOwnerRememberSnapshot(owner, snap);

    if (snap->regd_count == 1)
        pairingheap_add(&RegisteredSnapshots, &snap->ph_node);

    return snap;
}
```

Three actions:

1. **Force a copy** if the snapshot is static (`!copied`).
2. **Increment refcount + register with ResourceOwner.**
3. **Add to RegisteredSnapshots heap** only on the first
   registration (`regd_count == 1`).  Subsequent registers
   just bump the count.

The `ResourceOwnerEnlarge` reserves space in the resource
owner's hash before the registration completes — this makes
the registration atomic from the resource owner's perspective.

## `UnregisterSnapshot` — symmetric reverse

`snapmgr.c:866-903` [verified-by-code]:

```c
static void
UnregisterSnapshotNoOwner(Snapshot snapshot)
{
    Assert(snapshot->regd_count > 0);
    Assert(!pairingheap_is_empty(&RegisteredSnapshots));

    snapshot->regd_count--;
    if (snapshot->regd_count == 0)
        pairingheap_remove(&RegisteredSnapshots, &snapshot->ph_node);

    if (snapshot->regd_count == 0 && snapshot->active_count == 0)
    {
        FreeSnapshot(snapshot);
        SnapshotResetXmin();
    }
}
```

The two `== 0` checks separate the two effects:

- **`regd_count == 0`** → remove from heap (free up xmin
  contribution).
- **`regd_count == 0 && active_count == 0`** → free the
  snapshot and recompute PGPROC->xmin.

Recomputing `xmin` always follows the heap removal so the
recomputation sees the post-removal heap state.

## `SnapshotResetXmin` — pushing PGPROC->xmin forward

`snapmgr.c:936-955` [verified-by-code]:

```c
static void
SnapshotResetXmin(void)
{
    Snapshot minSnapshot;

    if (ActiveSnapshot != NULL)
        return;

    if (pairingheap_is_empty(&RegisteredSnapshots))
    {
        MyProc->xmin = TransactionXmin = InvalidTransactionId;
        return;
    }

    minSnapshot = pairingheap_container(SnapshotData, ph_node,
                                        pairingheap_first(&RegisteredSnapshots));

    if (TransactionIdPrecedes(MyProc->xmin, minSnapshot->xmin))
        MyProc->xmin = TransactionXmin = minSnapshot->xmin;
}
```

Three cases:

### Case 1 — ActiveSnapshot not empty

```c
if (ActiveSnapshot != NULL)
    return;
```

The active stack is treated as opaque from this function's
perspective.  The reasoning in the function comment at lines
931-934 [from-comment]:

> For efficiency, we only consider recomputing PGPROC->xmin
> when the active snapshot stack is empty; this allows us not
> to need to track which active snapshot is oldest.

So PGPROC->xmin doesn't change while active snapshots exist —
even if the oldest active snapshot has a higher xmin than the
oldest registered one, no advance happens.  This is a
deliberate trade-off: cheap reset path, modest xmin-advance
quality.

### Case 2 — Both empty

```c
if (pairingheap_is_empty(&RegisteredSnapshots))
{
    MyProc->xmin = TransactionXmin = InvalidTransactionId;
    return;
}
```

No snapshots at all — release PGPROC->xmin entirely.  Vacuum
can now claim everything we used to be holding back.

### Case 3 — Some registered, no active

```c
minSnapshot = pairingheap_container(SnapshotData, ph_node,
                                    pairingheap_first(&RegisteredSnapshots));

if (TransactionIdPrecedes(MyProc->xmin, minSnapshot->xmin))
    MyProc->xmin = TransactionXmin = minSnapshot->xmin;
```

Get the smallest-xmin registered snapshot.  If our current
PGPROC->xmin is older than that, advance it.  This is the
classic "advance global xmin on snapshot release" mechanic.

Notice the **conditional advance**: we never *retract*
PGPROC->xmin, only push it forward.  Retraction would be
wrong because `TransactionXmin` is the basis for the
"oldest XID that could still be visible" promise.

## Subxact integration — Commit and Abort

### `AtSubCommit_Snapshot` — relabel to parent level

`snapmgr.c:960-975` [verified-by-code]:

```c
void
AtSubCommit_Snapshot(int level)
{
    ActiveSnapshotElt *active;

    for (active = ActiveSnapshot; active != NULL; active = active->as_next)
    {
        if (active->as_level < level)
            break;
        active->as_level = level - 1;
    }
}
```

On subxact commit, all `ActiveSnapshotElt`s tagged with this
nest level get their `as_level` decremented by 1 — they now
belong to the parent.  The loop terminates at the first
element with `as_level < level` because everything below it
is already at the parent level or above.

No snapshots are popped — the *element* persists, just its
ownership label changes.

### `AtSubAbort_Snapshot` — pop everything at this level

`snapmgr.c:981-1009` [verified-by-code]:

```c
void
AtSubAbort_Snapshot(int level)
{
    while (ActiveSnapshot && ActiveSnapshot->as_level >= level)
    {
        ActiveSnapshotElt *next;

        next = ActiveSnapshot->as_next;

        Assert(ActiveSnapshot->as_snap->active_count >= 1);
        ActiveSnapshot->as_snap->active_count -= 1;

        if (ActiveSnapshot->as_snap->active_count == 0 &&
            ActiveSnapshot->as_snap->regd_count == 0)
            FreeSnapshot(ActiveSnapshot->as_snap);

        pfree(ActiveSnapshot);
        ActiveSnapshot = next;
    }

    SnapshotResetXmin();
}
```

Walk down the stack popping every element with `as_level >=
level`.  Same refcount + free dance as `PopActiveSnapshot`.
The terminating `SnapshotResetXmin` may now advance
PGPROC->xmin if the abort dropped enough snapshots.

This is what makes `ROLLBACK TO SAVEPOINT` correctly release
snapshots created inside the savepoint.

## End-of-transaction cleanup — `AtEOXact_Snapshot`

`snapmgr.c:1015-1105` [verified-by-code].  Six steps:

### 1. Drop `FirstXactSnapshot`

```c
if (FirstXactSnapshot != NULL)
{
    pairingheap_remove(&RegisteredSnapshots, &FirstXactSnapshot->ph_node);
}
FirstXactSnapshot = NULL;
```

The transaction-snapshot-mode first snapshot was registered
manually (line 327-328 in `GetTransactionSnapshot`); now
unregister it.  No `FreeSnapshot` — the memory lives in
`TopTransactionContext` and will get released wholesale.

### 2. Clean up exported snapshots

Lines 1038-1066 [verified-by-code]:

```c
foreach(lc, exportedSnapshots)
{
    ExportedSnapshot *esnap = (ExportedSnapshot *) lfirst(lc);

    if (unlink(esnap->snapfile))
        elog(WARNING, "could not unlink file \"%s\": %m", esnap->snapfile);

    pairingheap_remove(&RegisteredSnapshots, &esnap->snapshot->ph_node);
}
exportedSnapshots = NIL;
```

Unlink the pg_snapshots files, drop the entries from the
registered heap.  Unlink failures get a WARNING — late in
commit there's no way to abort, and the file leak is harmless.

### 3. Drop catalog snapshot

```c
InvalidateCatalogSnapshot();
```

### 4. Sanity check on commit

```c
if (isCommit)
{
    if (!pairingheap_is_empty(&RegisteredSnapshots))
        elog(WARNING, "registered snapshots seem to remain after cleanup");

    for (active = ActiveSnapshot; active != NULL; active = active->as_next)
        elog(WARNING, "snapshot %p still active", active);
}
```

Either of these warnings indicates a coding bug: callers
should have matched their `Register`/`Unregister` and
`Push`/`Pop` properly.

### 5. Reset all state

```c
ActiveSnapshot = NULL;
pairingheap_reset(&RegisteredSnapshots);
CurrentSnapshot = NULL;
SecondarySnapshot = NULL;
FirstSnapshotSet = false;
```

### 6. Final xmin reset

```c
if (resetXmin)
    SnapshotResetXmin();
```

Conditional because the normal commit path already called
`ProcArrayEndTransaction` which cleared `MyProc->xmin`.  Only
abort paths need this final reset.

## The ResourceOwner integration

`snapmgr.c:224-243` [verified-by-code]:

```c
static const ResourceOwnerDesc snapshot_resowner_desc =
{
    .name = "snapshot reference",
    .release_phase = RESOURCE_RELEASE_AFTER_LOCKS,
    .release_priority = RELEASE_PRIO_SNAPSHOT_REFS,
    .ReleaseResource = ResOwnerReleaseSnapshot,
    .DebugPrint = NULL
};

static inline void
ResourceOwnerRememberSnapshot(ResourceOwner owner, Snapshot snap)
{
    ResourceOwnerRemember(owner, PointerGetDatum(snap), &snapshot_resowner_desc);
}
static inline void
ResourceOwnerForgetSnapshot(ResourceOwner owner, Snapshot snap)
{
    ResourceOwnerForget(owner, PointerGetDatum(snap), &snapshot_resowner_desc);
}
```

Snapshots release **after locks**.  This matters because
visibility checks during lock release might still need a
valid snapshot pointer; releasing snapshots first would crash.

The `ReleaseResource` callback fires only if the caller forgot
to `UnregisterSnapshot` — the resource owner's leak detector
catches it and calls `UnregisterSnapshotNoOwner` on our
behalf.

## Invariants worth remembering

1. **A snapshot dies only when `active_count == 0 &&
   regd_count == 0` (and is `copied = true`).**
2. **`as_level` is monotonically non-decreasing from top to
   bottom of the stack.**  Push enforces; abort relies on it.
3. **`PushActiveSnapshot` of a static-slot snapshot copies
   first.**  You can pass `GetTransactionSnapshot()`
   directly.
4. **`UpdateActiveSnapshotCommandId` requires
   `active_count == 1 && regd_count == 0`.**  Use
   `PushCopiedSnapshot` otherwise.
5. **`RegisteredSnapshots` is a pairing heap keyed by xmin,
   smallest at top.**  `pairingheap_first` returns the
   bottleneck.
6. **`RegisterSnapshot` adds to the heap only on first
   reference** (`regd_count == 1`); subsequent registers
   just bump the count.
7. **`SnapshotResetXmin` skips early if `ActiveSnapshot !=
   NULL`.**  Active snapshots aren't tracked by xmin; they
   pin PGPROC->xmin via their existence alone.
8. **`AtSubCommit_Snapshot` relabels; `AtSubAbort_Snapshot`
   pops.**  Subtransaction commit is a no-op on the stack
   structure.
9. **`AtEOXact_Snapshot` warns about leftover registered or
   active snapshots on commit.**  These are bugs.
10. **Snapshot release runs in
    `RESOURCE_RELEASE_AFTER_LOCKS`** — locks first, then
    snapshots, then catalogs.

## Useful greps

```bash
# Stack mutation API
grep -n "PushActiveSnapshot\|PopActiveSnapshot\|GetActiveSnapshot\|UpdateActiveSnapshotCommandId" \
    source/src/backend/utils/time/snapmgr.c

# Registered-heap API
grep -n "RegisterSnapshot\|UnregisterSnapshot\|RegisteredSnapshots" \
    source/src/backend/utils/time/snapmgr.c

# Refcount mutation sites
grep -n "active_count\|regd_count" \
    source/src/backend/utils/time/snapmgr.c

# Subxact integration
grep -n "AtSubCommit_Snapshot\|AtSubAbort_Snapshot\|AtEOXact_Snapshot" \
    source/src/backend/utils/time/snapmgr.c

# ResourceOwner hookup
grep -n "snapshot_resowner_desc\|ResourceOwnerRememberSnapshot\|ResourceOwnerForgetSnapshot" \
    source/src/backend/utils/time/snapmgr.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/resowner/resowner.c`](../files/src/backend/utils/resowner/resowner.c.md) | — | ResourceOwner integration |
| [`src/backend/utils/time/snapmgr.c`](../files/src/backend/utils/time/snapmgr.c.md) | — | stack + heap + refcount logic |
| [`src/include/utils/snapshot.h`](../files/src/include/utils/snapshot.h.md) | — | active_count, regd_count, ph_node |

<!-- /callsites:auto -->

## Cross-references

- [[snapshot-static-and-current]] — the six static slots that
  feed `Push`/`Register`.
- [[snapshot-export-historic-parallel]] — exported snapshots
  manually `pairingheap_add` into the registered heap.
- [[xmin-horizon-management]] — `SnapshotResetXmin` is the
  per-backend contribution to the global xmin.
- [[heap-tuple-visibility-mvcc]] — consumes the snapshot data
  during scan.
- [[subtransaction-stack]] — the subxact infrastructure that
  `AtSubAbort_Snapshot` participates in.
- [[commit-transaction-sequence]] — `AtEOXact_Snapshot` is one
  of the cleanup-after-commit callbacks.
- [[memory-contexts]] — `TopTransactionContext` is the home of
  `ActiveSnapshotElt` and `CopySnapshot` allocations.
