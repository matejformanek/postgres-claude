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

## Confidence tag tally
`[verified-by-code]=4`
