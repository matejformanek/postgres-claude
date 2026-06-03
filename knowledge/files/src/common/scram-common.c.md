---
path: src/common/scram-common.c
anchor_sha: 4b0bf0788b0
loc: 329
---

# scram-common.c

- **Source path:** `source/src/common/scram-common.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 329

## Purpose

The five RFC 5802 §3 primitives shared between SCRAM server
(`src/backend/libpq/auth-scram.c`) and client
(`src/interfaces/libpq/fe-auth-scram.c`):
`scram_SaltedPassword` (PBKDF2), `scram_H` (bare hash),
`scram_ClientKey`, `scram_ServerKey`, and `scram_build_secret`
(composes the stored `SCRAM-SHA-256$iter:salt$stored:server` string).
[verified-by-code, scram-common.c:1-15]

## Role in PG

Linked into both `libpq` (frontend) and the backend. The five
primitives implement the math; the wire-format protocol lives in
`auth-scram.c` / `fe-auth-scram.c`. `scram_build_secret` is the
single source of truth for the on-disk shape of
`pg_authid.rolpassword` for SCRAM users.

## Key functions

- `scram_SaltedPassword(password, hash_type, key_length, salt,
  saltlen, iterations, result, errstr)` (scram-common.c:37): PBKDF2
  with HMAC as the PRF.
  - First iteration: `HMAC(password, salt || INT(1))` → `Ui_prev`,
    copied to `result` (scram-common.c:64-74).
  - Subsequent iterations 1..`iterations-1`: `Ui = HMAC(password,
    Ui_prev)`, then XOR into `result` (scram-common.c:77-99).
  - **`CHECK_FOR_INTERRUPTS()` per inner iteration** in the backend
    (scram-common.c:79-85) — `scram_iterations` GUC can be set large,
    so this is interruptible. Frontend has no such guard.
  - **`Ui` / `Ui_prev` are stack `uint8[SCRAM_MAX_KEY_LEN]` buffers
    that are NOT explicitly scrubbed before return** (scram-common.c:47-48).
    They hold PBKDF2 intermediate state.
- `scram_H(input, hash_type, key_length, result, errstr)`
  (scram-common.c:111): one-shot hash. Allocates a `pg_cryptohash_ctx`
  per call (alloc + free). Used by `auth-scram.c::verify_client_proof`
  to compute `H(recovered ClientKey)` for compare against StoredKey.
- `scram_ClientKey` / `scram_ServerKey` (scram-common.c:141, 171):
  HMAC-`salted_password`("Client Key" or "Server Key"). Allocates a
  `pg_hmac_ctx` per call.
- `scram_build_secret(hash_type, key_length, salt, saltlen,
  iterations, password, errstr)` (scram-common.c:208):
  - Stack-allocates three `uint8[SCRAM_MAX_KEY_LEN]` buffers
    (`salted_password`, `stored_key`, `server_key`).
  - Pipeline: `scram_SaltedPassword` → `scram_ClientKey` (into
    `stored_key`) → `scram_H` (in-place into `stored_key`, the actual
    StoredKey is `H(ClientKey)`) → `scram_ServerKey`.
  - Base64-encodes salt, stored_key, server_key into a malloc/palloc
    output of `maxlen` bytes.
  - **Stack buffers `salted_password / stored_key / server_key` are
    NOT explicit_bzero'd before return** (scram-common.c:213-215). On
    stack they vanish at frame teardown, but a longjmp out of the
    `elog(ERROR)` paths leaves them on the stack longer than expected.

## OpenSSL vs fallback dispatch

This file is build-system agnostic; it uses `pg_hmac_*` and
`pg_cryptohash_*` which themselves are dispatched at link time.

## State / globals

None. All state is on stack.

## Concurrency

Reentrant. The interrupt check is the only async-aware piece.

## Phase D notes

- **The headline `SecretBuf` candidate site.** Every primitive here
  takes a `uint8 *` for salted-password / salt / result. None of them
  zero anything. The whole file would simplify if `SecretBuf` were
  the input/output type: it would own its scrub, and the
  `uint8[SCRAM_MAX_KEY_LEN]` stack arrays would go away.
- **`scram_SaltedPassword`'s `Ui_prev`/`Ui` are the most sensitive
  buffers in PG SCRAM:** they're the PBKDF2 intermediate state, and
  leaking one of them (e.g. via uninit-memory readback elsewhere)
  defeats the entire iteration count. Worth scrubbing here.
- **`scram_build_secret`'s three stack arrays carry the full SCRAM
  derivation chain** (SaltedPassword, StoredKey, ServerKey). On
  success they're base64'd into the returned string and discarded.
  Same scrub gap.
- **Hash-type hard-coded to SHA-256** by an `Assert(hash_type ==
  PG_SHA256)` at scram-common.c:225. A future SCRAM-SHA-512 would
  trip this; the entire iteration count / `SCRAM_MAX_KEY_LEN` /
  mechanism-name family would need extending in lockstep.
- **`pg_strong_random` is NOT used here.** The salt and nonce come
  from callers (`pg_be_scram_build_secret` in `auth-scram.c:480` calls
  `pg_strong_random` then passes the salt in). This file trusts the
  caller for randomness.

## Potential issues

- **[ISSUE-secret-scrub: PBKDF2 intermediate `Ui`/`Ui_prev` not
  explicit_bzero'd]** `scram-common.c:47-48, 101-102`. On stack but
  not actively scrubbed. Severity: maybe.
- **[ISSUE-secret-scrub: SCRAM derivation arrays in `scram_build_secret`
  not explicit_bzero'd]** `scram-common.c:213-215, 326-328`. The
  StoredKey/ServerKey on stack survive into the base64-encode phase
  and are not scrubbed at return. Severity: likely (the secret
  scrubbing gap A2 already flagged libpq-wide).
- **[ISSUE-stale-todo: `Assert(hash_type == PG_SHA256)` blocks
  SCRAM-SHA-512]** `scram-common.c:225`. Header has `SCRAM_MAX_KEY_LEN`
  sized for "the maximum" but only SHA-256 is wired. Documented
  drift. Severity: nit.
- **[ISSUE-side-channel: PBKDF2 inner loop has no constant-time
  invariant]** `scram-common.c:96-97` — XOR loop is constant-time
  per iteration; but the outer `pg_hmac_*` calls go through OpenSSL,
  which is not promised constant-time-per-key on all platforms. The
  iteration count itself (`scram_iterations` GUC) is queryable by
  observing wallclock of the SCRAM handshake. Severity: nit.

## Cross-refs

- Public API: `knowledge/files/src/include/common/scram-common.h.md`.
- Backend SCRAM driver: `knowledge/files/src/backend/libpq/auth-scram.c.md`.
- Backend rolpassword storage: `knowledge/files/src/backend/libpq/crypt.c.md`.
- HMAC backend: `knowledge/files/src/common/hmac.c.md` /
  `hmac_openssl.c.md`.
- Hash backend: `knowledge/files/src/common/cryptohash.c.md` /
  `cryptohash_openssl.c.md`.

## Tally

`[verified-by-code]=13 [from-comment]=2 [inferred]=2`
