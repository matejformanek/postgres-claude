---
path: src/common/archive.c
anchor_sha: 4b0bf0788b0
loc: 60
depth: read
---

# archive.c

- **Source path:** `source/src/common/archive.c`
- **Lines:** 60
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/archive.h`, `common/percentrepl.c` (the actual substitution engine).

## Purpose

Build the concrete `restore_command` string to invoke for fetching an archived WAL segment, substituting `%p` (target xlog path, native form), `%f` (xlog filename), `%r` (last-restartpoint filename). Used by backend recovery and `pg_rewind`. [from-comment, archive.c:25-37]

## Role in PG

Frontend and backend. Backend caller is `src/backend/access/transam/xlogarchive.c:RestoreArchivedFile`; the per-segment shell-out happens inside the postmaster's startup path.

## Key function

- `BuildRestoreCommand(restoreCommand, xlogpath, xlogfname, lastRestartPointFname)` (38-60). Calls `make_native_path()` on a copy of `xlogpath` (Windows path-separator munging), then delegates to `replace_percent_placeholders(restoreCommand, "restore_command", "frp", xlogfname, lastRestartPointFname, nativePath)`. [verified-by-code, archive.c:38-60]

## State / globals

None.

## Phase D notes

- **Shell-injection at the GUC boundary.** `restore_command` is a server-admin-set GUC that runs through `system()` after substitution. `%p`/`%f`/`%r` values come from WAL/timeline state, not user input — but **a hostile filename in `archive_status/`** (e.g. via tablespace-rooted attack) could feed unusual bytes into `%p`. [inferred, archive.c:53-54] [ISSUE-trust-boundary: restore_command substitution does not shell-quote `%p`/`%f`/`%r`; caller relies on admin to write `"%p"` with quotes in their GUC value (maybe)] — note this matches the upstream documentation's standing advice to use `"%p"` (quoted).
- `make_native_path` only touches separators; it does not escape shell metacharacters. [verified-by-code, archive.c:49-51]
- `percentrepl.c` itself does not quote; substitution is literal. [inferred]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=3 [inferred]=2`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
