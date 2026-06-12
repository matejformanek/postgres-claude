---
path: src/include/port/win32/netinet/in.h
anchor_sha: e18b0cb7344
loc: 3
depth: read
---

# netinet/in.h (win32)

## Purpose
Maps POSIX `<netinet/in.h>` (sockaddr_in / sockaddr_in6 / IPPROTO_* / etc.)
onto the Winsock equivalent by re-using the `sys/socket.h` shim, which pulls
in `<winsock2.h>` and `<ws2tcpip.h>` in the correct order. One-liner.

## Public symbols
None defined here; transitively exposes Winsock's IP-level constants and
sockaddr types.

## Internal landmarks
- Two-line file: comment + `#include <sys/socket.h>`.

## Invariants & gotchas
- See `win32/arpa/inet.h` — same pattern, same warning about not pulling `<winsock2.h>` directly.

## Cross-refs
- [[knowledge/files/src/include/port/win32/arpa/inet.h.md]] — same one-liner pattern.
- [[knowledge/files/src/include/port/win32/sys/socket.h.md]] — does the heavy lifting.
- [[knowledge/files/src/include/port/win32/netinet/tcp.h.md]] — sibling.
