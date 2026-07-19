---
path: src/include/port/win32/sys/socket.h
anchor_sha: e18b0cb7344
loc: 34
depth: read
---

# sys/socket.h (win32)

## Purpose
The keystone Windows socket-shim header. Pulls in `<winsock2.h>`, `<ws2tcpip.h>`,
and `<windows.h>` in the EXACT order Microsoft requires to avoid name
collisions, then `#undef`s the conflicting `ERROR` and `small` macros leaked by
`<wingdi.h>` (transitively included by `<windows.h>`). Restores PG's own
`ERROR` (mapped from `PGERROR`) and redirects `gai_strerror` to a thread-safe
PG-internal replacement.

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| (re-exports from Winsock) | — | — | sockets, addrinfo, htonl, ntohl, fd_set, select, etc. |
| `gai_strerror` | extern | `:33` | Override of Winsock's non-thread-safe `gai_strerror[A]`; impl `src/port/win32gai_strerror.c`. |

## Internal landmarks
- Header guard `WIN32_SYS_SOCKET_H` (`:3-4`, `:34`).
- Forced include order at `:18-20`: `winsock2.h` BEFORE `windows.h` (the other order pulls the wrong sockaddr/sockets API in via the old `<winsock.h>` and breaks ABI).
- `#undef ERROR` (`:22`) — `<wingdi.h>` defines `ERROR` as a logical-pen style value (`(-1)`); PG's `ereport(ERROR, ...)` macro shadows it.
- `#undef small` (`:23`) — RPC header inside `<windows.h>` defines `small` as `char`; collides with C++ semantic names and the like.
- `#ifdef PGERROR / #define ERROR PGERROR` (`:26-28`) — caller (`c.h`) wraps `ERROR` with `PGERROR` before this include and restores after.
- `#undef gai_strerror` (`:32`) before declaring our own — Winsock's is a macro that maps to `gai_strerrorA`/`gai_strerrorW`.

## Invariants & gotchas
- ALL portable PG networking code on Windows must include `<sys/socket.h>` (this shim) NOT `<winsock2.h>` directly. Direct includes skip the ERROR-restore dance and break `ereport(ERROR, ...)` at the call site.
- Winsock's `gai_strerror` returns thread-local-shared static storage — unsafe across multiple addrinfo lookups; PG's replacement returns string literals.
- This is the file behind the `c.h:#define gai_strerror pg_gai_strerror` confusion if you grep around — that older define has been replaced; the override is now via the `#undef` + extern here.
- Including `<wingdi.h>` directly (the alternative to letting `<windows.h>` pull it) "causes compile errors" per the comment at `:14` — don't try to be clever.

## Cross-refs
- [[knowledge/files/src/include/port/win32/netdb.h.md]] — pulls `<ws2tcpip.h>` directly, similar pattern.
- [[knowledge/files/src/include/port/win32/arpa/inet.h.md]] — one-liner that pulls this in.
- [[knowledge/files/src/include/port/win32/netinet/in.h.md]] — same one-liner pattern.
- [[knowledge/files/src/include/port/win32_port.h.md]]
- [[knowledge/issues/include-port.md]] — Windows include-order traps.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../../subsystems/port.md)
