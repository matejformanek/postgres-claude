# `storage/ipc/procarray.c`

- **Source:** `source/src/backend/storage/ipc/procarray.c` (5307 lines)
- **Header:** `source/src/include/storage/procarray.h`
- **Last verified commit:** `dc5116780846` (2026-06-21)
- **Depth:** deep-read (spine + locking)

## Purpose

`procArray` is the data structure used to **enumerate currently running
transactions**. It's the kernel of MVCC snapshot construction
(`GetSnapshotData`) and of every "is xid running?" query. On a hot
standby, it also tracks `KnownAssignedXids` — xids the primary thought
were running at the WAL position we replayed up to.

> "Because of various subtle race conditions it is critical that a
> backend hold the correct locks while setting or clearing its xid (in
> ProcGlobal->xids[]/MyProc->xid). See notes in
> src/backend/access/transam/README." `[from-comment] procarray.c:12-15`

## Data structures

### `ProcArrayStruct` (`:76-105`)

```
{ numProcs, maxProcs,
  maxKnownAssignedXids, numKnownAssignedXids, tail/head,
  lastOverflowedXid,
  replication_slot_xmin, replication_slot_catalog_xmin,
  pgprocnos[FLEXIBLE_ARRAY_MEMBER]  /* dense indexes into allProcs[] */
}
```

`pgprocnos` is **the dense ordering** scanned by `GetSnapshotData`.
Each entry's slot in the parallel arrays `ProcGlobal->xids[]`,
`ProcGlobal->subxidStates[]`, `ProcGlobal->statusFlags[]` is at the
same index. Each `PGPROC` carries a `pgxactoff` field giving its
current offset; the offset can change when other procs are removed.
`[from-comment] :2226`.

### `KnownAssignedXids` (recovery only)

A circular buffer of xids the primary advertised in the WAL stream.
On hot standby this **replaces** the per-PGPROC xid array (which is
empty during recovery — standby PGPROCs are not running transactions
in the WAL sense). `[from-comment] :22-30`.

`lastOverflowedXid` tracks the highest *subxid* we evicted from
KnownAssignedXids; if a snapshot's xmin ≤ this, we mark
`suboverflowed`. `:96, 2347-2348`.

### `GlobalVisState` (`:148+`)

Per-relation horizons used by `heap_page_prune` etc. without locking
`ProcArrayLock`. Four variants:
- `GlobalVisSharedRels` (shared catalogs)
- `GlobalVisCatalogRels` (per-DB catalogs)
- `GlobalVisDataRels` (regular tables)
- `GlobalVisTempRels` (temp tables — only our own xact matters)

Each carries `definitely_needed` (rows newer than this are definitely
visible) and `maybe_needed` (rows older than this can be removed). In
between, the caller may rerun `ComputeXidHorizons()` for accuracy.
`[from-comment] :119-139`.

## Locking

- **`ProcArrayLock`** (LWLock) — protects the array, `xids[]`,
  `subxidStates[]`, `statusFlags[]`, and `KnownAssignedXids`.
- **`XidGenLock`** — protects `nextXid` (in `transam/varsup.c`). Held
  briefly during `GetNewTransactionId`. **Acquisition order:
  `XidGenLock` then `ProcArrayLock`** when both needed.
  `[from-comment]` `transam/README`. [unverified-here] — not pinned
  in this file.

### `GetSnapshotData` (`:2114`) — the lock-free read protocol

This is the hottest read path in PG. Walked end-to-end:

1. **Take `ProcArrayLock` SHARED.** `:2178`.
2. **`GetSnapshotDataReuse`** (`:2034`) — short-circuit if
   `TransamVariables->xactCompletionCount` is unchanged since the
   snapshot was last built. This counter is bumped (under exclusive
   ProcArrayLock) every time a transaction with an xid completes
   (`ProcArrayEndTransactionInternal:768`). If unchanged, the set of
   running xids hasn't changed, so the snapshot contents would be
   identical — return the existing snapshot, re-installing
   `MyProc->xmin = snapshot->xmin`. `:2044-2079`.
3. Otherwise: read `TransamVariables->latestCompletedXid` →
   `xmax = latestCompleted + 1`. `:2186-2196`.
4. **Walk `pgprocnos[0..numProcs)`.** For each:
   - `xid = UINT32_ACCESS_ONCE(other_xids[pgxactoff])` — single
     volatile read; the writer (xact start in `GetNewTransactionId`)
     publishes with a barrier. `:2223`. `[from-comment]` cross-refs
     `transam/README`.
   - Skip `xid == InvalidTransactionId`, our own xid, xid ≥ xmax,
     and backends with `PROC_IN_LOGICAL_DECODING | PROC_IN_VACUUM`
     (logical decoders track xmin separately; vacuums don't need
     snapshot inclusion). `:2232-2265`.
   - `xip[count++] = xid`; possibly extend xmin downward.
   - If `subxidStates[pgxactoff].overflowed` → `suboverflowed = true`.
     Else `memcpy(subxip, proc->subxids.xids, nsubxids*4)`. The
     `pg_read_barrier()` at `:2302` pairs with the writer's
     `pg_write_barrier()` in `GetNewTransactionId`. `[from-comment]`.
5. If hot-standby, instead call `KnownAssignedXidsGetAndSetXmin` to
   fill `subxip[]` (top + sub xids merged). `:2344-2348`.
6. Read `replication_slot_xmin` / `_catalog_xmin` while still holding
   the lock. `:2357-2358`.
7. **Install `MyProc->xmin = TransactionXmin = xmin`** if not already set.
   `:2361-2362`.
8. **Release `ProcArrayLock`.** The release is a full memory barrier
   that publishes our xmin. `:2363`.
9. Update `GlobalVis*Rels.definitely_needed` / `maybe_needed`
   unlocked but using values gathered under the lock. `:2366-2443`.
10. Fill snapshot fields and return.

**Key invariant**: setting `MyProc->xmin` while holding ProcArrayLock
SHARED is safe because each backend only writes its own slot; the
shared lock prevents *other* backends from removing themselves from
the array (which would change xmin). `[from-comment] :2175-2176`.

### `ProcArrayEndTransaction` (`:663`) — commit/abort exit

1. If we have an xid, try `LWLockConditionalAcquire(ProcArrayLock, EX)`.
   If that fails immediately → `ProcArrayGroupClearXid` (group-commit
   path). `:680-686`.
2. Under exclusive lock, `ProcArrayEndTransactionInternal`:
   - Clear `ProcGlobal->xids[pgxactoff]`, `proc->xid`,
     `proc->vxid.lxid`, `proc->xmin`, `delayChkptFlags`.
   - Clear `PROC_VACUUM_STATE_MASK` from `statusFlags`.
   - Clear subxid cache.
   - `MaintainLatestCompletedXid(latestXid)` — bumps the global.
   - `TransamVariables->xactCompletionCount++` ← this is what
     `GetSnapshotDataReuse` watches. `:725-769`.
3. If no xid: no lock needed; just clear local fields. `:688-716`.

### `ProcArrayGroupClearXid` (`:784`) — group commit

When `ProcArrayLock` is contended, backends form a linked stack on
`ProcGlobal->procArrayGroupFirst` (CAS-based) and wait on their
PGSemaphore. The first arrival becomes leader: acquires
`ProcArrayLock` EX once, then walks the stack and clears every
follower's xid, then wakes them via `PGSemaphoreUnlock`. `:797-887`.

The wake loop *reads* `procArrayGroupNext` before clearing the
follower's `procArrayGroupMember` flag and waking — with a
`pg_write_barrier` between the read and the clear so the follower
doesn't wake to a stale `procArrayGroupNext`. `:873-887`.

## Other key functions

- `ProcArrayAdd` / `ProcArrayRemove` (`:464, :561`) — under
  `ProcArrayLock` EX, with a `pgxactoff` shuffle so the dense arrays
  stay packed. Updates every other backend's `pgxactoff` is *not*
  needed — only the moved entry's PGPROC->pgxactoff. The rest is just
  an array shift.
- `TransactionIdIsInProgress(xid)` (`:1393`) — the "is this xid still
  running?" probe. Tries the cached `RecentXmin` first, then walks
  the array; under hot standby falls through to `KnownAssignedXids`.
- `ComputeXidHorizons` (`:1674`) — full O(N) scan to compute the
  authoritative xmin per-relation-kind; called when `GlobalVisTest*`
  cannot resolve a maybe-needed xid.
- `KnownAssignedXids*` (`:4435-5328`) — circular-buffer ops used only
  on hot standby. The buffer can hold both top and sub xids
  interleaved; the comments at `:2318-2342` explain why xips are
  stored in `subxip[]` not `xip[]` during recovery.

## `xactCompletionCount` — the lock-free reuse key

A single `uint64` in `TransamVariables`. Bumped on **every** xid-having
commit/abort under `ProcArrayLock` EXCLUSIVE. Read under
`ProcArrayLock` SHARED in `GetSnapshotDataReuse`. The matched value is
stored in `snapshot->snapXactCompletionCount`. Because the increment is
inside the lock, two concurrent snapshot reads holding SHARED cannot
miss it: any commit that changed the running set *must* have bumped
the counter visibly. `[from-comment] :2050-2059`. This is the trick
that makes back-to-back `GetSnapshotData` calls O(1) on an idle system.

## Cross-references

- `access/transam/varsup.c` — `GetNewTransactionId` is the *writer*
  side of the snapshot read protocol.
- `access/transam/twophase.c` — prepared transactions occupy dummy
  PGPROCs in the array (`pid == 0`). `[from-comment] :17-20`.
- `replication/walreceiver/standby.c` — feeds KnownAssignedXids during
  recovery (`RecordKnownAssignedTransactionIds`,
  `ExpireTreeKnownAssignedTransactionIds`).
- `storage/lmgr/proc.c` — `ProcGlobal` definition; `PGPROC` lifecycle.
- `utils/time/snapmgr.c` — snapshot management around this API.

## Open questions

1. **The `pg_read_barrier()` at `:2302` is documented as pairing with
   `GetNewTransactionId`** in `transam/varsup.c`. The exact write-side
   barrier wasn't re-verified in this read. `[unverified-here]`.
2. **Acquisition order of `XidGenLock` and `ProcArrayLock`.** Stated
   in `transam/README` to be `XidGenLock` first. Not asserted in this
   file. `[unverified-here]`.
3. **`PROCARRAY_MAXPROCS`** — referenced in the comment at `:103` but
   not defined locally; it's `MaxBackends + max_prepared_xacts + …`
   computed via `PROCARRAY_MAXPROCS` macro in `proc.h`.
   `[unverified-here]`.
4. The `pgxactoff` shuffle in `ProcArrayRemove` was not deep-read; if
   two procs leave concurrently under EX lock the ordering is
   serialized, but I did not verify there are no stale pointers in
   `ProcGlobal->xids[]` for the duration of a remove. `[unverified]`.

## Synthesized by
<!-- backlinks:auto -->
- [architecture/mvcc.md](../../../../../architecture/mvcc.md)
- [data-structures/pgproc-fields.md](../../../../../data-structures/pgproc-fields.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
- [idioms/commit-transaction-sequence.md](../../../../../idioms/commit-transaction-sequence.md)
- [idioms/snapshot-static-and-current.md](../../../../../idioms/snapshot-static-and-current.md)
- [idioms/subxact-visibility-and-overflow.md](../../../../../idioms/subxact-visibility-and-overflow.md)
- [idioms/subxact-xidcache-and-pgproc.md](../../../../../idioms/subxact-xidcache-and-pgproc.md)
- [idioms/xmin-horizon-management.md](../../../../../idioms/xmin-horizon-management.md)

