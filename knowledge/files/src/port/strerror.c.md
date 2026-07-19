---
path: src/port/strerror.c
anchor_sha: e18b0cb7344
loc: 312
depth: read
---

# src/port/strerror.c

## Purpose

PG's portable `strerror()` / `strerror_r()` wrappers — `pg_strerror`
and `pg_strerror_r`. Always compiled (not gated on `HAVE_*`) because
the platform `strerror` family has three orthogonal warts the wrapper
papers over:

1. Two different `strerror_r` ABIs in the wild: POSIX returns `int`,
   GNU returns `char *`. Picked at compile time via
   `STRERROR_R_INT`. `[verified-by-code]`
2. Some libcs return empty string or `???` for out-of-range
   `errno` (ANSI-compliant but useless), or when locale transcoding
   fails. The wrapper falls back to a hard-coded symbol table
   (`get_errno_symbol`) and finally to `"operating system error %d"`.
3. Windows' `strerror` doesn't recognize Winsock error codes
   (10000-11999). Those are routed to a separate handler that
   `FormatMessage`s out of `netmsg.dll`.

`[from-comment]` `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *pg_strerror(int errnum)` | `strerror.c:35` | Static buffer per call — **not** thread-safe; thin wrapper around `pg_strerror_r` |
| `char *pg_strerror_r(int errnum, char *buf, size_t buflen)` | `strerror.c:46` | Thread-safe; caller-supplied buffer |

## Internal landmarks

- `gnuish_strerror_r` (`strerror.c:84-106`) — internal helper that
  emulates the GNU `strerror_r` ABI on top of whatever the platform
  offers:
  - `HAVE_STRERROR_R && STRERROR_R_INT` → POSIX `strerror_r` returning
    `int`; on success returns the caller's `buf`.
  - `HAVE_STRERROR_R && !STRERROR_R_INT` → GNU `strerror_r` returning
    `char *` directly.
  - `!HAVE_STRERROR_R` → falls back to plain `strerror()` and `strlcpy`s
    into the caller's buffer to minimize the thread-unsafety window
    (`strerror.c:97-104`).
- `get_errno_symbol` (`strerror.c:113-268`) — giant switch returning
  `"ENOENT"`, `"EPERM"`, etc. as a string. Used both as a last-ditch
  fallback (when `strerror` returns nothing useful) and as a stable
  cross-locale name for log messages. Each error is `#ifdef`-gated so
  the table works on every supported platform.
- `win32_socket_strerror` (`strerror.c:276-310`) — handles Winsock
  range (10000-11999). Caches the `netmsg.dll` handle as a static
  `HANDLE handleDLL` and uses `FormatMessage` with the `FROM_HMODULE`
  flag to look up the text. Failure falls back to `"unrecognized
  winsock error %d"`.
- The Winsock-range check at `strerror.c:53` is the entry-point fast
  path: `errnum >= 10000 && errnum <= 11999` routes to
  `win32_socket_strerror` before anything else.

## Invariants & gotchas

- **`pg_strerror` (no `_r`) uses a static buffer** (`strerror.c:37`) —
  fine for single-threaded callers (most of PG, given the per-process
  backend model), but two concurrent calls from threads (libpq users)
  will race. Threaded code paths must use `pg_strerror_r`.
- `EWOULDBLOCK`/`EAGAIN` and `EOPNOTSUPP`/`ENOTSUP` collisions handled
  via `#if (X != Y)` guards (`:259`, `:231`) — same numeric value
  collapses to one case label.
- `ENOTEMPTY == EEXIST` on AIX (`:217`) — same workaround pattern.
- **Locale-aware?** Yes — `pg_strerror_r` returns whatever the
  platform's `strerror_r` produces, which respects `LC_MESSAGES`. The
  `get_errno_symbol` fallback is always ASCII and never localized. The
  `"operating system error %d"` final fallback goes through `_()`
  (gettext, `:72`) for localization.
- The `netmsg.dll` handle is loaded with
  `DONT_RESOLVE_DLL_REFERENCES | LOAD_LIBRARY_AS_DATAFILE`
  (`strerror.c:284`) — we want strings, not code execution.

## Cross-refs

- `knowledge/files/src/port/win32error.c.md` — `_dosmaperr` maps
  Win32 `GetLastError` codes to `errno`; `strerror.c` then formats the
  resulting errno into a string. The two are complementary halves of
  the Windows error story.
- `knowledge/idioms/error-handling.md` — `ereport` consumers ultimately
  rely on `pg_strerror` for `%m` formatting.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
