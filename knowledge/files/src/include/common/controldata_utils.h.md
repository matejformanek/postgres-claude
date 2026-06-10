---
path: src/include/common/controldata_utils.h
anchor_sha: 4b0bf0788b0
loc: 21
depth: skim
---

# controldata_utils.h

- **Source path:** `source/src/include/common/controldata_utils.h`
- **Lines:** 21
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/controldata_utils.c`.

## Purpose

Three-function API for reading/writing `pg_control` — PG's single cluster-state file. Used by every tool that needs to inspect or update controldata: `pg_controldata`, `pg_resetwal`, `pg_rewind`, `pg_upgrade`, plus the backend `XLogCtlInitialise` startup path. [verified-by-code, controldata_utils.h:15-19]

## Public surface

- `get_controlfile(DataDir, *crc_ok_p)` — palloc'd copy of `ControlFileData`; CRC validity reported via out-parameter. [verified-by-code, controldata_utils.h:15]
- `get_controlfile_by_exact_path(ControlFilePath, *crc_ok_p)` — same, but with explicit path. [verified-by-code, controldata_utils.h:16-17]
- `update_controlfile(DataDir, *ControlFile, do_sync)` — recompute CRC, write `PG_CONTROL_FILE_SIZE` zero-padded, optionally fsync. [verified-by-code, controldata_utils.h:18-19]

## Phase D notes

See `controldata_utils.c.md` — the partial-write window on update is the headline.

## Issues

[ISSUE-trust-boundary: `update_controlfile` (`controldata_utils.h:18-19`)
is the only declared write path to `pg_control` and the header gives
no atomicity contract; A5's `common.md` finding: the .c performs a
single 8 KiB `write()` with no shadow file → torn-write window if
the host crashes mid-write, leaving an unreadable cluster (high)]
The header pretends "one call, atomic update"; the implementation
is not.

[ISSUE-undocumented-invariant: `*crc_ok_p` out-param
(`controldata_utils.h:15-17`) — callers MUST check it before
trusting `ControlFileData`. The header gives no enforcement.
Multiple call sites in pg_upgrade/pg_rewind have historically
ignored it (low)] A6 +cross-link.

[ISSUE-trust-boundary: `get_controlfile_by_exact_path`
(`controldata_utils.h:16-17`) takes an arbitrary path — used by
pg_combinebackup against a backup tree whose `pg_control` may be
attacker-influenced. Header documents no path-traversal expectation
(low)]

## Cross-refs

- A5 `common.md` — pg_control torn-write window.
- A6 `pg_upgrade` + `pg_rewind` — primary consumers.
- Companion: `src/common/controldata_utils.c.md`.

## Confidence tag tally
`[verified-by-code]=4`
