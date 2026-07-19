---
path: src/include/port/win32/sys/select.h
anchor_sha: e18b0cb7344
loc: 3
depth: read
---

# sys/select.h (win32)

## Purpose
POSIX `<sys/select.h>` placeholder for Windows. Empty — Winsock's `select()`
prototype is provided via `<winsock2.h>` (transitively pulled in by the
sys/socket.h shim), so this file just satisfies any `#include <sys/select.h>`
without adding declarations.

## Public symbols
None — placeholder.

## Internal landmarks
- Two-line file: comment only.

## Invariants & gotchas
- Don't try to use POSIX `fd_set` / `select` semantics on Windows — Winsock select() takes SOCKET handles only, not generic file descriptors, and ignores its `nfds` argument. PG's `WaitEventSet` (latch.c) is the portable API.

## Cross-refs
- [[knowledge/files/src/include/port/win32/sys/socket.h.md]] — pulls in winsock2 which declares select.
- [[knowledge/subsystems/]] — latch / WaitEventSet replaces direct select usage.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../../subsystems/port.md)
