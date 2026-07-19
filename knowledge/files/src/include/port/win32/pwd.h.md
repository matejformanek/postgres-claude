---
path: src/include/port/win32/pwd.h
anchor_sha: e18b0cb7344
loc: 3
depth: read
---

# pwd.h (win32)

## Purpose
POSIX `<pwd.h>` placeholder for Windows. Empty (just an `src/include/...`
comment) — Windows has no passwd database. Exists so `#include <pwd.h>` doesn't
fail during a Windows build; `getpwuid_r`/`getpwnam` equivalents come from
`pgwin32_is_admin` and other helpers declared in `win32_port.h`.

## Public symbols
None — placeholder.

## Internal landmarks
- Two-line file: copyright comment only.

## Invariants & gotchas
- See `grp.h` (win32) sibling — same pattern.

## Cross-refs
- [[knowledge/files/src/include/port/win32/grp.h.md]] — sibling.
- [[knowledge/files/src/include/port/win32_port.h.md]]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
