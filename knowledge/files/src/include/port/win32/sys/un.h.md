---
path: src/include/port/win32/sys/un.h
anchor_sha: e18b0cb7344
loc: 17
depth: read
---

# sys/un.h (win32)

## Purpose
Provides `struct sockaddr_un` for the Windows port. Modern Windows (10+)
supports AF_UNIX sockets, but the official header `<afunix.h>` isn't shipped
by every toolchain (older SDKs, MinGW). PG defines the layout locally so
backend code that uses AF_UNIX (e.g. potentially in the future for pgbouncer-
style local IPC) compiles uniformly.

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `struct sockaddr_un` | type | `:11-15` | `unsigned short sun_family; char sun_path[108];` — matches the Linux/BSD layout. |

## Internal landmarks
- Header guard `WIN32_SYS_UN_H` (`:3-4`, `:17`).
- `sun_path[108]` (`:14`) — matches Linux's `UNIX_PATH_MAX` of 108. Windows' own afunix.h uses 108 too.
- Comment at `:7-10` explains why this is defined locally instead of including `<afunix.h>`.

## Invariants & gotchas
- This is a header-only declaration — the actual AF_UNIX socket support depends on Windows version + Winsock initialization. Backend code currently uses TCP loopback on Windows; this header exists primarily for FUTURE AF_UNIX work, not as a working production path.
- Layout MUST match the OS's expected `sockaddr_un` because pointers to this struct get passed to `bind()`/`connect()` Winsock APIs. If Microsoft ever changes the layout, this struct drifts.
- 108-byte sun_path means full Unix path > 107 bytes will fail to fit — same limitation as Linux. Be sure socket dir path stays short.

## Cross-refs
- [[knowledge/files/src/include/port/win32_port.h.md]]
- [[knowledge/files/src/include/port/win32/sys/socket.h.md]]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../../subsystems/port.md)
