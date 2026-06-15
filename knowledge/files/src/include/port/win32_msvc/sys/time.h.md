---
path: src/include/port/win32_msvc/sys/time.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# src/include/port/win32_msvc/sys/time.h

## Purpose

Empty placeholder header. POSIX code says `#include <sys/time.h>` to pull
in `struct timeval`, `gettimeofday()`, etc.; MSVC has no such header but
the relevant symbols come in transitively through other Windows headers
(typically `<winsock2.h>` for `struct timeval`, plus PG's own
`gettimeofday` shim in `src/port/gettimeofday.c`). This file exists so
the `#include` directive resolves successfully — it's a no-op header.
`[inferred]`

## Public symbols

None — the file body is empty save for the path-tag comment on line 1.
`[verified-by-code]`

## Internal landmarks

One comment line: `/* src/include/port/win32_msvc/sys/time.h */`. No
declarations, no defines, no guard.

## Invariants & gotchas

- Active only on the Microsoft VC toolchain (`win32_msvc/sys/` added to
  the include path conditionally).
- The symbols POSIX would put here (`struct timeval`, `gettimeofday`)
  appear via other paths on Windows — see `src/port/gettimeofday.c`
  and `src/include/port/win32_port.h`.
- Do not delete: build files would break for any backend translation
  unit that does `#include <sys/time.h>`.

## Cross-refs

- `knowledge/files/src/port/gettimeofday.c.md` — the actual Windows
  `gettimeofday` implementation.
- `knowledge/subsystems/port-layer.md` — Windows portability strategy.
