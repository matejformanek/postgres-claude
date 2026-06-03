---
path: src/interfaces/libpq/fe-auth-oauth.c
anchor_sha: 4b0bf0788b0
loc: 1555
depth: deep
---

# fe-auth-oauth.c

- **Source path:** `source/src/interfaces/libpq/fe-auth-oauth.c`
- **Lines:** 1555
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-auth-oauth.h`, `fe-auth.c` (mechanism dispatch), `src/interfaces/libpq-oauth/` (the libpq-oauth plugin, OAUTHBEARER flow implementation with libcurl), `src/common/jsonapi.c` (JSON parser for server's error response), `src/common/oauth-common.c` (OAUTHBEARER_NAME, `oauth_parse_debug_flags`).

## Purpose

Client-side OAuth 2.0 / OIDC authentication for libpq via the **OAUTHBEARER** SASL mechanism (RFC 7628). Exports `pg_oauth_mech`. Handles:

- Initial bearer presentation (RFC 6750 Sec. 2.1: `auth=Bearer <token>`).
- Server-side parameter discovery — when client lacks a token, server sends a JSON error with discovery URI / scope, client retries.
- Mix-up-attack defense (RFC 9207): issuer ID must match between client config and server's discovery document.
- Three-way flow selection: user-installed v2 hook → v1 hook → builtin libpq-oauth plugin (loaded via dlopen on USE_DYNAMIC_OAUTH).
- v1-hook ABI poisoning: prevents v1 callbacks from accidentally accessing v2-only fields.

[verified-by-code, fe-auth-oauth.c:1-14]

## API surface

- `pg_oauth_mech` (47-52) — SASL vtable: `oauth_init`, `oauth_exchange`, `oauth_channel_bound`, `oauth_free`.
- `pqClearOAuthToken(conn)` (1430-1439) — `explicit_bzero` + free of `conn->oauth_token`. Called post-connect and during `pqClosePGconn`. **This is the one place in libpq's auth code that actively scrubs a secret.**

## State machine (`fe_oauth_step`, see fe-auth-oauth.h)

`oauth_exchange` (1194-1417) dispatches on `state->step`:

### `FE_OAUTH_INIT` (1208-1290)
1. Build `conn->oauth_issuer_id` / `oauth_discovery_uri` via `setup_oauth_parameters`. The latter requires both `oauth_issuer` and `oauth_client_id` set on the connection or fails. [verified-by-code, fe-auth-oauth.c:1138-1182]
2. If `conn->oauth_token` already cached → present it.
3. Else if discovery URI known → call `setup_token_request` to install a flow. May set `conn->oauth_token` immediately if the user-callback has a cached token; otherwise installs `conn->async_auth = run_oauth_flow`.
4. Else send a "discover" probe (empty `auth=` value) that's guaranteed to fail on the server, eliciting the server's metadata response.
5. Send `client_initial_response`. If we have a token, latch `client_finished_auth = true` (1287) — OAUTHBEARER has no client-side server-auth step like SCRAM. [verified-by-code, fe-auth-oauth.c:1278-1289]

### `FE_OAUTH_BEARER_SENT` (1292-1367)
- If server sent SASLFinal → unexpected for OAUTHBEARER, fail (1293-1303).
- Otherwise parse the server's JSON error via `handle_oauth_sasl_error`. Send the RFC-mandated dummy `\x01` response.
- If we had a token already (server rejected it) → transition to `FE_OAUTH_SERVER_ERROR` and wait for the FATAL.
- If still no `conn->async_auth` set, call `setup_token_request`. If a flow's cached token is available, jump to `reconnect`.
- Otherwise return `SASL_ASYNC` — caller switches to the async-poll loop driven by `run_oauth_flow`.

### `FE_OAUTH_REQUESTING_TOKEN` (1369-1383)
After the async flow finishes successfully → `goto reconnect`.

### `FE_OAUTH_SERVER_ERROR` (1385-1398)
If the server somehow sends additional data after we already saw its error: fail. RFC compliance check.

### `reconnect:` (1408-1416)
Set `conn->oauth_want_retry = true`, return `SASL_FAILED`. The libpq state machine will then restart the connection from scratch with the freshly-acquired token. **The current connection is intentionally torn down** because OAuth token retrieval may take human-loop time (device-code flow), exceeding the server's `authentication_timeout`. [from-comment, fe-auth-oauth.c:1245-1252]

## JSON parser for OAUTHBEARER error result (160-358)

- Targets top-level `status`, `scope`, `openid-configuration` fields. [verified-by-code, fe-auth-oauth.c:243-258]
- Rejects duplicate keys (327-334) and non-string values (336-343).
- Limits nesting to 8 (`MAX_SASL_NESTING_LEVEL`).
- **UTF-8 validation up front** (line 543): `pg_encoding_verifymbstr(PG_UTF8, msg, msglen)` rejects invalid bytes before the JSON parser sees them. [verified-by-code, fe-auth-oauth.c:539-548]
- Embedded NUL check (line 531-537): the server message length must match strlen — defense against a NUL-injected discovery URI.

## `issuer_from_well_known_uri` (372-512)

Derives an issuer identifier from a `.well-known/openid-configuration` or `.well-known/oauth-authorization-server` URI. Per RFC 8414 / RFC 9207:

- **HTTPS required** (389-406). HTTP only allowed if `OAUTHDEBUG_UNSAFE_HTTP` is set in the env-driven debug flags.
- **No query/fragment** in the URI (417-423). Important: a query string could carry a `?host=evil.com` smuggled past the prefix check.
- Recognizes both IETF-style (`/.well-known/openid-configuration` as PATH prefix) and OIDC-style (postfix) (431-465).
- Strips the `.well-known/...` segment to produce the issuer ID (492-511).

[verified-by-code, fe-auth-oauth.c:372-512]

## Issuer matching (mix-up defense, RFC 9207)

`handle_oauth_sasl_error` (596-623) computes `discovery_issuer` from the server's discovery URI, compares **byte-wise** (`strcmp`) against `conn->oauth_issuer_id`. Mismatch → fail with explicit "incompatible with oauth_issuer". The comment at 604-609 justifies byte-wise comparison: simpler, less attack surface than URL normalization. [from-comment, fe-auth-oauth.c:604-609]

## Builtin flow loading (3 modes, 822-996)

1. `!USE_LIBCURL` → `use_builtin_flow` is a no-op returning 0 (no builtin available).
2. `USE_DYNAMIC_OAUTH` → dlopen `libpq-oauth.so`, look up `libpq_oauth_init` and `pg_start_oauthbearer`. On macOS, absolute install path; elsewhere, basename via runtime search. Loaded plugin **stays in process for lifetime** (no dlclose). [verified-by-code, fe-auth-oauth.c:887-996]
3. Static linkage → just call `pg_start_oauthbearer` directly.

The dlopen path takes a pthread_mutex (`init_mutex`) to call `libpq_oauth_init` exactly once across threads. [verified-by-code, fe-auth-oauth.c:949-975]

## v1 → v2 hook ABI poisoning (1442-1554)

Background: libpq 18 introduced `PGoauthBearerRequestV2` with new fields (issuer, error) appended to the v1 struct. Client code written against v1 should not access these — but C has no enforcement.

`poison_req_v2(request, poison=true)`:
- Sets `request->issuer ^= 0x55aa55aa55aa55aa` (mask). If the v1 callback reads it as a string, it'll dereference garbage and crash.
- `VALGRIND_MAKE_MEM_NOACCESS` the v2-only region under Valgrind builds.
- Asserts `request->error == NULL` going in.

`poison_req_v2(request, poison=false)` reverses, and aborts with stderr message if `request->error` was set during the poison window (meaning the v1 callback wrote out-of-bounds). [verified-by-code, fe-auth-oauth.c:1466-1511]

This is unusual — defensive programming via deliberate memory corruption for misbehaving extensions. Worth flagging if Phase D wants to audit security boundaries.

## Invariants & gotchas

- **`oauth_token` is scrubbed via `explicit_bzero`** (line 1436). Only secret in libpq that gets this treatment — SCRAM password / salted password do not. [verified-by-code, fe-auth-oauth.c:1431-1438]
- **No channel binding** (`oauth_channel_bound` returns false, 1420-1423). If user sets `channel_binding=require`, OAUTHBEARER cannot be chosen — protected at the `pg_SASL_init` mechanism-priority step (fe-auth.c:577-582).
- **One issuer per client lifetime** (line 1119-1120): once `oauth_issuer_id` is set, never overwritten. Prevents an attacker server from rotating to a different IDP after the user-set issuer was selected. [verified-by-code, fe-auth-oauth.c:1119-1120]
- **`oauth_scope` from the server cannot override a user-set scope** (646-654). Defensive.
- **Discovery URI from the server cannot change once set** (632-643). Catches a server attempting to redirect after the first round.
- **`Bearer` scheme uses a trailing space as separator** in the auth header (RFC 6750). Hard-coded `"Bearer "` (133). [verified-by-code, fe-auth-oauth.c:133]
- **Async-poll integration**: `setup_token_request` allocates a heap copy of the request struct (`request_copy`, 1074-1085) because the original may live on the caller's stack; `state->async_ctx` owns the copy and `cleanup_oauth_flow` frees it.

## Potential issues

- ISSUE-libpq-oauth-001 (severity: maybe) — Token is sent **as part of an `appendPQExpBuffer(... "%s%s" ...)`** in `client_initial_response` (146). Tokens may contain format characters; printf-style insertion doesn't interpret them inside `%s`, so safe — but if the bearer-token format ever included literal control chars, no validation here would catch it. RFC 6750 allows almost-all ASCII; libpq accepts whatever the user/flow provides verbatim. [verified-by-code, fe-auth-oauth.c:115, 146]
- ISSUE-libpq-oauth-002 (severity: likely) — **No length cap on bearer token** before sending. A pathologically long token (e.g. 100 MB from a misbehaving custom flow) would be wrapped in a SASL initial-response and sent. Server caps the SASL message but the libpq side does not. DoS amplification or unintended fragmentation. [verified-by-code, fe-auth-oauth.c:113-156]
- ISSUE-libpq-oauth-003 (severity: maybe) — The `oauth_parse_debug_flags() & OAUTHDEBUG_UNSAFE_HTTP` allows HTTP discovery URIs (390-398). This is gated by a runtime env var (`PGOAUTHDEBUG`) but is a known footgun for test/CI configurations that leak into production. The flag check happens in two places (here and the flow plugin); a single audit point would be safer. [verified-by-code, fe-auth-oauth.c:389-398]
- ISSUE-libpq-oauth-004 (severity: maybe) — The poisoning logic at 1466-1511 modifies an extension-callback's input argument via XOR mask. If the v1 callback **passes a pointer to `request->issuer` to another function** (e.g. an async closure capturing the request struct), the XOR'd pointer escapes the poison window and remains scrambled — but the unpoison restores it. Side-effects via async callbacks captured during the poison window may dereference a still-XOR'd address. Only matters for misbehaving v1 callbacks but is unusual program semantics. [inferred, fe-auth-oauth.c:1466-1511]
- ISSUE-libpq-oauth-005 (severity: maybe) — `cleanup_oauth_flow` (804-817) frees `state->async_ctx` but does not zero the freed memory. The struct contained the token / error pointers — heap-residue. (The `conn->oauth_token` itself is scrubbed elsewhere.) [verified-by-code, fe-auth-oauth.c:804-817]
- ISSUE-libpq-oauth-006 (severity: maybe) — `dlopen` of `libpq-oauth.so` is keyed only by `module_name` constant. If `LD_LIBRARY_PATH` (or `DYLD_LIBRARY_PATH` on macOS) contains an attacker-controlled directory, a malicious `libpq-oauth.so` could be loaded. The macOS path uses an absolute path under `LIBDIR` (888-889), mitigating; the Linux path uses basename only (890-892), depending on the runtime linker's search order. SetUID applications using libpq via OAuth are at risk. [verified-by-code, fe-auth-oauth.c:880-894]
- ISSUE-libpq-oauth-007 (severity: maybe) — `dlerror()` is documented as not thread-safe (line 902-903). The fprintf to stderr (905, 927) under PGOAUTHDEBUG happens without a lock. Concurrent OAuth flows from multi-threaded apps may interleave error messages or read stale errors. [from-comment, fe-auth-oauth.c:900-903]

## Cross-refs

- Called by: `fe-auth.c::pg_SASL_init` (line 543 — picks `pg_oauth_mech` when server offers OAUTHBEARER and no SCRAM was already chosen).
- Builtin flow: `src/interfaces/libpq-oauth/` (separate plugin, not in this file).
- See also: `knowledge/files/src/interfaces/libpq/fe-auth.c.md`, `.../fe-auth-oauth.h.md`.

## Tally
`[verified-by-code]=27 [from-comment]=4 [from-readme]=0 [inferred]=1 [unverified]=0`
