# oauth.h

- **Source path:** `source/src/include/libpq/oauth.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Interface to libpq/auth-oauth.c" — backend OAuth 2.0 validator-module API.
Defines the loadable-module contract that token validators (e.g. an
issuer-specific JWT verifier) implement to plug into HBA `oauth` lines.

## Public API surface

- `ValidatorModuleState { sversion, private_data }` — passed to every
  callback; `sversion` carries `PG_VERSION_NUM` for future cross-version
  guards [from-comment].
- `ValidatorModuleResult { authorized, authn_id, error_detail }` —
  validator's output. Comments are explicit that `authn_id` may be set
  even when `authorized` is false so DBAs can correlate logs to user;
  `error_detail` is server-log only, never sent to the client [from-comment].
- Callback typedefs: `ValidatorStartupCB`, `ValidatorShutdownCB`,
  `ValidatorValidateCB` — only validate is required.
- `OAuthValidatorCallbacks { magic, startup_cb, shutdown_cb, validate_cb }`
  — module-supplied dispatch table.
- `OAuthValidatorModuleInit` — typedef for `_PG_oauth_validator_module_init`
  exported symbol that every validator must define.
- `pg_be_oauth_mech` — the `pg_be_sasl_mech` instance plugging OAuth into
  the SASL framework.
- HBA option helpers: `RegisterOAuthHBAOptions(state, num, opts[])` and
  `GetOAuthHBAOption(state, optname)` — per-HBA-line custom config.
- `check_oauth_validator(HbaLine *, int elevel, char **err_msg)`,
  `valid_oauth_hba_option_name(const char *)`.
- GUC: `oauth_validator_libraries_string`.

## Key constants

- `PG_OAUTH_VALIDATOR_MAGIC 0x20250220` — module ABI cookie; comment
  reserves it for "emergency use within a stable release line. May it
  never need to change." `PG_MODULE_MAGIC` already separates major
  versions [from-comment].

## Cross-refs

- Related backend: `src/backend/libpq/auth-oauth.c`.
- Related: `knowledge/files/src/include/libpq/sasl.h.md` (the
  `pg_be_sasl_mech` interface OAuth plugs into),
  `knowledge/files/src/include/libpq/hba.h.md` (HbaLine `oauth_*` fields).

## Potential issues

- **[ISSUE-leak: error_detail allocation lifetime is ambiguous]**
  `oauth.h:62-66` — "This string may be either of static duration or
  palloc'd." The validator-side caller has no way to tell which; if `auth.c`
  ever pfree's the string from `ValidatorModuleResult`, a static-duration
  pointer corrupts. Convention is undocumented. Severity: maybe.
- **[ISSUE-undocumented-invariant: validator must continue on shadow_pass NULL]**
  cross-ref `sasl.h` — the OAuth validator is wired via the SASL framework,
  whose contract requires running the mock exchange on unknown users to
  prevent username enumeration. `oauth.h` does not restate this
  obligation, so a validator author reading only this header could leak a
  "user does not exist" timing/length side channel. Severity: maybe.
- **[ISSUE-stale-todo: magic value date hardcoded]** `oauth.h:88` — magic
  is `0x20250220` (looks date-coded). Any patch that needs to bump it
  must agree on a successor convention; nothing here says how to choose
  the next value. Severity: low.

## Tally

`[verified-by-code]=4 [from-comment]=4 [inferred]=1`
