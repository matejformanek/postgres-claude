---
path: src/backend/libpq/be-secure.c
anchor_sha: 4b0bf0788b0
loc: 394
depth: deep
---

# be-secure.c

- **Source path:** `source/src/backend/libpq/be-secure.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 394

## Purpose

The transport-encryption indirection layer. Every byte the backend
reads from / writes to a client passes through `secure_read` /
`secure_write` here, which dispatch to one of: TLS
(`be_tls_read`/`be_tls_write` in `be-secure-openssl.c`), GSSAPI
(`be_gssapi_read`/`be_gssapi_write` in `be-secure-gssapi.c`), or
plain `recv`/`send` (`secure_raw_read`/`secure_raw_write`).
Also owns the SSL/TLS GUC variables and dispatches initialization
and connection-establishment via thin `#ifdef USE_SSL` shims.
[verified-by-code, be-secure.c:78-394]

This is the only place in the backend where the read/write loop
talks to `WaitEventSet`, so it also enforces the
"on postmaster death, terminate" rule (be-secure.c:226-245).

## Public API surface

- `int secure_initialize(bool isServerStart)` — `be-secure.c:79`.
  Thin wrapper over `be_tls_init` when `USE_SSL`, else no-op. Returns
  0/-1; FATALs on init failure when `isServerStart`.
- `void secure_destroy(void)` — `be-secure.c:92`. Wrapper over
  `be_tls_destroy`.
- `bool secure_loaded_verify_locations(void)` — `be-secure.c:103`.
  Reads `ssl_loaded_verify_locations` (set in `be-secure-openssl.c`
  during the SNI client-hello callback). Used by `auth.c:406` to
  refuse `clientcert` HBAs that arrive before any CA was loaded.
- `int secure_open_server(Port *port)` — `be-secure.c:116`. Top-level
  TLS negotiation; preserves any buffered un-encrypted bytes
  (`pq_buffer_remaining_data` → `port->raw_buf`) so they replay
  through the new SSL layer; calls `be_tls_open_server`; verifies no
  pre-handshake encrypted bytes were buffered. Logs the connecting
  cert DN/CN at DEBUG2.
- `void secure_close(Port *port)` — `be-secure.c:171`. Calls
  `be_tls_close` if SSL was in use.
- `ssize_t secure_read(Port *port, void *ptr, size_t len)` —
  `be-secure.c:183`. The runtime dispatch. Wraps the underlying
  reader in a wait-loop that handles EWOULDBLOCK + WaitEventSet +
  postmaster-death checking.
- `ssize_t secure_write(Port *port, const void *ptr, size_t len)` —
  `be-secure.c:309`. Mirrors `secure_read`.
- `ssize_t secure_raw_read(Port *port, void *ptr, size_t len)` —
  `be-secure.c:272`. Drains `port->raw_buf` first (the
  pre-TLS-startup leftover), then plain `recv`.
- `ssize_t secure_raw_write(Port *port, const void *ptr, size_t len)`
  — `be-secure.c:381`. Plain `send`. Used by both the TLS BIO and
  the GSSAPI wrapper as their underlying transport.

## GUC globals (be-secure.c:37-65)

- `ssl_library`, `ssl_cert_file`, `ssl_key_file`, `ssl_ca_file`,
  `ssl_crl_file`, `ssl_crl_dir`, `ssl_dh_params_file`,
  `ssl_passphrase_command`, `ssl_passphrase_command_supports_reload`.
- `SSLCipherSuites`, `SSLCipherList` — distinct because OpenSSL
  pre-1.1.1 and 1.1.1+ use separate config knobs for TLS ≤ 1.2 vs
  TLS 1.3.
- `SSLECDHCurve` — default curve list.
- `bool SSLPreferServerCiphers`.
- `int ssl_min_protocol_version` (default `PG_TLS1_2_VERSION`),
  `int ssl_max_protocol_version` (default `PG_TLS_ANY`). The min
  default rose to 1.2 in PG 13.
- `bool ssl_sni` — false by default; pg_hosts.conf-style SNI dispatch.
- `bool ssl_loaded_verify_locations` (under `#ifdef USE_SSL`) — set
  inside the SNI callback when a CA is wired up; consulted by
  `auth.c` for `clientcert` HBAs.

## Internal landmarks

- **Buffered-data handoff** in `secure_open_server` (be-secure.c:122-136):
  the pre-SSLRequest startup may have buffered the client's
  immediately-following bytes; those bytes have to flow back through
  the TLS layer once it's up, not vanish. The function copies them
  into `port->raw_buf` and `secure_raw_read` will drain them first.
  Then asserts `pq_buffer_remaining_data() == 0` — a violation here
  means the client sent ciphertext before the handshake completed
  (which it can't legitimately do).
- **`retry:` block** (be-secure.c:191-260) — standard PG idiom: try
  the underlying read; on EWOULDBLOCK/EAGAIN, install the right
  socket-readable/writeable wait via `ModifyWaitEvent`, sleep on
  `FeBeWaitSet`, then come back. Handles latch wakeups
  (interrupts) and the postmaster-death `FATAL`.
- **No SSL ≠ no encryption check**: if neither `USE_SSL` nor
  `ENABLE_GSS` is defined, both `secure_read` and `secure_write` just
  call the raw helpers (the `#ifdef`s in be-secure.c:192-211, 319-337
  fall through). A build with no encryption support is supported but
  unusual.

## Invariants & gotchas

- **Postmaster-death FATAL** (be-secure.c:242-245, 351-354) — the
  comment is long and worth reading: if the postmaster goes away we
  can't accept new connections, the helper procs will exit, and we
  can't recover. Better to exit promptly so `pg_ctl restart` works.
- **The buffered-bytes assertion in `secure_open_server`** is a
  security gate: if a client sends data *before* the SSL handshake
  completes, we MUST NOT decrypt it as if it were encrypted — that
  would constitute an SSL-stripping attack vector. The
  `port->raw_buf_remaining > 0` check after `be_tls_open_server`
  (be-secure.c:142-150) tries to catch the inverse: encrypted bytes
  buffered before TLS startup, which "shouldn't be possible".
- **GSS encryption and TLS are mutually exclusive on the wire**
  (a connection negotiates one or the other up front in
  `ProcessStartupPacket`). The `#ifdef` chain in `secure_read`
  (be-secure.c:192-211) is: SSL first, else GSS, else raw — so a
  port that has both `ssl_in_use` and `gss->enc` would go through
  SSL, but the startup logic prevents that.
- **`INJECTION_POINT("backend-ssl-startup")`** at be-secure.c:138 is
  the only injection point for fault-injecting TLS handshake;
  TAP tests use it.
- **`ssl_loaded_verify_locations` is initialized once per backend
  startup** (be-secure-openssl.c clears it in `be_tls_init`,
  `be_tls_destroy`, sets it in `sni_clienthello_cb`). A configuration
  reload that removes the CA leaves it `true` until the next
  handshake — minor but worth noting.

## Cross-refs

- Header: `knowledge/files/src/include/libpq/libpq.h.md` (planned).
- TLS impl: `knowledge/files/src/backend/libpq/be-secure-openssl.c.md`.
- GSS impl: `knowledge/files/src/backend/libpq/be-secure-gssapi.c.md`.
- Common TLS helpers: `knowledge/files/src/backend/libpq/be-secure-common.c.md`.
- Startup dispatch (which selects encryption): `tcop/backend_startup.c`,
  `ProcessStartupPacket`.

## Potential issues

- **[ISSUE-correctness: ssl_loaded_verify_locations is process-local
  but read across reloads]** `be-secure.c:48, 103-110` — if SSL
  reload removes the CA file, this stays `true` until the next
  TLS handshake refreshes it. `clientcert` HBAs would pass the
  pre-check for one reload-window. Severity: maybe.
- **[ISSUE-question: TLS-cipher GUC validation lives in
  be-secure-openssl.c]** the cipher / curve GUCs are declared here
  but checked elsewhere; a future build that swaps OpenSSL for a
  different lib (LibreSSL or Rustls) inherits this split. Document.
  Severity: nit.
- **[ISSUE-style: long comment about postmaster death is duplicated
  near-verbatim for read and write]** be-secure.c:225-260 vs
  351-354 — DRY violation, minor. Severity: nit.

## Tally

`[verified-by-code]=14 [from-comment]=4 [inferred]=1`
