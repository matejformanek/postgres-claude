---
path: src/backend/access/transam/twophase.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 2878
depth: deep
---

# twophase.c

- **Source path:** `source/src/backend/access/transam/twophase.c`
- **Lines:** 2878
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `source/src/include/access/twophase.h`,
  `source/src/include/access/twophase_rmgr.h`, `twophase_rmgr.c`,
  `xact.c` (`XactLogCommitRecord`/`XactLogAbortRecord`, called with a
  `twophase_xid`/`twophase_gid`), `storage/subsystems.h` (the
  `ShmemCallbacks` registration mechanism), `pg_twophase/` directory on
  disk.

## Purpose

Implements `PREPARE TRANSACTION` / `COMMIT PREPARED` / `ROLLBACK
PREPARED`. Each global transaction (gxact) has a global identifier
(GID), a *dummy* PGPROC that keeps its XID visible to
`TransactionIdIsInProgress`, and per-rmgr state captured at prepare
time. State lives in three places over its lifetime: the WAL record,
the `TwoPhaseState` shared-memory array, and a `pg_twophase/<fxid>`
file written lazily at checkpoint. [from-comment] `twophase.c:12-69`.

## Top-of-file comment (verbatim, abridged)

```
Each global transaction is associated with a global transaction
identifier (GID). The client assigns a GID to a postgres transaction
with the PREPARE TRANSACTION command.

We keep all active global transactions in a shared memory array.  When
the PREPARE TRANSACTION command is issued, the GID is reserved for the
transaction in the array. This is done before a WAL entry is made,
because the reservation checks for duplicate GIDs ...

A global transaction (gxact) also has dummy PGPROC; this is what keeps
the XID considered running by TransactionIdIsInProgress. ...

Life track of state data is following:
* On PREPARE TRANSACTION backend writes state data only to the WAL and
  stores pointer to the start of the WAL record in
  gxact->prepare_start_lsn.
* If COMMIT occurs before checkpoint then backend reads data from WAL
  using prepare_start_lsn.
* On checkpoint state data copied to files in pg_twophase directory and
  fsynced
* If COMMIT happens after checkpoint then backend reads state data from
  files
```
[from-comment] `twophase.c:12-69`.

## Public symbols

| Symbol | Site | Role |
|---|---|---|
| `MarkAsPreparing(fxid, gid, …)` | `twophase.c:365` | Reserve GID + grab a free gxact (step 1 of lifecycle). [verified-by-code] |
| `StartPrepare(gxact)` | `twophase.c:1058` | Build the in-memory state blob for all rmgrs. [verified-by-code] |
| `EndPrepare(gxact)` | `twophase.c:1151` | Emit `XLOG_XACT_PREPARE`, flush, `MarkAsPrepared`. [verified-by-code] |
| `RegisterTwoPhaseRecord(rmid, info, data, len)` | `twophase.c:1277` | Append a per-rmgr chunk to the state blob. [verified-by-code] |
| `FinishPreparedTransaction(gid, isCommit)` | `twophase.c:1503` | `COMMIT`/`ROLLBACK PREPARED`. [verified-by-code] |
| `LockGXact(gid, user)` | `twophase.c:560` | Find + exclusively claim a gxact for commit/abort. [verified-by-code] |
| `MarkAsPrepared(gxact, lock_held)` | `twophase.c:538` | Flip `valid`, enter dummy PGPROC into ProcArray. [verified-by-code] |
| `PostPrepare_Twophase()` | `twophase.c:350` | Clear `locking_backend` after PREPARE returns. [verified-by-code] |
| `AtAbort_Twophase()` / `AtProcExit_Twophase` | `twophase.c:310, 300` | Release/abort the gxact `MyLockedGxact` points at. [verified-by-code] |
| `StandbyTransactionIdIsPrepared(xid)` | `twophase.c:1473` | Standby check used by Hot Standby conflict logic. [verified-by-code] |
| `LookupGXact(gid, prepare_end_lsn, ts)` | `twophase.c:2694` | Logical-rep duplicate-prepare detection by origin LSN/ts. [verified-by-code] |
| `LookupGXactBySubid(subid)` | `twophase.c:2803` | Does any prepared xact belong to this subscription? [verified-by-code] |
| `TwoPhaseTransactionGid(subid, xid, …)` | `twophase.c:2753` | Form `pg_gid_<subid>_<xid>` for logical-rep 2PC. [verified-by-code] |
| `TwoPhaseGetOldestXidInCommit()` | `twophase.c:2835` | Oldest xid of a 2PC commit in its `DELAY_CHKPT_IN_COMMIT` window — for logical-rep conflict detection. [verified-by-code] |
| `TwoPhaseGetDummyProcNumber` / `TwoPhaseGetDummyProc` | `twophase.c:914, 929` | Map an fxid to its dummy PGPROC. [verified-by-code] |
| `TwoPhaseGetXidByVirtualXID(vxid, …)` | `twophase.c:862` | Reverse-lookup an xid from a cloned VXID. [verified-by-code] |
| `pg_prepared_xact(fcinfo)` | `twophase.c:719` | SRF backing the `pg_prepared_xacts` view. [verified-by-code] |

Checkpoint / recovery surface:

| Symbol | Site | Role |
|---|---|---|
| `CheckPointTwoPhase(redo_horizon)` | `twophase.c:1828` | Migrate WAL-only gxacts → `pg_twophase/` files. [verified-by-code] |
| `restoreTwoPhaseData()` | `twophase.c:1910` | Scan `pg_twophase/` at recovery start into shmem. [verified-by-code] |
| `PrescanPreparedTransactions(…)` | `twophase.c:1972` | Compute XID range, advance `nextXid` past subxacts. [verified-by-code] |
| `StandbyRecoverPreparedTransactions()` | `twophase.c:2051` | Re-acquire locks for standby. [verified-by-code] |
| `RecoverPreparedTransactions()` | `twophase.c:2089` | End-of-recovery: rebuild dummy PGPROCs + rmgr state. [verified-by-code] |
| `PrepareRedoAdd(fxid, buf, …)` | `twophase.c:2513` | Redo of `XLOG_XACT_PREPARE`: insert gxact w/ `inredo`. [verified-by-code] |
| `PrepareRedoRemove(xid, …)` / `PrepareRedoRemoveFull` | `twophase.c:2670, 2626` | Redo of commit/abort-prepared: drop gxact + file. [verified-by-code] |
| `RecordTransactionCommitPrepared(…)` | `twophase.c:2319` | Writes the commit-prepared record (see invariant 7). [verified-by-code] |
| `RecordTransactionAbortPrepared(…)` | `twophase.c:2438` | Writes the abort-prepared record. [verified-by-code] |

## Key types

- `GlobalTransactionData` / `GlobalTransaction` — one shared-memory
  entry per active gxact. Fields of note: `fxid` (FullTransactionId
  identity), `prepare_start_lsn` (where to re-read state from WAL),
  `prepare_end_lsn` (what to wait for before commit), `locking_backend`
  (the ProcNumber currently committing/aborting it, else
  `INVALID_PROC_NUMBER`), and the three flags `valid` / `ondisk` /
  `inredo`. `twophase.c:150-173` [verified-by-code]. Note the file-level
  comment at `twophase.c:120-148` is the canonical 4-step lifecycle
  description.
- `TwoPhaseStateData` — fixed header + `freeGXacts` free-list head +
  `numPrepXacts` + a `FLEXIBLE_ARRAY_MEMBER` `prepXacts[]` of pointers.
  Sized for `max_prepared_xacts`. `twophase.c:179-189` [verified-by-code].
- `TwoPhaseFileHeader` — on-disk/WAL-serialized header (magic, total_len,
  xid, database, counts of subxacts/rels/stats/invalmsgs, gidlen,
  `origin_lsn`/`origin_timestamp`). Assembled in `StartPrepare`
  `twophase.c:1083-1102` [verified-by-code].

## Internal landmarks

- **Shmem registration via `ShmemCallbacks`.** This file no longer
  exports a `TwoPhaseShmemSize`/`TwoPhaseShmemInit` pair called from
  `ipci.c`; instead it exports `const ShmemCallbacks
  TwoPhaseShmemCallbacks = { .request_fn = TwoPhaseShmemRequest,
  .init_fn = TwoPhaseShmemInit }` (`twophase.c:196-199`) and the request
  fn calls `ShmemRequestStruct(.name = "Prepared Transaction Table", …)`
  (`twophase.c:260-263`). The dummy PGPROCs come from
  `PreparedXactProcs[]` and are wired up with `GetNumberFromPGProc`
  (`twophase.c:292`). [verified-by-code] — newer API than older PG
  branches; cite this if a plan touches shmem sizing here.
- **`MyLockedGxact`** (`twophase.c:207`) — backend-local pointer to the
  one gxact this backend currently holds locked. The abort/exit hooks
  (`AtAbort_Twophase` `twophase.c:310`) consult it to decide whether to
  roll the entry back (preparing → discard) or merely unlock it
  (already prepared → leave for someone else to finish). [verified-by-code]
- **State blob writer chain.** `save_state_data` (`twophase.c:1030`)
  appends to a chunked `records` linked list; `StartPrepare` lays down
  the header + GID + subxacts + commit/abort rels + stats + invalmsgs;
  each 2PC-aware subsystem then calls `RegisterTwoPhaseRecord`; finally
  `EndPrepare` appends a `TWOPHASE_RM_END_ID` sentinel
  (`twophase.c:1158`) and ships the whole list to WAL with one
  `XLogRegisterData` per chunk. [verified-by-code] `twophase.c:1210-1215`.
- **Read-back paths.** `XlogReadTwoPhaseData` (`twophase.c:1418`) reads
  the blob back from WAL at `prepare_start_lsn`; `ReadTwoPhaseFile`
  (`twophase.c:1301`) reads it from disk and validates magic + CRC +
  size bounds. `FinishPreparedTransaction` picks one based on
  `gxact->ondisk` (`twophase.c:1537-1540`). [verified-by-code]
- **Files are keyed by FullTransactionId.** `TwoPhaseFilePath`
  (`twophase.c:956`) formats a 16-hex-digit name; `restoreTwoPhaseData`
  only accepts dir entries matching `strlen==16 && strspn(…
  "0123456789ABCDEF")==16` (`twophase.c:1919-1920`). [verified-by-code]
- **`ProcessRecords`** (`twophase.c:1698`) walks the saved blob at
  commit/abort time, dispatching each chunk through the
  `twophase_postcommit_callbacks` / `twophase_postabort_callbacks`
  tables defined in `twophase_rmgr.c`. [verified-by-code]

## Invariants & gotchas

1. **GID reservation precedes WAL.** The GID is reserved in the shmem
   array (with a duplicate check) *before* any WAL is written, so a
   second `PREPARE` of the same GID aborts cleanly. [from-comment]
   `twophase.c:17-22`; [verified-by-code] `MarkAsPreparing`
   `twophase.c:393-404`.

2. **Dummy PGPROC keeps the XID "running."** `MarkAsPrepared` calls
   `ProcArrayAdd` (`twophase.c:552`) so `TransactionIdIsInProgress`
   still reports the prepared XID. The same XID may briefly appear
   *twice* in ProcArray — that window is intentional and safe; the
   alternative (a window where the XID looks crashed) is not.
   [from-comment] `twophase.c:1236-1241`. [verified-by-code]

3. **State lifecycle WAL → disk happens only at checkpoint.**
   `CheckPointTwoPhase` (`twophase.c:1828`) serializes a gxact to a
   `pg_twophase/` file *only* when `(valid || inredo) && !ondisk &&
   prepare_end_lsn <= redo_horizon`, then flips `ondisk = true` and
   invalidates the LSNs. The whole loop runs under `TwoPhaseStateLock`
   in **SHARED** mode (it expects zero work in the common case), and the
   directory is `fsync`'d unconditionally afterward.
   [verified-by-code] `twophase.c:1854-1887`.

4. **`DELAY_CHKPT_START` closes the prepare/checkpoint race.**
   `EndPrepare` sets `MyProc->delayChkptFlags |= DELAY_CHKPT_START`
   (`twophase.c:1207`) across the `XLogInsert`+`XLogFlush`, clearing it
   only after `MarkAsPrepared` (`twophase.c:1250`). Without this, a
   checkpoint that started right after the WAL insert could finish
   without fsyncing the (not-yet-on-disk) state — same race class as
   `RecordTransactionCommit`'s clog write. [from-comment + verified-by-code]
   `twophase.c:1189-1207`.

5. **`DELAY_CHKPT_IN_COMMIT` + write barrier in commit-prepared.**
   `RecordTransactionCommitPrepared` sets `DELAY_CHKPT_IN_COMMIT`
   (`twophase.c:2349`), issues `pg_write_barrier()` (`twophase.c:2357`),
   then reads the commit timestamp — so its visibility ordering matches
   logical-replication conflict detection. The flag is cleared after
   `TransactionIdCommitTree` (`twophase.c:2416`). [verified-by-code]

6. **`TwoPhaseGetOldestXidInCommit` is the conflict-detection hook.**
   It returns the oldest XID among `valid` gxacts whose
   `locking_backend` is mid-commit (`DELAY_CHKPT_IN_COMMIT` set) in the
   *current database*. Safe to dereference `commitproc` under
   `TwoPhaseStateLock` because the backend can't be torn down without an
   exclusive `TwoPhaseStateLock`. [verified-by-code] `twophase.c:2835-2877`.
   (This resolves the old doc's "concurrent checkpoint + COMMIT
   PREPARED race not deep-read" open question — the synchronization is
   the two `delayChkptFlags` plus `TwoPhaseStateLock`.)

7. **Commit/abort ordering is critical.** `FinishPreparedTransaction`
   does: WAL commit/abort record → mark in pg_xact → `ProcArrayRemove`
   → drop relfiles (`DropRelationFiles`, *before* releasing locks,
   `twophase.c:1624`) → send inval messages → run rmgr callbacks under
   `TwoPhaseStateLock` → `RemoveGXact` → finally physically remove the
   on-disk file. The whole tail runs inside `HOLD_INTERRUPTS()`.
   [from-comment + verified-by-code] `twophase.c:1566-1691`.

8. **Redo dedup against restored files.** `PrepareRedoAdd` skips a
   PREPARE record whose `pg_twophase/` file already exists (it was
   restored by `restoreTwoPhaseData` after a crash mid-checkpoint),
   erroring only once consistency is reached, else warning.
   `gxact->ondisk = !XLogRecPtrIsValid(start_lsn)`. [verified-by-code]
   `twophase.c:2546-2598`. (Resolves the old `inredo`/`ondisk` open
   question.)

9. **Size guard.** `EndPrepare` rejects a state blob whose `total_len >
   MaxAllocSize` up front, so a too-large prepare fails at PREPARE time
   rather than at COMMIT-time re-read. [verified-by-code]
   `twophase.c:1180-1183`.

10. **`max_prepared_xacts == 0` disables the feature** and is fixed at
    startup; `MarkAsPreparing` errors with a hint to raise it.
    [verified-by-code] `twophase.c:118, 378-382`.

## Cross-references

- `xact.c:XactLogCommitRecord` / `XactLogAbortRecord` — invoked here
  with the `twophase_xid`/`gid` arguments; their redo eventually calls
  `PrepareRedoRemove`.
- `twophase_rmgr.c` — the `twophase_recover_callbacks` /
  `twophase_postcommit_callbacks` / `twophase_postabort_callbacks`
  dispatch tables that `ProcessRecords` / `RecoverPreparedTransactions`
  walk. See `[[knowledge/files/src/backend/access/transam/twophase_rmgr.c.md]]`.
- `storage/lmgr/lock.c`, `storage/lmgr/predicate.c`,
  `multixact.c:multixact_twophase_*`, `replication/origin.c`, `pgstat`,
  async-notify — each registers per-prepare state via
  `RegisterTwoPhaseRecord`.
- `storage/ipc/procarray.c` — consults the dummy PGPROC array for
  `TransactionIdIsInProgress`; `ProcArrayAdd`/`ProcArrayRemove` bracket
  the prepared lifetime.
- `replication/logical/worker.c` — uses `TwoPhaseTransactionGid`,
  `LookupGXact`, `LookupGXactBySubid`, and
  `TwoPhaseGetOldestXidInCommit` for two-phase logical replication and
  dead-row conflict detection.
- `[[knowledge/subsystems/access-transam.md]]`,
  `[[knowledge/architecture/wal.md]]`.

## Confidence tag tally

- `[verified-by-code]`: ~40 (re-verified at anchor
  `4b0bf0788b066a4ca1d4f959566678e44ec93422`; all spot-checked line
  numbers identical to prior anchor `ef6a95c7c64`).
- `[from-comment]`: 6.
- `[unverified]`: 0.

## Synthesized by
<!-- backlinks:auto -->
- [architecture/wal.md](../../../../../architecture/wal.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/prepare-transaction-2pc.md](../../../../../idioms/prepare-transaction-2pc.md)


- [subsystems/access-transam.md](../../../../../subsystems/access-transam.md)