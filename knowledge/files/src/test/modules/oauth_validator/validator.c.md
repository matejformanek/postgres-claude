---
path: src/test/modules/oauth_validator/validator.c
anchor_sha: e18b0cb7344
loc: 216
depth: read
---

# src/test/modules/oauth_validator/validator.c

## Purpose

Full reference test OAuth validator loadable: exercises **all three**
`OAuthValidatorCallbacks` (`startup_cb` / `validate_cb` / `shutdown_cb`),
custom HBA option registration via `RegisterOAuthHBAOptions` /
`GetOAuthHBAOption`, and the `ValidatorModuleState.private_data` round-trip.
Behavior is steered through GUCs so regression tests can flip success/failure,
inject error details, and verify HBA-option visibility timing.
`[verified-by-code]` `validator.c:31-38`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:73` | Registers GUCs and `MarkGUCPrefixReserved("oauth_validator")` |
| `_PG_oauth_validator_module_init` | `:123` | Returns the populated callbacks struct |
| GUC `oauth_validator.authn_id` | `:75` | Override authenticated identity |
| GUC `oauth_validator.authorize_tokens` | `:83` | If false, every token is rejected |
| GUC `oauth_validator.error_detail` | `:91` | Optional `errdetail` on failure |
| GUC `oauth_validator.internal_error` | `:99` | Make the validator report an internal error |
| GUC `oauth_validator.invalid_hba` | `:107` | Register a bogus HBA option (expects WARNING in logs) |

## Internal landmarks

- `validator_startup` (`:134`) — checks `state->sversion == PG_VERSION_NUM`,
  registers `hba_opts[] = {"authn_id", "log"}` via `RegisterOAuthHBAOptions`
  (`:149`), and asserts `GetOAuthHBAOption` returns NULL during startup
  (`:152-156`) — the API contract is that startup runs **before** any client
  has supplied HBA option values.
- Private-state round trip: writes `PRIVATE_COOKIE` at `:166`, validates it in
  both `validate_token` (`:191`) and `validator_shutdown` (`:176`).
- `validate_token` (`:186`) — logs the token / role / issuer / scope, returns
  `false` on internal-error mode, otherwise sets `authn_id` from (in order)
  the GUC, the `authn_id` HBA option, or the supplied role.
- All callback `authn_id` strings are `pstrdup`'d (`:209,211,213`) so they
  outlive the GUC's storage.

## Invariants & gotchas

- TEST MODULE — installs no hooks beyond the OAuth validator registration,
  but the `MarkGUCPrefixReserved` call is irreversible global state once
  loaded `[verified-by-code]` `:116`.
- `GetOAuthHBAOption` returns NULL during `startup_cb` by design — modules
  must not rely on per-connection HBA options at startup, only at
  `validate_cb` time (`:144-148` [from-comment]).
- Reading `state->sversion` is shown as a **negative example** (`:138-141`):
  real validators should not pin a version because that defeats upgrade
  compatibility.

## Cross-refs

- `source/src/include/libpq/oauth.h` — `OAuthValidatorCallbacks`,
  `ValidatorModuleState`, `RegisterOAuthHBAOptions`, `GetOAuthHBAOption`.
- `knowledge/files/src/test/modules/oauth_validator/fail_validator.c.md` —
  always-fail counterpart.
- `knowledge/files/src/test/modules/oauth_validator/magic_validator.c.md` —
  wrong-magic counterpart.
