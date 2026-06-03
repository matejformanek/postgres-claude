---
path: src/include/common/file_utils.h
anchor_sha: 4b0bf0788b0
loc: 66
depth: skim
---

# file_utils.h

- **Source path:** `source/src/include/common/file_utils.h`
- **Lines:** 66
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/file_utils.c`.

## Purpose

Frontend file-utility API: `pre_sync_fname` / `fsync_fname` / `sync_pgdata` / `sync_dir_recurse` / `durable_rename` / `fsync_parent_path`, plus the cross-platform `get_dirent_type` and `pg_pwritev_with_retry` / `pg_pwrite_zeros` helpers used by both frontend and backend. Also defines the `PGFileType` (REG/DIR/LNK/UNKNOWN/ERROR) and `DataDirSyncMethod` (FSYNC/SYNCFS) enums and the `pgsql_tmp` filename prefix. [verified-by-code, file_utils.h:18-65]

## Public surface

- Enums: `PGFileType`, `DataDirSyncMethod`. [verified-by-code, file_utils.h:18-31]
- Frontend-only (`#ifdef FRONTEND`): `pre_sync_fname`, `fsync_fname`, `sync_pgdata(pg_data, serverVersion, sync_method, sync_data_files)`, `sync_dir_recurse`, `durable_rename`, `fsync_parent_path`. [verified-by-code, file_utils.h:35-43]
- Both: `get_dirent_type(path, *de, look_through_symlinks, elevel)`, `compute_remaining_iovec`, `pg_pwritev_with_retry`, `pg_pwrite_zeros`. [verified-by-code, file_utils.h:45-60]
- `PG_TEMP_FILES_DIR "pgsql_tmp"` / `PG_TEMP_FILE_PREFIX "pgsql_tmp"`. [verified-by-code, file_utils.h:63-64]

## Phase D notes

- `pre_sync_fname`/`fsync_fname`/`sync_pgdata` are the bulk fsync surface PG depends on for durability. See `file_utils.c.md` for symlink/walk behavior.

## Confidence tag tally
`[verified-by-code]=4`
