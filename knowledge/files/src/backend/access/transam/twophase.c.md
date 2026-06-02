---
path: src/backend/access/transam/twophase.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 2878
depth: deep
---

# twophase.c

- **Source path:** `source/src/backend/access/transam/twophase.c`
- **Lines:** 2878
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `source/src/include/access/twophase.h`,
  `source/src/include/access/twophase_rmgr.h`, `twophase_rmgr.c`,
  `xact.c` (`XactLogCommitRecord`/`XactLogAbortRecord` with the
  `twophase_xid`/`twophase_gid` overload), the on-disk `pg_twophase/`
  directory.

## Purpose

Implements two-phase commit: `PREPARE TRANSACTION`, `COMMIT PREPARED`,
`ROLLBACK PREPARED`. Each *global transaction* (gxact) carries a
client-assigned GID, a dummy `PGPROC` (so `TransactionIdIsInProgress`
still counts the XID as running between prepare and finish), and a blob
of per-rmgr state (locks, predicate locks, pgstat drops, inval
messages, replication origin) captured at prepare time. The blob lives
in three places over its lifecycle: WAL (the `XLOG_XACT_PREPARE`
record), `TwoPhaseState` shared memory, and — only if it outlives a
checkpoint — a `pg_twophase/<fxid>` state file. [from-comment]
`twophase.c:12-69`.

State-data lifecycle [from-comment] `twophase.c:37-47`:

- PREPARE writes the blob to WAL only; `gxact->prepare_start_lsn` points
  at the record start.
- COMMIT/ROLLBACK *before* the next checkpoint reads it back from WAL via
  `prepare_start_lsn`.
- A checkpoint copies still-live blobs to `pg_twophase/` and fsyncs them
  (`CheckPointTwoPhase`), flipping `ondisk = true`.
- COMMIT/ROLLBACK *after* that checkpoint reads the disk file.

## Public symbols

| Symbol | Line | Kind | Role |
|---|---|---|---|
| `max_prepared_xacts` | `twophase.c:118` | GUC int | feature switch; sizes shmem & PGPROC pool. 0 ⇒ 2PC disabled |
| `TwoPhaseShmemCallbacks` | `twophase.c:196` | const data | `{request_fn, init_fn}` registered with the shmem subsystem |
| `AtAbort_Twophase` | `twophase.c:310` | void | abort hook: unlock or (if `!valid`) remove `MyLockedGxact` |
| `PostPrepare_Twophase` | `twophase.c:350` | void | clears `locking_backend` + `MyLockedGxact` after state transfer |
| `MarkAsPreparing` | `twophase.c:365` | GlobalTransaction | reserve GID, allocate gxact from freelist, dup-GID check |
| `pg_prepared_xact` | `twophase.c:719` | SQL SRF | backs the `pg_prepared_xacts` view |
| `TwoPhaseGetXidByVirtualXID` | `twophase.c:862` | TransactionId | VXID→XID among xacts prepared since startup (not recovered ones) |
| `TwoPhaseGetDummyProcNumber` | `twophase.c:914` | ProcNumber | dummy proc number for a prepared fxid |
| `TwoPhaseGetDummyProc` | `twophase.c:929` | PGPROC * | dummy PGPROC for a prepared fxid |
| `StartPrepare` | `twophase.c:1058` | void | assemble the state blob in memory (header + rmgr records) |
| `EndPrepare` | `twophase.c:1151` | void | WAL-insert `XLOG_XACT_PREPARE`, flush, `MarkAsPrepared`, syncrep wait |
| `RegisterTwoPhaseRecord` | `twophase.c:1277` | void | append one rmgr record to the in-memory blob |
| `StandbyTransactionIdIsPrepared` | `twophase.c:1473` | bool | does a disk state file exist for this xid (recovery) |
| `FinishPreparedTransaction` | `twophase.c:1503` | void | execute COMMIT PREPARED / ROLLBACK PREPARED |
| `CheckPointTwoPhase` | `twophase.c:1828` | void | migrate live WAL-only blobs → `pg_twophase/` files |
| `restoreTwoPhaseData` | `twophase.c:1910` | void | startup: scan `pg_twophase/`, seed `TwoPhaseState` |
| `PrescanPreparedTransactions` | `twophase.c:1972` | TransactionId | post-WAL: oldest valid XID, advance nextXid past subxids |
| `StandbyRecoverPreparedTransactions` | `twophase.c:2051` | void | mid-recovery: make prepared xacts visible to standby snapshots |
| `RecoverPreparedTransactions` | `twophase.c:2089` | void | end-of-recovery: reacquire locks, rebuild dummy PGPROCs |
| `PrepareRedoAdd` | `twophase.c:2513` | void | redo of PREPARE: add gxact w/ `inredo = true` |
| `PrepareRedoRemove` | `twophase.c:2670` | void | redo of COMMIT/ABORT PREPARED: drop gxact (xid wrapper) |
| `LookupGXact` | `twophase.c:2694` | bool | match GID + origin_lsn + origin_timestamp (logical rep) |
| `TwoPhaseTransactionGid` | `twophase.c:2753` | void | format `pg_gid_<subid>_<xid>` GID for apply-worker xacts |
| `LookupGXactBySubid` | `twophase.c:2803` | bool | any prepared xact owned by this subscription? |
| `TwoPhaseGetOldestXidInCommit` | `twophase.c:2835` | TransactionId | oldest prepared xact in its commit critical section (this DB) |

## Internal landmarks

- **Shmem sizing/init** — `TwoPhaseShmemRequest` (`twophase.c:248`) reserves
  the fixed `TwoPhaseStateData` + pointer array + the `GlobalTransactionData`
  pool; `TwoPhaseShmemInit` (`twophase.c:269`) builds the freelist and wires
  each gxact to a `PreparedXactProcs[i]` PGPROC. Registered via the
  `ShmemCallbacks` table (`storage/subsystems.h`), not a direct
  `ShmemInitStruct` call. [verified-by-code] `twophase.c:193-294`.
- **Gxact alloc/free** — `MarkAsPreparingGuts` (`twophase.c:439`) zeroes &
  fills the dummy PGPROC; `GXactLoadSubxactData` (`twophase.c:512`) loads
  cached subxids (clamps at `PGPROC_MAX_CACHED_SUBXIDS`, sets `overflowed`);
  `MarkAsPrepared` (`twophase.c:538`) flips `valid` and `ProcArrayAdd`s the
  dummy proc; `RemoveGXact` (`twophase.c:636`) returns it to the freelist.
- **Locking the gxact** — `LockGXact` (`twophase.c:560`) finds a valid,
  unlocked gxact by GID, checks owner/superuser + same-DB, stamps
  `locking_backend = MyProcNumber`. `TwoPhaseGetGXact` (`twophase.c:809`)
  has a one-entry `static` fxid→gxact cache for the repeated lookups during
  commit/recovery.
- **fxid helpers** — `AdjustToFullTransactionId` (`twophase.c:949`) widens a
  bare xid via `FullTransactionIdFromAllowableAt`; `TwoPhaseFilePath`
  (`twophase.c:956`) renders the 16-hex `pg_twophase/EEEEEEEEXXXXXXXX` name.
- **Blob assembly** — `save_state_data` (`twophase.c:1030`) appends
  MAXALIGN-padded chunks to the `records` chain (file-static).
  `ProcessRecords` (`twophase.c:1698`) walks the rmgr records and dispatches
  to a callback table; stops at `TWOPHASE_RM_END_ID`.
- **Blob I/O** — `ReadTwoPhaseFile` (`twophase.c:1301`, CRC-32C + magic +
  size validation), `XlogReadTwoPhaseData` (`twophase.c:1418`, reads the
  PREPARE record straight out of WAL via a private `XLogReaderState`),
  `RecreateTwoPhaseFile` (`twophase.c:1748`, write + fsync the file),
  `RemoveTwoPhaseFile` (`twophase.c:1729`), `ProcessTwoPhaseBuffer`
  (`twophase.c:2193`, the recovery-time validate/dispatch of one blob).
- **Commit/abort record writers** — `RecordTransactionCommitPrepared`
  (`twophase.c:2319`) and `RecordTransactionAbortPrepared` (`twophase.c:2438`),
  both static, both mirror `xact.c`'s non-prepared paths.
- **Redo removal** — `PrepareRedoRemoveFull` (`twophase.c:2626`) is the real
  worker behind the `PrepareRedoRemove` xid wrapper.
- **Subid GID parsing** — `IsTwoPhaseTransactionGidForSubid`
  (`twophase.c:2771`) round-trips a GID through `TwoPhaseTransactionGid` to
  confirm it belongs to a subscription.

## Invariants & gotchas

1. **GID reserved in shmem *before* the WAL write.** `MarkAsPreparing` scans
   for a duplicate GID and errors out under `TwoPhaseStateLock` *before*
   `EndPrepare` ever touches WAL — that's the whole reason reservation
   precedes logging. [from-comment] `twophase.c:17-22`; [verified-by-code]
   `twophase.c:391-422`.

2. **Same XID can be in ProcArray twice, briefly — and that is OK.**
   `EndPrepare` calls `MarkAsPrepared` (which `ProcArrayAdd`s the dummy
   PGPROC) *before* xact.c clears the XID from the real `MyProc`. The window
   has the XID present twice; the forbidden alternative is a window where it's
   absent and onlookers conclude the xact crashed. [from-comment]
   `twophase.c:1231-1242`.

3. **`DELAY_CHKPT_START` brackets the PREPARE WAL insert.** Set inside the
   crit section before `XLogInsert`, cleared after `XLogFlush`, so a
   checkpoint that starts right after the insert can't finish without seeing
   the gxact as a candidate to fsync — same race class as
   `RecordTransactionCommit`'s clog write. [from-comment] `twophase.c:1188-1207,1250`.

4. **`DELAY_CHKPT_IN_COMMIT` + `pg_write_barrier` order commit timestamp for
   conflict detection.** `RecordTransactionCommitPrepared` sets
   `DELAY_CHKPT_IN_COMMIT`, issues `pg_write_barrier()`, *then* reads
   `committs`. The barrier guarantees the flag is globally visible before the
   commit timestamp is taken, so logical-replication conflict detection can
   hold back dead rows correctly. Cleared after `TransactionIdCommitTree`.
   [from-comment] `twophase.c:2347-2367,2416`. There is an injection point
   `commit-after-delay-checkpoint` loaded before the crit section
   (`twophase.c:2343,2351`).

5. **Strict ordering in `FinishPreparedTransaction`.** WAL commit/abort
   record → mark in pg_xact → `ProcArrayRemove` → run rmgr callbacks (which
   release locks). Reordering would let `TransactionIdIsInProgress` lie or
   release locks before durability. Runs under `HOLD_INTERRUPTS()`.
   [from-comment] `twophase.c:1569-1576`; [verified-by-code] `twophase.c:1567-1689`.

6. **Neither prepared commit nor abort can be optimized away.** Because the
   xact already wrote its PREPARE record, the 2nd-phase record is always
   emitted and flushed. `RecordTransactionAbortPrepared` even PANICs if the
   xid already committed (caught mid-`RecordTransactionCommitPrepared`).
   [from-comment] `twophase.c:2315-2316,2434-2435`; [verified-by-code]
   `twophase.c:2461-2463`.

7. **`AtAbort_Twophase` decides by `valid`.** If we abort while still
   preparing (or after writing the 2nd-phase record), `!valid` ⇒ remove the
   entry entirely; otherwise just clear `locking_backend` so the xact can be
   finished later. After the WAL record is written, in-memory state may be
   wrong but it's too late to back out. [from-comment] `twophase.c:315-340`.

8. **Recovery dual-source dedup.** `restoreTwoPhaseData` seeds from disk
   first; `PrepareRedoAdd` then skips a PREPARE record whose `pg_twophase/`
   file already exists (else `reachedConsistency ? ERROR : WARNING`), to avoid
   duplicate `TwoPhaseState` entries after a crash mid-checkpoint.
   [from-comment] `twophase.c:2546-2577`.

9. **`ProcessTwoPhaseBuffer` prunes stale/future xacts.** Already-committed
   or already-aborted xids, and xids `>= nextXid` (PITR to an earlier point
   without cleaning `pg_twophase/`), are dropped with a WARNING and their file
   removed. [verified-by-code] `twophase.c:2209-2252`.

10. **CRC is the WAL's, not separate, at prepare time.** `EndPrepare` relies
    on WAL CRC protection (`twophase.c:1186-1187`); the standalone CRC-32C is
    only computed when the blob is materialized to a file
    (`RecreateTwoPhaseFile` / validated in `ReadTwoPhaseFile`). The on-disk
    format is documented at `twophase.c:963-977`.

11. **`max_prepared_xacts` is fixed at startup** and sizes both the shmem
    array and the `PreparedXactProcs` PGPROC pool — overflow of the freelist
    is a hard ERROR ("maximum number of prepared transactions reached").
    [verified-by-code] `twophase.c:407-412,2580-2585`.

## Cross-refs

- [[knowledge/architecture/wal.md]] — `XLOG_XACT_PREPARE` and the
  COMMIT/ABORT-PREPARED records are part of the `RM_XACT_ID` rmgr.
- [[knowledge/subsystems/access-transam.md]] — twophase sits alongside
  `xact.c`, `clog.c`, `xlog.c` in the transam subsystem.
- [[knowledge/files/src/backend/access/transam/twophase_rmgr.c.md]] — the
  `twophase_recover_callbacks` / `_postcommit_` / `_postabort_` dispatch
  tables indexed by `TwoPhaseRmgrId`.
- [[knowledge/files/src/backend/access/transam/xact.c.md]] —
  `XactLogCommitRecord` / `XactLogAbortRecord` are called here with the
  twophase xid+gid; `xact_redo_commit/abort` call `PrepareRedoRemove`.
- [[knowledge/idioms/locking-overview.md]] — everything mutating
  `TwoPhaseState` holds `TwoPhaseStateLock` (LW_EXCLUSIVE for writes,
  LW_SHARED for the scans/lookups).
- [[knowledge/data-structures/pgproc-fields.md]] — the dummy PGPROC's
  `delayChkptFlags`, `vxid`, `subxidStatus` fields are central here.
- `storage/lmgr/predicate.c` (`PredicateLockTwoPhaseFinish`),
  `multixact.c`, `replication/origin.c` register per-rmgr 2PC state.

## Confidence tag tally

- `[verified-by-code]`: 9
- `[from-comment]`: 11

## Synthesized by
<!-- backlinks:auto -->
- [architecture/wal.md](../../../../../architecture/wal.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
