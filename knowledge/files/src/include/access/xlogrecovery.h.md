# xlogrecovery.h

- **Source path:** `source/src/include/access/xlogrecovery.h`
- **Lines:** 232
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlogrecovery.c`, `catalog/pg_control.h`.

## Purpose

Public interface to `xlogrecovery.c`: recovery-target enums,
pause-state enum, `XLogRecoveryCtlData` shared-memory state,
`EndOfWalRecoveryInfo` return struct, and all phase entry/control
prototypes. [from-comment] `xlogrecovery.h:1-9`.

## Top-of-file comment (verbatim)

```
xlogrecovery.h

Functions for WAL recovery and standby mode
```
[verified-by-code] `xlogrecovery.h:1-4`.

## Public surface

### Enums (`xlogrecovery.h:22-61`) [verified-by-code]

- `RecoveryTargetType` — `UNSET`, `XID`, `TIME`, `NAME`, `LSN`,
  `IMMEDIATE`.
- `RecoveryTargetTimeLineGoal` — `CONTROLFILE`, `LATEST`, `NUMERIC`.
- `RecoveryTargetAction` — `PAUSE`, `PROMOTE`, `SHUTDOWN`.
- `RecoveryPauseState` — `NOT_PAUSED`, `PAUSE_REQUESTED`, `PAUSED`.

### `XLogRecoveryCtlData` (`xlogrecovery.h:66-124`) [verified-by-code]

Shared-memory recovery state, protected by `info_lck` (spinlock):
`SharedHotStandbyActive`, `SharedPromoteIsTriggered`,
`recoveryWakeupLatch`, `lastReplayedReadRecPtr` / `lastReplayedEndRecPtr` /
`lastReplayedTLI`, `replayEndRecPtr` / `replayEndTLI` (these
two reflect "currently replaying"), `recoveryLastXTime`,
`currentChunkStartTime`, `recoveryPauseState`, `recoveryNotPausedCV`.

### `EndOfWalRecoveryInfo` (`xlogrecovery.h:165-206`) [verified-by-code]

Output of `FinishWalRecovery`: `lastRec`/`lastRecTLI`,
`endOfLog`/`endOfLogTLI`, `lastPageBeginPtr`/`lastPage`,
`abortedRecPtr`/`missingContrecPtr`, `recoveryStopReason`,
`standby_signal_file_found`, `recovery_signal_file_found`.

### GUC externs (`xlogrecovery.h:129-149`) [verified-by-code]

`recoveryTargetInclusive`, `recoveryTargetAction`,
`recovery_min_apply_delay`, `PrimaryConnInfo`, `PrimarySlotName`,
`recoveryRestoreCommand`, `recoveryEndCommand`,
`archiveCleanupCommand`, `recoveryTargetXid`,
`recovery_target_time_string`, `recoveryTargetTime`,
`recoveryTargetName`, `recoveryTargetLSN`, `recoveryTarget`,
`wal_receiver_create_temp_slot`, `recoveryTargetTimeLineGoal`,
`recoveryTargetTLIRequested`, `recoveryTargetTLI`,
`reachedConsistency`, `StandbyMode`.

### Function prototypes (`xlogrecovery.h:156-230`) [verified-by-code]

`InitWalRecovery`, `PerformWalRecovery`, `FinishWalRecovery`,
`ShutdownWalRecovery`, `RemovePromoteSignalFiles`,
`HotStandbyActive`, `GetXLogReplayRecPtr`, `GetRecoveryPauseState`,
`SetRecoveryPause`, `GetXLogReceiptTime`, `GetLatestXTime`,
`GetCurrentChunkReplayStartTime`, `GetCurrentReplayRecPtr`,
`PromoteIsTriggered`, `CheckPromoteSignal`, `WakeupRecovery`,
`StartupRequestWalReceiverRestart`, `XLogRequestWalReceiverReply`,
`RecoveryRequiresIntParameter`, `xlog_outdesc`.

## Key invariants and locking

1. **`info_lck` is a spinlock** protecting all `XLogRecoveryCtl`
   shared fields. [from-comment] `xlogrecovery.h:123`.

2. **`recoveryWakeupLatch` and `procLatch` are distinct.**
   Comment at `xlogrecovery.h:80-94` explains why: the startup
   process waits for two different things (WAL arrival vs. recovery
   conflict) and they shouldn't multiplex on one latch.
   [from-comment]

3. **`replayEndRecPtr` vs `lastReplayedEndRecPtr`.** During redo,
   `replayEndRecPtr` is the end of the record being applied; once
   the redo function returns, both equal each other.
   [from-comment] `xlogrecovery.h:104-108`.

## Cross-references

- `xlogrecovery.c` implements all the prototypes.
- `xlog.c:StartupXLOG` calls `InitWalRecovery` / `PerformWalRecovery` /
  `FinishWalRecovery` in sequence.
- `xlogwait.c` waits on `lastReplayedEndRecPtr`.
- `replication/walreceiver.c` uses `PromoteIsTriggered`,
  `WakeupRecovery`, `StartupRequestWalReceiverRestart`.

## Open questions

None significant.

## Confidence tag tally

- `[verified-by-code]`: 11
- `[from-comment]`: 4
