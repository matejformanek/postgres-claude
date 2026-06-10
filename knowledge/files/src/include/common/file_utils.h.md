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

## Issues

[ISSUE-trust-boundary: `durable_rename(oldfile, newfile)`
(`file_utils.h:41`) is the canonical "atomic update" helper, but the
header gives no warning that it does NOT use `O_NOFOLLOW` — A5 +
A6 finding: pg_rewind's `file_ops.c` uses this on attacker-influenced
paths in the target data directory, opening a TOCTOU symlink window
(high)] Cross-link: A14 `basic_archive` uses the same helper for
its archive-staging echo.

[ISSUE-trust-boundary: `get_dirent_type(path, *de, look_through_symlinks, elevel)`
(`file_utils.h:45-48`) has a `look_through_symlinks` flag whose
default semantics depend on the caller. The header offers no
guidance about when symlink-following is safe vs. when it enables
attacker-controlled redirection (medium)] A6 echo —
pg_rewind/pg_upgrade walk attacker-influenced trees.

[ISSUE-undocumented-invariant: `sync_pgdata` /
`sync_dir_recurse` (`file_utils.h:38-40`) recurse over the entire
data directory; depth/cycle handling is comment-only (low)]
Symlink loops in `pg_tblspc/` would loop indefinitely without
explicit cycle detection — implementation detail lives in .c.

[ISSUE-trust-boundary: `pg_pwrite_zeros` (`file_utils.h:60`) is
the zero-fill helper; A5 hosting site cluster for "torn write
mitigation" pattern echoes back to controldata_utils.h (low)]

## Cross-refs

- A5 `common.md` — durable_rename TOCTOU; pwrite_zeros.
- A6 `pg_rewind` + `pg_upgrade` — primary consumers.
- A14 `basic_archive` — durable_rename echo.
- Companion: `src/common/file_utils.c.md`.

## Confidence tag tally
`[verified-by-code]=4`
