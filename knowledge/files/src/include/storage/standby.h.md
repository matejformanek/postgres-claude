# `storage/standby.h`

- **Source:** `source/src/include/storage/standby.h` (150 lines)
- **Header companion:** `storage/standbydefs.h` (xl_standby_lock etc.)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Hot standby + recovery-conflict API. See `standby.c.md`.

## GUCs

- `max_standby_archive_delay = 30000 ms`
- `max_standby_streaming_delay = 30000 ms`
- `log_recovery_conflict_waits = false`

## RecoveryConflictReason

```
RECOVERY_CONFLICT_DATABASE
RECOVERY_CONFLICT_TABLESPACE
RECOVERY_CONFLICT_LOCK
RECOVERY_CONFLICT_SNAPSHOT
RECOVERY_CONFLICT_LOGICALSLOT
RECOVERY_CONFLICT_BUFFERPIN
RECOVERY_CONFLICT_STARTUP_DEADLOCK    /* startup is itself stuck */
RECOVERY_CONFLICT_BUFFERPIN_DEADLOCK
```

`NUM_RECOVERY_CONFLICT_REASONS = 8`.

**Note**: this is a *different* enum from `ProcSignalReason`. There's
only one `PROCSIG_RECOVERY_CONFLICT` bit at the procsignal level; the
specific reason is communicated via `PGPROC->pendingRecoveryConflicts`,
an array of these enum values. `[verified-by-code]
procsignal.h:41-43`.

## Conflict resolution API

`ResolveRecoveryConflictWith{Snapshot,Tablespace,Database,Lock,BufferPin}`
— the resolver functions called by the startup process to wait for /
kill conflicting backends.

`CheckRecoveryConflictDeadlock` — invoked from `CHECK_FOR_INTERRUPTS`
on the *blocking* backend to detect a deadlock with the startup
process.

## Standby Rmgr (RM_STANDBY_ID)

`StandbyAcquireAccessExclusiveLock(xid, dbOid, relOid)` — replay
side, install a recovery lock against a dummy PGPROC.
`StandbyReleaseLockTree(xid, nsubxids, subxids)` — release on
commit/abort replay.
`StandbyReleaseAllLocks()`, `StandbyReleaseOldLocks(oldxid)` —
recovery housekeeping.

## RunningTransactionsData

The structure passed by `GetRunningTransactionData` (read by the primary
when it WAL-logs the running-xacts snapshot, and consumed by
`ProcArrayApplyRecoveryInfo` on the standby to rebuild
`KnownAssignedXids`).

```c
{
  xcnt, subxcnt,
  subxid_status,    /* enum: IN_ARRAY / MISSING / IN_SUBTRANS */
  nextXid,
  oldestRunningXid,         /* NOT oldestXmin */
  oldestDatabaseRunningXid,
  latestCompletedXid,
  *xids                     /* xcnt+subxcnt items */
}
```

This is **distinct from a Snapshot** because it carries primary-side
state not interpretable as a visibility filter on this server.

## WAL writers (primary side)

- `LogAccessExclusiveLock(dbOid, relOid)` / `LogAccessExclusiveLockPrepare()`
  — at AccessExclusiveLock acquisition.
- `LogStandbySnapshot()` — at periodic intervals from `bgwriter.c`.
- `LogStandbyInvalidations(nmsgs, msgs, RelcacheInitFileInval)` —
  inval messages embedded in commit records.
