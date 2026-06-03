# win32.h

- **Source path:** `source/src/interfaces/libpq/win32.h`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 24 lines

## Purpose

> "Some compatibility functions" [line 8, from-comment]

The smallest header in libpq. Three macro redirects to map POSIX-named file I/O calls to the underscore-prefixed MSVC CRT names, plus a winsock-error helper forward-decl.

## Macros

- `close(a) → _close(a)`
- `read(a,b,c) → _read(a,b,c)`
- `write(a,b,c) → _write(a,b,c)`

The "open provided elsewhere" comment (line 11) acknowledges that `open` is **deliberately not** redefined here — the project handles it via a different shim (likely `src/port/open.c`).

`#undef EAGAIN` (line 16, comment: "doesn't apply on sockets") — strips out any libc `EAGAIN` definition because Windows socket EAGAIN-equivalent is `WSAEWOULDBLOCK`. Mixing them would cause silent retry bugs. [verified-by-code, from-comment]

## Externs

- `winsock_strerror(int err, char *strerrbuf, size_t buflen)` — defined in `win32.c`. Wired up via `libpq-int.h`'s `SOCK_STRERROR` macro on Windows.

## Tally

`[verified-by-code]=2 [from-comment]=2`
