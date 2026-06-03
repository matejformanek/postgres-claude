# wait_error.c

`waitpid(2)`/`wait(2)` status-decoding helpers shared by FE and BE.
Three small functions that translate the encoded `int` status
returned by `wait()`/`waitpid()`/`pclose()`/`system()` into a
human-readable string or normalized exit code.
(`source/src/common/wait_error.c:1-15`) [verified-by-code]

## Purpose

Wrap `WIFEXITED`/`WEXITSTATUS`/`WIFSIGNALED`/`WTERMSIG` once, in a
translation-aware way, so every place that spawns a child
(`postmaster`, archive_command, `pg_dump`/`psql` shell escapes,
pg_regress, …) reports child failures consistently.

## Key functions

- `wait_result_to_str(exitstatus)` — returns a `pstrdup`'d (or
  malloc'd in FE) translated string. Branches:
  - `-1` → `"%m"` (errno from a pclose/system failure)
  - `WIFEXITED` → `"command not executable"` (126), `"command not
    found"` (127), else `"child process exited with exit code N"`
  - `WIFSIGNALED` → Windows: `"… terminated by exception 0x%X"`;
    POSIX: `"… terminated by signal N: <strsignal>"` via
    `pg_strsignal`. The `pg_strsignal` wrapper falls back to
    `"unrecognized signal"` for unknown signums.
  - default → `"… unrecognized status %d"`
  (`source/src/common/wait_error.c:32-86`)
- `wait_result_is_signal(exit_status, signum)` — true if the
  child died from `signum` directly OR a POSIX shell sat between
  us and the child and reported it as exit code `128 + signum`.
  Use only when there *could* be a shell intermediary.
  (`source/src/common/wait_error.c:101-109`)
- `wait_result_is_any_signal(exit_status, include_command_not_found)` —
  any signal direct or shell-reported. With
  `include_command_not_found=true`, also matches the 126/127
  "command not executable/found" exit codes.
  (`source/src/common/wait_error.c:120-129`)
- `wait_result_to_exit_code(exit_status)` — shell-style normalized
  code: 0-255 from `WEXITSTATUS`, `128+signum` for signal,
  pass-through for `-1`. (`source/src/common/wait_error.c:138-148`)

## State / globals

None.

## Phase D notes

None directly. Strings are bounded to a 512-byte stack buffer and
`pstrdup`'d out, so no OOB. `pg_strsignal` (declared in
`port.h`) is the only external dependency.

## Potential issues

- The 512-byte stack buffer at line 35 truncates silently if a
  `strsignal()` translation is unexpectedly long — practically
  impossible.
- On non-Windows, `WTERMSIG` of an unrecognized signal is fine
  (`pg_strsignal` handles it); on Windows, the exception code is
  formatted as `0x%X`. Both paths produce a stable, log-safe
  string.
