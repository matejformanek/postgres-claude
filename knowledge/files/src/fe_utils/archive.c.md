# `src/fe_utils/archive.c`

- **File:** `source/src/fe_utils/archive.c` (108 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

A single helper, `RestoreArchivedFile`, that runs a user-supplied
`restore_command` to fetch a WAL segment (or other fixed-size file) from offline
archival storage and returns an open read-only fd on success. It is the frontend
twin of the backend's archive-restore logic, used by `pg_rewind` and
`pg_combinebackup` to pull missing WAL out of an archive. The actual command
string is built by the shared `BuildRestoreCommand` (in `src/common/archive.c`),
so the `%f`/`%p` substitution and shell-escaping live there, not here.
`[from-comment]` (archive.c:27-37) / `[verified-by-code]` (:49-50)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `RestoreArchivedFile` | :38 | Run `restore_command` for `xlogfname`; on success return an open fd (size-checked); else `-1` (or `pg_fatal` on signal/hard error). |

## Internal landmarks

- Path assembly `archive.c:47` — `snprintf` of `"%s/" XLOGDIR "/%s"` (path /
  `pg_wal` / segment name) into a `MAXPGPATH` buffer. `[verified-by-code]`
- Command build `archive.c:49-50` — delegates to `BuildRestoreCommand(restoreCommand,
  xlogpath, xlogfname, NULL)`; the `NULL` last arg means no `%r` (last-restartpoint)
  substitution. `[verified-by-code]`
- Execute `archive.c:56-58` — `fflush(NULL)` then `system(xlogRestoreCmd)`; result
  string `pfree`d. `[verified-by-code]`
- Success + size crosscheck `archive.c:60-82` — on `rc == 0`, `stat` the target;
  if `expectedSize > 0` and size mismatches → `pg_fatal`; else `open(O_RDONLY |
  PG_BINARY)` and return the fd (`pg_fatal` if that open fails). `[verified-by-code]`
- Missing-after-success `archive.c:83-88` — if `stat` fails with anything other
  than `ENOENT`, `pg_fatal`; `ENOENT` falls through to the "not available" path.
  `[verified-by-code]`
- Signal / hard-error handling `archive.c:91-99` — `wait_result_is_any_signal(rc,
  true)` → `pg_fatal("\"restore_command\" failed: ...")`. Comment notes "command
  not found" style hard shell errors are treated as fatal too. `[from-comment]`
  (:91-96)
- Soft miss `archive.c:101-107` — otherwise `pg_log_error` and return `-1`, letting
  the caller decide. `[verified-by-code]`

## Invariants & gotchas

- **No shell-escaping happens in this file.** The task framing flagged a
  "`shell_escape`-style helper" — in current source the escaping is entirely
  inside `BuildRestoreCommand` / `replace_percent_placeholders` in
  `src/common/archive.c`; `archive.c` only concatenates a path and calls it.
  Any quoting-safety concern lives in `common/archive.c`, not here. `[verified-by-code]`
- **`system()` runs the command via the shell.** `restore_command` is operator-
  supplied config, so this is by-design, not an injection of untrusted input;
  but it is a `system()` call site worth noting. `[inferred]`
- Memory: `xlogRestoreCmd` is `pfree`d (`:58`) — frontend builds of this file get
  `pfree`/`palloc` shims via `postgres_fe.h`. `[verified-by-code]`
- Return contract: `>= 0` fd on success (caller owns/closes it), `-1` on a benign
  "not in archive" miss, and **never returns** on size mismatch, signal death, or
  a post-success open failure (all `pg_fatal`). `[verified-by-code]`
- The `expectedSize == 0` case disables the size crosscheck for unknown-size
  files. `[from-comment]` (:34-36)

## Cross-references

- `source/src/common/archive.c` — `BuildRestoreCommand` (does `%f`/`%p`/`%r`
  substitution and shell-escaping). This is where the real escaping audit belongs.
- `source/src/include/fe_utils/archive.h` — prototype.
- `source/src/include/access/xlog_internal.h` — `XLOGDIR`.
- `source/src/port/wait_error.c` — `wait_result_is_any_signal`, `wait_result_to_str`.
- `source/src/backend/access/transam/xlogarchive.c` — backend analogue
  (`RestoreArchivedFile` for the startup process).

## Confidence tag tally

- `[verified-by-code]` × 8
- `[from-comment]` × 3
- `[inferred]` × 1
