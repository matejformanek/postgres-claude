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

## Issues

[ISSUE-undocumented-invariant: `BuildRestoreCommand`
(`archive.h:16-19`) returns a string fed straight to `system(3)` /
`OpenPipeStream` and the header carries no warning about shell
escaping; identical posture to `percentrepl.h` (high)] A5's
`common.md`: `%p`/`%f`/`%r` substitution is byte-level — a WAL
file name with shell metacharacters substitutes verbatim. The trust
model is "WAL filenames are controlled by PG, restoreCommand is
DBA-set", but neither contract is written in the header.

[ISSUE-trust-boundary: shared FE+BE — pg_rewind /
pg_archivecleanup invoke this with potentially less-trusted argv
(low)]

## Cross-refs

- A5 `common.md` — GUC-boundary shell injection.
- A8 `archive_command` — sibling.
- A14 `basebackup_to_shell` — same %-substitution pattern.
- Companion: `src/common/archive.c.md`, `src/common/percentrepl.h.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=2`
