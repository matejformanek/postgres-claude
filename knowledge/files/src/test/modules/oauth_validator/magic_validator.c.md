---
path: src/test/modules/oauth_validator/magic_validator.c
anchor_sha: e18b0cb7344
loc: 48
depth: read
---

# src/test/modules/oauth_validator/magic_validator.c

## Purpose

In-tree OAuth validator loadable whose `OAuthValidatorCallbacks` carries the
**wrong magic marker** (`0xdeadbeef` instead of `PG_OAUTH_VALIDATOR_MAGIC`),
used to verify that the backend correctly **rejects loading** a validator
built against an incompatible ABI version. `[verified-by-code]`
`magic_validator.c:30`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_oauth_validator_module_init` | `:36` | Returns the bogus-magic callbacks struct |
| `validate_token` (static) | `:42` | Never reached; raises `FATAL` if the magic check is somehow bypassed |

## Internal landmarks

- The magic mismatch is checked by the backend OAuth machinery the moment the
  validator returns its callbacks struct; the module load itself succeeds, but
  registering the validator fails.

## Invariants & gotchas

- TEST MODULE — never load in production. The whole point is to fail.
- Magic markers in PG extension ABIs are bumped whenever the callback struct's
  layout changes; a wrong magic means a stale .so against newer headers.

## Cross-refs

- `source/src/include/libpq/oauth.h` — `PG_OAUTH_VALIDATOR_MAGIC` definition.
- `knowledge/files/src/test/modules/oauth_validator/validator.c.md` —
  correctly-built validator counterpart.
