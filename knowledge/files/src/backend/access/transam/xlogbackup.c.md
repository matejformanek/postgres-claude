# xlogbackup.c

- **Source path:** `source/src/backend/access/transam/xlogbackup.c`
- **Lines:** 92
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogbackup.h`,
  `backup/basebackup.c`, `xlog.c` (`pg_backup_start` /
  `pg_backup_stop` in `xlogfuncs.c`).

## Purpose

Builds the text contents for `backup_label` and `<...>.backup` history
files emitted at `pg_backup_stop` time. Pure formatting helpers; no
state. [from-comment] `xlogbackup.c:3-4`.

## Top-of-file comment (verbatim)

```
xlogbackup.c
    Internal routines for base backups.
```
[verified-by-code] `xlogbackup.c:3-4`.

## Public surface

- `build_backup_content(BackupState *state, bool ishistoryfile)` —
  `xlogbackup.c:29` [verified-by-code]

## Key types

- `BackupState` (declared in `xlogbackup.h`) — captures
  `BackupStartLSN`, `BackupEndLSN`, `StartTimeLine`, start/stop
  timestamps, `BackupTimeline`, `BackupLabel`, `BackupMethod`,
  `IncrementalBackup` info. Consumed by base backup machinery.

## Key invariants and locking

1. **No locks here.** Pure formatting given a populated
   `BackupState`.

## Functions of note

### `build_backup_content` — `xlogbackup.c:29` [verified-by-code]

Builds a `StringInfo` with the lines `START WAL LOCATION`,
`CHECKPOINT LOCATION`, `BACKUP METHOD`, `BACKUP FROM`,
`START TIME`, `LABEL`, `START TIMELINE`, plus (history file only)
`STOP WAL LOCATION`, `STOP TIME`, `STOP TIMELINE`. The exact key
strings are read by `xlogrecovery.c:read_backup_label` /
`xlogarchive` consumers.

## Cross-references

- `backup/basebackup.c` calls this to produce the label and history
  contents.
- `xlogfuncs.c:pg_backup_stop` returns the label content.
- `xlogrecovery.c:read_backup_label` parses the format produced
  here.

## Open questions

None.

## Confidence tag tally

- `[verified-by-code]`: 3
- `[from-comment]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
