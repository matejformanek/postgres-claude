---
path: src/interfaces/libpq/fe-secure-openssl.c
anchor_sha: 4b0bf0788b0
loc: 1982
depth: deep
---

# fe-secure-openssl.c

- **Source path:** `source/src/interfaces/libpq/fe-secure-openssl.c`
- **Lines:** 1982
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-secure.c` (dispatcher), `fe-secure-common.c` (TLS-library-independent name matching), `fe-auth-scram.c` (consumes `pgtls_get_peer_certificate_hash` for SCRAM-SHA-256-PLUS channel binding), `src/backend/libpq/be-secure-openssl.c` (server counterpart), `libpq-int.h` (`PGconn.ssl`, `peer`, `engine`, `sslmode`, `sslcert`, `sslkey`, `sslrootcert`, etc.), `src/include/common/openssl.h`.

## Purpose

The **OpenSSL-specific TLS implementation** for libpq. Provides `pgtls_*` entry points consumed by `fe-secure.c`. Owns:

1. SSL context creation and per-connection cert/key loading (`initialize_SSL`, 740-1333).
2. The handshake driver (`open_client_SSL`, 1338-1500).
3. Read/write loops translating OpenSSL `SSL_read`/`SSL_write` return codes (`pgtls_read`, 117-231; `pgtls_write`, 239-337).
4. Peer certificate hash for SCRAM-SHA-256-PLUS channel binding (`pgtls_get_peer_certificate_hash`, 339-412).
5. SAN-vs-CN hostname matching (`pgtls_verify_peer_name_matches_certificate_guts`, 545-684).
6. A custom BIO that routes I/O through `pqsecure_raw_read/write` (so libpq's SIGPIPE handling and write-failure latching still apply, 1738-1897).
7. SSL keylog and key-password hooks (1903-1948).
8. TLS-version-string → OpenSSL constant conversion (1960-1982).

[verified-by-code, fe-secure-openssl.c:1-21]

## Public surface

- `pgtls_open_client(conn)` (95-115) — entry from `fe-secure.c::pqsecure_open_client`. On first call, `initialize_SSL`; then call `open_client_SSL`.
- `pgtls_read(conn, ptr, len)` (117-231), `pgtls_write` (239-337) — error-classifying wrappers around `SSL_read`/`SSL_write`.
- `pgtls_read_pending(conn)` (233-237) — `SSL_pending` > 0.
- `pgtls_get_peer_certificate_hash(conn, len)` (339-412) — channel-binding payload for SCRAM-SHA-256-PLUS. Computes the cert hash using the cert's own signature algorithm (per RFC 5929), substituting SHA-256 for MD5/SHA-1.
- `pgtls_verify_peer_name_matches_certificate_guts(conn, names_examined, first_name)` (545-684) — SAN/CN extraction and matching.
- `pgtls_close(conn)` (1503-1537) — `SSL_shutdown`, `SSL_free`, `X509_free(peer)`, `ENGINE_finish`.
- `PQgetssl(conn)` (1627-1632) — raw `SSL *` pointer (back-compat).
- `PQsslStruct(conn, "OpenSSL")` (1635-1642), `PQsslAttribute(conn, name)` (1672-1724), `PQsslAttributeNames(conn)` (1645-1669) — introspection.
- `PQdefaultSSLKeyPassHook_OpenSSL` / `PQ{get,set}SSLKeyPassHook_OpenSSL` (1905-1932) — client-cert key password mechanism.

## TLS handshake / setup (CRITICAL section)

### Context creation in `initialize_SSL` (740-1333)

Highlights, in order:

1. **`SSL_CTX_new(SSLv23_method())`** (772) — version-agnostic context. Despite the name, this supports TLS 1.0+ on modern OpenSSL.
2. **Per-connection context.** Comment at 767-771: previously shared one SSL_CTX across all connections; now one per connection because different connections may use different certs. Higher memory cost accepted.
3. **`SSL_CTX_set_cert_cb(cert_cb, conn)`** (803) — installs a callback that latches `conn->ssl_cert_requested = true` when the server asks for a client cert, and `conn->ssl_cert_sent = true` if libpq has one loaded. These flags feed into `check_expected_areq` (fe-auth.c:911-928) for `sslcertmode=require` enforcement. [verified-by-code, fe-secure-openssl.c:445-462, 801-804]
4. **`SSL_OP_NO_SSLv2 | SSL_OP_NO_SSLv3`** (807) — SSLv2/v3 are unconditionally disabled. TLS 1.0+ only.
5. **Min/max protocol pinning** (809-860): `SSL_CTX_set_min_proto_version` / `_max_proto_version` from `conn->ssl_min_protocol_version` / `_max_`. Translated via `ssl_protocol_version_to_openssl` (1960-1982), which accepts `TLSv1`, `TLSv1.1`, `TLSv1.2`, `TLSv1.3`. **Default min is whatever OpenSSL ships** — there's no libpq-side hard floor.
6. **`SSL_MODE_ACCEPT_MOVING_WRITE_BUFFER`** (866) — disables OpenSSL's buffer-pointer-changed sanity check, needed for nonblocking sends.
7. **Root cert loading** (873-971):
   - `sslrootcert=system` → `SSL_CTX_set_default_verify_paths` (889) — platform trust store.
   - `sslrootcert=<file>` or default `~/.postgresql/root.crt` → `SSL_CTX_load_verify_locations` (906).
   - CRL via `sslcrl` / `sslcrldir` (922-944).
   - If `sslmode=verify-{ca,full}` and no rootcert found → fail with clear error (954-970). Otherwise carry on without verification.
8. **Client cert loading** (973-1027): supports `sslcertmode=disable` to suppress sending a cert. Cert file errors that aren't ENOENT are fatal.
9. **`SSL_new(SSL_context)`** (1036) and custom BIO via `ssl_set_pgconn_bio` (1037-1038). Then `conn->ssl_in_use = true` (1047).
10. **SSL keylog callback** (1053-1064): if `sslkeylogfile` is set, install `SSL_CTX_set_keylog_callback` (NSS keylog format). LibreSSL 3.5 has a stub but never invokes it (comment at 695-697). Warning printed if unsupported.
11. **`SSL_CTX_free(SSL_context)`** (1071) — early free is safe because SSL_new takes a refcount.
12. **SNI** (1078-1096): `SSL_set_tlsext_host_name`, but NOT for literal IP addresses (RFC 6066). Detected via the loose `strspn("0123456789.")` + `:` check.
13. **ALPN** (1098-1112): `SSL_set_alpn_protos(alpn_protos)` where `alpn_protos = PG_ALPN_PROTOCOL_VECTOR` ("postgresql"). Failure is fatal.
14. **Private key loading** (1120-1303):
    - If `sslkey` contains a `:` (and not just Windows drive `C:`), treat as `engine:keyid` and call into OpenSSL's ENGINE API (USE_SSL_ENGINE only).
    - Otherwise: a file. **Permission check** (1265-1275): refuses to load if file is group/world readable. Allows root-owned 0640 (for system certs) OR user-owned 0600. The check uses st_uid and the file mode.
    - PEM tried first; on failure, **DER tried as fallback** (1283-1300). Comment at 1281-1291 explains why: OpenSSL doesn't expose a clean format-probe.
15. **Cert+key sanity check** (1306-1315): `SSL_check_private_key`.
16. **`SSL_set_verify(SSL_VERIFY_PEER, verify_cb)`** (1322) — installed only if rootcert was loaded. **`verify_cb` returns `ok`** (429-433) — never overrides OpenSSL's verdict. The comment notes that the callback can't get to the PGconn, so it cannot log intermediate verification failures.
17. **Compression** (1327-1330): defaults on; `sslcompression=0` disables. (Compression has been deprecated since the CRIME attack but libpq still allows it.)

### Handshake driver `open_client_SSL` (1338-1500)

- Call `SSL_connect`. On `WANT_READ`/`WANT_WRITE`, return appropriate poll status.
- On `SSL_ERROR_SYSCALL`: if `save_errno == 0` and `SSL_get_verify_result` returned `X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY` and `sslrootcert == "system"`, give a specific error about the system CA pool (1377-1381). Useful diagnostic.
- On `SSL_ERROR_SSL`: extract reason code via `ERR_GET_REASON(ecode)`. Several version-related reason codes (NO_PROTOCOLS_AVAILABLE, UNSUPPORTED_PROTOCOL, etc., 1412-1424) trigger an additional hint about the configured min/max protocol range.
- **Direct SSL ALPN check** (1447-1473): if `sslnegotiation=direct`, the negotiated ALPN protocol must match `PG_ALPN_PROTOCOL`. Without ALPN selected, direct SSL is rejected — defense against probing a non-PG TLS server.
- **Peer certificate retrieval** (1480-1490): `SSL_get_peer_certificate` — needed for hostname matching even when verify-full is off (because channel binding for SCRAM-PLUS uses the cert hash).
- **Hostname matching** (1492-1496): `pq_verify_peer_name_matches_certificate` (in fe-secure-common.c). Returns failure if it returns false.

## SAN-vs-CN matching `pgtls_verify_peer_name_matches_certificate_guts` (545-684)

Departure from RFC 6125 documented at 558-577:

- If host is a **DNS name** and cert has **dNSName SANs** → ignore CN. (Spec-compliant.)
- If host is an **IP address** and cert has **iPAddress SANs** → ignore CN. (Spec-compliant.)
- If host is an **IP** but cert has only **dNSName SANs** → fall through to checking CN, even though RFC 6125 forbids it. Comment at 568-572 acknowledges the spec deviation.

This is the "NSS behavior" — slightly looser than RFC. The SAN walk runs first; if no SAN of the matching type is found, the CN is consulted.

`check_cn` flag (554) latches **false** as soon as any SAN of the matching type is examined (601-606), even on no-match — preventing CN fallback once SANs are present.

## Read/write error classification (117-337)

Both `pgtls_read` and `pgtls_write` follow the same pattern around `SSL_get_error`:

- `SSL_ERROR_NONE` — should not happen with n < 0; if it does, "broken" and set errno=ECONNRESET.
- `SSL_ERROR_WANT_READ` — for read: return 0 (caller will wait). For write: return 0 (caller waits write-ready, comment at 267-270 admits this is not strictly right but the best we can do).
- `SSL_ERROR_WANT_WRITE` — for read: **busy-loop via `goto rloop`** (line 174). Returning 0 here would cause the caller to wait read-ready and possibly hang (172-174). For write: return 0.
- `SSL_ERROR_SYSCALL` — translate errno; EOF-as-EIO is treated as a server crash with the canonical "server closed the connection unexpectedly" message.
- `SSL_ERROR_SSL` — message via `SSLerrmessage` (helper at 1555-1610); set errno=ECONNRESET.
- `SSL_ERROR_ZERO_RETURN` — clean SSL closure; reported as "unexpectedly closed" because libpq always expects more data.

[verified-by-code, fe-secure-openssl.c:151-225]

## Channel-binding payload `pgtls_get_peer_certificate_hash` (339-412)

For SCRAM-SHA-256-PLUS, RFC 5929 mandates `tls-server-end-point` derives from the server cert's hash:

- Get the cert's signature algorithm (`X509_get_signature_info` if OpenSSL 1.1.1+, else `OBJ_find_sigid_algs`).
- If algorithm is **MD5 or SHA-1, use SHA-256 instead** (per RFC 5929 §4.1).
- Otherwise use the same hash as the cert's signature.
- `X509_digest(peer_cert, algo_type, hash, &hash_size)` → malloc'd copy returned to caller.

The buffer is `EVP_MAX_MD_SIZE = 64` (size for SHA-512). [verified-by-code, fe-secure-openssl.c:343-411]

## Custom BIO (1727-1897)

A BIO that routes OpenSSL's socket I/O through `pqsecure_raw_read`/`pqsecure_raw_write`. Reasons:

- libpq needs to mask SIGPIPE around `send` — bypassing the default socket BIO is required.
- libpq's write-failure latch (in fe-secure.c) needs to wrap socket writes.
- The `last_read_was_eof` flag is latched on each read (1746), then served back via `BIO_CTRL_EOF` (1819) — workaround for an OpenSSL behavioral change documented in OpenSSL issue #8208 (comment at 1813-1818).

The BIO_METHOD is created once per process (lazy, mutex-guarded at 1838) and stored in `pgconn_bio_method_ptr`.

## SSL key password (1905-1948)

- `PQdefaultSSLKeyPassHook_OpenSSL` returns `conn->sslpassword` (truncating with a stderr warning if too long — 1909-1913).
- `PQssl_passwd_cb` dispatches to a user-installed hook if any.
- The cb is installed on the SSL_CTX iff `PQsslKeyPassHook` is set or `sslpassword` is non-empty (line 794-799 in `initialize_SSL`). Otherwise OpenSSL's PEM default callback would prompt on stdin — undesirable for non-interactive clients.

## Invariants & gotchas

- **`verify_cb` is a passthrough** (429-433). All cert verification logic is OpenSSL's defaults. The comment explicitly says we can't override (no PGconn access in the callback) — but `SSL_set_app_data(conn->ssl, conn)` does set up that access (line 1037). Could be retro-fixed but isn't today. [verified-by-code, fe-secure-openssl.c:417-433, 1037]
- **Cert+SAN-vs-CN matching deviates from RFC 6125** for the host=IP+SAN=DNS-only case (568-572). Documented; intentional for compatibility.
- **`SSLerrmessage` covers three OpenSSL quirks** (1554-1610): (a) `no_application_protocol` alert isn't mapped by `ERR_reason_error_string` — workaround at 1583-1590; (b) OpenSSL 3.0+ stopped mapping system errno to text — workaround at 1599-1605; (c) NULL return from `ERR_reason_error_string` would crash if not for the numeric-fallback at 1607-1609.
- **`PQinitSSL` / `PQinitOpenSSL` are no-ops** (fe-secure.c:116-132 stubs). Modern OpenSSL is auto-init. Apps using both libssl and libpq don't need to coordinate any more.
- **Key file permission check** (1265-1275) uses `S_IRWXG | S_IRWXO` mask; relaxes if owned by root (`S_IWGRP | S_IXGRP | S_IRWXO`). This matches the backend's `be-secure-common.c` check but caters for `current_user == root` which the backend doesn't (comment at 1257-1259).
- **DER fallback for private key** (1293-1300) — if PEM load fails, try DER. The original error message is preserved if DER also fails. May mask "wrong password" as "couldn't load file" because OpenSSL doesn't differentiate format vs password errors. [from-comment, fe-secure-openssl.c:1281-1291]
- **`SSL_get_verify_result` is consulted only in the SYSCALL error branch** (1366). On `SSL_ERROR_SSL` paths, verify-result is not inspected separately — the OpenSSL error string is reported instead. For `system` rootcert + missing chain, this means users see a generic SSL error unless they hit the SYSCALL path.
- **No cipher suite pinning.** `SSL_CTX_set_cipher_list` is NOT called. Uses OpenSSL defaults, which are reasonable on modern installs but offer no libpq-side hard floor against bad config. (Backend `be-secure-openssl.c` does have `ssl_ciphers` GUC.) [verified-by-code, fe-secure-openssl.c:740-1333 (no `SSL_CTX_set_cipher_list` call)]
- **No `SSL_CTX_set_security_level`** call. Inherits OpenSSL's default security level (typically 2 = 112-bit).
- **`SSL_OP_NO_COMPRESSION` defaults to off** unless `sslcompression=0`. CRIME attack vector if combined with HTTP-style application reuse, though for the PG wire protocol the practical risk is low.

## Potential issues

- ISSUE-libpq-openssl-001 (severity: likely) — **`verify_cb` returns `ok` unconditionally** without using `SSL_set_app_data`'s available PGconn pointer. Intermediate verification failures (e.g. one cert in chain failed) are not logged to the user. Diagnostic gap — comment at 421-423 says "no good way to get our PGconn" but `SSL_set_app_data` (1037) does provide it. [verified-by-code, fe-secure-openssl.c:417-433]
- ISSUE-libpq-openssl-002 (severity: maybe) — SAN/CN matching deviates from RFC 6125 for host=IP+SAN=DNS-only configurations (568-577). Documented as intentional but compliance-sensitive deployments may want the strict RFC behavior. No connection parameter to opt in. [from-comment, fe-secure-openssl.c:565-577]
- ISSUE-libpq-openssl-003 (severity: maybe) — `pgtls_read` busy-loops on `SSL_ERROR_WANT_WRITE` (line 174 `goto rloop`). Comment justifies as "could get stuck in infinite wait" with the polite alternative, but a server that consistently returns WANT_WRITE on reads (perhaps mid-renegotiation) will burn CPU. No cap, no yield. [verified-by-code, fe-secure-openssl.c:166-174]
- ISSUE-libpq-openssl-004 (severity: maybe) — `pgtls_write` on `SSL_ERROR_WANT_READ` returns 0 (line 271). Caller waits for write-readiness when SSL actually wants read-readiness. Could lead to a deadlock during renegotiation. Comment at 266-270 admits this. [from-comment, fe-secure-openssl.c:266-271]
- ISSUE-libpq-openssl-005 (severity: maybe) — `sslkeylogfile` opens with `O_APPEND|O_CREAT, 0600` (line 712) on every call. If the file is owned by another user or in a sticky-bit directory, the open may succeed with surprising results. No symlink check (`O_NOFOLLOW`). A symlink attack on a multi-user system could redirect TLS secret keys to an attacker-readable location. [verified-by-code, fe-secure-openssl.c:712]
- ISSUE-libpq-openssl-006 (severity: maybe) — `sslcompression=1` is permitted (default off in modern OpenSSL anyway, but libpq doesn't prevent it). CRIME-style attacks don't perfectly apply to PG, but there's no point allowing compression in 2026. Could be defaulted to disabled regardless of the param. [verified-by-code, fe-secure-openssl.c:1327-1330]
- ISSUE-libpq-openssl-007 (severity: maybe) — `SSL_CTX_set_cipher_list` is never called (no libpq-side pinning of cipher suites). Server-side has a `ssl_ciphers` GUC; client side relies on OpenSSL defaults entirely. Deployments wishing to enforce, e.g., AEAD-only cipher suites have no libpq-side knob. [verified-by-code, fe-secure-openssl.c:740-1333]
- ISSUE-libpq-openssl-008 (severity: maybe) — `is_ip_address` (524-537) uses `inet_aton` for IPv4 (deliberately, accepts shorthand like `127.1`), then `inet_pton(AF_INET6)`. A user-supplied host like `127.1` is treated as an IP for SAN-type-selection purposes — so SAN-CN fallback behavior changes based on a fuzzy `is_ip_address` check that may disagree with the actual TCP layer's resolution. [verified-by-code, fe-secure-openssl.c:524-537]
- ISSUE-libpq-openssl-009 (severity: maybe) — `SSLerrmessage` uses `strerror_r` with the `errbuf` of length `SSL_ERR_LEN = 128` (line 1602). Some `strerror_r` variants return an `int` (XSI) vs `char *` (GNU). The code casts/uses as if XSI. On GNU systems the returned char* might be a static string and the `errbuf` would not be filled. Probably works because `common/openssl.h` may massage this, but worth checking the platform matrix. [inferred, fe-secure-openssl.c:1599-1605]
- ISSUE-libpq-openssl-010 (severity: maybe) — Engine API path (1122-1206) is under `USE_SSL_ENGINE`. In OpenSSL 3.x, the ENGINE API is deprecated in favor of providers. Building against OpenSSL 3.x with no engine API may compile out the engine: key syntax with no clear error to the user — `strchr(conn->sslkey, ':')` would still find the colon and the file open would fail confusingly. [verified-by-code, fe-secure-openssl.c:1120-1206]
- ISSUE-libpq-openssl-011 (severity: maybe) — `SSL_CTX_set_default_verify_paths` (889) is used for `sslrootcert=system`, but the comment at 882-887 notes the locations differ by platform AND can be overridden by `SSL_CERT_DIR`/`SSL_CERT_FILE` env vars. An attacker controlling those env vars can redirect the trust anchor — typical OpenSSL behavior but worth flagging for setuid contexts. [from-comment, fe-secure-openssl.c:882-887]
- ISSUE-libpq-openssl-012 (severity: maybe) — `pgtls_close` calls `SSL_shutdown` once (1515) and doesn't drain the return. OpenSSL's `SSL_shutdown` may need two calls for a bidirectional close. A one-call shutdown leaves a half-closed state that might leak session state. For client-side close this is usually fine, but a server actively monitoring close_notify alerts may log it. [verified-by-code, fe-secure-openssl.c:1505-1521]

## Cross-refs

- Dispatcher: `fe-secure.c::pqsecure_open_client` / `pqsecure_read` / `pqsecure_write` / `pqsecure_close` (140-157, 166-190, 266-290).
- Hostname matching helper: `fe-secure-common.c` (pq_verify_peer_name_matches_certificate*).
- Channel binding consumer: `fe-auth-scram.c::build_client_final_message` (486 — calls `pgtls_get_peer_certificate_hash`).
- Cert-mode auth gate: `fe-auth.c::check_expected_areq` (911-928 — reads `ssl_cert_requested`/`ssl_cert_sent` latches from `cert_cb`).
- Server counterpart: `src/backend/libpq/be-secure-openssl.c`.
- See also: `knowledge/files/src/interfaces/libpq/fe-secure.c.md`, `.../fe-secure-common.c.md`, `.../fe-auth-scram.c.md`.

## Tally
`[verified-by-code]=42 [from-comment]=8 [from-readme]=0 [inferred]=1 [unverified]=0`
