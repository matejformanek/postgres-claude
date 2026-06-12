---
path: src/include/port/win32/arpa/inet.h
anchor_sha: e18b0cb7344
loc: 3
depth: read
---

# arpa/inet.h (win32)

## Purpose
Maps POSIX `<arpa/inet.h>` (`inet_ntop`, `inet_pton`, `htonl`, etc.) to the
Winsock equivalent. One-liner: `#include <sys/socket.h>` — which itself is
the win32 shim that pulls in `<winsock2.h>` + `<ws2tcpip.h>` + `<windows.h>`
in the correct order.

## Public symbols
None defined here; transitively re-exposes the inet family from Winsock.

## Internal landmarks
- Two-line file: comment + one include.

## Invariants & gotchas
- Don't include `<winsock2.h>` directly anywhere in PG code — always go via this shim or `sys/socket.h` so the `<windows.h>`-vs-`<wingdi.h>` ERROR-macro dance in `sys/socket.h` happens.

## Cross-refs
- [[knowledge/files/src/include/port/win32/sys/socket.h.md]] — does the actual heavy lifting.
- [[knowledge/files/src/include/port/win32/netinet/in.h.md]] — sibling, same one-liner.
