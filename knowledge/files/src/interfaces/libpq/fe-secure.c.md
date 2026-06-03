---
path: src/interfaces/libpq/fe-secure.c
anchor_sha: 4b0bf0788b0
loc: 581
depth: medium
---

# fe-secure.c

- **Source path:** `source/src/interfaces/libpq/fe-secure.c`
- **Lines:** 581
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-secure-openssl.c` (`pgtls_*` implementations), `fe-secure-gssapi.c` (`pg_GSS_read/write`, `pqsecure_open_gss`), `fe-secure-common.c` (cert-name matching), `libpq-int.h` (`PGconn.ssl_in_use`, `gssenc`, `sigpipe_so`, `sigpipe_flag`, `write_failed`).

## Purpose

The **dispatcher** between cleartext, TLS, and GSSAPI-encrypted I/O. Every libpq read/write goes through `pqsecure_read`/`pqsecure_write` here, which then branch to `pgtls_*` (USE_SSL) or `pg_GSS_*` (ENABLE_GSS) or the raw socket path. Also owns SIGPIPE masking and the connection-level write-failure latch. [verified-by-code, fe-secure.c:1-17]

## Public surface

- `PQsslInUse(conn)` (102) — returns `conn->ssl_in_use`. [verified-by-code, fe-secure.c:102-108]
- `PQinitSSL(do_init)` / `PQinitOpenSSL(do_ssl, do_crypto)` (116-132) — **no-ops since OpenSSL 1.1.0**. Kept for ABI. [verified-by-code, fe-secure.c:116-132]
- `pqsecure_open_client(conn)` (137-146) — dispatch to `pgtls_open_client` if USE_SSL else `PGRES_POLLING_FAILED`. [verified-by-code, fe-secure.c:137-146]
- `pqsecure_close(conn)` (151-157) — dispatch to `pgtls_close` if USE_SSL.
- `pqsecure_read(conn, ptr, len)` (166-190) — read dispatcher: tls / gss / raw.
- `pqsecure_raw_read(conn, ptr, len)` (192-244) — direct `recv()` with errno classification.
- `pqsecure_write(conn, ptr, len)` (266-290) — write dispatcher.
- `pqsecure_raw_write(conn, ptr, len)` (315-422) — direct `send()` with SIGPIPE masking and write-fail latching.
- `pq_block_sigpipe` / `pq_reset_sigpipe` (503-579) — POSIX thread-local SIGPIPE blocker for the `MSG_NOSIGNAL`-less path.

## Dummy versions (built-without-X stubs)

When `!USE_SSL` (425-452): `PQgetssl`, `PQsslStruct`, `PQsslAttribute`, `PQsslAttributeNames` return NULL/empty.
When `!USE_OPENSSL` (458-477): `PQ*SSLKeyPassHook_OpenSSL` no-ops.
When `!ENABLE_GSS` (480-494): `PQgetgssctx`, `PQgssEncInUse` return NULL/0.

## SIGPIPE handling (POSIX)

Three modes (line 53-95):

1. **Connection-level mask** (`conn->sigpipe_so`): caller has set `SO_NOSIGPIPE` on the socket (macOS only). Nothing to do at write time.
2. **Per-send flag** (`conn->sigpipe_flag`): `MSG_NOSIGNAL` is supported, pass it on every `send`.
3. **Fallback**: `pq_block_sigpipe` saves current sigmask, blocks SIGPIPE for this thread; after the send, `pq_reset_sigpipe` clears any pending SIGPIPE if `got_epipe`, then restores the saved mask.

The fallback path is used when neither `SO_NOSIGPIPE` nor `MSG_NOSIGNAL` works. The fallback assumes the C library doesn't queue multiple SIGPIPEs (line 538-541) — true on every Unix worth supporting, but documented as an assumption. [from-comment, fe-secure.c:538-548]

## Write-fail latch (subtle)

`pqsecure_raw_write` has a deeply weird contract:

- A "soft" retryable error (EAGAIN/EWOULDBLOCK/EINTR) returns -1 normally.
- A "hard" error (EPIPE/ECONNRESET/other) latches `conn->write_failed = true`, stores an error in `conn->write_err_msg`, **and returns `len` (claiming success)**. [verified-by-code, fe-secure.c:378-413]
- Subsequent writes short-circuit: `if (conn->write_failed) return len;` (333). All further data is silently discarded.

**Why?** Some TCP stacks report write failure before all incoming data has been read; libpq wants to keep reading to surface a real server-side error before reporting the dead-write. The error is reported lazily once the read side also dies. [from-comment, fe-secure.c:294-313]

**Implication:** any code in libpq that uses `pqsecure_raw_write` and observes "success" cannot trust the bytes hit the wire. The flush path elsewhere must consult `conn->write_failed`. This is a hardening pattern, not a bug — but anyone calling at this layer needs to know it.

## Read-side dispatch

`pqsecure_read` (166-190) probes in order:

1. `conn->ssl_in_use` → `pgtls_read` (OpenSSL).
2. `conn->gssenc` → `pg_GSS_read` (GSS unwrap).
3. Otherwise → `pqsecure_raw_read` (plain `recv`).

The two flags are **mutually exclusive** by protocol negotiation — but the dispatch doesn't assert that; if both got set (driver bug), TLS wins. [verified-by-code, fe-secure.c:171-187]

## Invariants & gotchas

- `pqsecure_raw_read` translates `errno = 0` (rare) to EOF (`n = 0`), line 227-230 — defensive against drivers that don't set errno on partial reads.
- `pqsecure_raw_read` does NOT set a connection-level "read failed" latch; transient EAGAIN is the caller's job to handle. Hard failure → message in `errorMessage`, but no latch.
- `EINTR` is treated as retryable (no message), consistent with POSIX. [verified-by-code, fe-secure.c:216-218]
- `pq_block_sigpipe` saves the prior pending SIGPIPE state (line 517-528) so that `pq_reset_sigpipe` can leave a pre-existing pending signal in place rather than swallowing it (line 561-572).

## Potential issues

- ISSUE-libpq-secure-001 (severity: maybe) — the "claim success on hard write failure" pattern (line 396, 411) is subtle. If a caller does its own retry-on-short-write loop and is unaware of the latch, it'll loop forever discarding bytes into `write_failed`. The current libpq state machine in `fe-misc.c` does check the latch, but external code reusing this function via libpq-int.h might not. [verified-by-code, fe-secure.c:333-334, 378-413]
- ISSUE-libpq-secure-002 (severity: maybe) — `pqsecure_raw_write` `goto retry_masked` (361) clears `sigpipe_flag` on receiving EINVAL with MSG_NOSIGNAL set. This permanently disables MSG_NOSIGNAL for the connection but never re-enables. If the EINVAL was transient (unlikely but possible kernel quirk), all subsequent sends pay the sigmask-block overhead. [verified-by-code, fe-secure.c:357-362]
- ISSUE-libpq-secure-003 (severity: maybe) — the `gssenc` branch in `pqsecure_read` only fires if USE_SSL was either not chosen or `ssl_in_use==0`. There's no path that mixes TLS and GSS encryption. If a future protocol allowed both (unlikely), only TLS would dispatch. [inferred, fe-secure.c:171-187]

## Cross-refs

- TLS implementation: `fe-secure-openssl.c` (`pgtls_open_client`, `pgtls_read`, `pgtls_write`, `pgtls_close`).
- GSS encryption: `fe-secure-gssapi.c` (`pg_GSS_read`, `pg_GSS_write`, `pqsecure_open_gss`).
- Higher-level callers: `fe-misc.c::pqReadData`, `pqSendSome`.
- See also: `knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md`.

## Tally
`[verified-by-code]=14 [from-comment]=3 [from-readme]=0 [inferred]=1 [unverified]=0`
