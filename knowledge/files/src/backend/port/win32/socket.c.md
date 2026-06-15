---
path: src/backend/port/win32/socket.c
anchor_sha: e18b0cb7344
loc: 707
depth: read
---

# src/backend/port/win32/socket.c

## Purpose

Wraps WinSock primitives (`WSASocket`, `WSARecv`, `WSASend`, `WSAEventSelect`,
`WaitForMultipleObjectsEx`) to provide POSIX-shaped, signal-aware socket
operations. Real backends and `pqcomm.c` call `recv` / `send` / `select` /
`accept` etc. without knowing they're Windows — `port/win32_port.h` defines
macros that route them to `pgwin32_recv`, `pgwin32_send`, `pgwin32_select`,
`pgwin32_accept`. The contract those wrappers must satisfy:

1. Map every `WSAGetLastError()` to a Berkeley `errno` value
   (`TranslateSocketError` at `socket.c:56`).
2. Allow PG's Win32 signal-emulation layer to deliver signals during
   blocking I/O — by including `pgwin32_signal_event` in every
   `WaitForMultipleObjectsEx` call.
3. Hide the fact that the underlying socket is **always non-blocking**
   (set at creation in `pgwin32_socket`) — emulate POSIX blocking
   semantics via wait-loops, and emulate emulated-non-blocking semantics
   via the `pgwin32_noblock` flag.

`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pgwin32_noblock` | `socket.c:28` | Global; when 1, behave as if socket were non-blocking |
| `int pgwin32_waitforsinglesocket(SOCKET s, int what, int timeout)` | `:181` | Workhorse: wait for socket-ready OR signal event |
| `SOCKET pgwin32_socket(int af, int type, int protocol)` | `:291` | `WSASocket(WSA_FLAG_OVERLAPPED)` + `FIONBIO` |
| `int pgwin32_bind` / `_listen` / `_accept` / `_connect` | `:315-379` | Thin wrappers with `TranslateSocketError` |
| `int pgwin32_recv(SOCKET, char *, int, int)` | `:382` | EWOULDBLOCK-aware blocking emulation |
| `int pgwin32_send(SOCKET, const void *, int, int)` | `:459` | Loops on UDP-busy quirk |
| `int pgwin32_select(int, fd_set *, fd_set *, fd_set *, const struct timeval *)` | `:517` | POSIX `select` shim |

## Internal landmarks

- **`TranslateSocketError`** (`socket.c:56-154`) — exhaustive switch
  mapping WSA error codes to POSIX errno. Comment at `:48-54` notes that
  most mappings are no-ops because `win32_port.h` aliases the Berkeley
  symbols to their WSA values; the switch exists mainly for near-miss
  codes (`WSAEINPROGRESS` → `EINPROGRESS`, `WSANOTINITIALISED` → `EINVAL`).
- **`pgwin32_waitforsinglesocket`** (`:181`) — static workhorse:
  - Lazy-creates `waitevent` (cached across calls, `:190-197`).
  - `WSAEventSelect(s, waitevent, what)` to associate.
  - `WaitForMultipleObjectsEx(2, {pgwin32_signal_event, waitevent}, ...)`.
  - On signal event → dispatch + return `errno=EINTR, ret=0`.
  - On socket event → return `1`.
  - On timeout → `errno=EWOULDBLOCK, ret=0`.
  - **UDP-write quirk** (`:232-263`): if waiting for write on a UDP
    socket, poll every 100ms and probe with a 0-byte `WSASend` —
    workaround for an observed locking pathology where the backend would
    hang in `WaitForMultipleObjectsEx`.
- **`pgwin32_socket`** (`:291`) — every socket is created with
  `WSA_FLAG_OVERLAPPED` + `FIONBIO=1` (non-blocking). The blocking
  semantics every other function emulates are layered above this.
- **`pgwin32_recv` retry-up-to-5** (`:418-441`) — explicit comment
  (`:432-439`): WinXP/2k has observed cases where `WSARecv` returns
  `WSAEWOULDBLOCK` even after `pgwin32_waitforsinglesocket` says the
  socket is readable. Sleep 10ms and retry, up to 5 times.
- **`pgwin32_select`** (`:517-706`):
  - Asserts no `exceptfds` (`:531`) — PG doesn't use it.
  - Pre-flight: for writefds, do a 0-byte dummy `WSASend` to discover
    write-ready sockets immediately (`:539-573`). Windows doesn't post
    `FD_WRITE` unless a previous send returned `WSAEWOULDBLOCK`, so this
    is needed to avoid spurious blocking.
  - Allocates up to `2*FD_SETSIZE` `WSAEVENT`s — one per socket-per-direction.
  - `WSAEventSelect` each socket with `FD_READ|FD_ACCEPT|FD_CLOSE` /
    `FD_WRITE|FD_CLOSE`.
  - Waits with `pgwin32_signal_event` appended as last event.
  - On wake, `WSAEnumNetworkEvents` each socket to recover which
    direction triggered (Wait... only reports ONE; we need ALL).

## Invariants & gotchas

- **Every socket is OS-level non-blocking.** This is the most important
  invariant. `pgwin32_socket` (`:303`) sets `FIONBIO=1` unconditionally.
  Direct WinSock `recv`/`send` calls on PG sockets will see
  `WSAEWOULDBLOCK` instead of blocking. ALL POSIX-blocking semantics
  are emulated in this file.
- **`pgwin32_noblock` flag is global.** `:25-27` warns: "should only be
  set for very short periods of time". Consumer is e.g. SSL handshake
  retries that want POSIX `EWOULDBLOCK` rather than the emulated
  block-loop. Setting it from one thread affects all sockets in the
  process — there's no per-socket variant.
- **`pgwin32_accept` does NOT return EINTR.** Comment at `:341-344`:
  pqcomm.c doesn't handle EINTR from accept, so this function polls
  signals once (`pgwin32_poll_signals` at `:345`) and then does a
  blocking `WSAAccept`. Signal delivery during the actual accept call
  is impossible; you have to wait for the next connection.
- **`pgwin32_connect` ignores signals.** Comment at `:357`: "No signal
  delivery during connect." The loop at `:373-376` continues over the
  `EINTR`-equivalent returns from `pgwin32_waitforsinglesocket`.
- **`WSANETWORKEVENTS` aggregation in select** (`:638-669`) — needed
  because `WaitForMultipleObjects` only reports one signaled event even
  when many are. PG must enumerate all sockets and collect every
  matching network-event bit, or it will starve fds.
- **No `exceptfds` support.** Comment at `:513` + assertion at `:531`.
  Anything that needs OOB / urgent-data signaling will misbehave; PG
  doesn't.
- **Cache thrash in `waitforsinglesocket`.** The single static
  `waitevent` is reused across all calls; if two threads ever called
  this concurrently they'd corrupt each other. PG runs one main thread
  + a signal-handling thread + the timer thread; only the main thread
  ever calls socket APIs, so it's safe in practice. `[inferred]`
- **`current_socket` tracking** (`:184, 207-209`) — caches whether the
  most-recently-waited socket was UDP, to avoid re-checking via
  `getsockopt(SO_TYPE)`. Comment at `:202-206` admits this UDP-special
  branch is "most likely useless and wrong" — kept for historical
  caution.

## Cross-refs

- `knowledge/subsystems/libpq-backend.md` — `pqcomm.c` is the immediate
  consumer of these wrappers.
- `knowledge/files/src/backend/port/win32/signal.c.md` — defines
  `pgwin32_signal_event`, `pgwin32_dispatch_queued_signals`,
  `UNBLOCKED_SIGNAL_QUEUE()` macro consumed here.
- `knowledge/files/src/include/port/win32_port.h.md` — the macros that
  redirect `recv`/`send`/`select`/etc. to these `pgwin32_*` wrappers.
