# contrib/basic_archive/basic_archive.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 298
**Verification depth:** full read

## Role

Reference / demo implementation of an `archive_library` (PG ≥ 15 archive-module
API): copies each WAL segment from `pg_wal/` to a configured
`archive_directory` via "test ! -f dest && cp src dest" semantics, but using
a `temp + fsync + durable_rename` pattern instead of raw `cp`, and with a
content-equality short-circuit when `dest` already exists.
[verified-by-code] `source/contrib/basic_archive/basic_archive.c:1-26`

## Public API

- `_PG_init()` — defines GUC `basic_archive.archive_directory` (PGC_SIGHUP,
  string) and marks `basic_archive.*` as reserved.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:64-77`
- `_PG_archive_module_init()` — returns the `ArchiveModuleCallbacks` table
  (`startup_cb=NULL`, `check_configured_cb=basic_archive_configured`,
  `archive_file_cb=basic_archive_file`, `shutdown_cb=NULL`).
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:52-58, 84-88`
- `basic_archive_file(state, file, path)` — the work routine; `file` is the
  WAL filename, `path` the absolute source path.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:140-217`

## Invariants

- INV-1: `archive_directory + '/' + file` must fit in `MAXPGPATH`; the
  GUC-check rejects values where `len(dir) + 64 + 2 >= MAXPGPATH`.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:95-117`
- INV-2: A pre-existing destination with identical contents is treated as
  success (after `fsync_fname` of file and directory) — this preserves
  archive completeness if the server crashed AFTER the rename but BEFORE
  the `.ready→.done` flag was persisted.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:154-180`
- INV-3: A pre-existing destination with DIFFERENT contents is an ERROR —
  the module deliberately refuses to overwrite.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:178-180`
- INV-4: Temp filename embeds `MyProcPid + millisecond-epoch` to make
  cross-process collisions in the same archive directory improbable.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:186-198`
- INV-5: Final move uses `durable_rename(temp, destination, ERROR)` — fsyncs
  both source FD and destination directory across the rename.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:206-211`

## Notable internals

- `compare_files` reads in 4 KiB chunks; uses `OpenTransientFile` (auto-cleanup
  on error), `read()` with short-read loops, and `memcmp`. Returns true iff
  both files reach EOF with identical content.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:223-298`
- Millisecond-epoch generation uses `pg_mul_u64_overflow` and
  `pg_add_u64_overflow` to defend against `tv_sec * 1000` overflowing.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:192-195`
- `copy_file(path, temp)` (from `storage/copydir.h`) does the heavy lifting
  including fsync of the temp file inside copy_file.
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:200-204`

## Trust-boundary / Phase-D surface

- **archive_directory** is a string GUC at `PGC_SIGHUP` — superuser/DBA-only.
  Not attacker-controllable from a regular session. The GUC check only
  validates length, not that the path is safe (no traversal/symlink check).
  **ISSUE-D1 (info)**: an operator who sets `archive_directory=/tmp` is
  letting WAL segments land where any local user can read them. Documented
  in user docs, not enforced in code. By design.
- **`file` parameter** comes from the archiver process and is a WAL filename
  (24 hex chars or `*.history`), not attacker-controlled.
- **`path` parameter** is also internally generated (`pg_wal/<file>`), not
  attacker-controlled.
- **TOCTOU between `stat` and `durable_rename`** (line 164 vs line 211):
  if another process creates `destination` between those two calls, the
  rename will silently overwrite it. Code comments acknowledge this:
  "this will overwrite any existing file, but this is only possible if
  someone else created the file since the stat() above"
  [verified-by-code] `source/contrib/basic_archive/basic_archive.c:207-211`.
  **ISSUE-D2 (low)**: in multi-archiver-to-same-dir setups (e.g., two
  primaries somehow targeting one share), this can silently swap
  one node's WAL segment for another. Documented elsewhere; not a
  defect in `basic_archive` itself.
- **Errors are loud, not swallowed** — every failure path uses `ereport(ERROR)`
  which the archiver treats as "try again later". No silent data loss.
  [verified-by-code] multiple sites at lines 178, 182, 195, 236, 256, 269, 288.

## Cross-refs

- `source/src/backend/archive/` (archive module API + archiver process).
- `source/src/common/file_utils.c` — `durable_rename`, `fsync_fname`.
- A8 (archive_command) — the operator-supplied shell parallel.
- A11 `basebackup_to_shell` — the sibling-but-trusted shell-out module.

## Issues raised

- **ISSUE-D1 (info)** — `archive_directory` GUC check is length-only, not
  path-safety. By design; operator's responsibility.
- **ISSUE-D2 (low)** — TOCTOU between `stat` and `durable_rename` allows
  silent overwrite if another writer beats us; acknowledged in comment.
