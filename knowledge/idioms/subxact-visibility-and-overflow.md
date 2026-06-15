# Subxact visibility — local stack, in-progress check, and snapshot

Three different "is this XID part of an active subtransaction?"
questions arise in PG, with three different answer paths:

1. **"Is this XID part of *my* current transaction tree?"** —
   answered locally from the in-process `TransactionState` stack
   without touching shared memory.
2. **"Is this XID running in *any* backend right now?"** —
   answered by `TransactionIdIsInProgress`, which has four
   fallback paths of increasing cost.
3. **"Is this XID still-in-progress according to *this snapshot*?"**
   — answered by `XidInMVCCSnapshot`, which uses the
   subxact-aware fields baked into the snapshot.

All three eventually fall back to pg_subtrans
([[subxact-subtrans-slru]]) for cases where the per-PGPROC subxid
cache ([[subxact-xidcache-and-pgproc]]) has overflowed. This doc
covers all three, with emphasis on the overflow protocol and how
snapshot capture handles it.

For the underlying data — the PGPROC `subxids[]` array — see
[[subxact-xidcache-and-pgproc]]. For the on-disk parent pointers,
see [[subxact-subtrans-slru]]. For how snapshots are built and
managed, see [[snapshot-static-and-current]] and
[[snapshot-active-stack-and-registered]].

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

- `source/src/backend/access/transam/xact.c:938-1034` —
  `TransactionIdIsCurrentTransactionId` (local stack walk).
- `source/src/backend/storage/ipc/procarray.c:1366-1620` —
  `TransactionIdIsInProgress` (the 4-path fallback chain).
- `source/src/backend/utils/time/snapmgr.c:1859-1963` —
  `XidInMVCCSnapshot` (snapshot-time visibility).
- `source/src/backend/storage/ipc/procarray.c:1305-1364` —
  `ProcArrayApplyXidAssignment` (standby-side
  `XLOG_XACT_ASSIGNMENT` replay).
- `source/src/include/utils/snapshot.h:1` — `Snapshot` struct
  showing `xip`/`subxip`/`xcnt`/`subxcnt`/`suboverflowed`/
  `takenDuringRecovery`.

## Path 1 — `TransactionIdIsCurrentTransactionId`

[xact.c:938-1034] is the cheapest path: "is this XID anywhere in my
own current-transaction tree?" It walks the local
`TransactionState` stack and the per-level `childXids[]` arrays.

```c
bool
TransactionIdIsCurrentTransactionId(TransactionId xid)
{
    /* Reject non-normal XIDs immediately. */
    if (!TransactionIdIsNormal(xid))
        return false;

    /* Top XID match? */
    if (TransactionIdEquals(xid, GetTopTransactionIdIfAny()))
        return true;

    /* Parallel worker? Use the leader's snapshot of current XIDs. */
    if (nParallelCurrentXids > 0) {
        /* binary search in ParallelCurrentXids[] */
        return found ? true : false;
    }

    /* Walk the local stack, including aborted-not-yet-popped levels. */
    for (s = CurrentTransactionState; s != NULL; s = s->parent) {
        if (s->state == TRANS_ABORT)
            continue;
        if (!FullTransactionIdIsValid(s->fullTransactionId))
            continue;
        if (TransactionIdEquals(xid, XidFromFullTransactionId(s->fullTransactionId)))
            return true;
        /* childXids[] is sorted — binary search */
        low = 0; high = s->nChildXids - 1;
        while (low <= high) {
            middle = low + (high - low) / 2;
            probe = s->childXids[middle];
            if (TransactionIdEquals(probe, xid)) return true;
            if (TransactionIdPrecedes(probe, xid)) low = middle + 1;
            else high = middle - 1;
        }
    }
    return false;
}
```

Five points worth highlighting:

1. **`TRANS_ABORT` levels are skipped** [xact.c:1008-1009]. An
   aborted subtransaction's XID is no longer part of "current" —
   the comment at xact.c:997-1001 spells out: "a transaction being
   aborted is no longer 'current', even though it may still have an
   entry on the state stack". This matters for visibility: tuples
   written by an aborted subxact should be visible to the parent as
   "definitely not mine".

2. **`childXids[]` is the per-level array of subcommitted child
   XIDs.** When a subxact commits (via `RELEASE` or implicit
   end-of-block), its XID is appended to the parent's `childXids[]`.
   The array is kept sorted, hence the binary search.

3. **Parallel workers use `ParallelCurrentXids[]`** [xact.c:967-993]
   instead of the stack. The leader serializes its current-XID set
   into a flat sorted array, attaches it to the parallel-context
   DSM, and the worker uses it for `TransactionIdIsCurrentTransactionId`
   checks. The worker can't walk the leader's `TransactionState`
   stack directly (different process), so this serialized
   snapshot stands in. See [[parallel-state-propagation]] for how
   it's serialized.

4. **Stack walk visits parents from current up to top.** A subxact
   X with parent P with parent Q in turn part of top T — looking up
   X, P, Q, or T all return true. Subcommitted *cousins* (siblings
   of an ancestor that have been subcommitted) also return true
   because they're in some ancestor's `childXids[]`.

5. **No shared memory access.** This is the entire point. The path
   is lock-free and runs in nanoseconds.

This function is consulted before any other visibility check —
`TransactionIdIsInProgress` itself calls it as an early shortcut
[procarray.c:1433-1437].

## Path 2 — `TransactionIdIsInProgress`

[procarray.c:1366-1620] is the "is this XID running anywhere?"
query. The comment at procarray.c:1370-1391 lays out the four
fallback paths:

> 1. The given Xid is a main transaction Id. We will find this out
>    cheaply by looking at ProcGlobal->xids.
> 2. The given Xid is one of the cached subxact Xids in the PGPROC
>    array. We can find this out cheaply too.
> 3. In Hot Standby mode, we must search the KnownAssignedXids list
>    to see if the Xid is running on the primary.
> 4. Search the SubTrans tree to find the Xid's topmost parent, and
>    then see if that is running according to ProcGlobal->xids[] or
>    KnownAssignedXids. This is the slowest way, but sadly it has to
>    be done always if the others failed, unless we see that the
>    cached subxact sets are complete (none have overflowed).

### Early shortcuts [procarray.c:1406-1437]

```c
/* (a) RecentXmin filter: anything < RecentXmin is settled. */
if (TransactionIdPrecedes(xid, RecentXmin)) return false;

/* (b) Recently-checked cache. */
if (TransactionIdEquals(cachedXidIsNotInProgress, xid)) return false;

/* (c) My own transaction. */
if (TransactionIdIsCurrentTransactionId(xid)) return true;
```

Three exits without touching shared memory at all. The `RecentXmin`
filter is the most important: most "is X running?" questions are
about XIDs older than the snapshot's xmin, which by definition are
settled. `RecentXmin` is updated frequently and serves as a fast
lower bound. `cachedXidIsNotInProgress` is a one-element cache that
helps with repeated checks for the same XID.

### `latestCompletedXid` filter [procarray.c:1465-1475]

After acquiring `ProcArrayLock` in SHARED mode:

```c
latestCompletedXid = TransamVariables->latestCompletedXid;
if (TransactionIdPrecedes(latestCompletedXid, xid)) {
    LWLockRelease(ProcArrayLock);
    return true;   /* xid is too new to be settled — must be running */
}
```

If our `xid` is greater than `latestCompletedXid`, it can't have
completed yet, so it must be running. This is the upper-bound
counterpart to `RecentXmin`.

### Step 1 + Step 2 — scan the PGPROC array

[procarray.c:1477-1543]:

```c
other_xids = ProcGlobal->xids;
other_subxidstates = ProcGlobal->subxidStates;

for (int pgxactoff = 0; pgxactoff < numProcs; pgxactoff++) {
    if (pgxactoff == mypgxactoff) continue;   /* handled above */

    pxid = UINT32_ACCESS_ONCE(other_xids[pgxactoff]);
    if (!TransactionIdIsValid(pxid)) continue;

    /* Step 1: main XID match? */
    if (TransactionIdEquals(pxid, xid)) {
        LWLockRelease(ProcArrayLock);
        return true;
    }

    /* If pxid > our xid, our xid can't be a subxact of this backend's tree. */
    if (TransactionIdPrecedes(xid, pxid)) continue;

    /* Step 2: scan this backend's cached subxids. */
    pxids = other_subxidstates[pgxactoff].count;
    pg_read_barrier();  /* pairs with barrier in subxid push */
    proc = &allProcs[arrayP->pgprocnos[pgxactoff]];
    for (j = pxids - 1; j >= 0; j--) {
        cxid = UINT32_ACCESS_ONCE(proc->subxids.xids[j]);
        if (TransactionIdEquals(cxid, xid)) {
            LWLockRelease(ProcArrayLock);
            return true;
        }
    }

    /* Remember main XID of overflowed-cache backends for step 4. */
    if (other_subxidstates[pgxactoff].overflowed)
        xids[nxids++] = pxid;
}
```

The hot path. Two things to notice:

- **`UINT32_ACCESS_ONCE`** [procarray.c:1492, 1524] forces the
  compiler to emit a single memory load, defeating reordering
  optimizations. Combined with `pg_read_barrier()` [line 1518], this
  is the lock-free read protocol that pairs with the
  `pg_write_barrier()` in the writer path.

- **The "ignore main Xids younger than target Xid"** filter at
  procarray.c:1511-1512. If a backend's main XID is greater than
  the XID we're checking, that backend can't be the originator of
  our XID (since a top-level XID is always assigned before its
  subxact XIDs). So we can skip the per-PGPROC subxid scan.

- **We remember "main XIDs of backends whose cache has overflowed"**
  in the `xids[]` workspace. These are the backends we need to
  consult pg_subtrans for in step 4.

### Step 3 — known-assigned XIDs on hot standby

[procarray.c:1546-1573]. On a standby, the
`KnownAssignedXids` array (maintained by replay of
`XLOG_RUNNING_XACTS` and incremental updates) holds the primary's
running-XID set. If `xid` is in that array, return true.

The array is *sorted*, so binary search is used:
`KnownAssignedXidsSearch(xid, false)`.

### Step 4 — fall back to pg_subtrans

[procarray.c:1575-1620]. If we couldn't decide from steps 1-3 but
we know some backend's cache overflowed (the `nxids > 0` case from
step 2's remembering), we now have to take the slow path:

```c
LWLockRelease(ProcArrayLock);

/* For each overflowed backend's main XID, ask pg_subtrans if our
 * xid's parent is that backend's main xid. */
topxid = SubTransGetTopmostTransaction(xid);
if (TransactionIdEquals(topxid, xid)) return false;  /* no parent — not a subxact */

for (i = 0; i < nxids; i++) {
    if (TransactionIdEquals(xids[i], topxid))
        return true;
}
return false;
```

Crucially, we **release `ProcArrayLock` before calling
`SubTransGetTopmostTransaction`** — that function does SLRU I/O
under its own bank lock, and the comment at procarray.c:1387-1391
explains we can buy back concurrency by dropping the proc array
lock here. The main XIDs we saved in `xids[]` won't change (a
backend can't reduce its top XID), so it's safe to use them after
releasing the lock.

The cost: one or more `SubTransGetParent` calls per
`SubTransGetTopmostTransaction`. With `subtransaction_buffers` set
appropriately and modest savepoint nesting, hits in the SLRU pool
are common and this stays fast. With overflow + cold cache, it's
slow enough to be observable in profiles — which is the whole
reason the PGPROC cache exists in the first place.

## Path 3 — `XidInMVCCSnapshot`

[snapmgr.c:1859-1963]. Snapshot-relative visibility: "should this
snapshot consider `xid` as still-in-progress?" The snapshot has
already been captured (via `GetSnapshotData` in the primary, or via
replay state on standby), so this is a query against frozen state,
not live `PGPROC` data.

The `Snapshot` struct holds:

- `xip[]`/`xcnt` — top-level XIDs running when the snapshot was
  taken.
- `subxip[]`/`subxcnt` — subxact XIDs of all backends, but only if
  no backend's cache had overflowed.
- `suboverflowed` — set if at least one backend's cache had
  overflowed when the snapshot was captured.
- `takenDuringRecovery` — set if the snapshot was taken on a hot
  standby (uses different storage convention).

### The non-overflowed path [snapmgr.c:1899-1925]

```c
/* Range checks first — most XIDs filtered here. */
if (TransactionIdPrecedes(xid, snapshot->xmin)) return false;
if (TransactionIdFollowsOrEquals(xid, snapshot->xmax)) return true;

if (!snapshot->takenDuringRecovery) {
    if (!snapshot->suboverflowed) {
        /* The fast path: subxip[] has full subxact info. */
        if (pg_lfind32(xid, snapshot->subxip, snapshot->subxcnt))
            return true;
        /* fall through to search xip[] */
    } else {
        /* Snapshot overflowed: convert to top-level via SubTrans. */
        xid = SubTransGetTopmostTransaction(xid);
        if (TransactionIdPrecedes(xid, snapshot->xmin)) return false;
    }
    if (pg_lfind32(xid, snapshot->xip, snapshot->xcnt))
        return true;
}
return false;
```

`pg_lfind32` is a SIMD-accelerated linear search for 32-bit
integers. The arrays are small (at most a few hundred entries on a
busy server), and SIMD comparison is fast enough that more
complicated data structures (sorted + binary-search) wouldn't pay
off. The comment at snapmgr.c:1893-1898 walks through the logic
of why both branches are correct.

When the snapshot overflowed, `subxip[]` is empty (not populated by
`GetSnapshotData`), and we have to ask pg_subtrans to map our XID
up to its top-level parent. Then we look in `xip[]`. Note the
recheck of `snapshot->xmin` after the conversion — if the subxact
mapped to a parent that's already settled, we can short-circuit.

### The recovery path [snapmgr.c:1927-1962]

Hot-standby snapshots use a different storage convention:

```c
if (snapshot->takenDuringRecovery) {
    /* On standby, ALL xids (top + subxact) live in subxip[].
     * xip[] is empty. */
    if (snapshot->suboverflowed) {
        xid = SubTransGetTopmostTransaction(xid);
        if (TransactionIdPrecedes(xid, snapshot->xmin)) return false;
    }
    if (pg_lfind32(xid, snapshot->subxip, snapshot->subxcnt))
        return true;
}
return false;
```

The comment at snapmgr.c:1929-1933 explains: "In recovery we store
all xids in the subxip array because it is by far the bigger array,
and we mostly don't know which xids are top-level and which are
subxacts."

The primary knows the distinction because each PGPROC tracks them
separately; the standby is just replaying WAL records that announce
"these XIDs are running" without per-XID type tags.

### Why `xmin`/`xmax` range checks are correct even with subxact remapping

The comment at snapmgr.c:1871-1877 is worth reading carefully:

> Make a quick range check to eliminate most XIDs without looking at
> the xip arrays. Note that this is OK even if we convert a subxact
> XID to its parent below, because a subxact with XID < xmin has
> surely also got a parent with XID < xmin, while one with XID >=
> xmax must belong to a parent that was not yet committed at the
> time of this snapshot.

The reasoning depends on the XID-assignment invariant: parent XID <
child XID always (enforced by
`Assert(TransactionIdFollows(xid, parent))` in
`SubTransSetParent`). So `child < xmin → parent < xmin` is
trivially true. And `child >= xmax → parent might also be >= xmax`,
which still counts as "in progress at snapshot time".

## The snapshot's `suboverflowed` flag

`GetSnapshotData` captures the running-xacts state by scanning the
PGPROC array under shared `ProcArrayLock`. During the scan:

```c
/* (pseudocode) */
for each backend at pgxactoff {
    xid = ProcGlobal->xids[pgxactoff];
    state = ProcGlobal->subxidStates[pgxactoff];
    if (TransactionIdIsValid(xid)) {
        snapshot->xip[snapshot->xcnt++] = xid;
        if (state.overflowed) {
            snapshot->suboverflowed = true;
            /* don't bother copying subxids[] — we'll fall back to SubTrans */
        } else {
            /* copy this backend's subxids[] into snapshot->subxip[] */
            for (i = 0; i < state.count; i++)
                snapshot->subxip[snapshot->subxcnt++] = proc->subxids.xids[i];
        }
    }
}
```

The `suboverflowed = true` decision is per-snapshot, not per-backend.
Once any backend has overflowed, the snapshot can't trust its
`subxip[]` to be complete, so it might as well drop the subxact
copying entirely and rely on pg_subtrans for queries. This trades
larger memory for faster snapshot capture, against more
SLRU traffic during visibility checks.

## The `ProcArrayApplyXidAssignment` integration

When the primary emits an `XLOG_XACT_ASSIGNMENT` record (because a
backend's `subxids[]` is about to overflow), the standby replays
it via `ProcArrayApplyXidAssignment`
[procarray.c:1304-1364, see [[subxact-xidcache-and-pgproc]]].

The replay:
1. **Sets `lastOverflowedXid` to the max XID in the assignment.**
   From now on, snapshots taken on the standby will have
   `suboverflowed = true` for XIDs ≥ `lastOverflowedXid`.
2. **Writes the subxids into pg_subtrans pointing at the
   top-level XID** (not the immediate parent — the standby
   collapses the tree, see [[subxact-xidcache-and-pgproc]]).
3. **Removes the subxids from `KnownAssignedXids`.** They're now
   subsumed under the top-level XID.

This is why standby snapshots have a different layout from primary
snapshots, and why `XidInMVCCSnapshot` branches on
`takenDuringRecovery`.

## Performance cost summary

| Path | Lookup cost | When used |
|---|---|---|
| `TransactionIdIsCurrentTransactionId` | local stack walk, ~10ns | always tried first |
| `TransactionIdIsInProgress` step 1 (main xid) | PGPROC array scan + lock, ~µs | every "is X running?" check |
| `TransactionIdIsInProgress` step 2 (cached subxids) | same scan, no extra cost | always |
| `TransactionIdIsInProgress` step 4 (pg_subtrans) | SLRU read(s), ~µs–ms | only when some cache overflowed |
| `XidInMVCCSnapshot` non-overflowed | SIMD scan of small array | every tuple visibility check |
| `XidInMVCCSnapshot` overflowed | `SubTransGetTopmostTransaction` + scan | every check on overflowed snapshot |

The 64-slot cap on the PGPROC cache exists precisely to keep most
production workloads in the top three rows.

## Invariants

- **`TransactionIdIsCurrentTransactionId` is consulted first** to
  short-circuit lookups for the calling backend's own subxacts.
- **`childXids[]` is sorted** at every `TransactionState` level —
  binary-searchable.
- **`TRANS_ABORT` levels are skipped** in the local stack walk.
- **`ParallelCurrentXids[]` substitutes for the stack in workers.**
  Sorted, binary-searched.
- **`UINT32_ACCESS_ONCE` + `pg_read_barrier`** is the lock-free
  read protocol against `ProcGlobal->xids[]` and
  `subxidStates[].count`.
- **`other_subxidstates[pgxactoff].overflowed` can only flip false→
  true while we hold the lock**; once a snapshot recorded it true,
  we trust that.
- **Snapshot range checks (`xmin`/`xmax`) are valid even with
  later parent remapping** because of the parent < child XID
  invariant.
- **`takenDuringRecovery` snapshots have empty `xip[]`**; all XIDs
  live in `subxip[]`.
- **`lastOverflowedXid` is the standby-side analog** of
  per-PGPROC `overflowed`. Snapshots taken when it's set track
  `suboverflowed = true`.

## Useful greps

```bash
# Every call site of the three visibility predicates:
grep -RnE 'TransactionIdIsCurrentTransactionId\(' source/src/backend | wc -l
grep -RnE 'TransactionIdIsInProgress\(' source/src/backend | head -20
grep -RnE 'XidInMVCCSnapshot\(' source/src/backend

# Counters for which fallback path is taken:
grep -nE 'xc_by_' source/src/backend/storage/ipc/procarray.c

# Inspect snapshot stats at runtime:
#   psql:  EXPLAIN (ANALYZE, BUFFERS) <query>;
#   pg_stat_slru WHERE name='SubTrans'

# Check overflow rates:
grep -RnE 'ProcArrayApplyXidAssignment|XLOG_XACT_ASSIGNMENT' source/src/backend

# Find ParallelCurrentXids construction:
grep -RnE 'ParallelCurrentXids|SerializeTransactionState' source/src
```

## Cross-references

- [[subxact-xidcache-and-pgproc]] — the in-PGPROC cache that
  populates `other_xids` / `other_subxidstates` arrays here. The
  64-cap and the overflow protocol are the input to this doc's
  visibility logic.
- [[subxact-subtrans-slru]] — `SubTransGetTopmostTransaction` is
  the slowest fallback. Cache sizing
  (`subtransaction_buffers`) directly impacts the cost of
  overflowed-snapshot visibility.
- [[subtransaction-stack]] — `TransactionState` + `childXids[]`
  drive path 1.
- [[snapshot-static-and-current]] — `GetSnapshotData()` captures
  the snapshot fields this doc uses (xip, subxip, suboverflowed).
- [[snapshot-active-stack-and-registered]] — when these snapshots
  get pushed/popped/released.
- [[heap-tuple-visibility-mvcc]] — the per-tuple visibility checks
  that consume `XidInMVCCSnapshot` results.
- [[parallel-state-propagation]] — how `ParallelCurrentXids[]` is
  serialized from leader to worker.
- [[xmin-horizon-management]] — `RecentXmin`/`latestCompletedXid`
  drive the early-exit shortcuts.
- [[clog-slru]] — pg_xact tracks definitive commit/abort status;
  `TransactionIdIsInProgress` returning false → caller consults
  clog for committed/aborted distinction.
