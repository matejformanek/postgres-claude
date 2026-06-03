---
path: src/interfaces/libpq/fe-auth-sasl.h
anchor_sha: 4b0bf0788b0
loc: 153
depth: shallow
---

# fe-auth-sasl.h

- **Source path:** `source/src/interfaces/libpq/fe-auth-sasl.h`
- **Lines:** 153
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-auth.c` (`pg_SASL_init`/`pg_SASL_continue` invoke these callbacks), `fe-auth-scram.c` (defines `pg_scram_mech`), `fe-auth-oauth.c` (defines `pg_oauth_mech`), `src/include/libpq/sasl.h` (backend counterpart).

## Purpose

Defines the **frontend SASL mechanism interface**. Each mechanism (currently SCRAM-SHA-256, SCRAM-SHA-256-PLUS, OAUTHBEARER) is a `pg_fe_sasl_mech` callback table. `fe-auth.c`'s `pg_SASL_init` selects a mechanism and drives `init` / `exchange` / `channel_bound` / `free` against it. Not part of the public libpq API. [verified-by-code, fe-auth-sasl.h:5-9]

## API surface

- `SASLStatus` enum (28-34): `SASL_COMPLETE`, `SASL_FAILED`, `SASL_CONTINUE`, `SASL_ASYNC`. The latter signals that the mechanism needs out-of-band I/O (e.g. OAuth token fetch) and that the caller must arrange `conn->async_auth`/`cleanup_async_auth` callbacks. [verified-by-code, fe-auth-sasl.h:28-34]
- `pg_fe_sasl_mech` struct (43-151), four function pointers:
  - `init(conn, password, mech)` — allocate per-connection state; may return NULL on OOM. [verified-by-code, fe-auth-sasl.h:66]
  - `exchange(state, final, input, inputlen, output, outputlen)` — drive one round. `input == NULL` triggers the client-first initial response (SCRAM). Output is malloc'd; caller frees. [verified-by-code, fe-auth-sasl.h:117-119]
  - `channel_bound(state)` — true iff a successful SCRAM-SHA-256-PLUS exchange completed. OAuth always returns false. [verified-by-code, fe-auth-sasl.h:136]
  - `free(state)` — released at connection drop, not on exchange completion. [verified-by-code, fe-auth-sasl.h:140-149]

## Invariants & gotchas

- The `input` argument to `exchange` is **guaranteed NUL-terminated** by the caller (`pg_SASL_continue` writes `challenge[payloadlen] = '\0'`, fe-auth.c:732), but mechanisms must still consult `inputlen` because SASL permits embedded NULs in challenges. [verified-by-code, fe-auth-sasl.h:86-89; fe-auth.c:731-732]
- `SASL_ASYNC` is structurally required to set up callbacks **before returning** (see comment, fe-auth-sasl.h:105-111). Failure to do so will hit an assertion in `pg_SASL_init`. [verified-by-code, fe-auth-sasl.h:105-111; fe-auth.c:653-654]
- A mechanism must NEVER report `channel_bound() == true` unless it actually completed and used channel binding (relied on by `check_expected_areq` to enforce `channel_binding=require`). [verified-by-code, fe-auth-sasl.h:122-126; fe-auth.c:1033-1038]

## Potential issues

- ISSUE-libpq-sasl-001 (severity: maybe) — the `SASLStatus` enum has no `SASL_INVALID`/`SASL_INTERNAL_ERROR` distinction. A buggy mechanism returning a value outside the enum range (e.g. uninitialized stack) would fall through the switch in `pg_SASL_continue` and be treated as `SASL_COMPLETE`. No explicit defensive check in the caller. [inferred, fe-auth.c:737-792]

## Cross-refs

- Implementations: `fe-auth-scram.c` (lines 33-38), `fe-auth-oauth.c` (lines 47-52).
- Backend equivalent: `src/include/libpq/sasl.h`. The two interfaces are intentionally symmetric.

## Tally
`[verified-by-code]=10 [from-comment]=0 [from-readme]=0 [inferred]=1 [unverified]=0`
