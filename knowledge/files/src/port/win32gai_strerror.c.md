---
path: src/port/win32gai_strerror.c
anchor_sha: e18b0cb7344
loc: 45
depth: read
---

# src/port/win32gai_strerror.c

## Purpose

Thread-safe Windows replacement for `gai_strerror()` — the
`getaddrinfo` error-code-to-string formatter. Windows ships
`gai_strerrorA`, but its documentation explicitly warns it is not
thread-safe (it returns a pointer into a per-call static buffer that
can race). This file replaces it with a hard-coded switch returning
string literals, which are inherently thread-safe.
`[from-comment]` `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `const char *gai_strerror(int errcode)` | `win32gai_strerror.c:22` | Returns a string literal; never NULL; unknown codes return "Unknown server error" |

## Internal landmarks

- Switch covers the POSIX `EAI_*` codes: `EAI_AGAIN`, `EAI_BADFLAGS`,
  `EAI_FAIL`, `EAI_FAMILY`, `EAI_MEMORY`, `EAI_NONAME`, `EAI_SERVICE`,
  `EAI_SOCKTYPE` (`win32gai_strerror.c:26-41`).
- Default returns `"Unknown server error"` (`win32gai_strerror.c:42-43`).
- Messages are pulled verbatim from common glibc text — gives PG users
  consistent error strings across Linux and Windows.

## Invariants & gotchas

- Always returns a **string literal** — caller must not free or
  modify. Effectively `const`, even though older POSIX prototypes
  drop the qualifier.
- **No `EAI_SYSTEM` case** — Windows' `getaddrinfo` doesn't produce
  `EAI_SYSTEM` (that's a Linux/glibc convention for "consult errno").
- Note this is a Windows-only file (under `#if defined(WIN32)` in the
  build configuration, not via `#ifdef` in the source).

## Cross-refs

- `source/src/include/port.h` — declares the prototype that this
  file satisfies.
- `source/src/backend/libpq/auth.c`, `pg_hba.c`, libpq client code —
  consumers calling `gai_strerror` after a failed `getaddrinfo`.
