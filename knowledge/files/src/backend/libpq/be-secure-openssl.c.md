---
path: src/backend/libpq/be-secure-openssl.c
anchor_sha: 4b0bf0788b0
loc: 2502
depth: deep
---

# be-secure-openssl.c

- **Source path:** `source/src/backend/libpq/be-secure-openssl.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 2502

## Purpose

The OpenSSL (and LibreSSL) implementation of every `be_tls_*` symbol
that `be-secure.c` shims out to. Builds and reconfigures the
`SSL_CTX`, parses `pg_hosts.conf` into per-hostname configs, runs
the TLS handshake (with SNI-driven cert-swap via the OpenSSL
client-hello callback), implements the cert verification callback,
extracts peer DN/CN, computes the channel-binding hash, maps PG's
TLS-version GUCs to OpenSSL macros, and converts OpenSSL error
codes to human-readable strings. The single largest file in the
libpq subdirectory.

`be_tls_init` is called both at server start AND on SIGHUP reload;
its all-or-nothing reload discipline (build a *new* `SSL_CTX`, only
swap on success) is the reason a bad TLS reload doesn't disrupt
existing connections. [verified-by-code, be-secure-openssl.c:148-583]

## Public API surface

All called from `be-secure.c` via thin wrappers:

- `int be_tls_init(bool isServerStart)` — `be-secure-openssl.c:149`.
  Configure or reconfigure the TLS subsystem. Parses pg_hosts.conf
  (if `ssl_sni`), builds an `SSL_CTX`, sets protocol min/max,
  disables tickets / compression / renegotiation / session cache,
  loads DH + ECDH, sets ciphers. **Builds a tentative SSL_CTX in a
  local MemoryContext; only commits to `SSL_context` on success
  (be-secure-openssl.c:552-569)** — failed reloads leave the running
  server untouched.
- `void be_tls_destroy(void)` — `be-secure-openssl.c:823`. Frees the
  global SSL_CTX and clears `ssl_loaded_verify_locations`.
- `int be_tls_open_server(Port *port)` — `be-secure-openssl.c:832`.
  Per-connection: `SSL_new`, wire up the `port_bio`, install the
  SNI / verify callbacks, `SSL_accept` loop, extract peer cert
  (`peer_cn`, `peer_dn`, RFC2253-formatted), reject embedded NULLs
  (CVE-2009-4034 class).
- `void be_tls_close(Port *port)` — `be-secure-openssl.c:1166`. Free
  `port->ssl`, `port->peer`, `port->peer_cn`, `port->peer_dn`.
- `ssize_t be_tls_read(Port *port, void *ptr, size_t len, int *waitfor)`
  / `be_tls_write(...)` — `be-secure-openssl.c:1196 / 1255`. Translate
  `SSL_read`/`SSL_write` outcomes into errno-style returns; map
  WANT_READ/WANT_WRITE to `*waitfor`.
- Connection-info accessors used by SQL functions and `pg_stat_ssl`:
  `be_tls_get_cipher_bits` (2198), `be_tls_get_version` (2212),
  `be_tls_get_cipher` (2221), `be_tls_get_peer_subject_name` (2230),
  `be_tls_get_peer_issuer_name` (2239), `be_tls_get_peer_serial`
  (2248), `be_tls_get_certificate_hash` (2269 — for SCRAM channel
  binding).
- Hook: `openssl_tls_init_hook` (be-secure-openssl.c:78) — overrideable
  to replace `default_openssl_tls_init`. Wired into custom passphrase
  handlers (`auth_delay`, `auth_passthrough` etc.).

## Internal landmarks

- **`init_host_context`** (be-secure-openssl.c:612). Per-hostname
  `SSL_CTX` build: `SSL_CTX_use_certificate_chain_file` →
  `check_ssl_key_file_permissions` (from be-secure-common.c) →
  `SSL_CTX_use_PrivateKey_file` → `SSL_CTX_check_private_key` →
  optional CA + CRL load via `SSL_CTX_load_verify_locations` /
  `X509_STORE_load_locations` (be-secure-openssl.c:740-810).
- **`sni_clienthello_cb`** (be-secure-openssl.c:1917). Hand-parses
  the `server_name` TLS extension out of the ClientHello (OpenSSL's
  servername callback fires too late). Matches case-insensitively
  per RFC 952/921 against `SSL_hosts->sni`; falls back to
  `default_host`; raises `SSL_AD_MISSING_EXTENSION` if no fallback.
- **`ssl_update_ssl`** (be-secure-openssl.c:1823) — swaps the cert /
  key / chain / CA into the live SSL object once SNI picks a config.
  Uses `SSL_use_cert_and_key` because `SSL_set_SSL_CTX` has known
  weirdness (link to upstream issue 6109 at be-secure-openssl.c:1838).
- **`verify_cb`** (be-secure-openssl.c:1637) — callback invoked for
  each cert in the chain during verification. Stashes detail into a
  `CallbackErr` reachable via `SSL_get_ex_data` (idx 0); the
  `be_tls_open_server` loop pulls it out and ereports.
  `prepare_cert_name` (be-secure-openssl.c:1597) truncates and
  ASCII-cleans cert subjects before logging to thwart log-injection
  attacks via a malicious cert.
- **`alpn_cb`** (be-secure-openssl.c:1776) — ALPN negotiation. Only
  `PG_ALPN_PROTOCOL` is allowed. Rejection returns
  `SSL_TLSEXT_ERR_ALERT_FATAL` per RFC 7301.
- **`info_cb`** (be-secure-openssl.c:1725) — emits per-state DEBUG4
  log lines during handshake. Pure observability.
- **`port_bio_*`** (be-secure-openssl.c:1343, 1367, 1386, 1416) — a
  custom OpenSSL BIO_METHOD that routes through
  `secure_raw_read`/`secure_raw_write` so OpenSSL respects PG's
  `raw_buf` (the pre-handshake byte stash) and PG's
  postmaster-death wait semantics.
- **Cipher / curve config** — `initialize_dh` (be-secure-openssl.c:2076)
  loads `ssl_dh_params_file` or falls back to the OpenSSL stock
  `FILE_DH2048` (2048-bit MODP from RFC 3526); `initialize_ecdh`
  (be-secure-openssl.c:2114) parses `SSLECDHCurve` (a colon-separated
  list since v12, e.g. `X25519:secp384r1`).
- **Error mapping** — `SSLerrmessage` (be-secure-openssl.c:2169) +
  `SSLerrmessageExt` (be-secure-openssl.c:2150) translate OpenSSL
  `unsigned long` error codes; handles the OpenSSL 3 case where
  `ERR_reason_error_string` returns NULL for system errnos
  (`ERR_SYSTEM_ERROR` macro, be-secure-openssl.c:2187-2190).
- **Version GUC mapping** — `ssl_protocol_version_to_openssl`
  (be-secure-openssl.c:2405) + `ssl_protocol_version_to_string`
  (be-secure-openssl.c:2440). Returns -1 for unsupported, which
  `be_tls_init` reports as "not supported by this build".
- **`X509_NAME_to_cstring`** (be-secure-openssl.c:2332) — RFC2253-format
  DN render; also `pg_any_to_server` converts to server encoding
  before the result is handed to the rest of PG.

## File-scope state

- `SSL_CTX *SSL_context` (be-secure-openssl.c:109) — the active
  context; pointer-swap atomic for SIGHUP reload.
- `MemoryContext SSL_hosts_memcxt` (be-secure-openssl.c:110) —
  per-reload context holding the parsed `pg_hosts.conf` plus all
  the `init_host_context` allocations; `host_context_cleanup_cb`
  (be-secure-openssl.c:594) is a reset callback that frees the
  OpenSSL-managed `SSL_CTX` objects when the memcxt is wiped.
- `struct hosts *SSL_hosts` (be-secure-openssl.c:111-127) — holds
  `sni` list (named hosts), `no_sni` (for clients without the SNI
  extension), `default_host` (fallback).
- `host_cache` simplehash (be-secure-openssl.c:64-74) — duplicate
  hostname detection during pg_hosts.conf parsing.
- `bool dummy_ssl_passwd_cb_called`, `bool ssl_is_server_start` —
  flags read by the passphrase callbacks.

## Invariants & gotchas

- **Reloads are atomic.** `be_tls_init` does all its work in a
  scratch memcxt and only commits to `SSL_context` / `SSL_hosts` at
  the very end (be-secure-openssl.c:552-569). A bad reload (missing
  cert, expired key, syntax error in pg_hosts.conf) leaves the
  running config intact — `ereport(LOG)`, return -1.
- **`SSLv23_method()` despite the name.** Comment at
  be-secure-openssl.c:379-383: "We use SSLv23_method() because it
  can negotiate use of the highest mutually supported protocol
  version" — the actual version floor is enforced by
  `SSL_CTX_set_min_proto_version` (defaults to TLS 1.2).
- **TLS session tickets and session caching are disabled**
  (be-secure-openssl.c:490-496). Tickets break PG's lack of session
  state across the connection-per-backend model; the
  `SSL_CTX_set_num_tickets(0)` covers TLS 1.3 stateful tickets, the
  `SSL_OP_NO_TICKET` covers stateless. Renegotiation is also
  disabled (be-secure-openssl.c:502-514).
- **Compression is disabled** (`SSL_OP_NO_COMPRESSION`,
  be-secure-openssl.c:498-499) — CRIME-attack mitigation.
- **`secure_open_server` saves and restores `raw_buf`** so any
  client bytes that arrived in the SSLRequest packet's tail get
  replayed *through* TLS, not stripped. The `port_bio_read`
  (be-secure-openssl.c:1343) wraps this via `secure_raw_read`.
- **Embedded-NULL rejection in peer CN/DN** (be-secure-openssl.c:1097-1104,
  1143-1155) — CVE-2009-4034 was a cross-implementation
  ASN1-string-with-embedded-NULL bypass; PG rejects the connection
  if any string field length doesn't match `strlen` of the bytes.
- **`ssl_loaded_verify_locations` is set in `sni_clienthello_cb`**
  (be-secure-openssl.c:1902 inside the LibreSSL fallback;
  HAVE_SSL_CTX_SET_CLIENT_HELLO_CB path sets it inside
  `init_host_context` per-host). Consumed by `auth.c:406` for the
  `clientcert` HBA pre-check.
- **LibreSSL gaps.** Several `#ifdef HAVE_SSL_CTX_SET_CLIENT_HELLO_CB`
  branches at be-secure-openssl.c:889-905, 211-216, 1813 — LibreSSL
  doesn't support the client-hello callback so it can't do SNI;
  `ssl_sni` is force-rejected at GUC check time on those builds.
- **`X509_NAME_to_cstring` runs `pg_any_to_server`** (be-secure-openssl.c:2379).
  Encoding-unsafe cert subjects can't poison the log; same idea as
  `prepare_cert_name` (be-secure-openssl.c:1597) which `pg_clean_ascii`'s
  the result for the verify-callback path.
- **The custom `port_bio`** is a *security* feature, not just a
  performance one: it forces OpenSSL to go through PG's
  socket-wait + postmaster-death-check pathway rather than calling
  `read(2)` itself.
- **`SSL_OP_CIPHER_SERVER_PREFERENCE`** is set conditionally on
  `SSLPreferServerCiphers` (be-secure-openssl.c:548-549). When
  false (default), the client picks; admins who want a strict
  policy enable it.

## Cross-refs

- Indirection: `be-secure.c` — wraps every `be_tls_*` symbol.
- Common helpers: `be-secure-common.c` — `check_ssl_key_file_permissions`,
  `run_ssl_passphrase_command`, `load_hosts`.
- Used by SCRAM: `be_tls_get_certificate_hash` →
  `auth-scram.c:1325`.
- Used by auth gate: `ssl_loaded_verify_locations` → `auth.c:406`.
- Used by CheckCertAuth: `port->peer_cn`, `port->peer_dn` set here
  → `auth.c:2701-2778`.
- Frontend counterpart: `src/interfaces/libpq/fe-secure-openssl.c`
  (the file-permission check and protocol-version mapping must
  stay in sync per comments at be-secure-openssl.c:152 and
  be-secure-common.c:153).

## Potential issues

- **[ISSUE-correctness: TLS 1.0 / 1.1 still selectable by GUC]**
  `be-secure-openssl.c:2405-2434` — `PG_TLS1_VERSION` and
  `PG_TLS1_1_VERSION` are still mapped; admin can set
  `ssl_min_protocol_version = 'TLSv1'`. Default is 1.2 since PG 13.
  Modern OpenSSL refuses < 1.0 anyway, but the GUC surface
  predates that consensus. Severity: nit (default is safe).
- **[ISSUE-undocumented-invariant: PG_ALPN_PROTOCOL must match
  frontend]** be-secure-openssl.c:1769, 1047-1058 — the literal
  protocol string is defined in `pqcomm.h`; mismatch silently fails
  the handshake. Cross-file dependency. Severity: nit.
- **[ISSUE-leak: peer_cn / peer_dn allocated from TopMemoryContext
  but freed inconsistently]** be-secure-openssl.c:1082, 1138 —
  `MemoryContextAlloc(TopMemoryContext, ...)`; freed in
  `be_tls_close` (be-secure-openssl.c:1182-1191) which is only
  called on normal connection close. A backend that exits abruptly
  takes the whole process down so no real leak, but `pfree` on a
  partially-built `peer_dn` after early-return at
  be-secure-openssl.c:1090 doesn't happen — `peer_cn` is leaked in
  that error path. Severity: nit (process-exit cleanup).
- **[ISSUE-correctness: SNI ClientHello byte-parsing is hand-rolled]**
  be-secure-openssl.c:1931-1973 — sketchy hand-walked TLS extension
  parser with explicit `*tlsext++` and `<<8 | byte` decoding. A
  bug here is an early-handshake DoS vector. Severity: maybe.
  Worth fuzzing if not already.
- **[ISSUE-question: `host_cache_pointer` lowercases via pstrdup+
  pg_tolower]** be-secure-openssl.c:2459-2472 — allocates per-lookup
  string. On a busy SNI-heavy server that's a lot of palloc
  churn in the hash. Severity: nit.
- **[ISSUE-doc-drift: comment about TLS-cipher GUC referring to "for
  TLSv1.2 and below"]** be-secure-openssl.c:522-545 — fine, but the
  GUC names `ssl_ciphers` (TLS <=1.2) vs `ssl_ciphersuites` (TLS
  1.3) are easy to confuse; the file doesn't link the GUC docs.
  Severity: nit.
- **[ISSUE-correctness: passphrase callback `dummy_ssl_passwd_cb`
  pattern]** be-secure-openssl.c:1580 + global flag at
  be-secure-openssl.c:129 — the dummy callback sets a flag so the
  caller can detect "tried to prompt for a passphrase during
  reload"; brittle if any other code reads the flag. Severity: nit.
- **[ISSUE-undocumented-invariant: no validation that ssl_cert_file
  and ssl_key_file are mutually consistent]** beyond what
  `SSL_CTX_check_private_key` provides. A symlink swap between
  reloads could yield a config where cert and key don't match yet
  it loads — `SSL_CTX_check_private_key` would catch it, but
  worth a corpus note. Severity: nit.

## Tally

`[verified-by-code]=28 [from-comment]=12 [inferred]=2`
