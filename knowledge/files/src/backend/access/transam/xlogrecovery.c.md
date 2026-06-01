# xlogrecovery.c

- **Source path:** `source/src/backend/access/transam/xlogrecovery.c`
- **Lines:** 5111
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogrecovery.h`,
  `xlog.c` (`StartupXLOG` is the caller), `xlogreader.c`, `xlogprefetcher.c`,
  `xlogutils.c`, `catalog/pg_control.h`.

## Purpose

Owns the WAL recovery state machine. Three-phase model:
`InitWalRecovery` (decide crash / archive / standby), `PerformWalRecovery`
(the main redo apply loop), `FinishWalRecovery` (end-of-recovery cleanup).
Also implements the recovery-target machinery (stop conditions, pause,
timeline switching), the read-record loop that pulls bytes via
`xlogreader` and `xlogprefetcher`, and the WAL-source fallback logic
(`WaitForWALToBecomeAvailable`). [from-comment] `xlogrecovery.c:3-13`.

## Top-of-file comment (verbatim)

```
xlogrecovery.c
    Functions for WAL recovery, standby mode

This source file contains functions controlling WAL recovery.
InitWalRecovery() initializes the system for crash or archive recovery,
or standby mode, depending on configuration options and the state of
the control file and possible backup label file.  PerformWalRecovery()
performs the actual WAL replay, calling the rmgr-specific redo routines.
FinishWalRecovery() performs end-of-recovery checks and cleanup actions,
and prepares information needed to initialize the WAL for writes.
```
[from-comment] `xlogrecovery.c:3-14`.

## Public surface

Phase entry points:

- `XLogRecoveryShmemRequest` / `XLogRecoveryShmemInit` —
  `xlogrecovery.c:400, 409` [verified-by-code]
- `EnableStandbyMode` — `xlogrecovery.c:423` [verified-by-code]
- `InitWalRecovery` — `xlogrecovery.c:457` [verified-by-code]
- `PerformWalRecovery` — `xlogrecovery.c:1612` [verified-by-code]
- `FinishWalRecovery` — `xlogrecovery.c:1417` [verified-by-code]
- `ShutdownWalRecovery` — `xlogrecovery.c:1567` [verified-by-code]

Replay-loop internals:

- `ApplyWalRecord` — `xlogrecovery.c:1883` [verified-by-code]
- `xlogrecovery_redo` — `xlogrecovery.c:2047` [verified-by-code]
- `ReadRecord` — `xlogrecovery.c:3108` [verified-by-code]
- `XLogPageRead` — `xlogrecovery.c:3277` [verified-by-code]
- `WaitForWALToBecomeAvailable` — `xlogrecovery.c:3534` [verified-by-code]
- `XLogFileRead` / `XLogFileReadAnyTLI` — `xlogrecovery.c:4202, 4284`
  [verified-by-code]
- `ReadCheckpointRecord` — `xlogrecovery.c:4060` [verified-by-code]
- `rescanLatestTimeLine` — `xlogrecovery.c:4115` [verified-by-code]

Consistency + pause + stop:

- `CheckRecoveryConsistency` — `xlogrecovery.c:2151` [verified-by-code]
- `verifyBackupPageConsistency` — `xlogrecovery.c:2438` [verified-by-code]
- `recoveryStopsBefore` / `recoveryStopsAfter` —
  `xlogrecovery.c:2550, 2703` [verified-by-code]
- `GetRecoveryPauseState` / `SetRecoveryPause` / `ConfirmRecoveryPaused` —
  `xlogrecovery.c:3047-3107` [verified-by-code]
- `recoveryApplyDelay` — `xlogrecovery.c:2959` [verified-by-code]

Backup-label / tablespace-map readers:

- `read_backup_label` — `xlogrecovery.c:1167` [verified-by-code]
- `read_tablespace_map` — `xlogrecovery.c:1313` [verified-by-code]
- `readRecoverySignalFile` — `xlogrecovery.c:984` [verified-by-code]
- `validateRecoveryParameters` — `xlogrecovery.c:1068` [verified-by-code]
- `CheckTablespaceDirectory` — `xlogrecovery.c:2118` [verified-by-code]

## Key types / structs

- `XLogRecoveryCtlData` (defined in this file ~`xlogrecovery.c:200-…`)
  — shared-memory state: `info_lck`, `replayEndRecPtr`/`replayEndTLI`,
  `lastReplayed*`, `recoveryLastXTime`, `recoveryPauseState`,
  `SharedHotStandbyActive`. [verified-by-code] `xlogrecovery.c:1623-1641`.
- `RecoveryTargetType`, `RecoveryTargetAction`, `RecoveryPauseState`,
  enum types defined in `include/access/xlogrecovery.h`.
- `standbyState` (module-level) — STANDBY_DISABLED, STANDBY_INITIALIZED,
  STANDBY_SNAPSHOT_PENDING, STANDBY_SNAPSHOT_READY. [verified-by-code]
  `xlogrecovery.c:1954` (use).

## Key invariants and locking

1. **Startup process is the only writer of recovery state.** Other
   backends read via `XLogRecoveryCtl` under `info_lck`.
   [from-comment] [verified-by-code] `xlogrecovery.c:1623-1641, 1946-1949`.

2. **`nextXid` is advanced past every record's `xl_xid`.**
   `ApplyWalRecord` calls `AdvanceNextFullTransactionIdPastXid`
   *before* dispatching to the redo routine. [verified-by-code]
   `xlogrecovery.c:1897`.

3. **TLI switch precedes the record that caused it.** `replayTLI`
   is updated before `RmgrTable[rmid].rm_redo()` runs, so any
   resulting writes carry the new TLI. [from-comment]
   `xlogrecovery.c:1899-1940`.

4. **`replayEndRecPtr` is bumped before replay** so that any
   `XLogFlush` issued by the redo routine (in turn calling
   `UpdateMinRecoveryPoint` because `XLogInsertAllowed()` is false in
   recovery) sees the right value. [from-comment]
   `xlogrecovery.c:1942-1949`.

5. **`RecordKnownAssignedTransactionIds(xid)` runs for every xid-bearing
   record once `standbyState >= STANDBY_INITIALIZED`.**
   [verified-by-code] `xlogrecovery.c:1954-1956`.

6. **Some XLOG records are handled directly by `xlogrecovery_redo`, not
   the rmgr's `rm_redo`.** These include `XLOG_BACKUP_END`,
   `XLOG_END_OF_RECOVERY`, `XLOG_OVERWRITE_CONTRECORD`,
   `XLOG_CHECKPOINT_REDO`. [verified-by-code]
   `xlogrecovery.c:2047-…`.

7. **`PANIC` on missing redo point.** If a checkpoint's `redo` points
   back to an LSN with a non-`XLOG_CHECKPOINT_REDO` record, FATAL
   ereport. [verified-by-code] `xlogrecovery.c:1674-1678`.

8. **Promotion is signal-driven.** `StartupRequestWalReceiverRestart`
   (`xlogrecovery.c:4384`), `PromoteIsTriggered` (`xlogrecovery.c:4403`)
   are the SIGUSR1/promote-file path.

## Functions of note

### `InitWalRecovery` — `xlogrecovery.c:457-983` [verified-by-code]

Inspects control file + presence of `standby.signal` / `recovery.signal`
/ `backup_label` / `tablespace_map` to choose the recovery mode. Reads
`postgresql.conf` recovery parameters via `validateRecoveryParameters`.
Sets up `xlogreader` and `xlogprefetcher`. Determines `RedoStartLSN`,
`CheckPointLoc`, `CheckPointTLI`, `wasShutdown` flags returned to
`StartupXLOG`.

### `PerformWalRecovery` — `xlogrecovery.c:1612` [verified-by-code]

The main redo loop. Snapshot of behavior:

1. Initialize `XLogRecoveryCtl` lastReplayed / replayEnd pointers
   (`xlogrecovery.c:1623-1641`).
2. Send `PMSIGNAL_RECOVERY_STARTED` to postmaster.
3. Open prefetcher at `RedoStartLSN` (or just-after `CheckPointLoc`).
4. If `RedoStartLSN < CheckPointLoc`, the record at `RedoStartLSN` must
   be `XLOG_CHECKPOINT_REDO`; FATAL otherwise.
5. `RmgrStartup()` — give every resource manager a chance to init.
6. **Inner loop:** `ReadRecord` → `ApplyWalRecord` → check stop
   conditions (`recoveryStopsBefore` / `recoveryStopsAfter`) → check
   pause → optional `recoveryApplyDelay`.
7. On exit, `RmgrCleanup()` (not in shown snippet but invariant).

### `ApplyWalRecord` — `xlogrecovery.c:1883` [verified-by-code]

Per-record dispatcher: sets ereport callback, advances nextXid,
handles `XLOG_CHECKPOINT_SHUTDOWN` / `XLOG_END_OF_RECOVERY` for TLI
switch detection, updates `replayEndRecPtr`, records KnownAssignedXids,
then either calls `xlogrecovery_redo` directly (for recovery-only
record types) or `RmgrTable[record->xl_rmid].rm_redo(xlogreader)`.

### `ReadRecord` — `xlogrecovery.c:3108-…` [verified-by-code]

Pulls the next record via the prefetcher; on missing WAL, calls
`WaitForWALToBecomeAvailable` to switch among archive, pg_wal, and
streaming sources.

### `WaitForWALToBecomeAvailable` — `xlogrecovery.c:3534` [verified-by-code]

The state machine cycling through `XLOG_FROM_ARCHIVE`,
`XLOG_FROM_PG_WAL`, `XLOG_FROM_STREAM`, with retry intervals
(`wal_retrieve_retry_interval`).

### `CheckRecoveryConsistency` — `xlogrecovery.c:2151` [verified-by-code]

Decides whether the database is consistent enough to open for read-only
hot-standby connections. Compares `replayEndRecPtr` against
`minRecoveryPoint` and `backupEndPoint`.

### `verifyBackupPageConsistency` — `xlogrecovery.c:2438` [verified-by-code]

When `wal_consistency_checking` is set for the record's rmgr, replays
the record into a copy of the original page, then compares against
the redo result, panic on mismatch. The masking is per-rmgr.

## Cross-references

- `xlog.c:StartupXLOG` is the only caller of `InitWalRecovery` and
  `PerformWalRecovery`.
- `xlogreader.c` decodes the records.
- `xlogprefetcher.c` wraps the reader with async block prefetch.
- `xlogutils.c:XLogReadBufferForRedo` is the helper redo handlers use
  to fetch the modified page; consistency-check feeds into it.
- `rmgrlist.h` defines the table of `rm_redo` callbacks dispatched here.
- `procarray.c:RecordKnownAssignedTransactionIds` is the standby-state
  feed.
- `xlogwait.c` — backends waiting for `replayEndRecPtr` to advance.

## Open questions

- The full set of XLOG_xxx subcases handled directly in
  `xlogrecovery_redo` vs. via `xlog_redo` (rmgr) not fully enumerated
  here. [unverified]
- `recoveryStopsBefore` / `recoveryStopsAfter` evaluate the full
  matrix of recovery-target options (xid / time / lsn / name / immediate);
  not deep-read. [unverified]
- `XLogPageRead`'s interaction with the prefetcher on partial-page
  reads + record straddling not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 32
- `[from-comment]`: 5
- `[unverified]`: 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
