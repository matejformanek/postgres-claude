# xlogbackup.h

- **Source path:** `source/src/include/access/xlogbackup.h`
- **Lines:** 43
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlogbackup.c`, `backup/basebackup.c`.

## Purpose

The `BackupState` struct used to thread base-backup metadata through
`pg_backup_start` / `pg_backup_stop` and the streaming-backup code.
[from-comment] `xlogbackup.h:3-4`.

## Top-of-file comment (verbatim)

```
xlogbackup.h
   Definitions for internals of base backups.
```
[verified-by-code] `xlogbackup.h:3-4`.

## Key types

### `BackupState` (`xlogbackup.h:21-38`) [verified-by-code]

Start fields:
- `char name[MAXPGPATH + 1]`
- `XLogRecPtr startpoint`, `TimeLineID starttli`
- `XLogRecPtr checkpointloc`
- `pg_time_t starttime`
- `bool started_in_recovery`
- `XLogRecPtr istartpoint`, `TimeLineID istarttli` (incremental backup base)

Stop fields:
- `XLogRecPtr stoppoint`, `TimeLineID stoptli`, `pg_time_t stoptime`.

## Public surface

- `build_backup_content(BackupState *state, bool ishistoryfile)` —
  returns a heap-allocated `char *` with the `backup_label` or
  `<...>.backup` history content. [verified-by-code] `xlogbackup.h:40`.

## Cross-references

- `xlogbackup.c` implements `build_backup_content`.
- `xlogfuncs.c:pg_backup_start/stop` and `backup/basebackup.c` are the
  primary users.

## Confidence tag tally

- `[verified-by-code]`: 4
- `[from-comment]`: 1
