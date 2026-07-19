---
path: src/include/port/win32_msvc/utime.h
anchor_sha: e18b0cb7344
loc: 3
depth: read
---

# src/include/port/win32_msvc/utime.h

## Purpose

One-line MSVC fallback shim. Re-exports the POSIX `<utime.h>` shape — the
`struct utimbuf` and `utime()` prototype used for setting file access /
modification times — from MSVC's actual header `<sys/utime.h>`. POSIX code
that says `#include <utime.h>` finds nothing on the Microsoft VC toolchain;
this header bridges the gap. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| (re-exports) | `utime.h:3` | `#include <sys/utime.h>` — pulls in `struct utimbuf`, `utime()`, `_utime()` |

## Internal landmarks

The entire file is one `#include` directive on line 3. The comment
"for non-unicode version" `[from-comment]` flags that this picks the
ANSI/`char*` overload, not the `_wutime` wide-character variant.

## Invariants & gotchas

- Only compiled when the toolchain is the legacy Microsoft VC compiler
  (`win32_msvc/` is added to the include path conditionally — see
  `meson.build` / `Makefile.global.in` for the MSVC-only inclusion gate).
- MinGW does NOT use this directory — it has its own POSIX-compatible
  `<utime.h>`.
- No header guard: the file is so small (one include) that the guard
  on `<sys/utime.h>` itself is sufficient.

## Cross-refs

- `knowledge/files/src/include/port/win32_msvc/unistd.h.md` — sibling MSVC shim.
- `knowledge/subsystems/port-layer.md` — overall portability strategy
  for Windows builds.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
