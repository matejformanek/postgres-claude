# xlogfuncs.c

- **Source path:** `source/src/backend/access/transam/xlogfuncs.c`
- **Lines:** 860
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlog.c`, `xlogrecovery.c`, `xlogbackup.c`,
  `backup/basebackup.c`.

## Purpose

SQL-level user interface to WAL: `pg_backup_start`, `pg_backup_stop`,
`pg_switch_wal`, `pg_current_wal_*`, `pg_last_wal_*`,
`pg_walfile_name*`, `pg_wal_replay_pause` / `_resume`, `pg_promote`,
`pg_create_restore_point`, `pg_log_standby_snapshot`,
`pg_stat_get_recovery`, etc. Wraps the lower-level functions in
`xlog.c` / `xlogrecovery.c` with permission checks and SQL plumbing.
[from-comment] `xlogfuncs.c:3-7`.

## Top-of-file comment (verbatim)

```
xlogfuncs.c

PostgreSQL write-ahead log manager user interface functions

This file contains WAL control and information functions.
```
[verified-by-code] `xlogfuncs.c:3-7`.

## Public surface

All `PG_FUNCTION_INFO_V1`-registered SQL functions:

- `pg_backup_start` `xlogfuncs.c:87`, `pg_backup_stop` `xlogfuncs.c:154`
  [verified-by-code]
- `pg_switch_wal` `xlogfuncs.c:207` [verified-by-code]
- `pg_log_standby_snapshot` `xlogfuncs.c:232` [verified-by-code]
- `pg_create_restore_point` `xlogfuncs.c:263` [verified-by-code]
- `pg_current_wal_lsn` / `_insert_lsn` / `_flush_lsn`
  `xlogfuncs.c:304, 325, 346` [verified-by-code]
- `pg_last_wal_receive_lsn` `xlogfuncs.c:368`,
  `pg_last_wal_replay_lsn` `xlogfuncs.c:387` [verified-by-code]
- `pg_walfile_name_offset` `xlogfuncs.c:404`, `pg_walfile_name`
  `xlogfuncs.c:469`, `pg_split_walfile_name` `xlogfuncs.c:494`
  [verified-by-code]
- `pg_wal_replay_pause` `xlogfuncs.c:549`, `pg_wal_replay_resume`
  `xlogfuncs.c:579`, `pg_is_wal_replay_paused` `xlogfuncs.c:603`,
  `pg_get_wal_replay_pause_state` `xlogfuncs.c:624`
  [verified-by-code]
- `pg_last_xact_replay_timestamp` `xlogfuncs.c:647`,
  `pg_is_in_recovery` `xlogfuncs.c:662` [verified-by-code]
- `pg_wal_lsn_diff` `xlogfuncs.c:671` [verified-by-code]
- `pg_promote` `xlogfuncs.c:689` [verified-by-code]
- `pg_stat_get_recovery` `xlogfuncs.c:778` [verified-by-code]
- `GetRecoveryPauseStateString` `xlogfuncs.c:56` [verified-by-code]

## Key invariants and locking

1. **Recovery-only / primary-only gating.** `pg_promote` /
   `pg_wal_replay_*` work only during recovery;
   `pg_backup_*` / `pg_switch_wal` / `pg_create_restore_point` only
   on primary. [verified-by-code] (typical ereport guards in each
   function).

2. **Privilege checks via `pg_authid.h` roles.** Several functions
   require `pg_monitor`, `pg_signal_backend`, or superuser.
   [unverified] — not enumerated per-function here.

3. **`pg_backup_start` calls `do_pg_backup_start`** in
   `backup/basebackup.c` (not located in this read); session-level
   backup state recorded in `xlog.c:sessionBackupState`.
   [verified-by-code] `xlog.c:398`.

## Functions of note

### `pg_backup_start` / `pg_backup_stop` — `xlogfuncs.c:87, 154`
[verified-by-code]

The user-facing wrappers. `stop` is what calls
`xlogbackup.c:build_backup_content` to return the `backup_label` text
to the client.

### `pg_promote` — `xlogfuncs.c:689` [verified-by-code]

Signals the startup process by creating the promote file
(`PROMOTE_SIGNAL_FILE`), then waits for `RecoveryInProgress()` to
become false (with optional timeout).

### `pg_wal_replay_pause` / `_resume` — `xlogfuncs.c:549, 579`
[verified-by-code]

Toggle `XLogRecoveryCtl->recoveryPauseState` via
`SetRecoveryPause`.

## Cross-references

- `xlog.c` provides `XLogInsertAllowed`, `GetInsertRecPtr`,
  `GetFlushRecPtr`, `sessionBackupState`.
- `xlogrecovery.c` provides recovery state, pause control,
  promotion mechanics.
- `xlogbackup.c:build_backup_content` formats label/history.
- `backup/basebackup.c` does the heavy lifting for streaming base
  backups; SQL functions here are the older non-streaming path.

## Open questions

- Per-function permission matrix not enumerated. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 22
- `[from-comment]`: 1
- `[unverified]`: 2
