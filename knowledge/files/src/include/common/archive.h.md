---
path: src/include/common/archive.h
anchor_sha: 4b0bf0788b0
loc: 21
depth: skim
---

# archive.h

- **Source path:** `source/src/include/common/archive.h`
- **Lines:** 21
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/archive.c`.

## Purpose

Single-function API for substituting `%p`/`%f`/`%r` placeholders in the `restore_command` GUC. Used by both backend (recovery WAL restore) and `pg_rewind`/`pg_archivecleanup`. [verified-by-code, archive.h:13-19]

## Public surface

- `BuildRestoreCommand(restoreCommand, xlogpath, xlogfname, lastRestartPointFname)` — palloc'd substituted command string. [verified-by-code, archive.h:16-19]

## Phase D notes

- This is the GUC → shell-command boundary. See `archive.c.md` ISSUE entries.

## Confidence tag tally
`[verified-by-code]=2`
