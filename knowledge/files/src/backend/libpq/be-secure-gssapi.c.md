---
path: src/backend/libpq/be-secure-gssapi.c
anchor_sha: 4b0bf0788b0
loc: 790
depth: deep
---

# be-secure-gssapi.c

- **Source path:** `source/src/backend/libpq/be-secure-gssapi.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 790

## Purpose

GSSAPI **transport encryption** — the protocol-level alternative to
TLS, negotiated up-front via the GSSENCRequest startup packet just
as TLS is negotiated via SSLRequest. After
`secure_open_gssapi()` succeeds, all subsequent reads and writes go
through `be_gssapi_read` / `be_gssapi_write` which wrap each chunk
of PostgreSQL protocol bytes in a `gss_wrap` packet with a 4-byte
network-order length header. Distinct from `auth.c::pg_GSS_recvauth`
which performs **GSSAPI authentication** (only); this file handles
the *encryption channel*. [from-comment, be-secure-gssapi.c:1-12,
30-62]

The packet framing (`uint32 length || gss_wrap(payload)`) is wire
protocol and cannot change without a major-version bump:
`PQ_GSS_MAX_PACKET_SIZE = 16384` is hardcoded into the spec
(be-secure-gssapi.c:54). The authentication exchange uses a separate
larger buffer (`PQ_GSS_AUTH_BUFFER_SIZE = 65536`) because GSSAPI
auth tokens can be much larger than the steady-state encrypted
packets (be-secure-gssapi.c:56-62).

## Public API surface

- `ssize_t be_gssapi_write(Port *port, const void *ptr, size_t len)` —
  `be-secure-gssapi.c:105`. Encrypts and queues up to `len` bytes
  into the static `PqGSSSendBuffer`, then writes via
  `secure_raw_write`. Returns -1 with errno on retryable / fatal
  error; the all-or-nothing return is a deliberate simplification
  (be-secure-gssapi.c:115-129 — references commit `d053a879b` for the
  past bugs from partial-write reporting).
- `ssize_t be_gssapi_read(Port *port, void *ptr, size_t len)` —
  `be-secure-gssapi.c:272`. Reads one encrypted packet into
  `PqGSSRecvBuffer`, decrypts via `gss_unwrap` into
  `PqGSSResultBuffer`, then doles out bytes to the caller. Returns
  early as soon as any data has been delivered.
- `ssize_t secure_open_gssapi(Port *port)` — `be-secure-gssapi.c:505`.
  The transport-negotiation loop: client sends first, we loop
  `gss_accept_sec_context` until `GSS_S_COMPLETE`, switch buffer
  sizes from AUTH (64k) to MAX (16k), compute the wrap size limit
  via `gss_wrap_size_limit`, set `port->gss->enc = true`. Returns 0
  or -1.
- Accessors used by SQL functions and `pg_stat_gssapi`:
  - `bool be_gssapi_get_auth(Port *port)` — `be-secure-gssapi.c:746`.
  - `bool be_gssapi_get_enc(Port *port)` — `be-secure-gssapi.c:758`.
  - `const char *be_gssapi_get_princ(Port *port)` —
    `be-secure-gssapi.c:771`. The principal name as set in
    `auth.c::pg_GSS_checkauth`.
  - `bool be_gssapi_get_delegation(Port *port)` —
    `be-secure-gssapi.c:784`.

## Internal landmarks / file-scope state

- **Static buffers** (be-secure-gssapi.c:67-86). Because only one
  GSS-encrypted connection per backend, all state is process-local:
  - `PqGSSSendBuffer` / `PqGSSSendLength` / `PqGSSSendNext` /
    `PqGSSSendConsumed` — outbound queue + retry bookkeeping.
  - `PqGSSRecvBuffer` / `PqGSSRecvLength` — inbound encrypted buffer.
  - `PqGSSResultBuffer` / `PqGSSResultLength` / `PqGSSResultNext` —
    decrypted plaintext buffer.
  - `PqGSSMaxPktSize` — max payload that fits in a single output
    packet after `gss_wrap` overhead; computed via
    `gss_wrap_size_limit` (be-secure-gssapi.c:727-735).
- **`read_or_wait`** (be-secure-gssapi.c:433) — blocking helper used
  only during transport negotiation; waits on
  `WaitLatchOrSocket(WL_SOCKET_READABLE | WL_EXIT_ON_PM_DEATH)`.
- **Confidentiality assertion** — `be_gssapi_read` errors with
  `COMMERROR` if `conf_state == 0` from `gss_unwrap`
  (be-secure-gssapi.c:403-409). The peer asked for encryption but
  sent an integrity-only packet — that's a downgrade attempt, refuse.
- **Buffer-size handoff** at the end of `secure_open_gssapi`
  (be-secure-gssapi.c:707-722) — `free(big)` then `malloc(small)`.
  The big AUTH buffer is no longer needed once the steady-state
  PROTOCOL kicks in; freeing keeps the per-backend resident set
  small in a busy server.

## Invariants & gotchas

- **`PQ_GSS_MAX_PACKET_SIZE = 16384` is part of the wire protocol.**
  Both sides have to agree because we hand entire packets to GSSAPI.
  Comment at be-secure-gssapi.c:46-53: "this #define is effectively
  part of the protocol spec and can't ever be changed."
- **`be_gssapi_write` is all-or-nothing.** If it returns -1 mid-write
  the caller must retry with the same or more data; if it returns
  -1 with errno EWOULDBLOCK the caller retries the same buffer.
  `PqGSSSendConsumed` tracks how many *source* bytes have already
  been encrypted into the buffer, so the retry sanity-checks
  `len >= PqGSSSendConsumed` (be-secure-gssapi.c:131-136 —
  "GSSAPI caller failed to retransmit all data needing to be
  retried"). Violating this kills the connection with `ECONNRESET`.
- **No `elog(FATAL)` inside read/write** — would recurse into the
  client-error path. Use `COMMERROR` + return errno. Discipline
  noted in the header (be-secure-gssapi.c:99-103).
- **Static state means at most one GSS connection per backend** —
  fine for PG's per-connection-fork model; would be a problem in a
  threaded server.
- **Confidentiality is required, not integrity-only.** The
  `conf_state == 0` check (be-secure-gssapi.c:403) means we reject
  even cryptographically-integrity-checked unencrypted packets.
  This is the right thing for `wal_level=replica` over GSS, etc.
- **Oversize input check** on the wire (be-secure-gssapi.c:358-366)
  prevents a malicious client from forcing arbitrary memory
  allocations during decode. Same check for the auth-time buffer
  (be-secure-gssapi.c:587-594).
- **Delegated credentials** are pulled out and stored via
  `pg_store_delegated_credential` only if the client offered them
  AND `pg_gss_accept_delegation` GUC is true (auth.c:1031-1034 and
  be-secure-gssapi.c:629-633).
- **GSSAPI auth happens differently depending on whether encryption
  is in use.** `secure_open_gssapi` runs `gss_accept_sec_context`
  itself and stores the context in `port->gss->ctx`; then
  `auth.c:ClientAuthentication` notices `port->gss->enc == true` and
  calls `pg_GSS_checkauth` directly (auth.c:558-559) — *no second*
  `gss_accept_sec_context` exchange. The auth context comes from
  the encryption negotiation.

## Cross-refs

- Header: `knowledge/files/src/include/libpq/libpq.h.md` (declares
  `secure_open_gssapi`).
- GSSAPI auth path: `knowledge/files/src/backend/libpq/auth.c.md`
  (`pg_GSS_recvauth`, `pg_GSS_checkauth`).
- Shared helpers: `src/backend/libpq/be-gssapi-common.c`.
- Startup-time dispatch that calls `secure_open_gssapi`: see
  `ProcessStartupPacket` in `tcop/backend_startup.c`.
- Frontend counterpart: `src/interfaces/libpq/fe-secure-gssapi.c`
  (must agree on `PQ_GSS_MAX_PACKET_SIZE`).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: PQ_GSS_MAX_PACKET_SIZE must match
  libpq's value]** be-secure-gssapi.c:54 — there is no static-assert
  or runtime check across the two implementations. A mismatched
  libpq client would see corrupt packet length parsing. Severity:
  maybe.
- **[ISSUE-correctness: confidentiality-required check is one-way]**
  be-secure-gssapi.c:403-409 — the server requires `conf_state == 1`
  on receive but does it set `conf_req_flag=1` when calling
  `gss_wrap`? Spot-check be-secure-gssapi.c:206-225 — yes,
  `gss_wrap(&minor, gctx, 1, GSS_C_QOP_DEFAULT, ...)` (the `1` is
  `conf_req_flag`). OK.
- **[ISSUE-leak: PqGSSResultBuffer holds decrypted plaintext
  indefinitely]** be-secure-gssapi.c:411-412 — `memcpy` from the
  GSSAPI-allocated `output.value` into our static buffer, but the
  buffer persists across calls and is not zeroed when consumed. A
  later `pg_log_backend_memory_contexts` or core dump would expose
  recent plaintext. Severity: maybe.
- **[ISSUE-style: globals not in a struct]** be-secure-gssapi.c:69-86
  — nine related statics. Wrapping in a `static struct
  PqGSSState { ... } gss_state` would clarify ownership. Severity:
  nit.
- **[ISSUE-question: malloc not palloc for buffers]**
  be-secure-gssapi.c:533-535 — uses raw `malloc` (so the buffers
  survive a per-connection MemoryContext reset). Comment says
  "By malloc'ing the buffers at this point, we avoid wasting static
  data space in processes that will never use them, and we ensure
  that the buffers are sufficiently aligned." OK, but means leak
  inspection tools see them as "never freed". Severity: nit.
- **[ISSUE-correctness: secure_open_gssapi does not free big buffers
  on early-error return]** be-secure-gssapi.c:559-704 — if `read_or_wait`
  returns -1 inside the loop (be-secure-gssapi.c:570-571) the malloc'd
  AUTH buffers leak. The backend exits soon thereafter so practically
  harmless. Severity: nit.

## Tally

`[verified-by-code]=16 [from-comment]=8 [inferred]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
