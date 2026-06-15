---
path: src/include/port/win32_msvc/unistd.h
anchor_sha: e18b0cb7344
loc: 9
depth: read
---

# src/include/port/win32_msvc/unistd.h

## Purpose

MSVC fallback shim that defines the three POSIX file-descriptor constants
`STDIN_FILENO`, `STDOUT_FILENO`, `STDERR_FILENO` that the Microsoft VC
runtime omits. POSIX guarantees these as 0/1/2; backend code uses them
when calling `write()`, `dup2()`, `isatty()`, etc., and the comment in this
file flags that `_fileno(stdin)` is unreliable on MSVC (returns -1 when the
stream is closed), so a literal constant is safer. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `STDIN_FILENO` | `unistd.h:7` | `0` |
| `STDOUT_FILENO` | `unistd.h:8` | `1` |
| `STDERR_FILENO` | `unistd.h:9` | `2` |

## Internal landmarks

No code, just three `#define` lines. No header guard — collisions are
harmless because the values are mandated by POSIX.

## Invariants & gotchas

- Active only on the Microsoft VC toolchain (the `win32_msvc/` include
  directory is selected at configure time). MinGW gets the values from
  its own `<unistd.h>`.
- Comment explicitly warns against using `_fileno(stdin)` etc. as the
  values — they can return -1 when the standard streams are closed,
  which is why the literal 0/1/2 are hard-coded. `[from-comment]`
- This file does NOT provide the rest of POSIX `<unistd.h>` (no
  `getopt`, no `read`/`write` etc.); those come from `<io.h>` /
  `<process.h>` on MSVC, mostly via `src/include/port.h` and
  `src/include/port/win32_port.h`.

## Cross-refs

- `knowledge/files/src/include/port/win32_msvc/utime.h.md` — sibling MSVC shim.
- `knowledge/subsystems/port-layer.md` — Windows portability strategy.
