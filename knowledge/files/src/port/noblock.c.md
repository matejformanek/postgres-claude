---
path: src/port/noblock.c
anchor_sha: e18b0cb7344
loc: 66
depth: read
---

# src/port/noblock.c

## Purpose

Tiny portability shim for toggling a socket between blocking and
non-blocking I/O. Unix uses `fcntl(F_GETFL)` + `F_SETFL` with `O_NONBLOCK`;
Windows uses `ioctlsocket(FIONBIO, ...)`. The function-level wrappers paper
over the API and return-value difference (fcntl returns -1 on failure;
ioctlsocket returns nonzero). `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `bool pg_set_noblock(pgsocket sock)` | `noblock.c:25` | Put socket in non-blocking mode; true on success |
| `bool pg_set_block(pgsocket sock)` | `noblock.c:49` | Put socket in blocking mode; true on success |

## Internal landmarks

- Unix arm of each (`:27-35`, `:51-59`) — two-call sequence `fcntl(F_GETFL)`
  to read current flags, then `F_SETFL` with `O_NONBLOCK` set or cleared.
  Cannot use one call because we don't want to clobber other fd flags.
- Win32 arm (`:36-41`, `:60-65`) — `ioctlsocket(sock, FIONBIO, &arg)` with
  arg=1 (non-block) or arg=0 (block).

## Invariants & gotchas

- **Sockets only.** `pgsocket` is `int` on Unix and `SOCKET` (uintptr_t-ish)
  on Windows. The Win32 arm uses `ioctlsocket`, not `ioctl` — it would not
  work on a regular file descriptor. For non-socket fd nonblock on Unix
  this code happens to work, but on Win32 it would error.
- **`pg_set_block` after `pg_set_noblock` is symmetric.** The fcntl arm
  clears just the `O_NONBLOCK` bit, preserving anything else like
  `O_CLOEXEC` or `O_APPEND` that someone else set. `[verified-by-code]`
- No errno propagation on success; on failure callers check the return and
  separately consult errno (Unix) or `WSAGetLastError()` (Windows). The
  bool return is intentionally minimal.

## Cross-refs

- `source/src/backend/libpq/be-secure.c` — flips listening sockets to
  non-blocking during SSL handshake.
- `source/src/interfaces/libpq/fe-connect.c` — frontend sets non-blocking
  before `connect()` for timeout support.
- `source/src/include/port.h` — prototypes.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
