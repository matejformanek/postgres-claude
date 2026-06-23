# `storage/ipc/standby.c`

- **Source:** `source/src/backend/storage/ipc/standby.c` (1528 lines)
- **Header:** `source/src/include/storage/standby.h`,
  `source/src/include/storage/standbydefs.h`
- **Last verified commit:** `031904048aa2` (re-pinned 2026-06-23)
- **Depth:** read

## Purpose

Functions used in **Hot Standby mode** — specifically, everything
keyed off the `RM_STANDBY_ID` resource manager:
- Replaying AccessExclusiveLocks from the primary (so standby queries
  don't see uncommitted DDL).
- Replaying RunningXacts snapshots (so KnownAssignedXids gets
  initialized).
- **Recovery conflict resolution** — when WAL replay would invalidate
  data a standby query is using.

[from-comment] `standby.c:3-9`.

## Tunables

- `max_standby_archive_delay = 30 * 1000` (ms) — how long replay
  waits before killing conflicting queries when reading from archive.
- `max_standby_streaming_delay = 30 * 1000` (ms) — same, when
  streaming.
- `log_recovery_conflict_waits` (default off) — log waits ≥
  `deadlock_timeout`.

## Recovery conflict reasons

`RecoveryConflictReason` enum (in `procsignal.h`):
- `PROCSIG_RECOVERY_CONFLICT_SNAPSHOT` — vacuum is about to remove
  rows still visible to a standby snapshot.
- `PROCSIG_RECOVERY_CONFLICT_TABLESPACE` — DROP TABLESPACE on primary.
- `PROCSIG_RECOVERY_CONFLICT_LOCK` — primary held AccessExclusiveLock
  on a relation the standby query needs.
- `PROCSIG_RECOVERY_CONFLICT_BUFFERPIN` — replay needs an exclusive
  buffer lock that's pinned by a standby query.
- `PROCSIG_RECOVERY_CONFLICT_DATABASE` — DROP DATABASE.
- `PROCSIG_RECOVERY_CONFLICT_STARTUP_DEADLOCK` — the startup process
  is itself blocked.
- `PROCSIG_RECOVERY_CONFLICT_LOGICALSLOT` — invalidated logical slot.

## Resolution flow

`ResolveRecoveryConflictWithVirtualXIDs` (the central routine):
1. Sleep up to `max_standby_streaming_delay` (or `_archive_delay`).
2. While conflict still present: `SignalRecoveryConflict(proc, …)`
   one waiter at a time via procsignal.
3. The conflicting backend's interrupt handler decides whether the
   query can be aborted (some sleeps in WAL, snapshot, etc. cannot be).
4. Eventually times out → kill the laggard (`SIGTERM`).

The standby-deadlock timer (`got_standby_deadlock_timeout`) fires
after `deadlock_timeout` ms and triggers the
`PROCSIG_RECOVERY_CONFLICT_STARTUP_DEADLOCK` path, which kills the
backend holding the buffer pin the startup process needs.

## AccessExclusiveLock replay

The primary WAL-logs `xl_standby_lock` records every time someone
acquires AccessExclusiveLock on a relation. On the standby:
1. `StandbyAcquireAccessExclusiveLock` (`:988`) first creates the
   `RecoveryLockXidHash` entry (keyed by xid) and the `RecoveryLockHash`
   entry (keyed by `xl_standby_lock` = xid/dbOid/relOid) via
   `HASH_ENTER`, and **only `if (!found)`** does it call
   `LockAcquire(&locktag, AccessExclusiveLock, true /*sessionLock*/,
   false /*dontWait*/)` and then link the new lockentry into the xid's
   chain (`:1008-1029`). The lock is acquired in the actual heavyweight
   lock table by a dummy PGPROC representing the primary's transaction.
2. On the primary's commit/abort record, `StandbyReleaseLockTree`
   walks the xid's chain and releases all of them.

This is **the only place** the lock table is fed by something other
than a backend taking its own lock — recovery uses a dummy PGPROC.
`[from-comment]` `:45-53`.

**OOM-resilience (b85f9c00fb88, in this anchor batch).** The function
now creates both hash entries *before* acquiring the heavyweight lock
and uses the ordinary throwing `LockAcquire` (which is
`LockAcquireExtended(..., reportMemoryError=true, ...)`), **not** the
old `reportMemoryError=false` form. Because the entries exist and the
`lockentry` is linked into the xid chain only after the lock succeeds,
an OOM thrown by `LockAcquire` leaves consistent state that a retry can
recover, rather than silently swallowing the error mid-replay.
[verified-by-code, `:1008-1029` @ `031904048aa2`]

## RunningXacts snapshot

`xl_running_xacts` records are emitted by the primary periodically
(`bgwriter.c::LogStandbySnapshot`). On the standby, they call
`ProcArrayApplyRecoveryInfo` in `procarray.c` to rebuild
`KnownAssignedXids`. On the *primary* side, `LogCurrentRunningXacts`
(`:79`) gathers data via `GetRunningTransactionData` and writes the
record.

## Cross-references

- `procarray.c` — `KnownAssignedXids*`, `SignalRecoveryConflict*`,
  `GetRunningTransactionData`.
- `access/transam/xlogrecovery.c` — feeds standby records here.
- `replication/walreceiver.c` — receives the WAL.
- `lmgr.c` — `LockAcquire` ultimately for the dummy-PGPROC locks
  (the ordinary throwing form, `reportMemoryError=true`, since
  b85f9c00fb88 — see OOM-resilience note above).

## Open questions

1. **Lock-bucket exhaustion during replay**: a long-running
   primary-side DDL frenzy could in theory overflow the lock table on
   the standby. Not explicitly handled here. `[unverified]`.
2. **`max_standby_streaming_delay` measurement** — is it from "WAL
   record was received" or "replay started"? Not chased.
   `[unverified]`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
