---
path: src/common/exec.c
anchor_sha: 4b0bf0788b0
loc: 713
depth: read
---

# exec.c

- **Source path:** `source/src/common/exec.c`
- **Lines:** 713
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `port/path.c` (path-component helpers), `common/string.c` (`pg_strcasecmp`), `port/wait_error.c` (`wait_result_to_str`).

## Purpose

Resolve `argv[0]` to an absolute, canonical, symlink-followed path. Find sibling binaries under the same install tree (`find_other_exec`). Run a small command through a pipe (`pipe_read_line`) and check exit status (`pclose_check`). Wire up locale/service paths from the resolved binary (`set_pglocale_pgservice`). On `EXEC_BACKEND` Unix-test builds, also expose `pg_disable_aslr` for shared-memory-address determinism. On Windows, the Windows-specific helpers `AddUserToTokenDacl`/`GetTokenUser` live in the same file because they're used by `restricted_token.c`'s siblings. [from-comment, exec.c:1-15] [verified-by-code, exec.c:80-713]

## Role in PG

Frontend and backend (validate_exec / find_my_exec / find_other_exec / set_pglocale_pgservice). The backend's `PostmasterMain` calls `find_my_exec` to resolve `postgres`-binary path for re-fork. `find_other_exec` is how pg_ctl finds `postgres` from its own location, how `pg_upgrade` finds `pg_dump`, etc.

## Key functions

- `validate_exec(path)` (88-152, approx.) — `stat()`+`access()` checks; returns 0/-1/-2 depending on existence, executability, readability. Windows requires `.exe` suffix; the function appends one for the test if not present. [verified-by-code, exec.c:88-152]
- `find_my_exec(argv0, retpath)` (161-228) — three-step:
  1. If `argv0` contains a separator, `validate_exec(argv0)` then `normalize_exec_path`.
  2. Windows fallback: try cwd.
  3. Walk `$PATH` entries left-to-right with `first_path_var_separator`, `validate_exec` each. First hit wins. `normalize_exec_path` resolves symlinks via `realpath`. [verified-by-code, exec.c:161-228]
- `normalize_exec_path(path)` (241-266) — delegates to `pg_realpath` (`realpath(3)`); on macOS uses the `_DARWIN_BETTER_REALPATH` define for F_GETPATH semantics; on Windows uses `_fullpath`. [verified-by-code, exec.c:241-303]
- `find_other_exec(argv0, target, versionstr, retpath)` (310-344) — `find_my_exec`, strip basename, append `/<target>.exe?`, `validate_exec`, then `popen("\"<retpath>\" -V")` and `strcmp` the first line against `versionstr`. Returns 0 on match, -1 on not-found / non-executable, -2 on version mismatch. [verified-by-code, exec.c:310-344]
- `pipe_read_line(cmd)` (352-388, approx.) — `popen("r")`, `pg_get_line`, error-handle, return palloc'd string. [verified-by-code, exec.c:352-388]
- `pclose_check(stream)` (391-416) — `pclose`, then `wait_result_to_str` for any non-zero exit. [verified-by-code, exec.c:391-416]
- `set_pglocale_pgservice(argv0, app)` (429-468) — `find_my_exec`, then `bindtextdomain(app, get_locale_path(...))` and `setenv("PGSYSCONFDIR")` if not already set. **Does not override** an existing PGSYSCONFDIR. [verified-by-code, exec.c:429-468]
- `pg_disable_aslr(void)` (479-492, `#ifdef EXEC_BACKEND`) — Linux `personality(ADDR_NO_RANDOMIZE)` or FreeBSD `procctl(PROC_ASLR_CTL, PROC_ASLR_FORCE_DISABLE)`. [verified-by-code, exec.c:479-492]

## State / globals

- `int _CRT_glob = 0;` on Windows-mingw (line 50) — disables CRT auto-globbing of argv. [verified-by-code, exec.c:48-51]
- No file-scope mutable state otherwise.

## Phase D notes

- **`$PATH` is trusted** by `find_my_exec` when `argv0` has no separator. A process started by a parent with a hostile `$PATH` will land on the attacker-chosen binary. This is standard POSIX `execvp` semantics and the comment at line 188 acknowledges it ("the user must have been relying on PATH"). PG mitigates by **always invoking `realpath`** on the resolved path (line 248), so the absolute path used for `find_other_exec` cannot be back-pointed to an attacker-controlled symlink later. [verified-by-code, exec.c:161-228] [maybe — Phase D]
- **`find_other_exec` runs `popen("\"<retpath>\" -V")` with double-quoting** (line 331). This is the only quoting done. A `<retpath>` containing a literal `"` would break out — but `<retpath>` is the output of `realpath` joined with a hard-coded literal target name (`postgres`, `pg_dump`, etc.) so we never embed user-controlled bytes. [verified-by-code, exec.c:325-331] [maybe]
- **`pipe_read_line` does not sanitize what comes back from the child.** A subverted `pg_dump -V` could return a manipulated first line; the only consumer is `strcmp(line, versionstr) == 0`, so the worst case is a "version mismatch" or a successful match — no further interpretation. [verified-by-code, exec.c:336-342]
- **`set_pglocale_pgservice` honors a pre-existing `PGSYSCONFDIR`** (line 462). A parent that wants to redirect the libpq service-file lookup just sets the env var; PG trusts it. Same for `PGLOCALEDIR` (line 459: `setenv(..., 0)` does not override). [verified-by-code, exec.c:454-467]
- **macOS `_DARWIN_BETTER_REALPATH` define is at the top of the file** (line 24) — must be set before `#include <stdlib.h>` to take effect. If a future include reorder buries `<stdlib.h>` earlier, `realpath` silently falls back to the older non-F_GETPATH path. [verified-by-code, exec.c:18-30] [maybe]
- **Backend `EXEC_BACKEND` build only** is the consumer of `pg_disable_aslr`; default Linux/macOS Unix builds do not call it. [verified-by-code, exec.c:470-493]
- **`pipe_read_line` uses `popen`** which is `/bin/sh -c <cmd>` — even the trusted-input invocations route through the shell. [verified-by-code, exec.c:361]

## Cross-references

- `port/path.c` for `first_dir_separator`, `last_dir_separator`, `join_path_components`, `canonicalize_path`.
- `restricted_token.c` for the Windows token side of the exec story.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=12 [maybe]=4`
