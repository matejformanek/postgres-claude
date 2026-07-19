---
path: src/include/port/win32_msvc/dirent.h
anchor_sha: e18b0cb7344
loc: 34
depth: read
---

# src/include/port/win32_msvc/dirent.h

## Purpose

MSVC fallback shim that synthesises POSIX `<dirent.h>` for the Microsoft VC
toolchain, which ships no native equivalent. Declares `struct dirent`, the
opaque `DIR` handle, and the three lifecycle calls `opendir / readdir /
closedir`, plus the `DT_*` file-type constants. The actual implementation
lives in `src/port/dirent.c`, which wraps Win32 `FindFirstFile` /
`FindNextFile`. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `struct dirent` | `dirent.h:9-16` | `d_ino`, `d_reclen`, `d_type`, `d_namlen`, `d_name[MAX_PATH]` |
| `typedef struct DIR DIR` | `dirent.h:18` | opaque handle |
| `DIR *opendir(const char *)` | `dirent.h:20` | POSIX-style entry point |
| `struct dirent *readdir(DIR *)` | `dirent.h:21` | |
| `int closedir(DIR *)` | `dirent.h:22` | |
| `DT_UNKNOWN` … `DT_WHT` | `dirent.h:25-33` | file-type constants matching POSIX values (0, 1, 2, 4, 6, 8, 10, 12, 14) |

## Internal landmarks

- Header guard `_WIN32VC_DIRENT_H` (`:7-8`, `:34`).
- `d_name` sized to `MAX_PATH` (`:15`) — Win32's traditional 260-char
  path cap. Long-path support would need the `\\?\` prefix, which this
  shim doesn't handle.
- `DT_*` numeric values match POSIX (4 = directory, 8 = regular file)
  so callers don't need to branch on platform when checking entry type.

## Invariants & gotchas

- The header only declares; `src/port/dirent.c` provides the actual
  Win32-backed implementation. Don't try to use this header without
  that .c file in the build.
- `MAX_PATH` must be in scope at include time (pulled in transitively
  via `<windows.h>`). If you include this header in isolation you'll
  hit a compile error.
- Active only on Microsoft VC; MinGW has its own `<dirent.h>`.

## Cross-refs

- `knowledge/files/src/port/dirent.c.md` — the implementation.
- `knowledge/subsystems/port-layer.md` — Windows portability strategy.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
