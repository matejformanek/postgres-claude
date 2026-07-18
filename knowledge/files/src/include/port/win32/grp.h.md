---
path: src/include/port/win32/grp.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# grp.h (win32)

## Purpose
POSIX `<grp.h>` placeholder for Windows. Empty header — Windows has no
`getgrgid`/`getgrnam`-style group database, so the file exists only so
`#include <grp.h>` (referenced by e.g. `src/backend/libpq/auth.c` paths for
`ident`/`peer` auth) resolves cleanly during a Windows build. Backend code
that needs group info on Windows goes through SID/ACL APIs in `win32_port.h`
and `win32security.c`.

## Public symbols
None — placeholder.

## Internal landmarks
- One line: `/* src/include/port/win32/grp.h */`.

## Invariants & gotchas
- Any portable code that calls `getgrgid()` etc. should be already `#ifdef WIN32`-gated; this file just keeps the `#include` from being a compile error.

## Cross-refs
- [[knowledge/files/src/include/port.h.md]]
- [[knowledge/files/src/include/port/win32_port.h.md]]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
