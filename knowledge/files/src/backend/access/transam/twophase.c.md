# twophase.c

- **Source path:** `source/src/backend/access/transam/twophase.c`
- **Lines:** 2878
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/twophase.h`,
  `source/src/include/access/twophase_rmgr.h`, `twophase_rmgr.c`,
  `xact.c` (`XactLogCommitRecord`/`AbortRecord` overload with
  `twophase_xid`), `pg_twophase/` directory on disk.

## Purpose

Implements `PREPARE TRANSACTION` / `COMMIT PREPARED` / `ROLLBACK
PREPARED`. Each gxact has a global identifier (GID), a dummy PGPROC,
and per-rmgr state captured at prepare time. State lives in WAL +
TwoPhaseState shared memory + `pg_twophase/<fxid>` files after
checkpoint. [from-comment] `twophase.c:12-69`.

## Top-of-file comment (verbatim)

A long NOTES block at `twophase.c:12-69` covering: GID reservation in
shmem before WAL, dummy PGPROC keeping XID "running", state-file
lifecycle (WAL → pg_twophase/ on checkpoint), redo rules
(`inredo`/`ondisk` flags). [from-comment] `twophase.c:12-69`.

## Public surface

Backend-facing:

- `StartPrepare(gxact)` — `twophase.c:1058` [verified-by-code]
- `EndPrepare(gxact)` — `twophase.c:1151` [verified-by-code]
- `MarkAsPreparing(fxid, gid, …)` — `twophase.c:365` [verified-by-code]
- `MarkAsPrepared(gxact, lock_held)` — `twophase.c:538`
  [verified-by-code]
- `FinishPreparedTransaction(gid, isCommit)` — `twophase.c:1503`
  [verified-by-code]
- `LockGXact(gid, user)` — `twophase.c:560` [verified-by-code]
- `RegisterTwoPhaseRecord(rmid, info, data, len)` — `twophase.c:1277`
  [verified-by-code]
- `LookupGXact(gid, prepare_end_lsn, …)` — `twophase.c:2694`
  [verified-by-code]
- `StandbyTransactionIdIsPrepared(xid)` — `twophase.c:1473`
  [verified-by-code]

Shared-mem + lifecycle:

- `TwoPhaseShmemRequest`, `TwoPhaseShmemInit`,
  `AtProcExit_Twophase`, `AtAbort_Twophase`, `PostPrepare_Twophase` —
  `twophase.c:249-364` [verified-by-code]

Checkpoint / recovery:

- `CheckPointTwoPhase(redo_horizon)` — `twophase.c:1828` [verified-by-code]
- `restoreTwoPhaseData()` — `twophase.c:1910` [verified-by-code]
- `PrescanPreparedTransactions` — `twophase.c:1972` [verified-by-code]
- `StandbyRecoverPreparedTransactions` — `twophase.c:2051`
  [verified-by-code]
- `RecoverPreparedTransactions` — `twophase.c:2089` [verified-by-code]
- `PrepareRedoAdd(fxid, buf, …)` — `twophase.c:2513` [verified-by-code]
- `PrepareRedoRemoveFull(fxid, giveWarning)` — `twophase.c:2626`
  [verified-by-code]

Commit/abort with 2PC:

- `RecordTransactionCommitPrepared` — `twophase.c:2319`
  [verified-by-code]
- `RecordTransactionAbortPrepared` — `twophase.c:2438`
  [verified-by-code]

Helpers:

- `TwoPhaseFilePath(*path, fxid)` — `twophase.c:956` [verified-by-code]
- `TwoPhaseGetDummyProcNumber` / `TwoPhaseGetDummyProc` —
  `twophase.c:914, 929` [verified-by-code]
- `LookupGXactBySubid`, `TwoPhaseTransactionGid` — `twophase.c:2803, 2753`
  [verified-by-code]

## Key types

- `GlobalTransaction` / `GlobalTransactionData` — shared-memory entry
  per active gxact: fxid, GID string, prepare_start_lsn,
  `inredo`/`ondisk`/`valid` flags, dummy PGPROC pointer. Declared in
  `twophase.h` / `twophase_rmgr.h`.
- `TwoPhaseState` — array + free list of gxacts in shared memory.
- `TwoPhaseFileHeader` — on-disk file header; format is shared with
  WAL serialization.

## Key invariants and locking

1. **GID reservation precedes WAL.** "The GID is reserved for the
   transaction in the array. This is done before a WAL entry is made,
   because the reservation checks for duplicate GIDs and aborts the
   transaction if there already is a global transaction in prepared
   state with the same GID." [from-comment] `twophase.c:17-22`.

2. **Dummy PGPROC keeps XID running.** Otherwise
   `TransactionIdIsInProgress` would think the prepared xact is no
   longer active. [from-comment] `twophase.c:24-26`.

3. **State lifecycle: WAL → pg_twophase/ at checkpoint.** Commit
   before checkpoint reads from WAL via `prepare_start_lsn`; commit
   after checkpoint reads the disk file. [from-comment]
   `twophase.c:37-47`.

4. **`CheckPointTwoPhase` is what migrates WAL → disk file.**
   Only gxacts with `inredo` set and start LSN behind the
   `redo_horizon` are persisted; flag flips to `ondisk = true`.
   [from-comment] `twophase.c:60-62`. [verified-by-code]
   `twophase.c:1828-…`.

5. **Two-phase rmgr per-prepare records.** Subsystems (Lock,
   `multixact.c`, predicate, async, pgstat) register state via
   `RegisterTwoPhaseRecord`; on commit/abort the dispatch table in
   `twophase_rmgr.c` is invoked.

6. **2PC commit record is `XLOG_XACT_COMMIT_PREPARED`**, emitted by
   `RecordTransactionCommitPrepared` calling
   `XactLogCommitRecord(..., twophase_xid, twophase_gid)`. The redo
   path then re-applies and calls `PrepareRedoRemove`.
   [verified-by-code] `twophase.c:2319-…`.

## Functions of note

### `StartPrepare` / `EndPrepare` — `twophase.c:1058, 1151` [verified-by-code]

`StartPrepare` builds an in-memory blob of state for all registered
rmgrs (via `save_state_data` and the twophase_rmgr callbacks).
`EndPrepare` writes the blob to WAL as `XLOG_XACT_PREPARE`, records
the `prepare_start_lsn`, flushes WAL, then marks `MarkAsPrepared`.

### `FinishPreparedTransaction` — `twophase.c:1503` [verified-by-code]

Implements `COMMIT PREPARED` and `ROLLBACK PREPARED`. Loads state
(from WAL via `XlogReadTwoPhaseData` `twophase.c:1418` or from
file via `ReadTwoPhaseFile` `twophase.c:1301`), calls the rmgr
postcommit/postabort callbacks, writes the commit/abort-prepared
record, removes the gxact.

### `CheckPointTwoPhase` — `twophase.c:1828` [verified-by-code]

For each in-memory gxact behind the redo horizon, calls
`RecreateTwoPhaseFile` to write it to `pg_twophase/<fxid>` and
fsync; updates `ondisk = true`.

### `RecoverPreparedTransactions` — `twophase.c:2089` [verified-by-code]

End-of-recovery handler. Re-acquires locks, re-registers per-rmgr
state, restores the dummy PGPROC so post-recovery
`TransactionIdIsInProgress` continues to report these XIDs.

## Cross-references

- `xact.c:XactLogCommitRecord`/`AbortRecord` are called here with
  the `twophase_xid` parameter.
- `twophase_rmgr.c` holds the callback dispatch table.
- `storage/lmgr/lock.c` registers lock state via the lock-rmgr 2PC
  callback.
- `multixact.c:multixact_twophase_*` registers MXID horizon needs.
- `replication/origin.c` registers replication-origin state.
- `procarray.c` consults the dummy PGPROC array for
  `TransactionIdIsInProgress`.

## Open questions

- The exact set of rmgrs in the 2PC dispatch table not enumerated
  here; see `twophase_rmgr.c` and the `TWOPHASE_RM_*` enum.
  [unverified]
- The `inredo` / `ondisk` / `valid` race-condition cases during
  concurrent checkpoint + COMMIT PREPARED not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 27
- `[from-comment]`: 7
- `[unverified]`: 2
