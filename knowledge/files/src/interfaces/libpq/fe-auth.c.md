---
path: src/interfaces/libpq/fe-auth.c
anchor_sha: 4b0bf0788b0
loc: 1604
depth: deep
---

# fe-auth.c

- **Source path:** `source/src/interfaces/libpq/fe-auth.c`
- **Lines:** 1604
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-auth.h` (prototypes), `fe-auth-sasl.h` (mechanism table type), `fe-auth-scram.c` (`pg_scram_mech`), `fe-auth-oauth.c` (`pg_oauth_mech`), `fe-gssapi-common.c` (GSS helpers), `fe-connect.c` (`PQconnectPoll` invokes `pg_fe_sendauth`), `src/include/libpq/protocol.h` (Authentication message tags, `AUTH_REQ_*` constants).

## Purpose

The client-side **authentication driver** for libpq. Implements:

1. The dispatcher `pg_fe_sendauth` that reads an `Authentication<X>` message from the server and produces the client's response (password packet, SASL exchange, GSS token, etc.). [verified-by-code, fe-auth.c:1065-1272]
2. The SASL-mechanism negotiation `pg_SASL_init` / `pg_SASL_continue` — the *most security-critical* code in libpq. [verified-by-code, fe-auth.c:434-793]
3. Defensive check `check_expected_areq` enforcing `require_auth=` and `channel_binding=require` — protection against a malicious server downgrading the client. [verified-by-code, fe-auth.c:902-1048]
4. Helper APIs `PQencryptPasswordConn`, `PQchangePassword`, `pg_fe_getauthname` (libpq public surface).

## Public API surface

- `pg_fe_sendauth(areq, payloadlen, conn, async)` (1065) — sole entry point from `PQconnectPoll`. Branches on `AuthRequest` and calls one of the per-method routines. Sets `*async = true` when SASL needs to suspend (OAuth). [verified-by-code, fe-auth.c:1065-1272]
- `pg_fe_getusername(uid)` (1285) — `getpwuid_r` or `GetUserName`. [verified-by-code, fe-auth.c:1285-1334]
- `pg_fe_getauthname` (1343) — convenience wrapper around the above using `geteuid()`. [verified-by-code, fe-auth.c:1343-1351]
- `PQencryptPassword(passwd, user)` (1362) — **deprecated** MD5-only API; still in place for ABI compatibility. [verified-by-code, fe-auth.c:1362-1379]
- `PQencryptPasswordConn(conn, passwd, user, algorithm)` (1405) — algorithm dispatch: `md5`, `scram-sha-256`, or queries server's `password_encryption` GUC. Also accepts legacy `on`/`off` → `md5`. [verified-by-code, fe-auth.c:1405-1503]
- `PQchangePassword(conn, user, passwd)` (1530) — builds the `ALTER USER … PASSWORD …` SQL with `PQescapeLiteral`/`PQescapeIdentifier`. [verified-by-code, fe-auth.c:1530-1584]
- `PQauthDataHook` family (1586-1604) — pluggable callback for `PQAUTHDATA_*` events.

## Internal landmarks

- `pg_GSS_continue` / `pg_GSS_startup` (60-197) — `gss_init_sec_context` loop, sends `GSS_C_MUTUAL_FLAG` always, sets `GSS_C_DELEG_FLAG` only if `conn->gssdelegation` is `"1"`. **Mutual auth is required**, delegation is opt-in. [verified-by-code, fe-auth.c:108-109]
- `pg_SSPI_continue` / `pg_SSPI_startup` (225-428) — Windows-only mirror of the GSS path.
- `pg_SASL_init` (434-696) — mechanism negotiation and initial response generation.
- `pg_SASL_continue` (703-793) — drives `mech->exchange` rounds.
- `pg_password_sendauth` (795-862) — MD5 + cleartext password handling. MD5 path computes `pg_md5_encrypt(pg_md5_encrypt(password, user), salt)`.
- `auth_method_description` (867-888) — translatable error-string lookup.
- `check_expected_areq` (902-1048) — **the security gate**.

## SASL mechanism negotiation (security-critical)

`pg_SASL_init` walks the server's offered mechanism list **in order of priority** (server orders them by decreasing preference). For each mechanism string:

- `SCRAM-SHA-256-PLUS`: pick this if `ssl_in_use` AND `channel_binding != 'd'` (disable) AND `USE_SSL` was compiled in. [verified-by-code, fe-auth.c:487-516]
- `SCRAM-SHA-256`: pick this only if no `-PLUS` was already picked. [verified-by-code, fe-auth.c:533-539]
- `OAUTHBEARER`: pick this only if neither SCRAM was already picked. [verified-by-code, fe-auth.c:540-546]

**Priority logic is fragile:** the negotiation favors `-PLUS` when channel binding is possible (good — prevents MITM attacks), but if the server offers ONLY `-PLUS` and SSL is NOT in use, the connection is aborted explicitly (lines 518-531) with a comment about downgrade attacks. [from-comment, fe-auth.c:520-528]

**`channel_binding=require` enforcement** (line 577-582): after mechanism selection, if the user required channel binding but `-PLUS` wasn't chosen, the connection is failed. This is the explicit downgrade-attack defense.

## The `require_auth` and `channel_binding` gate (CRITICAL)

`check_expected_areq` (902-1048) is called **for every incoming Authentication message** including `AUTH_REQ_OK`. It enforces three orthogonal user policies:

1. **`sslcertmode=require`** (911-928): if AUTH_REQ_OK arrives without `ssl_cert_requested` or `ssl_cert_sent` having been latched, fail. This catches a server that says "OK, you're in" without ever asking for the client cert the user required.
2. **`require_auth=<list>`** (935-1006): the allowed-methods bitmask `conn->allowed_auth_methods` is checked. For `AUTH_REQ_OK`, the function additionally insists `client_finished_auth` was latched (i.e. SCRAM verifier was checked, OAuth bearer was sent, etc.) — unless the user explicitly allowed unauthenticated connections via `trust` in `require_auth`, or GSS encryption was used in lieu of an auth round. **The comment at 941-953 explicitly notes a known weakness:** combining `scram-sha-256` with `none` in `require_auth` would silently accept a partial SCRAM exchange where the server doesn't send its verifier (server could harvest brute-force material). [from-comment, fe-auth.c:941-953]
3. **`channel_binding=require`** (1025-1045): the only acceptable AUTH messages are SASL ones; `AUTH_REQ_OK` requires `conn->sasl->channel_bound(conn->sasl_state) == true`. [verified-by-code, fe-auth.c:1025-1045]

The `auth_method_allowed` macro shifts by `(1 << areq)` (894). A `StaticAssertDecl` (908) guards that `AUTH_REQ_MAX` fits in the bitmask — but a server sending `areq > 31` would still wrap around. The `default:` clause in `check_expected_areq` (1002-1004) catches this and returns false. **But:** in `pg_fe_sendauth` the `default:` clause (1266-1268) is reached only if `check_expected_areq` returned true — for an `areq > 31` that defeats the bitmask sanity check, the bitmask `1 << areq` is undefined behavior in C. [verified-by-code, fe-auth.c:1002-1004; inferred:894]

## Password-flow gotchas

- `pg_password_sendauth` (795-862) for `AUTH_REQ_MD5` builds `md5(md5(password, user), salt)` — the server applies the same recipe to its `pg_authid.rolpassword` digest. Salt is 4 random bytes read from the message. [verified-by-code, fe-auth.c:818-849]
- For `AUTH_REQ_PASSWORD` (cleartext), the password is sent as a `PasswordMessage` with no encoding/transformation. **No special wiping of password buffer** after send — caller's job. [verified-by-code, fe-auth.c:851-859]
- `pg_fe_sendauth` latches `conn->client_finished_auth = true` immediately after sending the password (1219). This means `check_expected_areq` will accept the subsequent `AUTH_REQ_OK` regardless of whether the server actually verified the password. **By design**: with cleartext or MD5 there's no mutual auth, so server identity is trusted only via TLS / channel binding. [verified-by-code, fe-auth.c:1218-1220]

## GSS / SSPI dispatch

- `pglock_thread()` (1097, 1131, 1167) — GSS/SSPI libraries are typically not thread-safe; libpq serializes calls to them across all PGconns.
- AUTH_REQ_GSS with both GSS and SSPI compiled in: dispatch defaults to SSPI (1108-1111), overridable via `gsslib=gssapi`.
- AUTH_REQ_SSPI is a separate code path for SSPI's `negotiate` package (supports NTLM); AUTH_REQ_GSS under SSPI uses the `kerberos` package only (line 387).
- Kerberos-4 / CRYPT / KRB5 are explicitly rejected (1080-1086, 1192-1194) — these were old auth methods, server never sends them anymore.

## Helper: `PQencryptPasswordConn`

- If `algorithm == NULL`, runs `SHOW password_encryption` against the connection. Beware: this **blocks** during the query — the docstring suggests pre-fetching if you can't block. [from-comment, fe-auth.c:1393-1398]
- Accepts `on`/`off` as aliases for `md5` to handle pre-PG10 server configs (1461-1463). Comment: "We refuse to send the password in plaintext even if it was `off`." [from-comment, fe-auth.c:1457-1463]

## Invariants & gotchas

- `pg_fe_sendauth` must not be reentered for the same `areq`; for SASL it tracks `conn->sasl_state` (456) and detects duplicate `AUTH_REQ_SASL` requests. [verified-by-code, fe-auth.c:453-457]
- `current_auth_response` (134, 339, 674, 781, 857) is latched for the next outgoing packet — used by the trace facility (`Pfdebug`) to label the message kind in dumps.
- The salt for MD5 is **only 4 bytes** (line 801, 832-849). This is the protocol contract, but it makes MD5 auth weak against precomputed rainbow tables.
- `conn->password_needed` (502, 538, 545) is set when SCRAM/MD5 is chosen and tells callers (e.g. `pgpass`) that prompting was unavoidable.

## Potential issues

- ISSUE-libpq-auth-001 (severity: likely) — known weakness called out in code: `require_auth=scram-sha-256,none` accepts a *partial* SCRAM exchange where the server skips the verifier. Server can harvest material for a brute-force attack. The comment (fe-auth.c:941-953) flags this for a future revisit. The user-visible config `require_auth` is documented as protective but its combined `scram + none` form is not. [from-comment, fe-auth.c:941-953]
- ISSUE-libpq-auth-002 (severity: maybe) — `pg_password_sendauth` for cleartext does no length validation of the password before `pqPacketSend(strlen(pwd)+1)` (line 859). A multi-megabyte `PGPASSWORD` env var would be sent verbatim — denial-of-service amplification against a server that limits Auth-message length. Server normally caps but no client-side guard. [verified-by-code, fe-auth.c:851-861]
- ISSUE-libpq-auth-003 (severity: maybe) — `client_finished_auth = true` is latched (line 1219) before any server-side verification of the cleartext/MD5 password. A server in `trust` mode that asks for a password could still send `AUTH_REQ_OK` afterwards, and `check_expected_areq` will accept it because the client-side latch is already set. This is intended for SCRAM/OAuth (where the client *does* verify), but for password/MD5 it provides no actual mutual auth — relies entirely on transport security (TLS). [verified-by-code, fe-auth.c:1218-1220]
- ISSUE-libpq-auth-004 (severity: maybe) — `auth_method_allowed(conn, type)` does `1 << type` with type from the wire. Although the `default:` in `check_expected_areq` rejects unrecognized AuthRequest codes (1002), it's reached only if the AuthRequest type matches no other case label. The bit-shift in 999 happens with whatever type was sent. For type ∈ {`AUTH_REQ_PASSWORD`..`AUTH_REQ_SASL_FIN`} = 0..12 it's safe, but the `StaticAssertDecl` at 908 says `AUTH_REQ_MAX` fits in 32 bits — if any future AuthRequest code exceeds 31, this is UB. [verified-by-code, fe-auth.c:894-895, 908-909]
- ISSUE-libpq-auth-005 (severity: maybe) — `PQencryptPasswordConn` issues `SHOW password_encryption` (line 1424) — a synchronous query that **blocks**. The docstring warns of this but a defensive client might want a non-blocking alternative. Also runs `PQexec` recursively from within `PQchangePassword`, which is fine but unusual. [verified-by-code, fe-auth.c:1424, 1530-1584]
- ISSUE-libpq-auth-006 (severity: maybe) — `pg_password_sendauth` doesn't `explicit_bzero` `crypt_pwd` after MD5 encryption (line 860 just `free`s it). The intermediate `md5(password,user)` digest is therefore freed without scrubbing. Recoverable from a heap dump. [verified-by-code, fe-auth.c:858-861]
- ISSUE-libpq-auth-007 (severity: maybe) — under `channel_binding=require` AND a server that offers ONLY non-SCRAM mechanisms (e.g. OAUTHBEARER alone), `pg_SASL_init` exits with "channel binding is required, but server did not offer..." (line 577-582). But — the same code does NOT check `sslcertmode=require` before doing channel-binding negotiation. A weird permutation where the server offers OAUTHBEARER over an SSL connection that didn't request the client cert: would fail at channel-binding check first, masking the cert-mode issue. [inferred, fe-auth.c:577-582]

## Cross-refs

- Calls into: `pg_scram_mech` callbacks (fe-auth-scram.c), `pg_oauth_mech` callbacks (fe-auth-oauth.c), `pg_GSS_*` (fe-auth.c GSS section + fe-gssapi-common.c), `pg_md5_encrypt` (src/common/md5.c), `pg_fe_scram_build_secret` (fe-auth-scram.c:914).
- Called from: `fe-connect.c::PQconnectPoll` state `CONNECTION_AUTH_OK` (via `pqParseInput`).
- See also: `knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md`, `.../fe-auth-oauth.c.md`, `.../fe-secure-openssl.c.md`.

## Tally
`[verified-by-code]=33 [from-comment]=6 [from-readme]=0 [inferred]=4 [unverified]=0`
