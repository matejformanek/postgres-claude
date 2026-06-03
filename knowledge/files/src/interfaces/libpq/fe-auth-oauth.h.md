---
path: src/interfaces/libpq/fe-auth-oauth.h
anchor_sha: 4b0bf0788b0
loc: 47
depth: shallow
---

# fe-auth-oauth.h

- **Source path:** `source/src/interfaces/libpq/fe-auth-oauth.h`
- **Lines:** 47
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-auth-oauth.c` (implementation), `fe-auth-sasl.h` (struct type), `fe-auth.c` (chooses `pg_oauth_mech`), libpq-oauth plugin (`libpq-oauth.so`, loaded via dlopen when `USE_DYNAMIC_OAUTH`).

## Purpose

Private header for the OAUTHBEARER SASL mechanism. Defines the state-machine enum, the per-connection state struct, the one externally-visible cleanup helper, and exports `pg_oauth_mech` for `fe-auth.c`'s mechanism table. [verified-by-code, fe-auth-oauth.h:1-46]

## Types

- `enum fe_oauth_step` (22-28): four-state machine:
  - `FE_OAUTH_INIT` — about to send the initial response (token or discovery probe).
  - `FE_OAUTH_BEARER_SENT` — waiting for server verdict on the bearer.
  - `FE_OAUTH_REQUESTING_TOKEN` — async token retrieval is running.
  - `FE_OAUTH_SERVER_ERROR` — server rejected the token; just waiting for the FATAL.
  [verified-by-code, fe-auth-oauth.h:22-28]
- `fe_oauth_state` (30-40): mechanism state attached to `conn->sasl_state`:
  - `step` — current state.
  - `conn` — back-pointer.
  - `async_ctx` — holds a `PGoauthBearerRequestV2 *` while a flow is in flight.
  - `v1` — true if the user-installed callback only supports v1 of the request struct (triggers poisoning, see fe-auth-oauth.c:1466).
  - `builtin` — true if using the builtin libpq-oauth flow vs. a user-installed one (affects error messaging tone).
  - `flow_module` — `dlopen` handle for libpq-oauth.so under `USE_DYNAMIC_OAUTH`.
  [verified-by-code, fe-auth-oauth.h:30-40]

## API surface

- `pqClearOAuthToken(PGconn *conn)` (42) — `explicit_bzero` + free of `conn->oauth_token`. Called proactively post-connect and during `pqClosePGconn`. [verified-by-code, fe-auth-oauth.h:42; fe-auth-oauth.c:1430-1439]
- `pg_oauth_mech` (45) — the mechanism table consumed by `pg_SASL_init`. [verified-by-code, fe-auth-oauth.h:45]

## Invariants & gotchas

- `async_ctx` is a malloc'd copy of the original `PGoauthBearerRequestV2`; the original may live on the caller's stack and so cannot outlive the hook call. The lifetime contract is one-way (caller → libpq copy). [from-comment, fe-auth-oauth.c:862-866, 1074-1085]
- `flow_module` is **never dlclose**'d after successful init (fe-auth-oauth.c:936-939). Once loaded the plugin sticks around for process lifetime — this is intentional to avoid races with concurrent flows.

## Potential issues

- ISSUE-libpq-oauth-h-001 (severity: maybe) — the struct contains no version field. Future libpq versions adding a field cannot be detected by the libpq-oauth.so plugin at runtime; the plugin must be ABI-locked to a specific libpq. The dlopen path therefore depends on the plugin being shipped in lockstep with libpq.so (which is what the build system does, but third-party reimplementations could drift). [inferred, fe-auth-oauth.h:30-40]

## Cross-refs

- Implementation: `fe-auth-oauth.c` (1555 LOC).
- Dynamic plugin entry point: `pg_start_oauthbearer()` defined in `src/interfaces/libpq-oauth/`. The libpq-oauth.h header is loaded only by libpq-oauth.so itself.

## Tally
`[verified-by-code]=9 [from-comment]=2 [from-readme]=0 [inferred]=1 [unverified]=0`
