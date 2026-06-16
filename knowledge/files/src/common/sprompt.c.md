# sprompt.c

`simple_prompt` / `simple_prompt_extended` — **the** interactive
prompt helper used by `psql`, `initdb`, `pg_basebackup`,
`pg_dump`, `pg_receivewal`, `pg_recvlogical`, `clusterdb`,
`createdb`, … any tool that needs a username, password, or yes/no
answer from a TTY. The password path is the most security-relevant
single function in `src/common/`.
(`source/src/common/sprompt.c:1-181`) [verified-by-code]

## Purpose

Read a single line of user input from `/dev/tty` (or `CONIN$` on
Windows), optionally suppressing local echo for passwords, while
allowing a higher-level SIGINT handler to cancel the prompt via
longjmp. Returns the input as a malloc'd string with the trailing
newline stripped.

## Key functions

- `simple_prompt(prompt, echo)` — thin wrapper that forwards with
  `prompt_ctx = NULL` (no cancellation).
  (`source/src/common/sprompt.c:37-41`)
- `simple_prompt_extended(prompt, echo, prompt_ctx)` — the real
  implementation. Sequence:
  1. Try to open `termin`/`termout` against `/dev/tty` (POSIX) or
     `CONIN$`/`CONOUT$` (Windows). On Windows additionally checks
     `$OSTYPE != "msys"` because MSYS direct-console I/O is broken.
     If any open fails or we're on MSYS, fall back to
     `stdin`/`stderr`. (`source/src/common/sprompt.c:67-117`)
  2. If `!echo`: POSIX `tcgetattr` + `t.c_lflag &= ~ECHO` +
     `tcsetattr(TCSAFLUSH)`; Windows `SetConsoleMode(ENABLE_LINE_INPUT
     | ENABLE_PROCESSED_INPUT)`. The original termios/console mode
     is saved in `t_orig` for restore.
     (`source/src/common/sprompt.c:119-137`)
  3. Print `_(prompt)` (translated) to `termout`, fflush.
  4. Read the line with `pg_get_line(termin, prompt_ctx)`.
     `pg_get_line` is responsible for the SIGINT/longjmp handshake.
  5. On NULL read (EOF or cancellation), return `pg_strdup("")`.
     (`source/src/common/sprompt.c:148-149`)
  6. `pg_strip_crlf(result)`.
  7. If `!echo`: restore `t_orig`, print `"\n"`.
     Otherwise if `prompt_ctx->canceled`, also print `"\n"`.
     (`source/src/common/sprompt.c:154-172`)
  8. Close `termin`/`termout` unless they're `stdin`.

## State / globals

None (purely stack-local state).

## Phase D notes

[ISSUE-secret-scrub: simple_prompt returns a malloc'd password
buffer with NO documented scrub contract; callers don't
explicit_bzero before pg_free (HIGH)] **This is the A4 finding.**
The header comment at lines 30-35 says "Caller is responsible for
freeing it when done." but says nothing about scrubbing. The
buffer is allocated inside `pg_get_line` →
`pg_malloc`/`palloc`, returned to the caller, and the caller
(libpq's `pqGetpwuid`, `psql/command.c`'s `\password`,
`pg_basebackup`'s password path, …) typically does
`free(password)` after handing the string to `PQconnectdb`. No
`explicit_bzero` anywhere in the helper, and no helper-side API to
request one. **Fix at the helper layer would touch every caller.**

[ISSUE-trust-boundary: TTY-restore window during termios reset is
not signal-safe (maybe)] If SIGINT fires between `tcsetattr(…
&t)` (echo off, line 126) and the matching restore at line 158,
the user's terminal is left with `ECHO` disabled. The cancellation
path goes through `pg_get_line`'s `siglongjmp`, which unwinds back
to the caller of `simple_prompt_extended` without running the
restore. Mitigated by most callers exiting on SIGINT, but in
interactive `psql` with a custom SIGINT handler this can leak.

[ISSUE-info-disclosure: fallback to stdin/stderr means a script
piping `echo password | tool` will display the prompt on stderr
but read from stdin — echo cannot be disabled on a non-tty stdin
(low)] Lines 110-117: when `/dev/tty` open fails, echo-suppression
via `tcsetattr` would be a no-op (`fileno(stdin)` isn't a tty).
Password silently echoes in scripted contexts — but this is
documented behaviour and expected.

[ISSUE-undocumented-invariant: `simple_prompt` always returns
non-NULL (line 148-149 swaps NULL→empty string) — callers
sometimes test for NULL anyway (low)]

## Potential issues

- Windows code path uses `fgets()` under `pg_get_line` which reads
  in the console's *input* code page; the comment at lines 67-87
  flags that non-ASCII passwords are unportable on Windows.
- `pg_strip_crlf` strips both `\r` and `\n` from the end; if a
  user types a password containing a literal `\r`, only the tail
  is touched (good).
- The `_(prompt)` translation at line 141 runs the prompt through
  gettext — fine since prompts are static strings, but a caller
  passing untrusted text would face format-string risk if it later
  contained `%` chars (none observed in tree).

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
