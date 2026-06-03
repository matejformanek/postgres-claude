# Issues — `libpq` (backend + frontend + headers)

Per-subsystem issue register for the entire libpq stack. See
`knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent docs:**
- `knowledge/files/src/include/libpq/*` (20 headers)
- `knowledge/files/src/backend/libpq/*` (17 backend `.c`)
- `knowledge/files/src/interfaces/libpq/*` (32 frontend `.c`/`.h`)

**Source:** 227 entries surfaced 2026-06-03 by the A2 libpq-stack
parallel sweep (6 general-purpose agents reading 69 files). Each is
mirrored in the corresponding per-file doc's `## Potential issues` block.

This is **the densest Phase D data-leak surface** in PostgreSQL — auth,
crypto, wire protocol, and connection state all converge here. Items
below are grouped by Phase D-relevance pattern rather than by file.

---

## P0 — Phase D data-leak candidates (likely / confirmed severity)

Items where I have high confidence the surface is real and exploitable
or routinely-exposed; these are the entries to brainstorm hardening
patches for first.

### Secret scrubbing — the dominant pattern

`explicit_bzero` is called in **exactly one** backend code path
(`auth-oauth.c:341`) and **exactly one** frontend path (OAuth token
cleanup). Everywhere else, credentials are `pfree`'d without zeroing,
left in PGconn/Port for the connection lifetime, or copied into static
buffers.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | auth.c | leak | likely | Client password not zeroed after `auth_failed`/success | open | knowledge/files/src/backend/libpq/auth.c.md |
| 2026-06-03 | auth.c | leak | likely | LDAP bindpasswd lives cleartext in HbaLine + not scrubbed | open | knowledge/files/src/backend/libpq/auth.c.md |
| 2026-06-03 | auth.c | leak | likely | shadow_pass not zeroed in any failure path | open | knowledge/files/src/backend/libpq/auth.c.md |
| 2026-06-03 | auth-scram.c | leak | likely | Client proof / nonces / SaltedPassword not scrubbed | open | knowledge/files/src/backend/libpq/auth-scram.c.md |
| 2026-06-03 | crypt.c | leak | likely | shadow_pass + crypt_pwd stack buffers not zeroed | open | knowledge/files/src/backend/libpq/crypt.c.md |
| 2026-06-03 | be-secure-common.c | leak | likely | passphrase not zeroed on success path | open | knowledge/files/src/backend/libpq/be-secure-common.c.md |
| 2026-06-03 | be-secure-gssapi.c | leak | likely | PqGSSResultBuffer holds decrypted plaintext until pfree | open | knowledge/files/src/backend/libpq/be-secure-gssapi.c.md |
| 2026-06-03 | libpq-be.h | leak | confirmed | SCRAM `client_key` / `server_key` live in Port struct full connection lifetime; no scrub-on-teardown | open | knowledge/files/src/include/libpq/libpq-be.h.md |
| 2026-06-03 | libpq-be.h | leak | likely | peer_cn / peer_dn lifetime not stated; persist in Port | open | knowledge/files/src/include/libpq/libpq-be.h.md |
| 2026-06-03 | libpq-int.h | leak | confirmed | PGconn holds pgpass, sslpassword, scram client/server key, oauth_token, oauth_client_secret + per-host passwords for the full connection lifetime; no clearance discipline | open | knowledge/files/src/interfaces/libpq/libpq-int.h.md |
| 2026-06-03 | fe-auth.c | leak | likely | MD5 intermediate digest not scrubbed after send | open | knowledge/files/src/interfaces/libpq/fe-auth.c.md |
| 2026-06-03 | fe-auth-scram.c | leak | likely | Client password + SaltedPassword not scrubbed on free | open | knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md |
| 2026-06-03 | fe-auth-oauth.c | leak | likely | `cleanup_oauth_flow` does not scrub `async_ctx` | open | knowledge/files/src/interfaces/libpq/fe-auth-oauth.c.md |

**Phase D pitch**: one coordinated `explicit_bzero`/`secure_zero` sweep
patch covering auth paths in backend + libpq. Add a `SecretBuf` wrapper
that auto-zeros on free; convert sites incrementally.

### Downgrade / protocol-confusion / state-machine

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | fe-auth.c:941 | correctness | likely | `require_auth=scram-sha-256,none` partial-exchange weakness (documented in code comment) — silently accepts partial SCRAM | open | knowledge/files/src/interfaces/libpq/fe-auth.c.md |
| 2026-06-03 | fe-auth.c:1219 | correctness | likely | `client_finished_auth = true` latched immediately post-password-send → MD5/cleartext have no mutual auth | open | knowledge/files/src/interfaces/libpq/fe-auth.c.md |
| 2026-06-03 | fe-auth-scram.c | correctness | likely | `client_finished_auth` latched even on server-signature mismatch | open | knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md |
| 2026-06-03 | fe-connect.c | undocumented-invariant | likely | `sslmode=prefer` (the default) can silently degrade to plaintext with no application signal beyond post-hoc `PQparameterStatus("ssl_in_use")` | open | knowledge/files/src/interfaces/libpq/fe-connect.c.md |
| 2026-06-03 | fe-auth-scram.c | correctness | likely | No SASLprep on username (RFC 5802 §5.1) | open | knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md |
| 2026-06-03 | protocol.h | undocumented-invariant | confirmed | `'p'` byte is overloaded across four FE auth-response messages (`PqMsg_GSSResponse` / `PqMsg_PasswordMessage` / `PqMsg_SASLInitialResponse` / `PqMsg_SASLResponse`), disambiguated only by what `AUTH_REQ_*` the server just sent — state-machine-confusion attack surface | open | knowledge/files/src/include/libpq/protocol.h.md |

### DoS — uncapped server-controlled inputs

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | fe-auth-scram.c | correctness | likely | No upper bound on PBKDF2 iteration count from server → CPU DoS via hostile server | open | knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md |
| 2026-06-03 | fe-auth.c | correctness | likely | No PGPASSWORD length cap | open | knowledge/files/src/interfaces/libpq/fe-auth.c.md |
| 2026-06-03 | fe-auth-oauth.c | correctness | likely | No bearer token length cap | open | knowledge/files/src/interfaces/libpq/fe-auth-oauth.c.md |
| 2026-06-03 | fe-secure-gssapi.c | correctness | likely | Server can fill 64KB error buffer on connect | open | knowledge/files/src/interfaces/libpq/fe-secure-gssapi.c.md |
| 2026-06-03 | fe-misc.c | correctness | maybe | No upper bound on input buffer growth | open | knowledge/files/src/interfaces/libpq/fe-misc.c.md |
| 2026-06-03 | fe-protocol3.c | correctness | maybe | `msgLength > 30000` cap is a magic number | open | knowledge/files/src/interfaces/libpq/fe-protocol3.c.md |
| 2026-06-03 | pqcomm.h | undocumented-invariant | likely | `MAX_STARTUP_PACKET_LENGTH` is a security knob — not flagged as such | open | knowledge/files/src/include/libpq/pqcomm.h.md |
| 2026-06-03 | pqcomm.c | correctness | maybe | `pq_putmessage_noblock` grows send buffer monotonically — single 100MB message leaves 100MB buffer for the rest of the backend lifetime | open | knowledge/files/src/backend/libpq/pqcomm.c.md |

### TLS / cert validation

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | be-secure-openssl.c | correctness | likely | TLS 1.0 / 1.1 still selectable via `ssl_min_protocol_version` | open | knowledge/files/src/backend/libpq/be-secure-openssl.c.md |
| 2026-06-03 | be-secure-openssl.c | correctness | likely | Hand-rolled SNI parser in client-hello cb | open | knowledge/files/src/backend/libpq/be-secure-openssl.c.md |
| 2026-06-03 | fe-secure-openssl.c | correctness | likely | `verify_cb` is a passthrough — never overrides OpenSSL verdict and doesn't log intermediate failures | open | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md |
| 2026-06-03 | fe-secure-openssl.c | correctness | likely | SAN-vs-CN matching is NSS-style; deviates from RFC 6125 for host=IP + SAN=DNS-only configs | open | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md |
| 2026-06-03 | fe-secure-openssl.c | correctness | likely | `sslkeylogfile` opened without `O_NOFOLLOW` | open | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md |
| 2026-06-03 | fe-secure-openssl.c | correctness | likely | `sslcompression=1` still permitted (CRIME risk reactivated when offered) | open | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md |
| 2026-06-03 | fe-secure-openssl.c | correctness | likely | No client-side cipher pinning (`SSL_CTX_set_cipher_list` never called) — backend has `ssl_ciphers` GUC, frontend has no equivalent | open | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md |
| 2026-06-03 | fe-secure-openssl.c | undocumented-invariant | likely | `USE_SSL_ENGINE` path is deprecated in OpenSSL 3.x → providers; `sslkey=engine:keyid` syntax could silently degrade | open | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md |
| 2026-06-03 | fe-secure-openssl.c | question | maybe | `SSL_CERT_DIR`/`SSL_CERT_FILE` env override system trust silently | open | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md |
| 2026-06-03 | be-secure.c | correctness | maybe | `ssl_loaded_verify_locations` stale across SIGHUP reload | open | knowledge/files/src/backend/libpq/be-secure.c.md |
| 2026-06-03 | libpq.h | correctness | maybe | 3DES still in default cipher list | open | knowledge/files/src/include/libpq/libpq.h.md |

### Wire-protocol "do not change" constants undocumented

Same pattern as the catalog header sweep surfaced: byte values, mechanism
strings, ALPN names are on-wire-load-bearing but only `dependency.h`'s
`DependencyType` enum carries the "don't change this" comment.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | protocol.h | undocumented-invariant | likely | Every PqMsg_* byte + AUTH_REQ_* code is wire-load-bearing; no header preamble | open | knowledge/files/src/include/libpq/protocol.h.md |
| 2026-06-03 | pqcomm.h | undocumented-invariant | likely | ALPN value (`postgresql`) is wire-load-bearing | open | knowledge/files/src/include/libpq/pqcomm.h.md |
| 2026-06-03 | pqcomm.h | correctness | likely | 1234.567x cancel/SSL/GSS negotiation codes are magic numbers | open | knowledge/files/src/include/libpq/pqcomm.h.md |
| 2026-06-03 | libpq-fs.h | undocumented-invariant | likely | INV_READ / INV_WRITE are part of the LO ABI | open | knowledge/files/src/include/libpq/libpq-fs.h.md |
| 2026-06-03 | sasl.h / scram.h | undocumented-invariant | likely | SCRAM mechanism strings (`SCRAM-SHA-256`, `SCRAM-SHA-256-PLUS`) + channel-binding type (`tls-server-end-point`) are wire-frozen by RFC compliance | open | knowledge/files/src/include/libpq/sasl.h.md |

### Trust boundaries — plugins, dlopen, env vars

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | auth-oauth.c | undocumented-invariant | likely | Validator runs in the connecting backend's address space; can crash or leak | open | knowledge/files/src/backend/libpq/auth-oauth.c.md |
| 2026-06-03 | fe-auth-oauth.c | leak | likely | Linux `libpq-oauth.so` loaded by basename; depends on runtime linker search order (LD_LIBRARY_PATH injection surface) | open | knowledge/files/src/interfaces/libpq/fe-auth-oauth.c.md |
| 2026-06-03 | libpq-events.c | undocumented-invariant | likely | `PQregisterEventProc` plugins run in-process with full PGconn access; no unregister API; live until PQfinish; plugin registration is unauthenticated | open | knowledge/files/src/interfaces/libpq/libpq-events.c.md |
| 2026-06-03 | oauth-debug.h | leak | likely | `UNSAFE:trace` debug flag logs bearer token to stderr | open | knowledge/files/src/interfaces/libpq/oauth-debug.h.md |
| 2026-06-03 | fe-trace.c | leak | likely | `PQtrace` dumps DataRow values + Parse/Bind parameters verbatim, including secrets | open | knowledge/files/src/interfaces/libpq/fe-trace.c.md |
| 2026-06-03 | fe-exec.c | leak | likely | `PQescapeString` (no-Conn variant) uses process-global encoding state set by most recent connection — multi-connection apps have stale-globals injection vector; always use `PQescapeStringConn` | open | knowledge/files/src/interfaces/libpq/fe-exec.c.md |

### Information disclosure

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | be-gssapi-common.h | leak | maybe | GSS error text granularity may leak Kerberos state to client | open | knowledge/files/src/include/libpq/be-gssapi-common.h.md |
| 2026-06-03 | crypt.h | leak | maybe | `logdetail` is the side-channel ledger — must not be forwarded to client ErrorResponse | open | knowledge/files/src/include/libpq/crypt.h.md |
| 2026-06-03 | fe-cancel.c | leak | likely | Unauthenticated PQcancel sends cleartext cancel packet (legacy path) | open | knowledge/files/src/interfaces/libpq/fe-cancel.c.md |
| 2026-06-03 | fe-cancel.c | correctness | likely | Cancel-key forging surface (32-bit key, unauthenticated path) | open | knowledge/files/src/interfaces/libpq/fe-cancel.c.md |
| 2026-06-03 | fe-protocol3.c | leak | likely | Error-fields `F`/`L`/`R` leak server file/line/routine in VERBOSE mode (default DEFAULT excludes them, but apps often crank verbosity up) | open | knowledge/files/src/interfaces/libpq/fe-protocol3.c.md |

---

## P1 — Undocumented invariants (medium severity)

The "you must already know" pattern: code relies on something that
isn't stated in comments. These rarely cause bugs alone but multiply
risk when the code is touched without the originating context.

Selected (full per-file list lives in each `knowledge/files/.../...md`'s
`## Potential issues` block):

- **be-secure-openssl.c** — PG_ALPN_PROTOCOL cross-file constant.
- **be-secure-openssl.c** — peer_cn / peer_dn lifetime on early return.
- **be-secure-openssl.c** — cert/key mutual consistency obligation.
- **auth-sasl.c** — shadow_pass lifetime; NULL contract.
- **auth-oauth.c** — `set_authn_id` called twice in success path.
- **auth.c** — `uaCert` fall-through to other auth methods.
- **hba.c** — `ident → peer` rewrite silently (XXX comment from PG 8.0).
- **be-fsstubs.c** — LO direct bytea access bypasses TOAST.
- **fe-secure-gssapi.c** — credential acquisition race on delegation path.
- **fe-secure-gssapi.c** — gcred not released on all failure paths.
- **fe-secure-gssapi.c** — EIO conflates wrap-error with oversize.

---

## P2 — Stale TODOs / deprecated symbols

The "remove someday" cluster.

- **libpq-fe.h** — 15+ deprecated PQ* symbols still exported for ABI compat (`PQrequestCancel`, `PQescapeString`/`PQescapeBytea`, `PQgetline`/`PQputline` family, `PQfn`, `PQoidStatus`, `PQdisplayTuples`/`PQprintTuples`, `PQsetdb`, `PQfreeNotify`, `PQinitSSL`, `CONNECTION_SETENV`, `PGRES_POLLING_ACTIVE`). Pruning needs SONAME bump.
- **fe-print.c** — `PQprint` is a 270-line legacy result-printer; deprecation candidate.
- **fe-exec.c** — `PQfn` (Function-Call protocol) legacy.
- **legacy-pqsignal.c** — exists only for pre-9.3 client binaries; ABI shim.
- **be-fsstubs.c** — "should be moved" comment dates to PG 8.0 era.
- **be-fsstubs.h** — naming wart frozen by ABI.
- **be-secure-common.c** — `pg_hosts.conf` parser still named after old design.
- **libpq-be-fe-helpers.h** — "connections not put into non-blocking mode" acknowledged but unaddressed.
- **pg-gssapi.h** — Windows X509_NAME collision is a known `#undef` hack.
- **pqsignal.h** — `sa_sigaction` not yet implemented.
- **pqcomm.h** — 1234.567x magic numbers.
- **crypt.c** — `md5_password_warnings` default + expiry threshold comments out of date.

---

## P3 — Win32 / portability shim coverage gaps

- **pthread-win32.c** — `pthread_setspecific` / `getspecific` are silent no-ops (potential silent bug if any code uses TLS via this layer).
- **pthread-win32.c** — `pthread_mutex_destroy` not provided (small handle leak).
- **win32.c** — Winsock error table dates from 1990s with obsolete DLLs still in fallback chain.
- **win32.c** — `strcpy` bounds, DLL handle leak.
- **ifaddr.c** — no explicit IPv6-mapped-IPv4 handling; `::ffff:1.2.3.4` won't match IPv4 HBA lines on platforms without `IPV6_V6ONLY`.

---

## Cross-cutting observations from the sweep

1. **`explicit_bzero` is used in exactly two places** across 60+ files reading credentials. A coordinated sweep patch would close the dominant Phase D surface. Hardest part: getting the SCRAM crypto buffers (SaltedPassword, client key, server key) zeroed without breaking error-recovery paths that still need them.

2. **The on-wire-format invariant pattern repeats from the catalog sweep.** 26 catalog headers + ~20 libpq headers all encode "this byte / character / string is the on-disk or on-wire value, do not change" without explicit warnings. A single project-wide doc-only patch could close both clusters.

3. **`PGcancelConn` riding on `PQconnectPoll`** (modern authenticated cancel) is architecturally elegant — reuses ~5000 lines of TLS/GSS/auth logic. Downside: any conn-state bug now affects both ordinary and cancel paths.

4. **The `logdetail` / `error_detail` "server-log-only" convention** is consistent but unenforced (`crypt.h`, `sasl.h`, `oauth.h`). A type-level `ServerLogOnly *` wrapper would prevent regressions.

5. **`COMMERROR` (don't try to write to client)** is a corpus-wide PG idiom used in any I/O failure path; both `pqcomm.c` and `be-gssapi-common.c` call it out. Worth a `knowledge/idioms/commerror.md` if the file-by-file pass surfaces more sites.

6. **The frontend has constant-time crypto compare (`timingsafe_bcmp`) for ServerSignature** but no equivalent client-side mutual-auth check on plain/MD5 paths — those rely entirely on TLS transport security.

7. **OpenSSL 3.x API drift is well-managed** in backend code (`#ifdef`s for SSL_CTX_set_client_hello_cb, SSL_CTX_set_num_tickets, SSL_OP_NO_RENEGOTIATION, ERR_SYSTEM_ERROR), but the **frontend ENGINE path is still active** — `USE_SSL_ENGINE` builds against 3.x will degrade to providers eventually.

8. **HBA case-handling is consistent** (SNI hostname `pg_strncasecmp` per RFC 952/921; GSSAPI realm `pg_strcasecmp` when `pg_krb_caseins_users`). No mismatch found.

9. **PGconn credential lifetime is the structural problem.** PGconn carries `pgpass`, `sslpassword`, `scram_client_key`/`scram_server_key`, `oauth_token`, `oauth_client_secret`, per-host password array — for the full connection lifetime. There is no clearance discipline in `freePGconn`. A SecretBuf wrapper + a teardown audit is the structural fix.

10. **The validator-library OAuth design** keeps heavy crypto outside the backend but runs the validator in the connecting backend's address space — a malicious or buggy validator can crash or leak. Hardening territory (sandboxing?).

## P4 — A2 follow-up: backend/libpq + header files missed by the file-grouped sweep

The 2026-06-03 A2 sweep grouped its register rows by Phase-D pattern and
left six files with inline `## Potential issues` tags unmirrored here
(`pg-corpus-maintainer` 2026-06-03 reverse-check). Mirrored below verbatim
from each per-file doc.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pqmq.c:255-263 | question | maybe | Parallel-worker DEBUG5→DEBUG1 downgrade reaches client even when client_min_messages=LOG — partial client_min_messages bypass, undocumented | open | knowledge/files/src/backend/libpq/pqmq.c.md |
| 2026-06-03 | pqmq.c:205-207 | correctness | nit | SHM_MQ_DETACHED treated as EOF/success — genuine queue-detach during transmit silently dropped, no distinct error to callers | open | knowledge/files/src/backend/libpq/pqmq.c.md |
| 2026-06-03 | pqmq.c:172-194 | undocumented-invariant | nit | SendProcSignal fires before checking send result — inverts produce-then-notify ordering; spurious signal on WOULD_BLOCK | open | knowledge/files/src/backend/libpq/pqmq.c.md |
| 2026-06-03 | pqformat.c:413-441 | correctness | maybe | pq_getmsgint returns unsigned; hostile 0xFFFFFFFF length may pass `<= maxlen` if maxlen unsigned — audit length-prefix consumers in COPY/replication/extension protocol | open | knowledge/files/src/backend/libpq/pqformat.c.md |
| 2026-06-03 | pqformat.c:511-550 | correctness | maybe | pq_getmsgbytes/pq_getmsgtext/pq_copymsgbytes int arithmetic underflows on INT32_MIN datalen if a StringInfo is synthesized from untrusted shm-mq input | open | knowledge/files/src/backend/libpq/pqformat.c.md |
| 2026-06-03 | pqformat.c:97 | undocumented-invariant | nit | msgtype stashed in buf->cursor pre-send; a future sendXXX touching cursor would silently corrupt the message type — wants Assert in pq_endmessage | open | knowledge/files/src/backend/libpq/pqformat.c.md |
| 2026-06-03 | pqformat.c (pqcomm.c) | stale-todo | nit | pq_putmessage_v2 vestige remains in pqcomm.c while pqformat has no v2 path — asymmetry bites if a v2 caller ever appears | open | knowledge/files/src/backend/libpq/pqformat.c.md |
| 2026-06-03 | pqexpbuffer.c:213 | correctness | maybe | INT_MAX ceiling silently caps PQExpBuffer growth at ~2GiB; a 2GiB request succeeds truncated and only fails-broken on the next enlargePQExpBuffer call | open | knowledge/files/src/interfaces/libpq/pqexpbuffer.c.md |
| 2026-06-03 | pqexpbuffer.c (vsnprintf) | correctness | maybe | vsnprintf on buffer tail with avail=maxlen-len could corrupt the next heap chunk on a buggy libc; relies on configure detecting broken snprintf and using src/port/snprintf.c | open | knowledge/files/src/interfaces/libpq/pqexpbuffer.c.md |
| 2026-06-03 | libpq-be-fe.h:244-257 | correctness | maybe | `#define PQclear libpqsrv_PQclear` macro takeover hides function-pointer assignments (`&PQclear`); extension callback registration silently gets the wrapper expecting a libpqsrv_PGresult* | open | knowledge/files/src/include/libpq/libpq-be-fe.h.md |
| 2026-06-03 | libpq-be-fe.h:69-119 | undocumented-invariant | maybe | libpqsrv_PQwrap uses MCXT_ALLOC_NO_OOM+ereport but libpqsrv_PGresultSetParent uses throwing MemoryContextAlloc — undocumented OOM-path asymmetry | open | knowledge/files/src/include/libpq/libpq-be-fe.h.md |
| 2026-06-03 | pqformat.h:99-124 | undocumented-invariant | maybe | pq_writestring caller must pre-size for client-encoding expansion; only an Assert guards — a non-assert build writes past the buffer on UTF-8 multibyte growth | open | knowledge/files/src/include/libpq/pqformat.h.md |
| 2026-06-03 | pqformat.h:170-187 | stale-todo | nit | pq_sendint marked deprecated with no removal horizon; new callers passing b=8 get a runtime elog(ERROR), not a compile error | open | knowledge/files/src/include/libpq/pqformat.h.md |
| 2026-06-03 | hba.h:117 | leak | maybe | HbaLine.ldapbindpasswd held as plain char* for config lifetime; no scrub/no-log hint in the header — audit hba.c errcontext/debug dumps (declaration site of the auth.c P0 LDAP-bindpasswd finding) | open | knowledge/files/src/include/libpq/hba.h.md |
| 2026-06-03 | hba.h:42 | undocumented-invariant | maybe | USER_AUTH_LAST=uaOAuth macro lives inside the enum; adding a value after uaOAuth without updating the macro silently undercounts array sizing | open | knowledge/files/src/include/libpq/hba.h.md |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| _(none yet)_ | | | | | |

## Notes

This register grew from 0 to 227 entries in a single ~13-min parallel
sweep — denser than the catalog headers register (68 entries from 72
docs). Why: libpq concentrates the auth + crypto + protocol surface
that the rest of PG delegates to it. The catalog-header issues were
mostly "undocumented invariants"; libpq's are concrete attack
surfaces.

For Phase D launch: the top 3 candidate patches that emerge from this
register, in increasing scope:

1. **Doc-only**: wire-protocol "do not change" comment sweep
   (`protocol.h`, `pqcomm.h`, SASL mechanism names) + on-disk-char
   sweep from the catalog register. Single coordinated patch.
2. **Defensive**: `explicit_bzero` sweep across auth paths + a
   `SecretBuf` wrapper to make secret-zeroing the default. Touches
   ~12 files; each change is local.
3. **Architectural**: PGconn credential clearance discipline — define
   when each secret can be safely zeroed during the connection
   lifetime, audit `freePGconn`, possibly factor secrets into a
   dedicated struct.
