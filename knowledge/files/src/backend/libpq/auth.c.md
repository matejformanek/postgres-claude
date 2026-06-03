---
path: src/backend/libpq/auth.c
anchor_sha: 4b0bf0788b0
loc: 2779
depth: deep
---

# auth.c

- **Source path:** `source/src/backend/libpq/auth.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 2779

## Purpose

The top-level driver for client authentication. After the TLS/GSS
negotiation has produced a populated `Port`, the per-connection
backend calls `ClientAuthentication(Port *)`; that function dispatches
on `port->hba->auth_method` and either succeeds (sending
`AUTH_REQ_OK`) or calls `auth_failed()` which `proc_exit`s. Every
backend goes through this funnel before `InitPostgres` continues; it
is the *only* place where the trust boundary between an
unauthenticated socket peer and a logged-in role is crossed.

Implements the non-SASL methods inline (password / MD5 / GSSAPI /
SSPI / ident / peer / PAM / BSD auth / LDAP / cert) and dispatches
SASL (SCRAM, OAuth) into `auth-sasl.c`. [from-comment, auth.c:1-13;
verified-by-code, auth.c:374-675]

## Public API surface

- `ClientAuthentication(Port *port)` — `auth.c:374`. The top-level
  driver. Does the pre-auth `clientcert` check (auth.c:403-421),
  switches on `auth_method` (auth.c:426-632), runs the post-auth cert
  usermap check for `clientCertFull`/`uaCert` (auth.c:634-646), fires
  the `ClientAuthentication_hook` (auth.c:665), then either
  `AUTH_REQ_OK` or `auth_failed()`. [verified-by-code, auth.c:373-675]
- `sendAuthRequest(Port *port, AuthRequest areq, const void *extradata, int extralen)`
  — `auth.c:682`. Writes one `AuthenticationRequest` ('R') message,
  flushes immediately unless `areq` is `AUTH_REQ_OK` or
  `AUTH_REQ_SASL_FIN` (which piggyback on the ReadyForQuery flush).
  [verified-by-code, auth.c:681-704]
- `set_authn_id(Port *port, const char *id)` — `auth.c:336`. Sets
  `MyClientConnectionInfo.authn_id` exactly once; ereports `FATAL` on
  a second call (auth.c:348-352). Auth methods are required to call
  it as soon as the underlying identity is established, *before*
  usermap. [verified-by-code, auth.c:335-366]
- Globals: `ClientAuthentication_hook` (auth.c:217), `pg_krb_server_keyfile`,
  `pg_krb_caseins_users`, `pg_gss_accept_delegation` (auth.c:174-176),
  `ldap_password_hook` (auth.c:157). [verified-by-code]

## Internal landmarks

- **`auth_failed`** (auth.c:233) — per-method translatable error
  string; uses `ERRCODE_INVALID_AUTHORIZATION_SPECIFICATION` unless
  the method is password-like, in which case it switches to
  `ERRCODE_INVALID_PASSWORD` so that libpq's `.pgpass` retry logic
  triggers. `proc_exit(0)` on `STATUS_EOF` to avoid log spam from
  password-less psql probes. [verified-by-code, auth.c:233-318]
- **The dispatch switch** at auth.c:426. Has explicit `Assert(false)`
  branches in the `#else` arms for `uaGSS`, `uaSSPI`, `uaPAM`,
  `uaBSD`, `uaLDAP` — `hba.c` will reject an HBA line whose method
  isn't compiled in, so reaching the assert is a corruption bug.
  [verified-by-code, auth.c:565-621]
- **Password-method spine:** `CheckPasswordAuth` (auth.c:793) →
  `recv_password_packet` → `get_role_password` → `plain_crypt_verify`
  (in `crypt.c`); `CheckPWChallengeAuth` (auth.c:828) dispatches
  between `CheckMD5Auth` (auth.c:888) and SASL/SCRAM. Both `pfree` the
  shadow password before returning. [verified-by-code, auth.c:792-917]
- **`recv_password_packet`** (auth.c:712) — guards against
  `mtype != 'p'`, oversize messages (`PG_MAX_AUTH_TOKEN_LENGTH`), and
  empty passwords (`buf.len == 1`, auth.c:767-770). Empty passwords
  are rejected here so PAM/LDAP don't silently accept "no password".
  [verified-by-code, auth.c:711-781]
- **GSSAPI block** (auth.c:925-1172). `pg_GSS_recvauth` does the SPNEGO
  loop with `gss_accept_sec_context`; `pg_GSS_checkauth` splits at `@`,
  strips realm if `!include_realm`, optionally matches
  `port->hba->krb_realm`, then runs `check_usermap`. Sets
  `set_authn_id(princ)` *before* the usermap check (auth.c:1118) so
  the log captures who tried, regardless of the map outcome.
  [verified-by-code, auth.c:925-1171]
- **Ident** (auth.c:1685) — TCP to RFC 1413 port 113 on the client
  host; bound to local IP so the ident daemon can correlate.
  Synchronous `recv`, no `WaitLatchOrSocket` (auth.c:1681-1683 has an
  XXX). [verified-by-code, auth.c:1684-1854]
- **Peer** (auth.c:1870) — `getpeereid()` + `getpwuid_r()` on Unix-socket
  connections. Bails with `ENOSYS` message if the platform lacks
  `getpeereid`. [verified-by-code, auth.c:1869-1928]
- **LDAP** (auth.c:2231-2670) — two modes: search+bind
  (`ldapbasedn`-driven) and simple bind. The search-mode path
  hand-filters `* ( ) \ /` from `port->user_name` (auth.c:2528-2542) to
  block LDAP filter injection. Bind passwords flow through the
  pluggable `ldap_password_hook`. [verified-by-code]
- **CheckCertAuth** (auth.c:2701) — chooses `peer_dn` vs `peer_cn` per
  `hba->clientcertname`; for `uaCert` records the DN as the authn_id
  *before* check_usermap (auth.c:2749). [verified-by-code,
  auth.c:2700-2778]

## Invariants & gotchas

- `set_authn_id` must be called by every auth method on success, and
  must not be called twice. The "two providers fighting" `FATAL` is a
  hard tripwire (auth.c:348-352). [verified-by-code]
- Empty passwords are rejected at the wire (auth.c:767-770); HBA-level
  `password` / `LDAP` / `PAM` cannot accept "" even if the back-end
  authority would. CREATE/ALTER USER ALSO forbids storing "" — the
  wire check exists because PAM/LDAP delegate, so the catalog check
  isn't enough. [from-comment, auth.c:754-766]
- `MD5` salt is generated via `pg_strong_random(md5Salt, 4)` and the
  function returns `STATUS_ERROR` on RNG failure rather than falling
  through (auth.c:894-900). [verified-by-code]
- `CheckPWChallengeAuth` picks the wire mechanism (MD5 vs SCRAM) based
  on the *stored* hash type, falling back to `Password_encryption`
  when the user doesn't exist, "so most genuine users probably have a
  password of that type, and if we pretend that this user had a
  password of that type, too, it 'blends in' best." This is the
  user-enumeration defense. [from-comment, auth.c:840-848;
  verified-by-code, auth.c:849-868]
- Replication walsenders get differently-worded `pg_hba.conf rejects
  replication connection` / `no pg_hba.conf entry for replication
  connection` messages (auth.c:458-465, 525-532). Database
  walsenders (`am_db_walsender`) fall through to the regular path.
  [verified-by-code]
- The `ClientAuthentication_hook` fires regardless of outcome so
  extensions can log every attempt or insert post-failure delays
  (auth.c:213-217, 665-666). [from-comment]
- `uaCert` is implemented by falling through `uaTrust` (status set to
  `STATUS_OK`) and then the post-switch block at auth.c:634-646 forces
  `CheckCertAuth`. Easy to misread; comment at auth.c:624 flags it.
  [verified-by-code]

## Cross-refs

- Header: `knowledge/files/src/include/libpq/auth.h.md`
  (prototype list; this doc covers implementation).
- Subsystem: `knowledge/subsystems/libpq-backend.md` (planned).
- SASL framework: `knowledge/files/src/backend/libpq/auth-sasl.c.md`.
- Mechanism impls: `auth-scram.c.md`, `auth-oauth.c.md`.
- Password storage: `crypt.c.md`.
- Frontend counterpart: `src/interfaces/libpq/fe-auth.c`.

## Potential issues

- **[ISSUE-leak: client password buffer not zeroed before pfree]**
  `auth.c:801-816` — `CheckPasswordAuth` receives `passwd` via
  `recv_password_packet`, passes it to `plain_crypt_verify`, then
  `pfree(passwd)` without `explicit_bzero`. The plaintext sits in
  freed allocator memory until that chunk is reused. Same pattern in
  `CheckMD5Auth` (auth.c:914), `CheckLDAPAuth` (auth.c:2497, 2666),
  PAM (`pam_passwd` global). Compare with `auth-oauth.c:341` which
  *does* `explicit_bzero(input_copy, inputlen)` after token use —
  inconsistency suggests the password path predates the discipline.
  Severity: maybe (per-connection backend exits soon, but during the
  session a `pg_log_backend_memory_contexts` snapshot could surface
  it).
- **[ISSUE-leak: shadow password not zeroed on free]** `auth.c:814-815,
  870-871` — `pfree(shadow_pass)` without `explicit_bzero`. The
  shadow contains SCRAM StoredKey/ServerKey or MD5 hash — not the
  plaintext, but recovery of these enables offline brute force.
  Severity: maybe.
- **[ISSUE-correctness: ident_inet lacks timeout / interrupt
  responsiveness]** `auth.c:1681-1683, 1811-1816` — the XXX comment
  flags it explicitly. `recv()` blocks indefinitely if the ident
  daemon stops responding mid-reply; only `CHECK_FOR_INTERRUPTS` in
  the EINTR retry loop helps, and a slow remote can stall the backend
  to `authentication_timeout`. Severity: maybe (documented).
- **[ISSUE-undocumented-invariant: uaCert path implicitly forces
  CheckCertAuth via uaTrust fall-through]** `auth.c:623-626, 634-646`
  — comments call this out but anyone refactoring the switch could
  easily break it by adding a `break` after `uaCert`. Tag this as
  needing a corpus note. Severity: nit.
- **[ISSUE-leak: ldap_simple_bind_s passes plaintext, no scrub]**
  `auth.c:2648` — `passwd` is sent to LDAP server in cleartext over
  the LDAP socket (start-TLS optional via `ldaptls`); on failure path
  the `pfree(passwd)` (auth.c:2666) does not `explicit_bzero`.
  Severity: maybe.
- **[ISSUE-question: ident protocol over IPv6 / behind NAT]**
  `auth.c:1762-1775` — the bind-to-local-IP comment assumes the
  ident daemon sees the same 4-tuple. With NAT or proxy-protocol
  this is wrong; no mention of `PROXY` headers. Severity: nit.
- **[ISSUE-doc-drift: GSSAPI block still says "MIT Kerberos required"
  but credential store extensions never wired up]** `auth.c:937-941,
  544-547` — comment says "we might consider using the credential
  store extensions in the future" but the future never arrived; flag
  for triage. Severity: nit.

## Tally

`[verified-by-code]=22 [from-comment]=8 [inferred]=0`
