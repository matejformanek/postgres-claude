---
path: src/test/modules/oauth_validator/fail_validator.c
anchor_sha: e18b0cb7344
loc: 47
depth: read
---

# src/test/modules/oauth_validator/fail_validator.c

## Purpose

Minimal in-tree OAuth validator loadable that **always fails** in its
`validate_cb`. Used by the `oauth_validator` test suite to exercise the
backend's reaction when a configured validator module rejects every token
(sentinel `FATAL` from inside the validator callback). `[verified-by-code]`
`fail_validator.c:45`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_oauth_validator_module_init` | `:35` | Loadable entry point required by the OAuth validator ABI; returns the static `OAuthValidatorCallbacks` |
| `fail_token` (static) | `:41` | The `validate_cb`; raises `FATAL` immediately |

## Internal landmarks

- `validator_callbacks` (`:28-32`) — only sets `PG_OAUTH_VALIDATOR_MAGIC` and
  `.validate_cb`; no `startup_cb` / `shutdown_cb`.
- `pg_unreachable()` after the `elog(FATAL, ...)` is a hint for the compiler
  that control does not return.

## Invariants & gotchas

- TEST MODULE — must never be set as a production `oauth_validator_libraries`
  entry; any token validation request makes the backend die FATAL.
- Demonstrates the minimum ABI surface: magic marker + `validate_cb` only,
  startup/shutdown optional `[verified-by-code]`.

## Cross-refs

- `knowledge/files/src/test/modules/oauth_validator/validator.c.md` — full
  validator demonstrating all three callbacks and HBA options.
- `source/src/include/libpq/oauth.h` — `OAuthValidatorCallbacks` ABI struct.
