---
path: src/backend/libpq/pqcomm.c
anchor_sha: 4b0bf0788b0
loc: 2088
depth: deep
---

# pqcomm.c

- **Source path:** `source/src/backend/libpq/pqcomm.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 2088

## Purpose

The low-level frontend/backend wire layer. Owns the listening sockets
(unix-domain + TCP), accepts new connections, manages the per-backend
8 KB recv and 8 KB send ring buffers, and implements the `PQcommMethods`
vtable that `pqformat.c` and `auth.c` call through. Ignorant of
protocol semantics — moves bytes only. The top-of-file note that "there
are no functions to send raw bytes or partial messages; this ensures
that the channel will not be clogged by an incomplete message if
execution is aborted by ereport(ERROR) partway through the message"
is the file's load-bearing invariant. [from-comment, pqcomm.c:1-26]

Backend `libpq` and the client-side `interfaces/libpq` share names but
have been entirely separate codebases for many releases — do not confuse
`pq_putmessage` (here) with `PQputmessage` (client).
[from-comment, pqcomm.c:16-19]

## Public API surface

### Setup / teardown
| Line | Symbol | Notes |
|---|---|---|
| 174 | `pq_init(client_sock) → Port *` | Per-backend libpq init: allocate Port, copy raddr, fill laddr via `getsockname`, set TCP_NODELAY + SO_KEEPALIVE, configure keepalive GUCs, alloc 8 KB send buffer in `TopMemoryContext`, register `socket_close` on_proc_exit, set socket non-blocking + FD_CLOEXEC, build `FeBeWaitSet` (3 events: socket-writable / latch / postmaster-death). |
| 418 | `ListenServerPort(family, host, port, sockdir, *socks, *n, max)` | Postmaster-side: bind + listen on a family. AF_UNIX path Lock_AF_UNIX → Setup_AF_UNIX (chmod, chown). TCP path sets SO_REUSEADDR (non-Windows), IPV6_V6ONLY when available; `listen(maxconn = 2 * MaxConnections)`. |
| 794 | `AcceptConnection(server_fd, *client_sock)` | Accept (blocking — postmaster polled for readiness). On EMFILE-style failure, `pg_usleep(100 ms)` before returning STATUS_ERROR so the postmaster's poll loop doesn't busy-spin. |
| 830 | `TouchSocketFiles()` | `utime(NULL)` on every AF_UNIX socket file so /tmp cleaners don't garbage them. Called periodically. |
| 848 | `RemoveSocketFiles()` | unlink AF_UNIX sockets at postmaster shutdown. |

### Internal (vtable: `PqCommSocketMethods`)
| Line | Symbol | Notes |
|---|---|---|
| 334 | `socket_comm_reset()` | Just clears `PqCommBusy` after an error inside pqcomm — does NOT throw away unsent data |
| 349 | `socket_close(code, arg)` | on_proc_exit: tear down GSS + SSL; set `MyProcPort->sock = PGINVALID_SOCKET` but do NOT `close()` (let client see synchronous-close) |
| 1327 | `socket_flush()` | Blocking flush of send buffer; no-op if PqCommBusy |
| 1435 | `socket_flush_if_writable()` | Non-blocking flush attempt |
| 1461 | `socket_is_send_pending()` | `PqSendStart < PqSendPointer` |
| 1491 | `socket_putmessage(type, s, len)` | type-byte + ntoh(len+4) + payload, atomic from the caller's POV |
| 1524 | `socket_putmessage_noblock(...)` | `repalloc` send buffer if needed so message fits |

### Low-level I/O (exported via pqformat.c / auth.c)
| Line | Symbol | Notes |
|---|---|---|
| 963 | `pq_getbyte()` | Blocking 1-byte; asserts `PqCommReadingMsg` |
| 982 | `pq_peekbyte()` | Same, no advance |
| 1003 | `pq_getbyte_if_available(*c)` | Non-blocking; returns 1/0/EOF |
| 1062 | `pq_getbytes(*b, len)` | Blocking N bytes |
| 1127 | `pq_buffer_remaining_data()` | Bytes available without recv() |
| 1141 | `pq_startmsgread()` | Set `PqCommReadingMsg`; FATAL if already set ("protocol synchronization was lost") |
| 1165 | `pq_endmsgread()` | Clear it |
| 1181 | `pq_is_reading_msg()` | Query |
| 1203 | `pq_getmessage(StringInfo s, int maxlen)` | Frame: read 4-byte ntoh length, validate 4 ≤ len ≤ maxlen, read body; on OOM `PG_TRY/PG_CATCH` and `pq_discardbytes` to stay in sync, then RE_THROW |
| 1561 | `pq_putmessage_v2(type, s, len)` | Protocol-v2 compatibility — only for the "unsupported protocol version" error message |
| 2056 | `pq_check_connection()` | Use FeBeWaitSet WL_SOCKET_CLOSED poll to detect dead client |

### TCP keepalive / user-timeout GUCs (1632–2051)
| Line | Symbol |
|---|---|
| 1633/1668 | `pq_getkeepalivesidle` / `pq_setkeepalivesidle` |
| 1717/1752 | interval get/set |
| 1801/1831 | count get/set |
| 1876/1906 | `pq_gettcpusertimeout` / `pq_settcpusertimeout` |
| 1954/1974 etc. | `assign_tcp_*` / `show_tcp_*` GUC hooks |

## Internal landmarks

### File-static state
- `sock_paths` (111) — list of AF_UNIX socket file paths held by the
  postmaster; used by `TouchSocketFiles` / `RemoveSocketFiles`. [verified-by-code, pqcomm.c:110-111]
- `PqSendBuffer` (dynamic), `PqSendBufferSize` (default 8192,
  may grow via `pq_putmessage_noblock`), `PqSendPointer`, `PqSendStart`
  (123-126) — send ring.
- `PqRecvBuffer` (fixed 8192), `PqRecvPointer`, `PqRecvLength` (128-130) —
  recv ring.
- `PqCommBusy`, `PqCommReadingMsg` (135-136) — state flags.
- `PqCommSocketMethods` (156) — the vtable; `PqCommMethods` global
  pointer (165) starts at this; `pqmq.c::pq_redirect_to_shm_mq` swaps
  it for parallel workers.
- `FeBeWaitSet` (167) — 3-slot WaitEventSet (socket writable / latch /
  postmaster death) used by the latch-based blocking primitives.

### TCP keepalive option macros (89-102)
`PG_TCP_KEEPALIVE_IDLE` resolves to `TCP_KEEPIDLE` on Linux/BSD,
`TCP_KEEPALIVE_THRESHOLD` on Solaris ≥ 11, `TCP_KEEPALIVE` on macOS
(distinct from Solaris's same-name option). Windows uses a totally
different `SIO_KEEPALIVE_VALS` ioctl.

### `pq_recvbuf` (897)
- Left-shifts any unread data to the start of the buffer before
  recv'ing more; so the buffer is never more than `PQ_RECV_BUFFER_SIZE`
  but the "live window" can be anywhere in it. [verified-by-code, pqcomm.c:900-912]
- Switches the socket to blocking before `secure_read`. Loops on EINTR.
- **Critical:** errors are logged at `COMMERROR`, NEVER at
  ERROR/FATAL that would try to write to the client. The comment is
  emphatic about recursion → stack overflow. [from-comment, pqcomm.c:932-942]

### `pq_getmessage` (1203) — the protocol-frame reader
- Validates `4 ≤ len ≤ maxlen`; bad length → COMMERROR + return EOF.
- `enlargeStringInfo` is wrapped in PG_TRY so OOM doesn't lose protocol
  sync — the catch arm `pq_discardbytes(len)` the malicious giant
  message and then rethrows.
- Clears `PqCommReadingMsg` only on success / after sync recovery.

### `internal_flush_buffer` (1362) — the send workhorse
- Returns 0 on EAGAIN/EWOULDBLOCK in non-blocking mode (caller retries).
- On real send failure: drop buffered data (`*start = *end = 0`), set
  `ClientConnectionLost = 1` and `InterruptPending = 1` so the next
  `CHECK_FOR_INTERRUPTS` terminates the backend. Repeated send errors
  deduplicated via `static int last_reported_send_errno`. [verified-by-code, pqcomm.c:1391-1417]

### `Lock_AF_UNIX` / `Setup_AF_UNIX` (685, 720)
- "Abstract" Linux sockets (prefix `@`) skip both lock-file and chmod.
  [verified-by-code, pqcomm.c:688-690, 723-725]
- For real socket files: create a lock file, unlink any stale socket
  (safe because we hold the interlock), append to `sock_paths`.
- Setup_AF_UNIX must run BEFORE listen() to close the "unwanted
  connection" race window. [from-comment, pqcomm.c:728-731]

### `pq_check_connection` (2056)
- Modifies the FeBeWaitSet socket slot to `WL_SOCKET_CLOSED` (POLLRDHUP
  on Linux) and polls with timeout 0. Latch-event short-circuit: reset
  latch + retry, so a spurious latch wakeup doesn't mask the closed
  signal. [verified-by-code, pqcomm.c:2065-2087]

## Invariants & gotchas

- **Outgoing-message atomicity.** Every message goes through one
  `pq_putmessage` call. No partial-message API. ereport(ERROR)
  mid-StringInfo-build is safe because pqformat owns the half-built
  buffer in its own memory context. [from-comment, pqcomm.c:11-15]
- **`PqCommReadingMsg` is the protocol-sync interlock.** Any code path
  that calls `pq_startmsgread` without a matching `pq_endmsgread` /
  successful `pq_getmessage` will trip the FATAL "protocol
  synchronization was lost" on the next attempt. [verified-by-code, pqcomm.c:1148-1153]
- **`PqCommBusy` re-entrancy guard.** `socket_putmessage` /
  `pq_putmessage_v2` / `socket_flush` set it across their work; if an
  ereport during that work tries to send (e.g., a warning), they
  silently return 0. This is the SIGQUIT-during-putmessage scenario
  for `quickdie()`. [from-comment, pqcomm.c:1482-1487]
- **`COMMERROR` not `ERROR` on socket I/O failure.** Sending an
  ereport(ERROR) to the client when the socket is broken recurses into
  pqcomm. Every `secure_read` / `secure_write` failure path therefore
  uses `ereport(COMMERROR, …)` which logs server-side only.
  [from-comment, pqcomm.c:932-942, 1031-1044, 1391-1395]
- **Backend socket is non-blocking; latches give blocking semantics.**
  `pq_init` sets `pg_set_noblock(port->sock)` (non-Win32). All
  "blocking" reads/writes loop via `WaitLatchOrSocket` (through
  `secure_read`/`secure_write` in be-secure.c). This is what lets
  CHECK_FOR_INTERRUPTS work in the middle of I/O. [from-comment, pqcomm.c:289-294]
- **`socket_close` does NOT close(2) the FD.** Comment: lets client see
  a synchronous close. The FD leaks until process exit. Set
  `MyProcPort->sock = PGINVALID_SOCKET` to block further use.
  [from-comment, pqcomm.c:382-393]
- **`pq_putmessage_noblock` grows the send buffer arbitrarily.** Used
  to stage a whole COPY / replication record in one shot. Memory cost
  paid out of `TopMemoryContext`. [verified-by-code, pqcomm.c:1534-1539]
- **`pq_getmessage`'s `maxlen` is the only DoS guard.** It is the
  caller's responsibility to pass a tight bound — `auth.c` uses ~16 KB
  for startup packets, the main protocol loop uses `PQ_LARGE_MESSAGE_LIMIT`
  (1 GB). Trusting an extension caller is dangerous. [verified-by-code, pqcomm.c:1223-1229]
- **The keepalive GUC `assign_*` hooks don't validate — they just
  apply.** "The kernel API provides no way to test a value without
  setting it" so PG just SET and reports via `ereport(LOG)` on failure.
  Effectively a stealth no-op on platforms missing the option. [from-comment, pqcomm.c:1955-1968]
- **Windows SO_SNDBUF heuristic.** `pq_init` bumps Windows OS send
  buffer to ≥ `PQ_SEND_BUFFER_SIZE * 4` (32 KB), guarded against
  unnecessary writes that would disable Windows 7 dynamic send
  buffering. [from-comment, pqcomm.c:226-246]
- **`pq_init` ereports FATAL on getsockname/setsockopt failure.**
  Aggressive: the postmaster will respawn the backend, but a
  consistently-failing system call can become a fork-bomb. [verified-by-code, pqcomm.c:192-194,210-214,219-222]
- **`ListenServerPort` continues on per-address failure.** Returns
  STATUS_ERROR only if NO address was added. So `listen_addresses =
  '0.0.0.0,::'` with broken IPv6 stack will silently succeed on IPv4
  only. [verified-by-code, pqcomm.c:675-677]

## Cross-refs

- Header: `source/src/include/libpq/libpq.h` (`PqCommMethods`),
  `source/src/include/libpq/libpq-be.h` (`Port`)
- TLS layer above: `source/src/backend/libpq/be-secure.c`,
  `be-secure-openssl.c`, `be-secure-gssapi.c`
- Vtable peer: `source/src/backend/libpq/pqmq.c` (parallel-worker redirect)
- Caller: `source/src/backend/tcop/postgres.c` (`PostgresMain`,
  `SocketBackend`), `auth.c`
- Latch primitive: `source/src/backend/storage/ipc/latch.c`
- Postmaster listen orchestration: `source/src/backend/postmaster/postmaster.c`

## Potential issues

- **[ISSUE-correctness: pq_getmessage int32 length, signed read]**
  `pqcomm.c:1206,1221-1229` — `len` is `int32`. After `pg_ntoh32` we
  reinterpret a `uint32` wire value as signed. A wire value of
  `0x80000000` would become negative and fail the `len < 4` check
  (caught), but a value like `0x7FFFFFFF` is ~2 GB and passes if
  `maxlen` is large enough. Then `enlargeStringInfo(s, len)` is called
  with a 2 GB request — handled by OOM path (PG_TRY catches and
  discards). The 1 GB `PQ_LARGE_MESSAGE_LIMIT` cap in callers is the
  real defense. Worth verifying every external `pq_getmessage(s,
  maxlen)` site uses a sensible bound. severity: maybe
- **[ISSUE-correctness: PqSendBuffer can grow without bound across
  the backend's lifetime]** `pqcomm.c:1534-1539` — `repalloc(…,
  required)` and `PqSendBufferSize = required` is never shrunk. A
  one-time 100 MB message in a long-lived backend leaves a 100 MB
  buffer. Memory-pressure-blind. severity: maybe
- **[ISSUE-undocumented-invariant: socket_close leaks the FD by
  design]** `pqcomm.c:382-393` — documented in comments but worth
  re-flagging: the kernel reaps the FD only at process exit. Combined
  with the per-connection fork model this is fine, but extensions
  cloning the backend process must remember this. severity: nit
- **[ISSUE-leak: last_reported_send_errno is static, never reset on
  successful reset]** `pqcomm.c:1365,1400-1402,1420` — reset to 0 only
  after a successful send completes. After connection drop + new
  connection (which gets a new backend, so different process — fine).
  Within one backend life, edge cases where errno repeats could
  suppress useful logs. severity: nit
- **[ISSUE-question: TCP_USER_TIMEOUT GUC not validated against
  keepalive sum]** `pqcomm.c:1906-1949` — `tcp_user_timeout` should
  usually be ≥ `keepalive_idle + keepalive_intvl * keepalive_count`
  to mean anything useful. PG doesn't enforce or warn. severity: nit
- **[ISSUE-correctness: AcceptConnection 100 ms backoff is a fixed
  sleep]** `pqcomm.c:813-815` — under sustained EMFILE, postmaster
  sleeps 0.1 s per accept failure. Could starve other postmaster
  duties (signal handling, dead-child reap). Adaptive backoff would
  be friendlier. severity: nit
- **[ISSUE-undocumented-invariant: abstract-socket lock-skip means no
  stale-socket cleanup]** `pqcomm.c:688-690` — abstract Linux sockets
  bypass `Lock_AF_UNIX` (so also bypass the stale-unlink that follows
  it). The abstract namespace cleans itself on socket close, so this
  is correct, but the rationale isn't spelled out. severity: nit
- **[ISSUE-leak: ListenServerPort silently logs partial success]**
  `pqcomm.c:675-677` — when `listen_addresses` resolves to multiple
  addresses and some fail, only `LOG`-level messages are emitted; the
  postmaster proceeds with whatever bound successfully. An admin
  expecting IPv6 may not notice they only got IPv4. severity: maybe

## Tally

`[verified-by-code]=28 [from-comment]=17 [inferred]=0`
