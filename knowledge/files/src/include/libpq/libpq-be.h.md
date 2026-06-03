# libpq-be.h

- **Source path:** `source/src/include/libpq/libpq-be.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions for structures and externs used by the postmaster during
client authentication." Defines the `Port` struct — the backend-side
per-connection state, accessed globally as `MyProcPort` — plus the secure
transport (SSL/GSS) hook prototypes. Backend-internal: **NOT exported to
clients** [from-comment].

## Public API surface

- `ClientConnectionInfo { authn_id, auth_method }` — copied to parallel
  workers (Port is not). Serialized via `SerializeClientConnectionInfo()`
  [from-comment]. `authn_id` is the post-auth identity that fed the
  pg_ident usermap; NULL under `trust` [from-comment].
- `Port` — per-connection state; allocated in `TopMemoryContext`
  [from-comment]. Fields fall into groups:
  - Socket / addressing: `sock`, `noblock`, `proto`, `laddr`, `raddr`,
    `remote_host`, `remote_hostname`, `remote_hostname_resolv` (+1/-1/0/-2
    tri-state), `remote_hostname_errcode`, `remote_port`, `local_host[64]`.
  - Startup-packet payload: `database_name`, `user_name`, `cmdline_options`,
    `guc_options`, `application_name` (latter only used for the
    "connection authorized" log; the GUC takes over post-startup
    [from-comment]).
  - Auth cycle: `HbaLine *hba`.
  - TCP keepalives: `default_keepalives_idle`/`_interval`/`_count`,
    `default_tcp_user_timeout`, plus current values; default sentinel is
    `0` (AF_UNIX or unknown) and `-1` (getsockopt failed) [from-comment].
  - SCRAM: `scram_ClientKey[SCRAM_MAX_KEY_LEN]`, `scram_ServerKey[...]`,
    `has_scram_keys`.
  - GSSAPI: `pg_gssinfo *gss` when `ENABLE_GSS||ENABLE_SSPI`; `void *gss`
    otherwise to keep struct offsets stable for extension ABI
    [from-comment].
  - SSL: `ssl_in_use`, `peer_cn`, `peer_dn`, `peer_cert_valid`,
    `alpn_used`, `last_read_was_eof`; OpenSSL `SSL *ssl` and `X509 *peer`
    when `USE_OPENSSL`, else `void *`.
  - SSL pre-buffered bytes: `raw_buf`, `raw_buf_consumed`,
    `raw_buf_remaining` — the "unread" hack so the SSL layer can re-read
    bytes that the upper layer already consumed [from-comment].
- `ClientSocket { sock, raddr }` — accepted-fd handoff from postmaster.
- `pg_gssinfo { outbuf, cred, ctx, name, princ, auth, enc, delegated_creds }`
  — GSS per-connection state.
- SSL hooks (under `USE_SSL`): `be_tls_init`, `be_tls_destroy`,
  `be_tls_open_server`, `be_tls_close`, `be_tls_read`/`_write`,
  `be_tls_get_cipher_bits`, `be_tls_get_version`, `be_tls_get_cipher`,
  `be_tls_get_peer_subject_name`, `be_tls_get_peer_issuer_name`,
  `be_tls_get_peer_serial`, `be_tls_get_certificate_hash` (for SCRAM
  channel binding `tls-server-end-point`) [from-comment]; init hook
  `openssl_tls_init_hook`.
- GSS read/write/getters (under `ENABLE_GSS`): `be_gssapi_read`,
  `be_gssapi_write`, `be_gssapi_get_auth`, `_get_enc`, `_get_princ`,
  `_get_delegation`.
- TCP keepalive setters/getters: `pq_getkeepalivesidle/interval/count`,
  `pq_gettcpusertimeout`, and the `pq_set*` mirrors.
- Globals: `FrontendProtocol`, `MyClientConnectionInfo`.

## Key constants

- `FILE_DH2048` — RFC 3526 2048-bit DH parameters baked into the source;
  comment notes that `DH_check()` flags `DH_NOT_SUITABLE_GENERATOR`
  because "leaking a bit is preferred" [from-comment].

## Internal landmarks

- `Port` lives in `TopMemoryContext` and all pointed-to allocations must
  too [from-comment]. Forgetting this on a new field leaks across
  PG_CATCH or context resets.
- The `void *gss`/`void *ssl`/`void *peer` placeholders for `!ENABLE_GSS`
  and `!USE_OPENSSL` are deliberate ABI shims — extensions that look up
  field offsets must still work [from-comment].
- `raw_buf` triplet is a documented layering hack: the SSL library re-reads
  bytes the upper layer already pulled from the socket.

## Cross-refs

- Related backend: `src/backend/libpq/pqcomm.c`, `src/backend/libpq/auth.c`,
  `src/backend/libpq/be-secure*.c`, `src/backend/libpq/be-fsstubs.c`.
- Related: `knowledge/files/src/include/libpq/hba.h.md`,
  `knowledge/files/src/include/libpq/pqcomm.h.md`,
  `knowledge/files/src/include/libpq/scram.h.md`,
  `knowledge/files/src/include/libpq/pg-gssapi.h.md`.

## Potential issues

- **[ISSUE-leak: SCRAM keys live in Port for the connection lifetime]**
  `libpq-be.h:186-188` — `scram_ClientKey` / `scram_ServerKey` (SHA-256
  keys derived from the user's password) sit in `Port` for the life of the
  backend after a successful SCRAM auth. They are required for channel-
  binding / replication-cred passthrough, but nothing in the header asks
  callers to zero them on connection teardown or after their last use.
  Worth confirming whether the per-backend `TopMemoryContext` teardown
  actually zeroes memory or just frees it. Severity: maybe.
- **[ISSUE-leak: peer_cn / peer_dn lifetime not stated]** `libpq-be.h:209-210`
  — these come from the client certificate; nothing in the header says
  whether they are escaped before being interpolated into error messages
  or log lines. CN/DN with embedded control chars or quoted-printable
  could break log scrapers. Severity: maybe.
- **[ISSUE-undocumented-invariant: has_scram_keys must be checked before keys are used]**
  `libpq-be.h:186-188` — the comment says "true if the above two are
  valid" but does not say what state the key bytes are in when the flag is
  false (zero, uninitialized stack, leftover from prior auth attempt). A
  callsite that reads the keys without consulting the flag could leak
  whatever happens to be there. Severity: maybe.
- **[ISSUE-doc-drift: comment says raw_buf_remaining ssize_t, code matches]**
  `libpq-be.h:230-240` — minor: the comment refers to "bytes unread" and
  `raw_buf_consumed = 0`, but the field is `ssize_t`, which means a
  signed value the caller is expected to leave non-negative. No invariant
  is asserted at the type level. Severity: maybe.
- **[ISSUE-stale-todo: FILE_DH2048 is the RFC 3526 group]** `libpq-be.h:265-273`
  — hardcoded MODP-2048 from RFC 3526 (2003). The PG ecosystem has long
  since moved toward ECDHE; this fallback exists for clients that don't
  pick an ECDHE cipher. Worth a Phase D ticket to consider whether the
  fallback can be raised to a larger MODP group or dropped. Severity:
  maybe.

## Tally

`[verified-by-code]=10 [from-comment]=10 [inferred]=2`
