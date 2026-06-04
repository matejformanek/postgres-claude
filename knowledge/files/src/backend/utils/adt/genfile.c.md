# src/backend/utils/adt/genfile.c

## Purpose

The `pg_read_file` / `pg_read_binary_file` / `pg_stat_file` / `pg_ls_dir`
family — raw filesystem access exposed as SQL functions, plus per-directory
helpers (`pg_ls_logdir`, `pg_ls_waldir`, `pg_ls_tmpdir`,
`pg_ls_archive_statusdir`, `pg_ls_summariesdir`, `pg_ls_logicalsnapdir`,
`pg_ls_logicalmapdir`, `pg_ls_replslotdir`). These are the functions
`pg_rewind --source-server` calls via libpq to read the source cluster's
WAL/control file/data files.

## Role in PG

- Backend-only, no `_PG_init` — declared directly in `pg_proc.dat`.
- The privilege model is a **two-tier hybrid**:
  1. `pg_read_server_files` predefined role membership → can read **any
     path on the server**, full stop (`genfile.c:65-67`).
  2. Non-member callers go through `convert_and_check_filename` which
     restricts to paths under `DataDir`, paths under `Log_directory`
     (which may be outside `DataDir`), or relative paths "in or below
     the data directory" (`genfile.c:73-90`).
- Default ACL on the underlying SQL functions is `REVOKE EXECUTE FROM
  PUBLIC` — you must be either a member of `pg_read_server_files` *or*
  granted execute on the function by a superuser. So a fresh role sees
  **nothing**.

## Key functions

Filename gate (CRITICAL):
- `convert_and_check_filename(text *arg) → char *` (`genfile.c:53-92`).
  1. `text_to_cstring(arg)` → cstring.
  2. `canonicalize_path(filename)` — collapses `./`, `../`, etc.
     (modifies in place, may change length).
  3. If `has_privs_of_role(GetUserId(), ROLE_PG_READ_SERVER_FILES)` →
     return the canonicalized path unchanged. **No further validation.**
  4. Else if `is_absolute_path(filename)`:
     - allowed iff `path_is_prefix_of_path(DataDir, filename)` OR
       (`Log_directory` is absolute AND
       `path_is_prefix_of_path(Log_directory, filename)`).
     - otherwise `ERRCODE_INSUFFICIENT_PRIVILEGE` "absolute path not
       allowed".
  5. Else (relative) require `path_is_relative_and_below_cwd(filename)`,
     i.e. doesn't escape pgdata. Otherwise `ERRCODE_INSUFFICIENT_PRIVILEGE`
     "path must be in or below the data directory".

Bulk reader:
- `read_binary_file(filename, seek_offset, bytes_to_read, missing_ok)`
  (`genfile.c:102-204`). Clamps `bytes_to_read` to
  `MaxAllocSize - VARHDRSZ`; opens via `AllocateFile`; `fseeko` with
  `SEEK_SET` for non-negative offset or `SEEK_END` otherwise (so
  negative `seek_offset` reads from end of file). For
  `bytes_to_read < 0` reads to EOF via incremental `StringInfo`
  enlarge, capping at `MaxAllocSize - 1` with the "file length too
  large" error (`genfile.c:164-174`).
- `read_text_file` (`genfile.c:210-228`) wraps the binary reader with
  `pg_verifymbstr` so the returned `text` is valid in the database
  encoding.
- `pg_read_file_common` / `pg_read_binary_file_common` (`:239-273`) —
  arg-validation wrappers that reject negative `bytes_to_read` when not
  reading to EOF.

SQL entry points (each just an `convert_and_check_filename` + reader
call):
- `pg_read_file_off_len`, `pg_read_file_off_len_missing`,
  `pg_read_file_all`, `pg_read_file_all_missing` — text variants
  (`:285-345`).
- `pg_read_binary_file_*` — bytea variants (`:348-407`).
- `pg_stat_file` / `pg_stat_file_1arg` (`:413-493`) — returns
  `(size, access, modification, change, creation, isdir)` via `stat(2)`.
- `pg_ls_dir(path[, missing_ok, include_dot_dirs])` (`:499-549`) —
  basic directory listing (filenames only).

Per-directory wrappers (each calls the static `pg_ls_dir_files` that
emits `(name, size, mtime)` tuples and skips dotfiles + non-regular):
- `pg_ls_logdir()` (`:634-637`) — `Log_directory`, missing_ok=false.
- `pg_ls_waldir()` (`:641-644`) — `XLOGDIR` (`pg_wal`).
- `pg_ls_tmpdir_noargs` / `pg_ls_tmpdir_1arg(tblspc)` (`:649-682`) —
  pgsql_tmp under default or given tablespace; `missing_ok=true`.
- `pg_ls_archive_statusdir()` (`:688-691`) — `pg_wal/archive_status`,
  missing_ok=true.
- `pg_ls_summariesdir()` (`:697-700`) — `pg_wal/summaries`, missing_ok=true.
- `pg_ls_logicalsnapdir()` / `pg_ls_logicalmapdir()` (`:707-720`).
- `pg_ls_replslotdir(slotname)` (`:727-746`) — validates slot exists
  via `SearchNamedReplicationSlot`, missing_ok=false.

## State / globals

None local. Reads `DataDir`, `Log_directory` (GUCs).

## Phase D notes — CRITICAL

This is the **answer to the orchestrator's question 4**: what gates
`pg_read_file` / `pg_read_binary_file` server-side?

- **Two layers**:
  1. SQL-level: default ACL revokes execute from PUBLIC, so the
     function is unreachable unless explicitly granted. The
     conventional grant target is the `pg_read_server_files`
     predefined role.
  2. C-level: `convert_and_check_filename` (`genfile.c:53-92`).

- **`pg_read_server_files` is the universal bypass**: any role with
  that role's privileges can read **any path on the server**, no
  further validation. This is the role pg_rewind needs.
  Equivalent to filesystem-level superuser within the postmaster's
  process scope.

- **Path validation for non-`pg_read_server_files` callers**:
  - `canonicalize_path` collapses `..` and `.` segments first — so
    `/etc/passwd` and `/var/lib/pgdata/../../etc/passwd` end up as the
    canonical `/etc/passwd` and `/etc/passwd` respectively, and the
    absolute-path check rejects both. Good.
  - Allowed: absolute paths under `DataDir` or `Log_directory`, OR
    relative paths that don't escape pgdata (per
    `path_is_relative_and_below_cwd`).
  - `Log_directory` allowance is **deliberately permissive** —
    server-log directory may be outside pgdata (e.g. `/var/log/postgresql`),
    so the check explicitly accepts it. A non-superuser granted EXECUTE
    on `pg_read_file()` can therefore read server logs by path.

- **Symlink following**: `AllocateFile` → `fopen(3)` follows symlinks
  by default. So if `Log_directory` or `DataDir` contains a symlink
  pointing outside, a non-server-files-role caller can transit it.
  No `O_NOFOLLOW` or `realpath` enforcement here. [verified-by-code]

- **`pg_stat_file` and `pg_ls_dir` use the same gate** —
  identical to read functions, so directory enumeration follows the
  same rules.

- **Hidden-file filter in `pg_ls_dir_files`** (`genfile.c:601`):
  per-directory wrappers skip names starting with `.`. The raw
  `pg_ls_dir(path, …, include_dot_dirs=true)` does NOT skip dotfiles;
  it just optionally also surfaces `.` and `..`.

- **`pg_ls_tmpdir`**: tablespace OID is user-supplied; validated via
  `SearchSysCacheExists1(TABLESPACEOID, …)` (`genfile.c:653-658`).
  But the resulting `TempTablespacePath` directory inside the
  tablespace is one the caller may not normally see — info disclosure
  of temp file names + sizes for *any* tablespace. The grant on
  `pg_ls_tmpdir` defaults to `pg_monitor` role.

## Potential issues

- [ISSUE-trust-boundary: `pg_read_server_files` is total bypass —
  membership equals "read any file the postgres uid can read",
  including `/etc/passwd`, SSH keys, etc. Documented + intentional,
  but worth flagging that "give pg_rewind a role" hands out FS-read
  superuser (HIGH by design)]
- [ISSUE-path-traversal: no `realpath(3)` / `O_NOFOLLOW` —
  symlinks under `DataDir` or `Log_directory` transit out
  transparently for non-pg_read_server_files callers. If an
  attacker can plant a symlink under either dir, they exfiltrate
  arbitrary files (maybe — requires symlink planting, but the data
  dir is owned by postgres uid so this is mostly a defence-in-depth
  gap) ]
- [ISSUE-info-disclosure: `Log_directory` allowance lets non-superusers
  with grant read server logs containing query text, auth attempts,
  etc. (low — by design)]
- [ISSUE-info-disclosure: `pg_ls_tmpdir(oid)` exposes temp file
  enumeration across tablespaces; grant default is `pg_monitor` (low)]
- [ISSUE-dos: unbounded read to EOF clamps at
  `MaxAllocSize-1 = 1 GiB - 1`; a caller can hold that allocation
  per backend. Plus the seek-from-end branch with `seek_offset < 0`
  lets a caller read arbitrary positions cheaply. No total-read-rate
  limit (low)]
- [ISSUE-correctness: `canonicalize_path` is called before the absolute-path
  test; for very long paths or unusual encodings the canonical form
  may differ from what an admin expected when granting access. Edge
  cases worth a fuzz pass (maybe)]
