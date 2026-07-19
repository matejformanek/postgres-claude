---
path: src/include/port/win32/netinet/tcp.h
anchor_sha: e18b0cb7344
loc: 7
depth: read
---

# netinet/tcp.h (win32)

## Purpose
Maps POSIX `<netinet/tcp.h>` (TCP_NODELAY, TCP_KEEPALIVE, TCP_KEEPIDLE, etc.)
onto the Winsock equivalent by including the `sys/socket.h` shim. The
underlying Winsock headers define these constants but with slightly different
semantics (`TCP_KEEPIDLE` vs `TCP_KEEPALIVE` naming on older Windows).

## Public symbols
None defined here; transitively exposes Winsock's TCP-level setsockopt
constants.

## Internal landmarks
- Header guard `WIN32_NETINET_TCP_H` (`:2-3`, `:7`).
- Body: `#include <sys/socket.h>` (`:5`).

## Invariants & gotchas
- TCP keepalive option names changed between Windows versions — newer Windows defines `TCP_KEEPIDLE` matching Linux; older builds only had `TCP_KEEPALIVE` with different semantics. PG's `pq_setkeepalivesidle()` etc. probe configure-time which names exist.
- On Windows, `TCP_QUICKACK` is unavailable — code paths that use it are `#ifdef TCP_QUICKACK`-guarded.

## Cross-refs
- [[knowledge/files/src/include/port/win32/netinet/in.h.md]] — sibling.
- [[knowledge/files/src/include/port/win32/sys/socket.h.md]] — does the heavy lifting.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../../subsystems/port.md)
