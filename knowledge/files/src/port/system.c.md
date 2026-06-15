---
path: src/port/system.c
anchor_sha: e18b0cb7344
loc: 117
depth: read
---

# src/port/system.c

## Purpose

Windows-only `system()` and `popen()` wrappers — `pgwin32_system()` and
`pgwin32_popen()`. The whole file is wrapped in `#if defined(WIN32) &&
!defined(__CYGWIN__)`. The wrappers exist because Windows' CMD.EXE
processes quote characters in a notoriously fragile way: a command
string with multiple quoted segments (e.g. `"C:\\Program
Files\\app.exe" "arg with spaces"`) gets misparsed unless the entire
command is wrapped in an *extra* outer pair of quotes. `[from-comment]`
`[verified-by-code]`

The header comment (`system.c:7-31`) is the authoritative explanation
— copied directly from `CMD /?` documentation. The TL;DR rule: CMD
preserves inner quotes only if there are exactly two quote chars in the
command. Wrap everything in one more pair to satisfy that count when
callers have already embedded a quoted exe path.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pgwin32_system(const char *command)` | `system.c:53` | Replacement for `system(3)` on Windows |
| `FILE *pgwin32_popen(const char *command, const char *type)` | `system.c:86` | Replacement for `popen(3)` on Windows; delegates to `_popen` |

## Internal landmarks

Both functions follow the exact same pattern:

1. `malloc(strlen + 3)` — original + 2 quote chars + `\0`
   (`system.c:64`, `:97`).
2. Build `"<command>"` into the buffer (`:70-73`, `:103-106`).
3. Call the underlying `system()` / `_popen()` with the wrapped
   string.
4. Save/restore `errno` around `free()` (`:77-79`, `:110-112`) — `free`
   itself can clobber `errno` and we want to surface the real error.

## Invariants & gotchas

- **Compiled only on native Windows.** `__CYGWIN__` is explicitly
  excluded (`system.c:39`) because Cygwin has a proper POSIX-y libc
  and doesn't need the wrap.
- The `#undef system` / `#undef popen` (`:49-50`) is necessary because
  `port.h` macro-redirects bare `system`/`popen` references to these
  wrappers — without the undef, the wrappers would recurse into
  themselves.
- Callers are still responsible for quoting individual arguments
  inside `command` (the header comment refers callers to
  `appendShellString()`). This wrapper handles **only** the
  outer-quote pair that CMD's parser requires.
- Error path on `malloc` failure sets `errno=ENOMEM` and returns
  `-1`/`NULL` (`:67`, `:100`).
- Note this file is **NOT** the same as the backend's
  `OpenPipeStream` / `ClosePipeStream` (those use `pipe()` + `fork()`
  on Unix and a different Windows path).

## Cross-refs

- `source/src/include/port.h` — the macro indirection that routes
  `system()`/`popen()` calls through here on Windows.
- `knowledge/files/src/port/win32env.c.md` — sibling Windows-only
  CRT-wrapper file.
- `knowledge/files/src/port/quotes.c.md` — `appendShellString` lives
  in port library and is the per-arg quoting helper referenced by the
  header comment.
