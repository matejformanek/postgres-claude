# xact.c

- **Source path:** `source/src/backend/access/transam/xact.c`
- **Lines:** 6506
- **Last verified commit:** `b7e4e3e7fa73`
- **Companion files:** `source/src/include/access/xact.h`, `README` (this directory),
  `source/src/backend/access/transam/parallel.c`,
  `source/src/backend/access/transam/twophase.c`,
  `source/src/backend/storage/ipc/procarray.c`.

## Purpose

Top-level transaction system. Implements the three-layer transaction architecture
(toplevel SQL handlers, mainloop control, low-level Start/Commit/Abort) described
in the README, plus the WAL commit/abort record assembly (`XactLogCommitRecord`,
`XactLogAbortRecord`) and their redo routines. [from-comment]
`xact.c:3-6`.

## Top-of-file comment (verbatim)

```
xact.c
  top level transaction system support routines

See src/backend/access/transam/README for more information.
```
[from-comment] `xact.c:3-6`.

## Public surface

State accessors and mainloop hooks (called by `postgres.c`):

- `IsTransactionState` — `xact.c:388-401` [verified-by-code]
- `IsAbortedTransactionBlockState` — `xact.c:409` [verified-by-code]
- `StartTransactionCommand` — `xact.c:3112` [verified-by-code]
- `CommitTransactionCommand` — `xact.c:3210` [verified-by-code]
- `AbortCurrentTransaction` — `xact.c:3504` [verified-by-code]
- `CommandCounterIncrement` — `xact.c:1130` [verified-by-code]

SQL block handlers (called by `tcop/utility.c`):

- `BeginTransactionBlock` `xact.c:3978`, `EndTransactionBlock` `xact.c:4098`,
  `UserAbortTransactionBlock` `xact.c:4258`, `PrepareTransactionBlock`
  `xact.c:4046`, `DefineSavepoint` `xact.c:4427`, `ReleaseSavepoint`
  `xact.c:4512`, `RollbackToSavepoint` `xact.c:4621`. [verified-by-code]

XID/snapshot accessors:

- `GetTopTransactionId`, `GetTopTransactionIdIfAny`, `GetCurrentTransactionId`,
  `GetCurrentTransactionIdIfAny` — `xact.c:428-484` [verified-by-code]
- `GetTopFullTransactionId`, `GetCurrentFullTransactionId` — `xact.c:485-541`
  [verified-by-code]
- `TransactionIdIsCurrentTransactionId` — `xact.c:943` [verified-by-code]

Internal subtransactions (e.g. PL/pgSQL):

- `BeginInternalSubTransaction` — `xact.c:4748` [verified-by-code]
- `ReleaseCurrentSubTransaction` — `xact.c:4822` [verified-by-code]
- `RollbackAndReleaseCurrentSubTransaction` — `xact.c:4850`
  [verified-by-code]

Callback registries:

- `RegisterXactCallback`/`UnregisterXactCallback` — `xact.c:3858-3889`
  [verified-by-code]
- `RegisterSubXactCallback`/`UnregisterSubXactCallback` — `xact.c:3918-3949`
  [verified-by-code]

Parallel-mode bridge:

- `EnterParallelMode`/`ExitParallelMode`/`IsInParallelMode` —
  `xact.c:1081-1129` [verified-by-code]
- `EstimateTransactionStateSpace`, `SerializeTransactionState`,
  `StartParallelWorkerTransaction`, `EndParallelWorkerTransaction` —
  `xact.c:5571-5704` [verified-by-code]

WAL record build + redo (exported for `twophase.c` and recovery):

- `XactLogCommitRecord` — `xact.c:5873` [verified-by-code]
- `XactLogAbortRecord` — `xact.c:6045` [verified-by-code]
- `xact_redo` — `xact.c:6422` [verified-by-code]

## Key types / structs

### `TransState` enum (`xact.c:143-151`) [verified-by-code]

Low-level state for the transaction-in-progress machine:
`TRANS_DEFAULT`, `TRANS_START`, `TRANS_INPROGRESS`, `TRANS_COMMIT`,
`TRANS_ABORT`, `TRANS_PREPARE`.

### `TBlockState` enum (`xact.c:159-186`) [verified-by-code]

User-visible block state seen by `*TransactionCommand`. 20 values: idle,
single-query, the in/abort/end progression, the `*_PENDING` "deferred"
states (see README §Subtransaction Handling), the `SUB*` mirrors and the
two `*_RESTART` variants used for `ROLLBACK TO`.

### `TransactionStateData` (`xact.c:195-223`) [verified-by-code]

The stack node. Notable fields:

- `fullTransactionId` — assigned lazily by `AssignTransactionId`
  (`xact.c:637`).
- `subTransactionId` — local counter, `TopSubTransactionId = 1`.
- `nestingLevel`, `gucNestLevel`.
- `curTransactionContext` / `priorContext` / `curTransactionOwner` —
  the memory + resource-owner pair restored on pop.
- `childXids[]` — subcommitted-child XID list, sorted (see README's
  "child > parent" invariant).
- `startedInRecovery` — true if `RecoveryInProgress()` at start; forces
  `XactReadOnly = true` (`xact.c:2164-2168`). [verified-by-code]
- `didLogXid`, `topXidLogged` — track XID inclusion in WAL.
- `parallelModeLevel`, `parallelChildXact` — see "EnterParallelMode"
  counter; `parallel.c` references these. [from-comment]
  `xact.c:190-193`.
- `parent` — stack link.

### `SerializedTransactionState` (`xact.c:229-242`) [verified-by-code]

Wire format for shipping the *current* XID set to a parallel worker.
Variable-length: header + sorted XID array. Used by
`SerializeTransactionState` and `StartParallelWorkerTransaction`.

### Module globals (`xact.c:80-329`) [verified-by-code]

- `XactIsoLevel`, `XactReadOnly`, `XactDeferrable`, `synchronous_commit`.
- `XactTopFullTransactionId` (`xact.c:127`): parallel-worker mirror of
  the leader's top XID.
- `nParallelCurrentXids`, `ParallelCurrentXids` (`xact.c:128-129`):
  sorted XID array passed from leader; consulted by
  `TransactionIdIsCurrentTransactionId` in parallel workers.
- `TopTransactionStateData` (`xact.c:249-253`): the bottom-of-stack
  state, pre-zeroed.
- `nUnreportedXids`, `unreportedXids[PGPROC_MAX_CACHED_SUBXIDS]`
  (`xact.c:259-260`): subxact XIDs awaiting an `XLOG_XACT_ASSIGNMENT`
  record.
- `TransactionAbortContext` (`xact.c:305`): pre-reserved memory context
  so `AbortTransaction`/`AbortSubTransaction` can run under OOM.

## Key invariants and locking

1. **`TRANS_INPROGRESS` is the only "valid" state for DB access.**
   `IsTransactionState` deliberately rejects `TRANS_START`,
   `TRANS_COMMIT`, `TRANS_PREPARE`, `TRANS_ABORT`, `TRANS_DEFAULT`.
   [from-comment] `xact.c:393-400`.

2. **Critical section straddles commit-marking.**
   `RecordTransactionCommit` enters `START_CRIT_SECTION` *before*
   setting `MyProc->delayChkptFlags |= DELAY_CHKPT_IN_COMMIT` and
   *before* `XactLogCommitRecord` so the assignment cannot be torn from
   the commit WAL insert. [verified-by-code] `xact.c:1469-1490`.

3. **`DELAY_CHKPT_IN_COMMIT` forces concurrent checkpoint to wait** so
   the pg_xact update is not lost on crash. [from-comment]
   `xact.c:1448-1454`. Cleared after `TransactionIdCommitTree` and
   `ProcArrayEndTransaction`. [verified-by-code]
   (`RecordTransactionCommit` further down; see `xact.c:1550-1620`.)

4. **`ProcArrayEndTransaction` happens after `RecordTransactionCommit`
   and before locks are released.** `xact.c:2427-2431` comment makes
   this explicit. [from-comment]

5. **Sync commit forced when relations are deleted.** `nrels > 0`
   forces `XLogFlush` regardless of `synchronous_commit`, because the
   files will be unlinked at commit. [from-comment] [verified-by-code]
   `xact.c:1532-1544`.

6. **DDL with no XID still emits standby invalidations.**
   `LogStandbyInvalidations` is called when `markXidCommitted` is false
   but `nmsgs != 0`. [verified-by-code] `xact.c:1421-1426`. The comment
   calls this a defect (`xact.c:1412-1420`).

7. **Parallel worker does not write its own commit record.** When
   `is_parallel_worker`, `RecordTransactionCommit` is skipped;
   `ParallelWorkerReportLastRecEnd(XactLastRecEnd)` informs the leader
   instead. [verified-by-code] `xact.c:2409-2422`.

8. **`RecoveryInProgress()` at start forces read-only.**
   `StartTransaction` sets `XactReadOnly = true` and remembers
   `s->startedInRecovery`. [verified-by-code] `xact.c:2164-2168`.

9. **VXID lock is acquired before XID announcement.**
   `VirtualXactLockTableInsert(vxid)` happens *before*
   `MyProc->vxid.lxid = vxid.localTransactionId`. [verified-by-code]
   `xact.c:2204-2217`. The README's "fetch atomicity" rule applies.

10. **Stop-timestamp is captured under the commit critical section.**
    `xactStopTimestamp` is asserted zero at `xact.c:1473` and set inside
    `GetCurrentTransactionStopTimestamp()` (called by
    `XactLogCommitRecord` at `xact.c:1484`). The comment at
    `xact.c:1465-1468` reminds you to read it *after* setting
    `DELAY_CHKPT_IN_COMMIT`. [from-comment]

## Functions of note (≥3 ≤8)

### `StartTransaction` — `xact.c:2106-2261` [verified-by-code]

State machine: `TRANS_DEFAULT → TRANS_START → TRANS_INPROGRESS`. Allocates
fresh `vxid` (procNumber + LocalTransactionId), inserts VXID lock
(`VirtualXactLockTableInsert`), publishes via `MyProc->vxid.lxid`, runs
`AtStart_*` initializers (memory context, resource owner, GUC, cache).
Sets `XactReadOnly = true` if `RecoveryInProgress()`. [from-comment]
`xact.c:2156-2168`.

### `CommitTransaction` — `xact.c:2270-2549` [verified-by-code]

The hard ordering required by the README:

1. Drain deferred triggers + close portals until quiescent (`xact.c:2299-2313`).
2. `CallXactCallbacks(XACT_EVENT_PRE_COMMIT)` and parallel-worker cleanup.
3. `smgrDoPendingSyncs(true, …)` — fsync WAL-skipped relfilenumbers
   *before* the commit record (README §"Skipping WAL"). [verified-by-code]
   `xact.c:2360`.
4. `AtEOXact_LargeObject`, `PreCommit_Notify`,
   `PreCommit_CheckForSerializationFailure`.
5. `AtEOXact_RelationMap(true, …)` — relation map last.
6. `state = TRANS_COMMIT`.
7. `RecordTransactionCommit()` — durable commit (skipped in workers).
8. `ProcArrayEndTransaction(MyProc, latestXid)` — clears XID under
   `ProcArrayLock` exclusive (the README's interlocking rule).
9. Resource-owner release in three phases (`BEFORE_LOCKS`,
   `RESOURCE_RELEASE_LOCKS`, `AFTER_LOCKS`).
10. `smgrDoPendingDeletes(true)` — unlink dropped files (the
    "post-WAL unlink" pattern of README §"Filesystem Actions").

### `RecordTransactionCommit` — `xact.c:1345-1620` [verified-by-code]

Where durable commit happens. Decides whether an XID is committed
(`markXidCommitted`); if not but `wrote_xlog`, only standby
invalidations are flushed. If yes:

- Enters `START_CRIT_SECTION`, sets `DELAY_CHKPT_IN_COMMIT`.
- `XactLogCommitRecord(...)` (synchronous or async).
- `TransactionTreeSetCommitTsData(...)` updates `commit_ts` SLRU.
- `XLogFlush(XactLastRecEnd)` if sync commit, `nrels > 0`, or
  `forceSyncCommit`. Otherwise `XLogSetAsyncXactLSN` for the walwriter.
- `TransactionIdCommitTree(xid, nchildren, children)` — atomically
  marks committed in pg_xact (multi-page case uses sub-commit-then-commit
  protocol; see `clog.c` doc and README §pg_xact).
- `SyncRepWaitForLSN` for synchronous replication.

### `AbortTransaction` — `xact.c:2855-3060` [verified-by-code]

Phase 1 of the README's "abort divided in two phases". Releases shared
resources (locks, buffer pins) but does *not* destroy
`TopTransactionContext`. Writes the abort record via
`RecordTransactionAbort` (`xact.c:1796`). Idempotent against repeated
calls — important because abort can recur during cleanup.

### `CleanupTransaction` — `xact.c:3062-3110` [verified-by-code]

Phase 2 of abort. Pops to the top and destroys `TopTransactionContext`.
Only called on the toplevel transaction.

### `XactLogCommitRecord` — `xact.c:5873-6036` [verified-by-code]

Assembles the `XLOG_XACT_COMMIT` (or `_COMMIT_PREPARED`) WAL record.
Variable structure: header + optional `xl_xact_xinfo` flags +
`xl_xact_dbinfo`, `xl_xact_subxacts`, `xl_xact_relfilelocators`,
`xl_xact_stats_items`, `xl_xact_invals`, `xl_xact_twophase`,
`xl_xact_origin`. Sub-records are conditionally appended via
`XLogRegisterData`. Sets `XLR_SPECIAL_REL_UPDATE` info bit when files
will be dropped. [verified-by-code] `xact.c:5942`.

### `xact_redo` — `xact.c:6422-…` [verified-by-code]

Recovery dispatch for RM_XACT_ID records. Parses commit/abort/prepare/
assignment subtypes; calls `xact_redo_commit` (`xact.c:6189`) /
`xact_redo_abort` (`xact.c:6343`) which in turn apply the same effects
(clog, commit_ts, file unlinks, invalidations) as live commit/abort.

### `AssignTransactionId` — `xact.c:637-…` [verified-by-code]

Lazy XID assignment. Recursively assigns parents first (preserving the
"child > parent" invariant from README §"Transaction and Subtransaction
Numbering"). Calls `GetNewTransactionId` (`varsup.c`), takes XID lock
on self, records parent in pg_subtrans (`SubTransSetParent`), reports
to ProcArray. Tracks `unreportedXids[]` to batch `XLOG_XACT_ASSIGNMENT`
records.

## Cross-references

- `varsup.c` — `GetNewTransactionId` (XID allocation; see invariant 9
  in README).
- `procarray.c` (`source/src/backend/storage/ipc/`) —
  `ProcArrayEndTransaction`, `ProcArrayApplyXidAssignment`.
- `clog.c` — `TransactionIdCommitTree` + sub-commit protocol.
- `commit_ts.c` — `TransactionTreeSetCommitTsData`.
- `subtrans.c` — `SubTransSetParent`.
- `twophase.c` — calls `XactLogCommitRecord`/`XactLogAbortRecord` with
  `twophase_xid != Invalid`.
- `xloginsert.c` — `XLogBeginInsert`/`XLogRegisterData`/`XLogInsert`
  (the assembly API).
- `xlog.c` — `XLogFlush`, `XLogSetAsyncXactLSN`.
- `xlogrecovery.c` — invokes `xact_redo` during replay.
- `parallel.c` — uses `EnterParallelMode`/`ExitParallelMode`,
  `SerializeTransactionState`/`StartParallelWorkerTransaction`.
- `pg_subtrans` truncation, autovacuum, sinval all hook in here.

## Open questions

- The exact contents and ordering of `xact_redo_commit` (clog before
  commit_ts? before sinval delivery?) are not re-derived here; the
  README's invariants should hold but I have not verified line-by-line.
  [unverified]
- The unreported-XID batching threshold for `XLOG_XACT_ASSIGNMENT`
  (`PGPROC_MAX_CACHED_SUBXIDS`) is not analyzed here. [unverified]
- `TransactionIdIsCurrentTransactionId` walks the stack and, in parallel
  workers, binary-searches `ParallelCurrentXids[]` (`xact.c:128`
  comment). Not re-verified to line. [unverified]
- The sync-rep wait window inside `RecordTransactionCommit` after
  clearing `DELAY_CHKPT_IN_COMMIT` was not deep-read here. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 28
- `[from-comment]`: 9
- `[from-README]`: 0 (deferred to README doc)
- `[inferred]`: 0
- `[unverified]`: 4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
- [idioms/abort-transaction-cleanup.md](../../../../../idioms/abort-transaction-cleanup.md)
- [idioms/commit-transaction-sequence.md](../../../../../idioms/commit-transaction-sequence.md)
- [idioms/parallel-state-propagation.md](../../../../../idioms/parallel-state-propagation.md)
- [idioms/prepare-transaction-2pc.md](../../../../../idioms/prepare-transaction-2pc.md)
- [idioms/subtransaction-stack.md](../../../../../idioms/subtransaction-stack.md)
- [idioms/subxact-visibility-and-overflow.md](../../../../../idioms/subxact-visibility-and-overflow.md)
- [idioms/subxact-xidcache-and-pgproc.md](../../../../../idioms/subxact-xidcache-and-pgproc.md)
- [idioms/trigger-constraint-deferral.md](../../../../../idioms/trigger-constraint-deferral.md)
- [idioms/trigger-during-error.md](../../../../../idioms/trigger-during-error.md)

