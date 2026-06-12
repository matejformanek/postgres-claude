# libpq (backend side)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Peter Eisentraut (31), Daniel Gustafsson (16), Tom Lane (14), Nathan Bossart (9)
- **Top reviewers (last 24mo):** Jacob Champion (11), Daniel Gustafsson (11), Tom Lane (10), Andres Freund (10)
- **Recent landmark commits (12mo):**
  - `112faf1378e (Fujii Masao, 2025-07-22): Log remote NOTICE, WARNING, and similar messages using ereport().`
  - `7d8f5957792 (Tom Lane, 2025-07-25): Create infrastructure to reliably prevent leakage of PGresults.`
  - `db01c90b2f0 (Tom Lane, 2025-08-02): Silence Valgrind leakage complaints in more-or-less-hackish ways.`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/libpq/`
- **Header path:** `source/src/include/libpq/`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **README anchor:** `source/src/backend/libpq/README.SSL` (no top-level README; only the SSL-flow ASCII diagram exists)

## 1. Purpose

Backend half of the frontend/backend protocol plumbing: socket I/O,
optional TLS/GSSAPI encryption, the HBA-driven authentication dispatcher,
SCRAM/MD5/SASL/Kerberos/PAM/LDAP/Cert/OAuth method handlers, large-object
("Inversion") fmgr stubs, and the IPv4/IPv6 netmask helpers used by
pg_hba.conf parsing. Note: the *frontend* libpq under
`src/interfaces/libpq` is a totally separate codebase that just happens
to share file-name conventions (see `pqcomm.c:16-19` [from-comment]).

## 2. Mental model

- **`Port`** ([verified-by-code] `src/include/libpq/libpq-be.h:128-241`) —
  the per-backend connection record, hung off the global `MyProcPort`,
  allocated in `TopMemoryContext`. Holds the socket, FE/BE protocol
  version, remote/local sockaddrs, the matched `HbaLine`, SCRAM keys,
  GSS workspace, SSL workspace and the `raw_buf` "unread" buffer used
  during TLS bring-up.
- **Layered I/O stack.** Top: `pq_putmessage`/`pq_getmessage` (message
  framing in `pqcomm.c` / formatting in `pqformat.c`). Middle: encryption
  multiplexer in `be-secure.c:secure_read`/`secure_write` — picks TLS,
  GSSAPI, or raw based on `port->ssl_in_use` and `port->gss->enc`
  ([verified-by-code] `be-secure.c:191-211, 308-378`). Bottom: `recv()`
  / `send()` via `secure_raw_read`/`secure_raw_write`
  ([verified-by-code] `be-secure.c:271-302, 380-394`).
- **HBA == declarative match table.** `pg_hba.conf` is tokenized into
  `TokenizedAuthLine`s, then parsed into `HbaLine`s, kept as a `List`
  in `PostmasterContext`. `check_hba()` is a linear scan of this list
  — first match wins, no match → `uaImplicitReject`
  ([verified-by-code] `hba.c:2338-2438`).
- **Auth dispatch is a single switch.** `ClientAuthentication()` first
  calls `hba_getauthmethod()` (which calls `check_hba`), then dispatches
  on `port->hba->auth_method` to one of `Check{Password,PWChallenge,LDAP,
  PAM,BSDAuth,SASLAuth}`, `auth_peer`, `ident_inet`, `pg_GSS_*`, etc.
  ([verified-by-code] `auth.c:426-632`).
- **SASL is a generic inner loop.** `CheckSASLAuth(mech, port, …)` drives
  the message ping-pong via the `pg_be_sasl_mech` callback struct; both
  SCRAM and OAUTHBEARER plug in through it
  ([verified-by-code] `auth-sasl.c:49-214`).
- **`pg_hosts.conf` (SNI).** Newer addition: a sibling config file using
  the same tokenizer that maps SNI hostnames to per-host SSL certs/keys
  ([verified-by-code] `be-secure-common.c:194-352, 364-438`).

## 3. Key files

- `auth.c` (~73 KB) — auth-method dispatcher + non-SASL methods
  (peer/ident/PAM/LDAP/BSD/MD5/password/Kerberos/SSPI). Top comment
  at line 1. Entry: `ClientAuthentication` `auth.c:373`.
- `auth-sasl.c` — generic SASL exchange loop, `CheckSASLAuth`
  `auth-sasl.c:49`.
- `auth-scram.c` (~45 KB) — SCRAM-SHA-256 mech impl. (read: not deep)
- `auth-oauth.c` (~32 KB) — OAUTHBEARER mech impl. (read: not deep)
- `hba.c` (~80 KB) — tokenizer, `pg_hba.conf` / `pg_ident.conf` parser,
  `check_hba()` rule-matching loop, ident-usermap matcher.
- `be-secure.c` — encryption multiplexer + retry-on-EAGAIN with latch.
- `be-secure-openssl.c` (~67 KB) — OpenSSL backend; SSL_CTX setup, DH/ECDH
  params, BIO bindings, SNI clienthello callback, ALPN.
- `be-secure-gssapi.c` — GSSAPI encryption packets (16 KB max,
  `be-secure-gssapi.c:54` [verified-by-code]).
- `be-secure-common.c` — ssl_passphrase_command runner, key-file
  permissions check, `pg_hosts.conf` loader for SNI.
- `be-gssapi-common.c` — small helper file.
- `crypt.c` — `get_role_password`, `encrypt_password`,
  `md5_crypt_verify`, `plain_crypt_verify`. Bridges pg_authid hashes
  to the auth methods.
- `pqcomm.c` (~53 KB) — socket setup, `ListenServerPort`,
  `AcceptConnection`, `pq_init`, low-level `pq_getmessage` / `pq_flush`,
  TCP keepalive setting (interface listed in top comment `pqcomm.c:28-52`).
- `pqformat.c` — `pq_beginmessage`/`pq_sendint`/`pq_getmsgbyte` etc.
  for building and parsing FE/BE messages; also `typsend`/`typreceive`
  binary I/O (top comment `pqformat.c:1-69`).
- `pqmq.c` — redirects `pq_putmessage` to a `shm_mq` for parallel
  workers piping protocol messages back to the leader
  (`PqCommMqMethods` `pqmq.c:42`).
- `pqsignal.c` — initializes `BlockSig` / `UnBlockSig` /
  `StartupBlockSig` masks ([verified-by-code] `pqsignal.c:22-99`).
- `be-fsstubs.c` — `lo_open`/`lo_read`/`lo_write` SQL functions for
  the large-object API; LO descriptors live in a private memcxt for
  the lifetime of the xact ([from-comment] `be-fsstubs.c:14-37`).
- `ifaddr.c` — `pg_range_sockaddr`, netmask math used by hba.c
  ([verified-by-code] `ifaddr.c:42-60`).

## 4. Key data structures

- **`Port`** (`src/include/libpq/libpq-be.h:128-241`). Per-connection
  state. Allocated in TopMemoryContext (`libpq-be.h:111`
  [from-comment]). Holds `sock`, `noblock`, `raddr`/`laddr`,
  `database_name`, `user_name`, `hba` (matched rule), TCP keepalive
  knobs, SCRAM ClientKey/ServerKey, `pg_gssinfo *gss`, SSL `peer`/`ssl`,
  and the TLS-bring-up `raw_buf`/`raw_buf_consumed`/`raw_buf_remaining`
  shim ([from-comment] `libpq-be.h:230-240`).
- **`ClientConnectionInfo`** (`libpq-be.h:86-106`). Just `authn_id` +
  `auth_method`; what gets copied into parallel workers. Lifetime is
  also TopMemoryContext, must be serialized for parallelism
  ([from-comment] `libpq-be.h:79-85`).
- **`HbaLine`** (`src/include/libpq/hba.h:94-136`). One parsed
  `pg_hba.conf` line: `conntype`, `databases`, `roles`, `addr`/`mask`/
  `ip_cmp_method` or `hostname`, `auth_method` enum, plus a flat bag
  of method-specific options (ldap*, krb_realm, oauth_*, clientcert).
- **`UserAuth` enum** (`hba.h:25-43`). Values: `uaReject`,
  `uaImplicitReject`, `uaTrust`, `uaIdent`, `uaPassword`, `uaMD5`,
  `uaSCRAM`, `uaGSS`, `uaSSPI`, `uaPAM`, `uaBSD`, `uaLDAP`, `uaCert`,
  `uaPeer`, `uaOAuth`. **Order matters** — `auth.c`'s switch and the
  `UserAuthName[]` array in `hba.c` are kept in sync ([from-comment]
  `hba.h:23`).
- **`TokenizedAuthLine`** (`hba.h:177-184`). One line lexed; `fields`
  is a list-of-lists of `AuthToken`. The parser then turns it into an
  `HbaLine`, `IdentLine`, or `HostsLine`. Same tokenizer drives all
  three files.
- **`pg_be_sasl_mech`** (`src/include/libpq/sasl.h`). Callback table:
  `get_mechanisms`, `init`, `exchange`, plus `max_message_length`. SCRAM
  and OAuth each ship one ([verified-by-code] `auth-sasl.c:50-214`).
- **`PQcommMethods`** (`src/include/libpq/libpq.h:36-46`). Vtable for
  output: `comm_reset`, `flush`, `flush_if_writable`, `is_send_pending`,
  `putmessage`, `putmessage_noblock`. Default points at socket impls in
  `pqcomm.c`; `pqmq.c:pq_redirect_to_shm_mq` swaps it to the shm_mq impl
  in parallel workers ([verified-by-code] `pqmq.c:42-60`).

## 5. Control flow — the common paths

### 5.1 New connection → ClientAuthentication
1. Postmaster `accept()`s, forks (or exec's), child runs
   `BackendStartup`/`PostgresMain`. (Out-of-scope here.)
2. `pq_init(client_sock)` allocates the `Port`, sets up `FeBeWaitSet`,
   default `PqCommMethods` (the socket vtable).
3. Startup-packet read: client may send `SSLRequest`/`GSSENCRequest`
   first. Backend responds `'S'`/`'G'`/`'N'` and on `'S'`/`'G'` calls
   `secure_open_server(port)` ([verified-by-code]
   `be-secure.c:115-165`) which:
   - Drains any already-buffered unencrypted bytes into `port->raw_buf`
     so the TLS layer can re-read them (`be-secure.c:121-136`).
   - Calls `be_tls_open_server(port)` → OpenSSL handshake in
     `be-secure-openssl.c`.
4. Then the real `StartupMessage` is read and parsed; `port->database_name`,
   `port->user_name` get filled.
5. `ClientAuthentication(port)` is called:
   - `hba_getauthmethod(port)` → `check_hba(port)` walks
     `parsed_hba_lines` (see §5.2). Sets `port->hba` (or
     `uaImplicitReject` line).
   - Pre-auth: if `hba->clientcert != clientCertOff`, require
     `secure_loaded_verify_locations() && port->peer_cert_valid`
     ([verified-by-code] `auth.c:403-421`).
   - `switch (port->hba->auth_method)` dispatches
     ([verified-by-code] `auth.c:426-632`). Examples:
     - `uaMD5`/`uaSCRAM` → `CheckPWChallengeAuth` →
       `CheckSASLAuth(&pg_be_scram_mech, …)` or `CheckMD5Auth`.
     - `uaPeer` → `auth_peer(port)` (getpeereid + ident-usermap).
     - `uaCert` → fall-through `STATUS_OK`, then `CheckCertAuth(port)`
       (handled below).
     - `uaOAuth` → `CheckSASLAuth(&pg_be_oauth_mech, …)`.
   - Post-auth: if `clientcert == clientCertFull` or method is `uaCert`,
     call `CheckCertAuth(port)` ([verified-by-code] `auth.c:634-646`).
   - `ClientAuthentication_hook` is fired (extensions).
   - On OK: `sendAuthRequest(port, AUTH_REQ_OK, …)`; on fail:
     `auth_failed()` which `ereport(FATAL)`s with a method-specific
     message ([verified-by-code] `auth.c:233-318`).

### 5.2 `check_hba` rule-matching order [verified-by-code]
`hba.c:2338-2438` — for each `HbaLine` in `parsed_hba_lines`:
1. **Connection type**: `ctLocal` requires `AF_UNIX`. `ctHostSSL` /
   `ctHostNoSSL` filtered by `port->ssl_in_use`. `ctHostGSS` /
   `ctHostNoGSS` filtered by `port->gss && port->gss->enc`.
2. **IP / hostname**: `ip_cmp_method` switch — `ipCmpMask` →
   `check_hostname()` if `hba->hostname` set, else `check_ip()` against
   `addr`/`mask`. `ipCmpSameHost`/`ipCmpSameNet` →
   `check_same_host_or_net()` (compares to interface list from
   `ifaddr.c`). `ipCmpAll` matches.
3. **Database** (`check_db`): special tokens `all`, `sameuser`,
   `samerole`, `samegroup`, `replication`, `@filename` are expanded;
   otherwise a literal match.
4. **Role** (`check_role`): supports `+rolename` (group membership via
   `is_member`), regex matching, `all`, `@filename`.
5. First line that survives all four → `port->hba = hba; return`.
6. No match → `palloc0` an `HbaLine` with `auth_method =
   uaImplicitReject`. **There is no second pass and no priority** —
   this is the linear-first-match semantics users see.

### 5.3 secure_read with EAGAIN/latch retry
`be-secure.c:182-269` [verified-by-code]:
1. Pre-call `ProcessClientReadInterrupt(false)`.
2. Pick TLS/GSS/raw read.
3. If `n<0 && !noblock && (errno == EWOULDBLOCK || EAGAIN)`: arm
   `FeBeWaitSet` for the appropriate event, `WaitEventSetWait` blocking
   forever. On `WL_POSTMASTER_DEATH` → `FATAL`. On `WL_LATCH_SET` →
   `ResetLatch + ProcessClientReadInterrupt(true)` and `goto retry`.
4. `ProcessClientReadInterrupt(false)` again on success.

`secure_write` mirrors this exactly with the writable variants
([verified-by-code] `be-secure.c:308-378`).

### 5.4 SASL message ping-pong [verified-by-code] `auth-sasl.c:49-214`
1. Send list of supported mechanisms as `AUTH_REQ_SASL`.
2. Loop:
   - Read `PqMsg_SASLResponse`. On EOF return `STATUS_EOF`.
   - First iter: read mech name + initial-response payload; call
     `mech->init(port, selected_mech, shadow_pass)` → opaque state.
   - Call `mech->exchange(opaq, input, inputlen, &output, &outputlen,
     logdetail)`.
   - If output: send `AUTH_REQ_SASL_CONT` (or `AUTH_REQ_SASL_FIN` on
     `PG_SASL_EXCHANGE_SUCCESS`).
3. On `PG_SASL_EXCHANGE_ABANDONED` → set `*abandoned`. On
   non-SUCCESS → `STATUS_ERROR`.

## 6. Locking and invariants

This subsystem is single-threaded per backend — no LWLocks here. The
relevant invariants are about *lifetimes* and *ordering*:

- `Port`, `ClientConnectionInfo`, `port->hba` all live in
  `TopMemoryContext` ([from-comment] `libpq-be.h:81, 111`).
- `parsed_hba_lines` lives in `PostmasterContext`, in a child
  `AllocSetContext` named `"hba parser context"` ([verified-by-code]
  `hba.c:2473-2476`). Reload swaps the list atomically only after the
  whole file parses OK ([verified-by-code] `hba.c:2440-2503` head comment).
- `set_authn_id()` must be called **exactly once** per successful auth.
  Calling it twice `ereport(FATAL)`s with "authentication identifier
  set more than once" ([verified-by-code] `auth.c:336-366`). This is
  defense against two providers fighting.
- `auth_failed()` is `Assert(elevel >= FATAL)` — failure always exits
  the backend ([verified-by-code] `auth.c:240`).
- TLS bring-up uses the `port->raw_buf` shim because any startup bytes
  that landed in the upper-layer buffer must be re-fed to OpenSSL via
  the BIO ([verified-by-code] `be-secure.c:121-155`,
  `be-secure-openssl.c:port_bio_read`).
- The `PQ_GSS_MAX_PACKET_SIZE = 16384` is *part of the wire protocol*
  and "can't ever be changed" ([from-comment]
  `be-secure-gssapi.c:46-54`).
- `PQcommMethods` indirection means anything that writes via
  `pq_putmessage` works the same in a normal backend or a parallel
  worker — the only behavioral difference is what `pqmq.c` does on
  flush. Don't bypass it.

## 7. Interactions with other subsystems

- **postmaster/** calls `ListenServerPort`, `AcceptConnection`,
  `pq_init`. Calls `ClientAuthentication` from
  `tcop/backend_startup.c`.
- **commands/user.c** — `crypt.c:encrypt_password` is used when
  CREATE/ALTER ROLE PASSWORD runs.
- **access/parallel** — `pqmq.c` redirects protocol output to a
  `shm_mq`; the leader reads via `pq_parse_errornotice`.
- **catalog/pg_authid** — `crypt.c:get_role_password` reads
  `rolpassword` and `rolvaliduntil`.
- **utils/misc/guc.c** — many `ssl_*`, `password_*`, `pg_krb_*` GUCs
  live in this module.
- **storage/large_object.c** — `be-fsstubs.c` calls into it for the
  actual LO read/write.
- **regex/** — `hba.c` compiles regex for `/^...$` HBA tokens.
- **executor / fmgr** — `foreign/` (separate doc) uses `Port`
  indirectly via `MyClientConnectionInfo` for FDW user-mapping.

## 8. Tests

- `src/test/authentication/` — TAP tests for HBA + each auth method
  (peer, scram, ldap, kerberos under separate dirs).
- `src/test/ssl/` — TAP tests for TLS, SNI, cert auth.
- `src/test/kerberos/`, `src/test/ldap/`, `src/test/modules/oauth_validator/`.
- No core regression-suite tests for auth — needs real OS / network
  resources, so it's TAP-only.

## 9. Open questions / unverified claims

1. **OAuth mechanism details** — `auth-oauth.c` is unread (32 KB);
   only know it plugs into `CheckSASLAuth` via `pg_be_oauth_mech` and
   has a special "abandoned" exchange flow.
2. **SCRAM channel binding details** — `auth-scram.c` and the
   `tls-server-end-point` cert hash path through
   `be_tls_get_certificate_hash` are unverified.
3. **`check_hostname` forward-confirmed-reverse-DNS semantics** —
   sketched only; the `remote_hostname_resolv` state machine in
   `libpq-be.h:115-125` is read from comments, not validated against
   `hba.c:1074-1163`.
4. **Parallel-leader path** for `pqmq.c` (`pq_set_parallel_leader`,
   `pq_parse_errornotice`) is not traced end-to-end.
5. **SSPI** Windows code path — unverified beyond the dispatcher case.
6. **`pg_hosts.conf` lifecycle** — when is it (re)loaded relative to
   `SIGHUP`? Read only the parser, not the call site.

## 10. Glossary

- **HBA** — Host-Based Authentication; the `pg_hba.conf` rules.
- **Port** — backend's per-connection context (`MyProcPort`).
- **uaXxx** — `UserAuth` enum values (auth methods).
- **ctXxx** — `ConnType` enum (local / host / hostssl / …).
- **SASL** — Simple Authentication and Security Layer, the generic
  challenge-response framework SCRAM and OAUTHBEARER both speak.
- **SCRAM** — Salted Challenge Response Authentication Mechanism;
  PG's default password auth, RFC 5802.
- **TLS / SSL** — used interchangeably in the source; OpenSSL is the
  only backend currently shipped (`USE_OPENSSL`).
- **GSSAPI** — Generic Security Services API; PG uses it for Kerberos
  auth and for full-stream encryption (separate from TLS).
- **SNI** — Server Name Indication; the TLS extension that lets a
  client tell the server which hostname it wants a cert for.
  `pg_hosts.conf` configures the cert/key per SNI host.
- **`FeBeWaitSet`** — the WaitEventSet covering the client socket +
  latch + postmaster-death pipe.
- **shadow_pass** — the encrypted password fetched from
  `pg_authid.rolpassword`.
- **Large Object / LO / Inversion** — historical PG blob storage,
  accessed by `lo_*` fmgr functions in `be-fsstubs.c`.
- **Implicit reject** — no `pg_hba.conf` line matched. Different error
  message from explicit `reject` so the DBA can tell which case it is
  ([from-comment] `auth.c:428-438`).
