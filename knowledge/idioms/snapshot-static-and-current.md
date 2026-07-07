# Snapshots — the six static slots and what they're for

`snapmgr.c` defines **six** statically-allocated `SnapshotData`
structs.  Three are MVCC snapshots that get filled by
`GetSnapshotData` (the procarray scan); three are constant
"behave like X" markers used by visibility code.  Understanding
which is which — and which entry point fills which — is the
first hurdle in reading PG's snapshot infrastructure.

This doc covers the **static slots, the three MVCC entry
points, and the catalog-snapshot quirk**.  The reference-counted
ActiveSnapshot stack and `RegisteredSnapshots` pairing heap are
[[snapshot-active-stack-and-registered]].  Exported snapshots,
historic snapshots for logical decoding, and parallel-worker
serialization are [[snapshot-export-historic-parallel]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/utils/time/snapmgr.c` — all entry points + static slots
- `source/src/include/utils/snapshot.h` — `SnapshotData` struct
- `source/src/backend/storage/ipc/procarray.c` — `GetSnapshotData`

## The six static slots

`snapmgr.c:141-146` [verified-by-code]:

```c
static SnapshotData CurrentSnapshotData = {SNAPSHOT_MVCC};
static SnapshotData SecondarySnapshotData = {SNAPSHOT_MVCC};
static SnapshotData CatalogSnapshotData = {SNAPSHOT_MVCC};
SnapshotData SnapshotSelfData = {SNAPSHOT_SELF};
SnapshotData SnapshotAnyData = {SNAPSHOT_ANY};
SnapshotData SnapshotToastData = {SNAPSHOT_TOAST};
```

And their pointers (lines 149-152):

```c
static Snapshot CurrentSnapshot = NULL;
static Snapshot SecondarySnapshot = NULL;
static Snapshot CatalogSnapshot = NULL;
static Snapshot HistoricSnapshot = NULL;
```

The three MVCC slots get **dynamically updated** by
`GetSnapshotData`; the three behavior slots are **read-only
constants**.  `HistoricSnapshot` is a separate pointer that's
non-NULL only during logical decoding.

The comment at `snapmgr.c:130-139` [from-comment] is the plain-
English summary:

> CurrentSnapshot points to the only snapshot taken in
> transaction-snapshot mode, and to the latest one taken in a
> read-committed transaction.  SecondarySnapshot is a snapshot
> that's always up-to-date as of the current instant, even in
> transaction-snapshot mode.  It should only be used for
> special-purpose code (say, RI checking.)  CatalogSnapshot
> points to an MVCC snapshot intended to be used for catalog
> scans; we must invalidate it whenever a system catalog
> change occurs.
>
> These SnapshotData structs are static to simplify memory
> allocation (see the hack in GetSnapshotData to avoid repeated
> malloc/free).

So there's a memory-savings reason for the static allocation —
`GetSnapshotData` writes into the static struct in place,
avoiding a per-call palloc.  But this is also why callers
**must register or push** their snapshot if they want to use
it across a CommandCounterIncrement — the static slot gets
clobbered by the next `GetSnapshotData`.

### Slot-by-slot crib sheet

| Slot | Type | Purpose | Updated when |
|---|---|---|---|
| `CurrentSnapshot` | MVCC | the query snapshot | `GetTransactionSnapshot()` |
| `SecondarySnapshot` | MVCC | "now" snapshot for special cases (RI checks, fkey lookups) | `GetLatestSnapshot()` |
| `CatalogSnapshot` | MVCC | for catalog scans | `GetCatalogSnapshot()` lazily |
| `SnapshotSelf` | SELF | see own uncommitted writes | constant |
| `SnapshotAny` | ANY | see everything (for vacuum, debug) | constant |
| `SnapshotToast` | TOAST | see committed TOAST chunks | constant |
| `HistoricSnapshot` | dynamic | logical-decoding-time catalog state | `SetupHistoricSnapshot` |

The MVCC vs. behavior-marker distinction is what
`snapshot->snapshot_type` records.  Visibility functions like
`HeapTupleSatisfiesMVCC` and `HeapTupleSatisfiesAny` are
dispatched from `HeapTupleSatisfiesVisibility` based on
exactly this field.  See [[heap-tuple-visibility-mvcc]] for
the MVCC path.

## The `SnapshotData` struct

`snapshot.h` defines the struct (not fully shown).  The fields
that actually carry data:

| Field | Meaning |
|---|---|
| `snapshot_type` | `SNAPSHOT_MVCC` / `SELF` / `ANY` / `TOAST` / `HISTORIC_MVCC` |
| `xmin` | XIDs < xmin are visible |
| `xmax` | XIDs ≥ xmax are invisible |
| `xip[]` / `xcnt` | in-progress XIDs (between xmin and xmax) |
| `subxip[]` / `subxcnt` | in-progress subxact XIDs |
| `suboverflowed` | the subxact array overflowed; fall back to clog probes |
| `takenDuringRecovery` | snapshot was taken on a standby |
| `curcid` | current command ID, for self-snapshot visibility |
| `active_count` | refcount for ActiveSnapshot stack |
| `regd_count` | refcount for RegisteredSnapshots heap |
| `copied` | true if this is a heap-allocated copy (vs. static slot) |
| `ph_node` | pairing-heap node for RegisteredSnapshots |

The two refcounts and the pairing-heap node belong to the
**reference-counted snapshot lifecycle** discussed in
[[snapshot-active-stack-and-registered]].  `copied` is what
distinguishes a static slot (which can be clobbered) from a
heap-allocated copy (which is stable).

## `GetTransactionSnapshot` — the per-query entry point

`snapmgr.c:271-346` [verified-by-code].  This is the function
the executor calls to get its query snapshot.  Three modes:

### Mode 1 — historic snapshot active

```c
if (HistoricSnapshotActive())
{
    Assert(!FirstSnapshotSet);
    return HistoricSnapshot;
}
```

[lines 282-291]  When logical decoding is active, the
"transaction snapshot" *is* the historic snapshot.  No
procarray scan; just return the pointer.  The `Assert` enforces
that we never mix modes — logical decoding is exclusive of
normal SQL execution.

### Mode 2 — first call in the transaction

```c
if (!FirstSnapshotSet)
{
    InvalidateCatalogSnapshot();
    Assert(pairingheap_is_empty(&RegisteredSnapshots));
    Assert(FirstXactSnapshot == NULL);

    if (IsInParallelMode())
        elog(ERROR, "cannot take query snapshot during a parallel operation");

    if (IsolationUsesXactSnapshot())
    {
        if (IsolationIsSerializable())
            CurrentSnapshot = GetSerializableTransactionSnapshot(&CurrentSnapshotData);
        else
            CurrentSnapshot = GetSnapshotData(&CurrentSnapshotData);
        CurrentSnapshot = CopySnapshot(CurrentSnapshot);
        FirstXactSnapshot = CurrentSnapshot;
        FirstXactSnapshot->regd_count++;
        pairingheap_add(&RegisteredSnapshots, &FirstXactSnapshot->ph_node);
    }
    else
        CurrentSnapshot = GetSnapshotData(&CurrentSnapshotData);

    FirstSnapshotSet = true;
    return CurrentSnapshot;
}
```

[lines 293-335]  Three sub-paths:

#### Serializable

`GetSerializableTransactionSnapshot` (in `predicate.c`) wraps
`GetSnapshotData` with the SSI machinery's serializable-
specific bookkeeping (predicate locks, read-only commit
optimization).

#### Repeatable Read

`GetSnapshotData` runs the procarray scan; then `CopySnapshot`
makes a **heap-allocated copy** so the snapshot survives the
inevitable next `GetSnapshotData` call.  This copy gets stored
in `FirstXactSnapshot` and registered in
`RegisteredSnapshots` so PGPROC->xmin advance respects it
until commit.

#### Read Committed (default)

Just `GetSnapshotData(&CurrentSnapshotData)`.  No copy; the
static slot will be overwritten by the next call.  This is
why Read Committed gets a fresh snapshot per statement.

The `InvalidateCatalogSnapshot` at the top is the
"transaction-snapshot must not be older than catalog snapshot"
invariant — see §Catalog snapshot below.

### Mode 3 — subsequent calls

```c
if (IsolationUsesXactSnapshot())
    return CurrentSnapshot;

InvalidateCatalogSnapshot();
CurrentSnapshot = GetSnapshotData(&CurrentSnapshotData);
return CurrentSnapshot;
```

[lines 337-345]  In Repeatable Read / Serializable, return the
same snapshot taken at first call.  In Read Committed, take a
fresh one — which clobbers `CurrentSnapshotData` in place.

### Why callers must register or push

The header comment at `snapmgr.c:266-269` [from-comment] is
explicit:

> Note that the return value points at static storage that
> will be modified by future calls and by
> CommandCounterIncrement().  Callers must call
> RegisterSnapshot or PushActiveSnapshot on the returned snap
> before doing any other non-trivial work that could
> invalidate it.

This is the single most important callsite contract.  Code
like:

```c
Snapshot snap = GetTransactionSnapshot();
/* do some operation that might run user code */
snap_use(snap);   /* BUG: snap may be invalid here */
```

is wrong.  Either `PushActiveSnapshot(snap)` (and
`PopActiveSnapshot` later) or `RegisterSnapshot(snap)` (and
`UnregisterSnapshot` later).  Both promote the static slot to
a heap-copied, refcounted snapshot.

## `GetLatestSnapshot` — the "now" snapshot

`snapmgr.c:353-377` [verified-by-code]:

```c
Snapshot
GetLatestSnapshot(void)
{
    if (IsInParallelMode())
        elog(ERROR, "cannot update SecondarySnapshot during a parallel operation");

    Assert(!HistoricSnapshotActive());

    if (!FirstSnapshotSet)
        return GetTransactionSnapshot();

    SecondarySnapshot = GetSnapshotData(&SecondarySnapshotData);
    return SecondarySnapshot;
}
```

Three things:

1. **Always takes a fresh snapshot.**  Even in Repeatable Read,
   the secondary snapshot reflects the current moment.
2. **Writes into `SecondarySnapshotData`** — a different
   static slot than `CurrentSnapshotData`, so it doesn't
   clobber the query snapshot.
3. **Used by RI (referential integrity) checks and fkey
   lookups.**  These need to see the latest committed state to
   know whether a referenced row exists, regardless of the
   query's isolation level.

The parallel-mode error: parallel workers share the leader's
snapshot via DSM; updating `SecondarySnapshot` mid-parallel
would create an inconsistency.

## `GetCatalogSnapshot` — the recyclable catalog snapshot

`snapmgr.c:384-398` [verified-by-code]:

```c
Snapshot
GetCatalogSnapshot(Oid relid)
{
    if (HistoricSnapshotActive())
        return HistoricSnapshot;
    return GetNonHistoricCatalogSnapshot(relid);
}
```

`GetNonHistoricCatalogSnapshot` at lines 406-442
[verified-by-code]:

```c
if (CatalogSnapshot &&
    !RelationInvalidatesSnapshotsOnly(relid) &&
    !RelationHasSysCache(relid))
    InvalidateCatalogSnapshot();

if (CatalogSnapshot == NULL)
{
    CatalogSnapshot = GetSnapshotData(&CatalogSnapshotData);

    /*
     * Make sure the catalog snapshot will be accounted for in
     * decisions about advancing PGPROC->xmin.  ...  just shove
     * the CatalogSnapshot into the pairing heap manually.
     */
    pairingheap_add(&RegisteredSnapshots, &CatalogSnapshot->ph_node);
}
return CatalogSnapshot;
```

Two cleverness moves:

### 1. The catalog snapshot is reused across catalog scans

Most catalog relations have syscaches; when one is updated, an
invalidation message is sent, which the receiver processes via
`AcceptInvalidationMessages` → which calls
`InvalidateCatalogSnapshot`.  So as long as `CatalogSnapshot`
is non-NULL and the queried relation is normally
syscache-tracked, the existing snapshot is good.

For relations that **don't** have a syscache and aren't on the
short list of `RelationInvalidatesSnapshotsOnly` (pg_largeobject,
pg_replication_origin, etc.), there's no notification — the
catalog snapshot has to be re-taken every time.  Hence the
`InvalidateCatalogSnapshot()` call at the top.

### 2. The pairing-heap insertion is manual

The catalog snapshot isn't owned by a `ResourceOwner`, so
`RegisterSnapshot` (which would charge a refcount to one)
isn't appropriate.  But the snapshot still needs to be tracked
in `RegisteredSnapshots` so its `xmin` participates in the
global xmin horizon.

The comment at `snapmgr.c:427-437` [from-comment]:

> Make sure the catalog snapshot will be accounted for in
> decisions about advancing PGPROC->xmin.  We could apply
> RegisterSnapshot, but that would result in making a physical
> copy, which is overkill; and it would also create a
> dependency on some resource owner, which we do not want for
> reasons explained at the head of this file.  Instead just
> shove the CatalogSnapshot into the pairing heap manually.

Direct `pairingheap_add` against the static slot — no copy,
no resource owner.  `InvalidateCatalogSnapshot` does the
reverse via `pairingheap_remove`.

## `InvalidateCatalogSnapshot` — the inval callback

`snapmgr.c:454-464` [verified-by-code]:

```c
void
InvalidateCatalogSnapshot(void)
{
    if (CatalogSnapshot)
    {
        pairingheap_remove(&RegisteredSnapshots, &CatalogSnapshot->ph_node);
        CatalogSnapshot = NULL;
        SnapshotResetXmin();
        INJECTION_POINT("invalidate-catalog-snapshot-end", NULL);
    }
}
```

Called whenever an invalidation message arrives that could
affect catalog visibility — i.e. inside `AcceptInvalidationMessages`
via the inval callback registration.  Three actions:

1. Remove from `RegisteredSnapshots` so xmin can advance.
2. Null the pointer.
3. Call `SnapshotResetXmin` which actually does the
   PGPROC->xmin recomputation.

The `INJECTION_POINT` is a testing hook used by isolation
tester to deterministically trigger races between snapshot
invalidation and other operations.

## `InvalidateCatalogSnapshotConditionally` — quiet-time cleanup

`snapmgr.c:476-483` [verified-by-code]:

```c
void
InvalidateCatalogSnapshotConditionally(void)
{
    if (CatalogSnapshot &&
        ActiveSnapshot == NULL &&
        pairingheap_is_singular(&RegisteredSnapshots))
        InvalidateCatalogSnapshot();
}
```

Called when the backend is about to wait on client input (idle
in transaction).  If the **only** registered snapshot is the
catalog one and there's no active snapshot, drop the catalog
snapshot too — so we don't hold back the global xmin horizon
during long idle waits.

This is one of the user-visible reasons a backend that's been
idle in transaction can briefly delay vacuum: even after this
optimization, the catalog snapshot might survive if any other
snapshot is also active.

## `SnapshotSetCommandId` — propagating CCI

`snapmgr.c:489-500` [verified-by-code]:

```c
void
SnapshotSetCommandId(CommandId curcid)
{
    if (!FirstSnapshotSet)
        return;

    if (CurrentSnapshot)
        CurrentSnapshot->curcid = curcid;
    if (SecondarySnapshot)
        SecondarySnapshot->curcid = curcid;
}
```

When a query inside the current transaction issues
`CommandCounterIncrement`, the next "own write visibility"
check needs to see the bumped CID.  This function pushes the
new CID into the active static snapshots so
`HeapTupleSatisfiesMVCC` reports the previous command's writes
as visible.

The `CatalogSnapshot` is **not** touched — a long comment
above the function discusses this; in practice, catalog
snapshots are short-lived enough that the CID propagation
doesn't matter for them.

## Behavior-marker snapshots — `Self`, `Any`, `Toast`

These three never call `GetSnapshotData`; they're
behavior-marker pointers handed to visibility code.

### SnapshotSelf

Allows the caller to see uncommitted writes from the current
transaction (and only the current transaction).  Used for
CREATE INDEX building from a CREATE TABLE that's in the same
transaction — the index build needs to see the rows that the
CREATE TABLE just inserted but hasn't committed yet.

### SnapshotAny

Sees everything: live, dead, in-progress.  Used by VACUUM,
pg_dump's `--snapshot=any` debug mode, and the heap-AM's
self-test paths.

### SnapshotToast

Sees committed TOAST chunks; ignores MVCC because TOAST chunks
are written before the heap tuple that points to them, so a
"normal" MVCC visibility check would invisibly hide TOAST
chunks pointed to by a tuple from an in-progress xact.

The three snapshot_types are dispatched in
`HeapTupleSatisfiesVisibility` (in
`access/heap/heapam_visibility.c`):

```c
case SNAPSHOT_MVCC:
    return HeapTupleSatisfiesMVCC(htup, snapshot, buffer);
case SNAPSHOT_SELF:
    return HeapTupleSatisfiesSelf(htup, snapshot, buffer);
case SNAPSHOT_ANY:
    return HeapTupleSatisfiesAny(htup, snapshot, buffer);
case SNAPSHOT_TOAST:
    return HeapTupleSatisfiesToast(htup, snapshot, buffer);
```

## `TransactionXmin` and `RecentXmin`

`snapmgr.c:159-160` [verified-by-code]:

```c
TransactionId TransactionXmin = FirstNormalTransactionId;
TransactionId RecentXmin = FirstNormalTransactionId;
```

Both updated by `GetSnapshotData`.  Distinguished use:

- **`TransactionXmin`** is the xmin of the *current
  transaction's* snapshot — set at first `GetSnapshotData` and
  not advanced further within the transaction.
- **`RecentXmin`** is the xmin of the *most recent* snapshot —
  updated on every `GetSnapshotData`, used as a fast "no XID
  older than this is in progress" check by HOT prune,
  vacuum, etc.

The initial value `FirstNormalTransactionId` (the minimum
valid normal-mode XID) is the conservative default that makes
sense before any snapshot has been taken.

## Invariants worth remembering

1. **Static slots get clobbered by the next `GetSnapshotData`.**
   Always `RegisterSnapshot` or `PushActiveSnapshot` before
   non-trivial work.
2. **`copied = true`** means heap-allocated, stable; `false`
   means it's pointing at a static slot.
3. **Catalog snapshot is reused across catalog scans** until
   an inval arrives.  `InvalidateCatalogSnapshot` is the
   callback.
4. **Repeatable Read first-snapshot is copied + registered.**
   Read Committed isn't.
5. **`HistoricSnapshotActive()` short-circuits both
   `GetTransactionSnapshot` and `GetCatalogSnapshot`.**
   During logical decoding, all reads use the historic
   snapshot.
6. **`SnapshotSetCommandId` propagates curcid into
   CurrentSnapshot and SecondarySnapshot only.**  Catalog
   snapshot is deliberately not touched.
7. **`Self`, `Any`, `Toast` are behavior markers, not
   snapshots.**  They never call `GetSnapshotData`.
8. **`TransactionXmin` is fixed for the transaction's life;
   `RecentXmin` advances with every snapshot.**
9. **`InvalidateCatalogSnapshotConditionally` drops the
   catalog snapshot only when it's the lone registered one.**
   This is the idle-in-transaction xmin-release heuristic.
10. **The pairing-heap insertion in
    `GetNonHistoricCatalogSnapshot` is manual** — no
    ResourceOwner ownership, no physical copy.

## Useful greps

```bash
# Static snapshot slots
grep -n "CurrentSnapshotData\|SecondarySnapshotData\|CatalogSnapshotData\|SnapshotSelfData\|SnapshotAnyData\|SnapshotToastData" \
    source/src/backend/utils/time/snapmgr.c

# Three MVCC entry points
grep -n "GetTransactionSnapshot\|GetLatestSnapshot\|GetCatalogSnapshot\|GetNonHistoricCatalogSnapshot" \
    source/src/backend/utils/time/snapmgr.c

# CommandCounterIncrement propagation
grep -n "SnapshotSetCommandId\|UpdateActiveSnapshotCommandId" \
    source/src/backend/utils/time/snapmgr.c

# RecentXmin / TransactionXmin consumers
grep -rn "RecentXmin\|TransactionXmin" \
    source/src/backend/storage/ipc/procarray.c \
    source/src/backend/access/heap/ | head -20

# Behavior-marker dispatch
grep -n "case SNAPSHOT_MVCC\|case SNAPSHOT_SELF\|case SNAPSHOT_ANY\|case SNAPSHOT_TOAST" \
    source/src/backend/access/heap/heapam_visibility.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/ipc/procarray.c`](../files/src/backend/storage/ipc/procarray.c.md) | — | GetSnapshotData |
| [`src/backend/utils/time/snapmgr.c`](../files/src/backend/utils/time/snapmgr.c.md) | — | all entry points + static slots |
| [`src/include/utils/snapshot.h`](../files/src/include/utils/snapshot.h.md) | — | SnapshotData struct |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- [[snapshot-active-stack-and-registered]] —
  `ActiveSnapshot`, `RegisteredSnapshots`, refcounting.
- [[snapshot-export-historic-parallel]] — exported snapshots,
  historic snapshots, parallel-worker serialization.
- [[snapshot-acquisition]] — older single-file summary of
  `GetSnapshotData`; this doc family supersedes it.
- [[heap-tuple-visibility-mvcc]] — the MVCC visibility
  gauntlet that consumes these snapshots.
- [[cache-invalidation-registration]] — `InvalidateCatalogSnapshot`
  is hooked into the inval-message machinery.
- [[parallel-worker-coordination]] — parallel snapshot
  sharing via DSM.
- [[memory-contexts]] — `TopTransactionContext` is the home
  of `ActiveSnapshotElt` allocations.
- [[xmin-horizon-management]] — `SnapshotResetXmin` is what
  pushes PGPROC->xmin forward when a snapshot is released.
