# XidCache in PGPROC — the 64-slot subxact-XID cache

Every backend that runs a transaction with savepoints accumulates a set
of **subtransaction XIDs**. Those XIDs need to be visible to other
backends' visibility checks: when backend B's snapshot says "is XID 47
running?", and 47 happens to be a subxact of backend A, the answer is
yes. PG could resolve every such query by walking pg_subtrans
([[subxact-subtrans-slru]]), but that'd require a SLRU read per
visibility check — too slow.

Instead, each backend caches its own subxact XIDs in **shared memory**
attached to its `PGPROC` struct, capped at `PGPROC_MAX_CACHED_SUBXIDS
= 64`. If the cap is exceeded, the cache is marked **overflowed** and
other backends fall back to SubTrans for that backend's XIDs. The cap
exists because the cache lives in fixed-size shared memory and an
unbounded cache would either waste memory for most backends or run out
for the rare ones with deep savepoint nesting.

The cache, the overflow protocol, and the
`XidCacheRemoveRunningXids` path are the subject of this doc. For the
SLRU that handles the overflow case, see [[subxact-subtrans-slru]].
For how snapshot visibility consumes this data, see
[[subxact-visibility-and-overflow]]. For the per-backend C-level stack
that drives savepoint lifecycle, see [[subtransaction-stack]].

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

- `source/src/include/storage/proc.h:30-56` — `PGPROC_MAX_CACHED_SUBXIDS`,
  `XidCacheStatus`, `XidCache`.
- `source/src/include/storage/proc.h:170-260` — `PGPROC` struct
  showing `subxids` + `subxidStatus` + `pgxactoff`.
- `source/src/include/storage/proc.h:270-330` — `PROC_HDR` (alias
  `ProcGlobal`), with the mirrored `subxidStates[]`/`xids[]` arrays
  used by hot-path scans.
- `source/src/backend/storage/ipc/procarray.c:3982-4070` —
  `XidCacheRemoveRunningXids` (subxact abort path).
- `source/src/backend/storage/ipc/procarray.c:1304-1364` —
  `ProcArrayApplyXidAssignment` (XLOG_XACT_ASSIGNMENT replay on
  standby).
- `source/src/backend/storage/ipc/procarray.c:1366-1500` —
  `TransactionIdIsInProgress` (the cache's primary reader on
  primary).
- `source/src/backend/access/transam/xact.c:2200-2400` —
  `RecordTransactionCommit` and the path that flushes subxids on
  parent commit.

## The two structs

```c
#define PGPROC_MAX_CACHED_SUBXIDS 64    /* XXX guessed-at value */

typedef struct XidCacheStatus {
    uint8 count;       /* number of cached subxids (≤ 64) */
    bool  overflowed;  /* has PGPROC->subxids overflowed */
} XidCacheStatus;

struct XidCache {
    TransactionId xids[PGPROC_MAX_CACHED_SUBXIDS];
};
```

[proc.h:43-56]. Two structs, intentionally separated:

- **`XidCache`** holds the actual XID array.
- **`XidCacheStatus`** holds the metadata (count + overflow flag).

The reason for splitting will be clearer when we look at the mirror.

The comment at proc.h:30-42 spells out the contract:

> Each backend advertises up to PGPROC_MAX_CACHED_SUBXIDS TransactionIds
> for non-aborted subtransactions of its current top transaction. These
> have to be treated as running XIDs by other backends.
>
> We also keep track of whether the cache overflowed (ie, the transaction
> has generated at least one subtransaction that didn't fit in the
> cache). **If none of the caches have overflowed, we can assume that an
> XID that's not listed anywhere in the PGPROC array is not a running
> transaction.** Else we have to look at pg_subtrans.

That bolded statement is the key invariant. Other backends'
visibility code can skip pg_subtrans entirely *if* no PGPROC has
`overflowed = true`. The whole machinery here is in service of
keeping that fast-path live.

Why 64? The comment says "XXX guessed-at value" [proc.h:43]. In
practice it's a compromise: enough that most apps with PL/pgSQL
EXCEPTION blocks or shallow savepoint usage never overflow, small
enough that 1000 backends only cost
`1000 × 64 × 4 = 256 KiB` of shared memory for the cache arrays.

## How it lives inside `PGPROC` and the `pgxactoff` mirror

The `PGPROC` struct (the per-backend record in shared memory) holds:

```c
struct PGPROC {
    ...
    XidCache       subxids;       /* the array (256 bytes) */
    XidCacheStatus subxidStatus;  /* count + overflowed */
    int            pgxactoff;     /* index into ProcGlobal->{xids,subxidStates}[] */
    ...
};
```

And `PROC_HDR` (the singleton header) holds **parallel arrays**
indexed by every backend's `pgxactoff`:

```c
typedef struct PROC_HDR {
    ...
    TransactionId  *xids;          /* one TransactionId per backend */
    XidCacheStatus *subxidStates;  /* one XidCacheStatus per backend */
    uint8          *statusFlags;
    ...
} PROC_HDR;
```

The comment at proc.h:175-178 names this the "mirror":

> Some fields in PGPROC (see "mirrored in ..." comment) are mirrored into
> an array of struct ProcXact in PROC_HDR (also known as ProcGlobal),
> indexed by PGPROC->pgxactoff. Both copies need to be maintained
> coherently.

Why the mirror? Because the hot path —
`TransactionIdIsInProgress(xid)` and `GetSnapshotData()` — wants to
scan **all backends'** counts and top XIDs, and doing that across
`MaxBackends` non-contiguous `PGPROC` structs would cause cache thrashing
and pipeline stalls. With the mirror, `ProcGlobal->xids[]` and
`ProcGlobal->subxidStates[]` are contiguous in memory, and
`pg_lfind32`-style SIMD/loop-unrolled scans become viable.

`pgxactoff` is the backend's slot. Both copies (the
`PGPROC->subxidStatus` and the `ProcGlobal->subxidStates[pgxactoff]`)
must be kept in sync. Backends update both whenever they grow or
shrink the cache:

```c
mysubxidstat = &ProcGlobal->subxidStates[MyProc->pgxactoff];
/* later: */
mysubxidstat->count--;       /* mirror */
MyProc->subxidStatus.count--; /* primary */
```

[procarray.c:4014, 4031-4032]. The order — mirror first, then primary
— interacts with the `pg_write_barrier()` at procarray.c:4030/4053:
readers do not hold `ProcArrayLock` in shared mode unconditionally
(the lock-free fast paths in `TransactionIdIsInProgress` use atomic
reads), so the memory-order discipline matters.

## Adding to the cache: `MarkAsSubcommitted` is *not* it

Surprisingly, the cache is **not** populated when a subxact starts.
Subxact XID assignment defers entering the cache until the subxact
either subcommits (i.e., its parent releases it via `RELEASE
SAVEPOINT` or by reaching its scope end) or until an explicit
WAL-record-emitting checkpoint flushes the assignment.

The path is in `RecordTransactionCommit` and `CommitSubTransaction`.
At subcommit time, the child's XID gets added to the parent's
`childXids[]` (in the per-backend transaction-state stack, see
[[subtransaction-stack]]). Eventually, when the top transaction
commits or hits an `XLOG_XACT_ASSIGNMENT` checkpoint, the child XIDs
flow into `MyProc->subxids[]` and `subxidStatus.count` ticks up.

The reason for the deferral: an **aborted** subxact's XID shouldn't
appear in `subxids[]` at all — aborted XIDs are still "running" from
some visibility perspectives, but they're tracked via pg_xact (clog)
status bits instead. By only inserting subcommitted XIDs into the
PGPROC cache, we keep the cache's semantic clean ("these XIDs are
part of my still-running transaction tree").

The 64-slot overflow path is handled by `XidCacheRemoveRunningXids`'s
inverse — the insertion side has to check if `count >=
PGPROC_MAX_CACHED_SUBXIDS` before pushing, and if so it sets
`overflowed = true` and skips the insert. After that, *all* further
subxact XIDs for this transaction land in pg_subtrans only.

## `XidCacheRemoveRunningXids` — the abort path

[procarray.c:3982-4070] is the function that removes XIDs when a
subxact (or a set of nested subxacts) aborts. Its job is to keep the
PGPROC cache coherent with reality. It's *only* called on subxact
abort; subxact commit doesn't remove from the cache (the XIDs are
still part of the parent's tree).

```c
void
XidCacheRemoveRunningXids(TransactionId xid,
                          int nxids, const TransactionId *xids,
                          TransactionId latestXid)
{
    LWLockAcquire(ProcArrayLock, LW_EXCLUSIVE);

    mysubxidstat = &ProcGlobal->subxidStates[MyProc->pgxactoff];

    /* Walk xids[] backwards (they're in increasing order). */
    for (i = nxids - 1; i >= 0; i--) {
        TransactionId anxid = xids[i];
        /* Scan our subxids cache backwards too. */
        for (j = MyProc->subxidStatus.count - 1; j >= 0; j--) {
            if (TransactionIdEquals(MyProc->subxids.xids[j], anxid)) {
                /* Swap with last; decrement count. */
                MyProc->subxids.xids[j] =
                    MyProc->subxids.xids[MyProc->subxidStatus.count - 1];
                pg_write_barrier();
                mysubxidstat->count--;          /* mirror */
                MyProc->subxidStatus.count--;   /* primary */
                break;
            }
        }
        /* Diagnostic: warn if we couldn't find it AND we haven't overflowed. */
        if (j < 0 && !MyProc->subxidStatus.overflowed)
            elog(WARNING, "did not find subXID %u in MyProc", anxid);
    }

    /* Also remove the "top of this abort group" xid. */
    /* ... (same swap-with-last logic) ... */

    /* Advance global latestCompletedXid + xactCompletionCount. */
    MaintainLatestCompletedXid(latestXid);
    TransamVariables->xactCompletionCount++;

    LWLockRelease(ProcArrayLock);
}
```

Five design points worth highlighting:

1. **`ProcArrayLock` is held exclusive.** The comment at
   procarray.c:4001-4006 acknowledges this could potentially be
   relaxed (we're only modifying our own backend's slot), but the
   memory ordering and the global counters (latestCompletedXid,
   xactCompletionCount) need lock protection regardless.

2. **Backwards scan is O(n+m) not O(n×m).** Both the input `xids[]`
   and the in-cache `subxids[]` are in increasing order. By scanning
   both backwards and using nested loops that "break" on match,
   typical removal is O(n+m). The comment at procarray.c:4017-4019
   explicitly calls this out.

3. **Swap-with-last is the canonical "remove from unordered set"
   trick.** Replace the to-be-removed element with the array's last
   element, then decrement count. After this, the array is no longer
   sorted — but the function does its backwards scan starting from
   `count-1` *before* the decrement, so the swap doesn't break the
   ongoing iteration. The next iteration uses the freshly-decremented
   count.

   The price: subsequent calls (e.g., the second loop at
   procarray.c:4048-4061 that removes `xid` itself) can't assume the
   array is still sorted. So that second loop is a linear scan, not
   a binary search.

4. **`pg_write_barrier()` between the swap and the count decrement.**
   This ensures that other backends reading the cache see the slot's
   replacement value **before** the count decrement that hides the
   slot above the new boundary. Without the barrier, a reader could
   see `count = N-1` while still being able to read the now-garbage
   slot at index `N-1`. The barrier is paired with `pg_read_barrier()`
   in the readers (or, more commonly, an `LWLockAcquire`-based
   acquire-release pair).

5. **`if (j < 0 && !overflowed)` is a soft warning, not an assert.**
   The comment at procarray.c:4037-4043 explains: if the cache
   overflowed, the XID legitimately may not be there. Also, this
   routine can be re-invoked during error recovery from an aborted
   `AbortSubTransaction`. So the warning is best-effort, not a
   correctness check.

After the loop, **`MaintainLatestCompletedXid(latestXid)`** advances
the global watermark that bounds `RecentXmin`-style fast paths in
visibility checks. The watermark must be moved under the lock so
that simultaneous `GetSnapshotData()` calls see a consistent view.

## What the overflow protocol costs

When `overflowed = true`, three things change for the **other**
backends:

1. `TransactionIdIsInProgress(xid)` can no longer rule out the
   possibility that `xid` is a subxact of this backend, even if
   `xid` isn't in this backend's cached `subxids[]`. So it has to
   call `SubTransGetTopmostTransaction(xid)` to find the parent and
   re-check.

2. `XidInMVCCSnapshot` similarly has to chase the parent chain via
   pg_subtrans for any snapshot that recorded `suboverflowed = true`
   at the time of capture.

3. `GetSnapshotData` itself flags the captured snapshot's
   `suboverflowed` if any PGPROC has `overflowed`, and stores only
   top-level XIDs in `xip[]` (omitting the per-backend subxid
   contributions in the `subxip[]` array). This makes the snapshot
   smaller (good) but slower to use (bad).

The cost is real but bounded. For workloads that hit the 64-cap
rarely (most production workloads with PL/pgSQL EXCEPTION blocks),
the path is fast. For workloads with deep savepoints (some bulk
loaders, some financial transaction batches), the SubTrans SLRU
becomes hot enough to merit tuning `subtransaction_buffers`.

`src/test/isolation/specs/subxid-overflow.spec` [referenced in
proc.h:41] exercises the overflow path.

## The recovery / standby case — `ProcArrayApplyXidAssignment`

On a hot standby, no real backends are running the actual subxacts,
but the standby still needs to know which XIDs are part of which
top-level transaction so it can answer visibility queries for its
own read-only queries.

The primary periodically emits `XLOG_XACT_ASSIGNMENT` WAL records
that batch-announce up to 64 subxids per record. The standby
processes them via `ProcArrayApplyXidAssignment` [procarray.c:1304-1364]:

```c
void
ProcArrayApplyXidAssignment(TransactionId topxid,
                            int nsubxids, TransactionId *subxids)
{
    RecordKnownAssignedTransactionIds(max_xid);

    /* Write all subxids into pg_subtrans pointing to topxid. */
    for (i = 0; i < nsubxids; i++)
        SubTransSetParent(subxids[i], topxid);

    /* Remove subxids from KnownAssignedXids tree (they're now subsumed). */
    KnownAssignedXidsRemoveTree(InvalidTransactionId, nsubxids, subxids);

    /* Advance lastOverflowedXid to track the high-water mark. */
    if (TransactionIdPrecedes(procArray->lastOverflowedXid, max_xid))
        procArray->lastOverflowedXid = max_xid;
}
```

Two surprises:

1. **The standby stores top-level XID, not the per-level parent.**
   The comment at procarray.c:1330-1339 explains: subtransaction
   commit isn't marked in clog until parent commit, so by the time a
   subxact aborts, clog already shows it as aborted. So the standby
   can collapse the whole tree to "this subxid belongs to this top
   transaction" and lose no information. On the primary, by
   contrast, `SubTransSetParent` is called with the immediate parent
   so that intra-transaction visibility checks see the full tree.

2. **`lastOverflowedXid` is maintained per-procArray, not per-PGPROC,
   on standby.** There's no per-backend PGPROC for an originating
   subxact on the standby (no real backend is running it), so the
   overflow state is global. `XidInMVCCSnapshot` on standby
   consults `lastOverflowedXid` instead of per-PGPROC `overflowed`
   flags.

## Invariants

- **`PGPROC.subxids` and `ProcGlobal->subxidStates[pgxactoff]` are
  kept coherent.** Updates must touch both; readers may read either
  depending on access pattern. The mirror exists for hot-path scans.
- **`subxidStatus.count <= PGPROC_MAX_CACHED_SUBXIDS = 64`.** Asserted
  implicitly by the insertion path's overflow check.
- **`subxidStatus.overflowed == true` is sticky for the duration of
  the top transaction.** Resetting requires top-level commit/abort.
- **If `overflowed == false`, the array is the **complete** set of
  this backend's non-aborted subxact XIDs.** Other backends can rely
  on the cache as authoritative.
- **`XidCacheRemoveRunningXids` is only called on subxact abort.**
  Subxact commit promotes XIDs to the parent's tree; they stay in
  the PGPROC cache.
- **The swap-with-last trick leaves `subxids[]` unordered after
  removal.** Subsequent scans must be linear, not binary.
- **`pg_write_barrier()` separates the swap from the count
  decrement.** Required for lock-free readers.
- **All PGPROC manipulation under exclusive `ProcArrayLock`** for
  the abort path. Insertion paths similarly take the lock, plus the
  XidGenLock for the XID-assignment ordering invariant.

## Useful greps

```bash
# Find every reader of MyProc->subxids:
grep -RnE 'MyProc->subxids|->subxids\.' source/src/backend

# Find every writer that maintains the mirror:
grep -RnE 'ProcGlobal->subxidStates' source/src/backend

# Hot paths that scan the global subxidStates array:
grep -nE 'subxidStates\[' source/src/backend/storage/ipc/procarray.c

# Inspect overflow at runtime:
#   psql -c 'SELECT pid, backend_xid, backend_xmin FROM pg_stat_activity;'
#   gdb: p MyProc->subxidStatus.overflowed
#         p MyProc->subxidStatus.count

# Trace the XLOG_XACT_ASSIGNMENT path on standby:
grep -RnE 'XLOG_XACT_ASSIGNMENT|ProcArrayApplyXidAssignment' source/src/backend
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | 2200 | RecordTransactionCommit and the path that flushes subxids on parent commit |
| [`src/backend/storage/ipc/procarray.c`](../files/src/backend/storage/ipc/procarray.c.md) | 1304 | ProcArrayApplyXidAssignment (XLOG_XACT_ASSIGNMENT replay on standby) |
| [`src/backend/storage/ipc/procarray.c`](../files/src/backend/storage/ipc/procarray.c.md) | 1366 | TransactionIdIsInProgress (the cache's primary reader on primary) |
| [`src/backend/storage/ipc/procarray.c`](../files/src/backend/storage/ipc/procarray.c.md) | 3982 | XidCacheRemoveRunningXids (subxact abort path) |
| [`src/include/storage/proc.h`](../files/src/include/storage/proc.h.md) | 30 | PGPROC_MAX_CACHED_SUBXIDS, XidCacheStatus, XidCache |
| [`src/include/storage/proc.h`](../files/src/include/storage/proc.h.md) | 170 | PGPROC struct showing subxids + subxidStatus + pgxactoff |
| [`src/include/storage/proc.h`](../files/src/include/storage/proc.h.md) | 270 | PROC_HDR (alias ProcGlobal), with the mirrored subxidStates[]/xids[] arrays used by hot-path scans |

<!-- /callsites:auto -->

## Cross-references

- [[subxact-subtrans-slru]] — the on-disk pg_subtrans that takes
  over when the cache overflows; its `SubTransGetTopmostTransaction`
  is the fallback path.
- [[subxact-visibility-and-overflow]] — `XidInMVCCSnapshot`,
  `TransactionIdIsInProgress`, the snapshot's `suboverflowed` flag,
  and the lock-conflict integration.
- [[subtransaction-stack]] — the per-backend C-level
  `TransactionState` stack that drives `BeginInternalSubTransaction`,
  `Commit/AbortSubTransaction`, and feeds into this cache.
- [[snapshot-static-and-current]] — how `GetSnapshotData()` reads
  the global subxid arrays to build a snapshot.
- [[snapshot-active-stack-and-registered]] — the snapshot stack that
  captures and uses these subxact-visibility decisions.
- [[xmin-horizon-management]] — `MaintainLatestCompletedXid` feeds
  into the xmin horizons that determine vacuum eligibility.
- [[clog-slru]] — pg_xact tracks subxact abort/commit status, which
  interacts with the cache state.
