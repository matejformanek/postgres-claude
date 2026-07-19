---
path: src/include/port/win32/netdb.h
anchor_sha: e18b0cb7344
loc: 7
depth: read
---

# netdb.h (win32)

## Purpose
Maps the POSIX `<netdb.h>` (host/service/proto database, `getaddrinfo` and
friends) onto the Winsock equivalent by including `<ws2tcpip.h>`. Lets portable
networking code (libpq, postmaster ipv4/ipv6 path) compile unchanged on
Windows.

## Public symbols
None defined here; transitively exposes `getaddrinfo`, `getnameinfo`,
`struct addrinfo`, and related from `<ws2tcpip.h>`.

## Internal landmarks
- Guarded by `WIN32_NETDB_H` (`:2-3`, `:7`).
- Body is just `#include <ws2tcpip.h>` (`:5`).

## Invariants & gotchas
- Order matters: `<winsock2.h>` must be included BEFORE `<windows.h>` on Windows or you get name conflicts. The umbrella `win32/sys/socket.h` enforces that. Pulling in `<ws2tcpip.h>` here transitively pulls `<winsock2.h>` first.
- The Winsock `getaddrinfo` is thread-safe but `gai_strerror` is NOT — overridden in `src/port/win32gai_strerror.c` and declared in `win32/sys/socket.h:33`.

## Cross-refs
- [[knowledge/files/src/include/port/win32/sys/socket.h.md]] — companion that handles winsock vs windows.h ordering.
- [[knowledge/files/src/include/port/win32_port.h.md]]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
