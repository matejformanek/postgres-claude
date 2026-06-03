---
path: src/interfaces/libpq/fe-secure-gssapi.c
anchor_sha: 4b0bf0788b0
loc: 777
depth: deep
---

# fe-secure-gssapi.c

- **Source path:** `source/src/interfaces/libpq/fe-secure-gssapi.c`
- **Lines:** 777
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-gssapi-common.c` (helpers), `fe-secure.c` (dispatcher), `src/backend/libpq/be-secure-gssapi.c` (server counterpart, symmetric), `libpq-int.h` (`PGconn.gss_*Buffer` family, `gctx`, `gcred`, `gssenc`).

## Purpose

**GSSAPI as a TLS-like transport.** When `gssencmode=require` or `prefer`, libpq negotiates a GSS context and then wraps/unwraps every byte through `gss_wrap`/`gss_unwrap`. This file implements:

1. `pqsecure_open_gss` — the transport-negotiation state machine, analogous to OpenSSL's `SSL_connect` loop. [verified-by-code, fe-secure-gssapi.c:480-749]
2. `pg_GSS_write` / `pg_GSS_read` — the encrypt/decrypt layer, called by `fe-secure.c::pqsecure_write/read` when `conn->gssenc` is true. [verified-by-code, fe-secure-gssapi.c:92-425]
3. `PQgetgssctx` / `PQgssEncInUse` — public introspection.

## Required flags (line 26-27)

```
GSS_C_MUTUAL_FLAG | GSS_C_REPLAY_FLAG | GSS_C_SEQUENCE_FLAG |
GSS_C_CONF_FLAG  | GSS_C_INTEG_FLAG
```

Reads: **mutual auth + replay protection + sequence enforcement + confidentiality + integrity** — all required. [verified-by-code, fe-secure-gssapi.c:26-27]

A GSS provider that can't deliver all five fails negotiation. This is the corresponding setting to TLS's "cipher suite must provide confidentiality+integrity".

## Wire format

```
[uint32 length (network order)] [<length> bytes of gss_wrapped data]
```

- `PQ_GSS_MAX_PACKET_SIZE = 16384` (53) — **part of the wire protocol**, cannot change. [from-comment, fe-secure-gssapi.c:43-52]
- `PQ_GSS_AUTH_BUFFER_SIZE = 65536` (61) — only used during the initial negotiation, where GSSAPI tokens can be up to ~64KB.

After negotiation succeeds, the buffers are freed and re-allocated at the smaller post-auth size (lines 691-703).

## `pg_GSS_write` (92-252)

Streaming encrypt:

1. If `len < PqGSSSendConsumed`, fail with EINVAL — the caller must retransmit at least what was already consumed (line 120-126). Tracks already-encrypted bytes across retries (the "retry with partial progress" anti-pattern from commit d053a879b is explicitly avoided per the comment at lines 114-118).
2. Loop encrypting `PqGSSMaxPktSize`-sized chunks via `gss_wrap(gctx, 1=conf_req, GSS_C_QOP_DEFAULT)`.
3. **`conf_state == 0` check** (line 206-211): if GSSAPI couldn't deliver confidentiality, refuse to send. Important — without this, a misconfigured GSSAPI library could downgrade to integrity-only. [verified-by-code, fe-secure-gssapi.c:206-211]
4. **Overflow guard** (213-220): rejects encrypted output > `PQ_GSS_MAX_PACKET_SIZE - 4`. Prevents a misbehaving GSSAPI from producing a packet the peer cannot accept.
5. Sends via `pqsecure_raw_write`. Partial writes are remembered in `PqGSSSendNext`.

## `pg_GSS_read` (266-425)

Streaming decrypt:

1. Drain any already-decrypted leftover bytes from `PqGSSResultBuffer` first (286-310).
2. Read 4-byte length prefix.
3. **Length sanity** (352-358): reject `input.length > PQ_GSS_MAX_PACKET_SIZE - 4`. Prevents server-driven memory allocation amplification. [verified-by-code, fe-secure-gssapi.c:349-359]
4. Read the payload, call `gss_unwrap`.
5. **`conf_state == 0` check** (400-406): refuse to consume a non-confidential packet — symmetric with the write check.

## `pqsecure_open_gss` (480-749)

The negotiation loop. State machine implicit in `conn->gctx`:

- First call: `gctx == GSS_C_NO_CONTEXT`. Allocate large buffers (501-513), no input data — `gss_init_sec_context` produces the first client token.
- Subsequent calls: have an input token from the server in `PqGSSRecvBuffer`. Pass it to `gss_init_sec_context`.

Notable details:

- **Server "E" error packet detection** (572-591): if the first byte of the supposed length word is 'E' (ASCII), treat as a server error response in PostgreSQL text format. The check rests on the assumption that legitimate length-words begin with two zero bytes (network order, packet < 65536). [from-comment, fe-secure-gssapi.c:565-571]
- **Delegation** (634-649): if `conn->gssdelegation == "1"` AND credentials were acquired, set `GSS_C_DELEG_FLAG`. Otherwise no delegation (the conservative default).
- **Buffer resize on completion** (691-703): the 64KB negotiation buffers are freed and 16KB operational buffers allocated. Comment at 685-690 warns this is safe ONLY because `pqDropConnection` will free the buffers on reconnect.
- **`gss_wrap_size_limit`** (709-711): computes `PqGSSMaxPktSize` — the largest plaintext that fits in a 16KB wrapped packet given the QoP overhead. Used by `pg_GSS_write` chunking.

## Invariants & gotchas

- **`conf_state == 0` aborts both directions.** Defense against a GSS provider silently downgrading. Comment elsewhere says it would "use EIO for lack of a better idea" — a future revision could surface a clearer error code. [verified-by-code, fe-secure-gssapi.c:206-211, 400-406]
- **`PqGSSSendConsumed`** must NOT increase past `len` across calls (asserted at line 239). Violations mean an internal accounting bug — the assertion is the protection.
- **GSS_C_DELEG_FLAG** is opt-in via `gssdelegation=1`. Default off; comment in fe-auth.c flags that delegation should be conservative since it forwards user credentials. [verified-by-code, fe-secure-gssapi.c:634-649]
- **Service-name loading** uses `pg_GSS_load_servicename` (line 630) which builds `<krbsrvname>@<host>`. If `host` is empty, this fails — meaning `gssencmode` cannot be used with Unix-domain sockets that have no hostname. [verified-by-code, fe-secure-gssapi.c:630-632; fe-gssapi-common.c:95-99]
- **No principal validation on the peer side.** The client trusts `gss_init_sec_context`'s return; the actual server principal is implied by the SPN the client constructed. No explicit check that the server delivered a ticket for the expected principal — this is left to GSSAPI's mutual-auth flag. [inferred, fe-secure-gssapi.c:655-668]
- The error-detection heuristic for length-word == 'E' (572) breaks if a legitimate first packet is > 0x4400_0000 bytes — that's > 1 GB, well above `PQ_GSS_AUTH_BUFFER_SIZE`, so will be caught by the length check anyway. Safe but worth knowing. [from-comment, fe-secure-gssapi.c:567-571]

## Potential issues

- ISSUE-libpq-gssapi-001 (severity: maybe) — The error-packet detection (572-591) reads up to `PQ_GSS_AUTH_BUFFER_SIZE - 1` bytes and copies them verbatim into the error message buffer. A malicious server could fill 64KB of localized text into the libpq errorMessage. Not a security issue per se but a DoS surface. [verified-by-code, fe-secure-gssapi.c:572-591]
- ISSUE-libpq-gssapi-002 (severity: maybe) — `pqsecure_open_gss` uses `pg_GSS_have_cred_cache` to acquire credentials (637-638), but only when delegation was requested. On the non-delegation path, credentials are obtained inside `gss_init_sec_context` via the default credential. If the user's credential cache has been recently revoked, the call might appear to succeed on the wire (server sends a token) but fail at the final commit. [inferred, fe-secure-gssapi.c:634-649]
- ISSUE-libpq-gssapi-003 (severity: maybe) — `gss_release_cred(&minor, &conn->gcred); conn->gcred = GSS_C_NO_CREDENTIAL;` on success (line 680-681) — but on the failure paths (e.g. line 605, 666-667), `conn->gcred` is not released. A reconnect attempt may reuse a non-null `gcred` and inadvertently double-release. The leak is bounded but not zero. [verified-by-code, fe-secure-gssapi.c:680-681, 663-667]
- ISSUE-libpq-gssapi-004 (severity: maybe) — `pg_GSS_write` sets `SOCK_ERRNO(EIO)` for both "wrap error" and "oversize packet" (lines 202, 209, 218). Caller cannot distinguish between transport failure and protocol violation — both look like "EIO". A defense-in-depth issue: protocol-violation errors should be unambiguous. [verified-by-code, fe-secure-gssapi.c:201-220]

## Cross-refs

- Dispatcher: `fe-secure.c::pqsecure_read/write` (lines 171-187, 271-287).
- Negotiation orchestration: `fe-connect.c::PQconnectPoll` state `CONNECTION_GSS_STARTUP`.
- Server counterpart: `src/backend/libpq/be-secure-gssapi.c` (mirrors this file's structure).
- See also: `knowledge/files/src/interfaces/libpq/fe-secure.c.md`, `.../fe-gssapi-common.c.md`.

## Tally
`[verified-by-code]=17 [from-comment]=4 [from-readme]=0 [inferred]=2 [unverified]=0`
