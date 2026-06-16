---
path: src/backend/libpq/auth-oauth.c
anchor_sha: 4b0bf0788b0
loc: 1136
depth: deep
---

# auth-oauth.c

- **Source path:** `source/src/backend/libpq/auth-oauth.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1136

## Purpose

Server-side `OAUTHBEARER` SASL mechanism (RFC 7628), added in v18.
Unlike SCRAM, the backend does *no* cryptographic verification of the
bearer token — it parses the OAUTHBEARER client message into an
HTTP-style `Authorization: Bearer <token>` value, then hands the
token off to an out-of-tree **validator library** (named in
`pg_hba.conf` and gated by the
`oauth_validator_libraries` GUC) that talks to whatever the
deployment's OAuth/OIDC issuer is. The validator returns
`(authorized, authn_id)`; PG enforces the usermap and the rest.
[from-comment, auth-oauth.c:1-15; verified-by-code,
auth-oauth.c:670-761, 770-833]

This is a deliberately small attack surface inside PG: parse the
RFC 7628 client message, validate the bearer-token *format*
(RFC 6750), defer the rest. The header makes it clear the validator
is mandatory and there is no fallback (auth-oauth.c:765-769).

## Public API surface

- `const pg_be_sasl_mech pg_be_oauth_mech` — `auth-oauth.c:54`. The
  vtable; `max_message_length = PG_MAX_AUTH_TOKEN_LENGTH` (tokens can
  be kilobytes).
- `bool check_oauth_validator(HbaLine *hbaline, int elevel, char **err_msg)`
  — `auth-oauth.c:857`. Called from `hba.c` during pg_hba parse;
  ensures the validator named on the HBA line is one of the libraries
  listed in `oauth_validator_libraries`, or fills it in from a
  single-entry list. [verified-by-code]
- Validator-facing helpers exported for in-tree use:
  - `RegisterOAuthHBAOptions(state, num, opts)` — `auth-oauth.c:951`.
    Validator declares which `validator.<key>=...` HBA options it
    understands; called from `startup_cb`. [verified-by-code]
  - `bool valid_oauth_hba_option_name(const char *name)` —
    `auth-oauth.c:1005`. Restricts validator-option names to
    `[A-Za-z0-9_-]+`. [verified-by-code]
  - `const char *GetOAuthHBAOption(state, optname)` —
    `auth-oauth.c:1092`. Validator pulls per-connection HBA options
    during `validate_cb`. Locked until
    `check_validator_hba_options` runs (auth-oauth.c:1099-1110).
- GUC: `char *oauth_validator_libraries_string` — `auth-oauth.c:35`,
  consumed by `check_oauth_validator`.

## Internal landmarks

- **State machine** (auth-oauth.c:63-69):
  `OAUTH_STATE_INIT` → on success `OAUTH_STATE_FINISHED`; on token
  failure → `OAUTH_STATE_ERROR`; on empty `auth=` (discovery request)
  → `OAUTH_STATE_ERROR_DISCOVERY`. Both error states require the
  client to send a single-byte `\x01` ack before the failure /
  abandon is reported (auth-oauth.c:193-220).
- **Validator vtable** — `OAuthValidatorCallbacks { magic, startup_cb,
  shutdown_cb, validate_cb }` (referenced auth-oauth.c:797-832).
  Magic number `PG_OAUTH_VALIDATOR_MAGIC` guards ABI churn.
  `validate_cb` is the only mandatory one (auth-oauth.c:816-819).
- **`oauth_exchange`** (auth-oauth.c:144) — the dispatcher.
  - Empty input → "send empty challenge" turn (auth-oauth.c:164-171).
  - Parses GS2 cbind flag (only `n` and `y` allowed; `p` errors
    because OAUTHBEARER has no channel binding) (auth-oauth.c:230-265).
  - Disallows `a=authzid` (auth-oauth.c:270-273).
  - `parse_kvpairs_for_auth` (auth-oauth.c:431) walks the
    `\x01`-separated `key=value\x01` pairs; only the `auth` value is
    kept, everything else is silently ignored per RFC.
  - Empty `auth=` → discovery (returns metadata pointing the client at
    `.well-known/openid-configuration` via
    `generate_error_response`, auth-oauth.c:530-576) → state becomes
    `ERROR_DISCOVERY` → on client ack returns `PG_SASL_EXCHANGE_ABANDONED`.
  - Non-empty → `validate(port, auth, logdetail)` (auth-oauth.c:672).
  - `explicit_bzero(input_copy, inputlen)` at end (auth-oauth.c:341)
    — **this is the only PG auth path that scrubs**.
- **`validate_token_format`** (auth-oauth.c:601) — strict RFC 6750
  parse: `Bearer ` (case-insensitive per RFC 9110), one+ space,
  base64-URL alphabet, trailing `=`. Errors log at `COMMERROR` (no
  client echo) because the auth value contains the secret token.
- **`validate`** (auth-oauth.c:672) — pulls the token, hands to
  `ValidatorCallbacks->validate_cb`, populates `set_authn_id` from
  the result, and if `!oauth_skip_usermap` runs `check_usermap`. The
  `oauth_skip_usermap` mode lets the validator be the final
  authorization authority (e.g. the validator already knows
  "this token is allowed to log in as role X").
- **Library loading** — `load_validator_library` (auth-oauth.c:772)
  via `load_external_function` + `_PG_oauth_validator_module_init`
  symbol; magic check; registers a `MemoryContextResetCallback` so
  `shutdown_cb` fires on context teardown (auth-oauth.c:828-832). One
  validator per process — globals `ValidatorCallbacks`,
  `validator_module_state` (auth-oauth.c:46-51).

## Invariants & gotchas

- **No in-tree validator.** Failure to load a validator is fatal at
  pg_hba parse time (`check_oauth_validator`). There is no built-in
  fallback; a deployment without a validator can't use `oauth`.
  [from-comment, auth-oauth.c:765-770]
- **The token never enters the catalog.** Unlike SCRAM, the backend
  has no stored secret to compare against — it must defer to the
  validator. This means `pg_authid.rolpassword` is irrelevant for
  OAuth users; the role just needs to exist.
- **`oauth_skip_usermap`** bypasses `check_usermap`; setting it makes
  the validator the sole gate. The validator MUST set `authn_id` to
  something audit-meaningful (auth-oauth.c:736-743).
- **Bearer scheme is case-insensitive** (auth-oauth.c:615 uses
  `pg_strncasecmp`) — required by RFC 9110, easily overlooked.
- **Token errors log at `COMMERROR`, not `LOG`** (auth-oauth.c:617-620,
  634-637, 656-659) — `COMMERROR` is server-log-only, ensures the
  raw token never echoes to the client. Discipline applies even
  inside `errdetail_log`.
- **`generate_error_response` JSON-escapes** issuer + scope
  (auth-oauth.c:566, 570) "belt-and-suspenders" because HBA-parse
  isn't required to vet those characters yet.
- **`PG_OAUTH_VALIDATOR_MAGIC`** acts like access-method API magic; a
  mid-major-version ABI break has a graceful refuse path
  (auth-oauth.c:805-810).
- **`ValidatorOptionsChecked` gate** (auth-oauth.c:1099-1110) forbids
  `GetOAuthHBAOption` during `startup_cb`. The validator can register
  option names then but cannot read concrete values until a real
  exchange is matched against an HBA line. Letting startup_cb
  see options would lock in "HBA matched first" as part of the API.

## Cross-refs

- Header: `knowledge/files/src/include/libpq/oauth.h.md` (planned).
- SASL framework: `knowledge/files/src/backend/libpq/auth-sasl.c.md`.
- Frontend counterpart: `src/interfaces/libpq/fe-auth-oauth.c`
  + `src/interfaces/libpq/fe-auth-oauth-curl.c` (the libcurl-based
  client flow).
- HBA wiring: `src/backend/libpq/hba.c` (see `parse_hba_auth_opt`,
  `check_oauth_validator` callsite).
- Sample validator: `src/test/modules/oauth_validator/`.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: discovery error response leaks issuer URL even if
  unauthenticated]** `auth-oauth.c:530-576` — by design (the RFC says
  to publish the discovery endpoint) but means an unauthenticated
  probe can enumerate the issuer + scope list. Reflected in the
  header comment (auth-oauth.c:535-540: "There's not really a way to
  hide this from the user"). Document explicitly. Severity: nit
  (intentional).
- **[ISSUE-undocumented-invariant: validator runs in the connecting
  backend's address space]** auth-oauth.c:794-797 — a malicious or
  buggy validator can `ereport(FATAL)`, crash, or leak. There's no
  mention of subprocess isolation; future validators that shell out
  to libcurl carry that risk. Severity: maybe.
- **[ISSUE-correctness: O(n^2) HBA-option check]**
  `auth-oauth.c:1040-1048` — comment says "O(n^2) shouldn't be a
  problem here in practice" but a validator that registers hundreds
  of options against an HBA line with hundreds of `validator.X=Y`
  pairs would feel it. Severity: nit.
- **[ISSUE-question: token validation has no per-validator
  timeout / cancellation contract]** — `ValidatorCallbacks->validate_cb`
  is called synchronously from the auth path; a slow OIDC endpoint
  blocks the backend until `authentication_timeout`. There is no API
  for the validator to register a wait-event class. Severity: maybe.
- **[ISSUE-question: validator can call `set_authn_id` multiple times
  via PG's `auth-oauth.c:711` path]** — but `set_authn_id`
  ereports FATAL on second call (auth.c:348-352). A validator that
  partially succeeds then retries internally would crash the
  connection. Worth a comment. Severity: nit.

## Tally

`[verified-by-code]=18 [from-comment]=8 [inferred]=1`
