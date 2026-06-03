---
path: src/common/hmac.c
anchor_sha: 4b0bf0788b0
loc: 330
---

# hmac.c

- **Source path:** `source/src/common/hmac.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 330

## Purpose

Fallback HMAC (RFC 2104) implementation built on top of the
`pg_cryptohash_*` facade. Selected when PG is built without OpenSSL.
Honours any of the six `pg_cryptohash_type` algorithms. [from-comment,
hmac.c:1-7]

## Role in PG

Linked into both frontend (libpq SCRAM client) and backend (SCRAM
server, postgres_fdw passthrough). Primary consumer is
`scram-common.c::scram_SaltedPassword / _ClientKey / _ServerKey`. A
non-OpenSSL build of libpq depends on this file.

## Key functions

- `pg_hmac_create(type)` (hmac.c:76): allocates `pg_hmac_ctx`,
  pre-fills `digest_size` / `block_size` for the requested algorithm
  (hmac.c:93-119), then constructs an inner `pg_cryptohash_ctx`. On
  failure of the inner ctx: `explicit_bzero` + `FREE` + `return NULL`
  (hmac.c:122-127).
- `pg_hmac_init(ctx, key, len)` (hmac.c:138): the heart of RFC 2104:
  - Fills `k_ipad` with `0x36`, `k_opad` with `0x5C`.
  - If `len > block_size`, hashes the key down once into a stack
    buffer (hmac.c:158-193) — uses a fresh `pg_cryptohash_ctx`.
  - XORs the (possibly shrunk) key into both pads (hmac.c:195-199).
  - Initializes the persistent inner hash with the ipad-block
    (hmac.c:202-203).
- `pg_hmac_update(ctx, data, len)` (hmac.c:223): forwards to the
  inner hash.
- `pg_hmac_final(ctx, dest, len)` (hmac.c:244):
  - Allocates a `digest_size` scratch buffer `h`, finalises the
    ipad-hash into it.
  - Reinits the inner hash, feeds opad-block then `h`, finalises into
    `dest`.
  - `FREE(h)` after — but **no `explicit_bzero(h)` before** (hmac.c:279).
- `pg_hmac_free(ctx)` (hmac.c:288): `pg_cryptohash_free` →
  `explicit_bzero(ctx, sizeof(pg_hmac_ctx))` → `FREE`.

## OpenSSL vs fallback dispatch

Build-time. Peer is `hmac_openssl.c`. Same public symbols.

## State / globals

None. `HMAC_IPAD = 0x36`, `HMAC_OPAD = 0x5C` constants only.

## Concurrency

Reentrant.

## Phase D notes

- **`ctx->k_ipad` and `ctx->k_opad` are scrubbed** (since the entire
  `pg_hmac_ctx` is `explicit_bzero`'d on free, hmac.c:295). Good.
- **`shrinkbuf` in `_init` is freed without scrubbing** (hmac.c:212-213).
  Contents are HMAC-of-key — for a password-derived HMAC this leaks a
  shorter form of the secret. Same for the intermediate ipad-hash in
  `_final` (hmac.c:279 `FREE(h)` without bzero). The leak window is
  one `pfree` / `free` away from `explicit_bzero`. Compare with
  cryptohash.c which *does* bzero on free. Severity: maybe.
- **The key copy of `len > block_size` path goes through a separate
  `pg_cryptohash_ctx`** which itself does bzero-on-free
  (hmac.c:192) — good.
- **No constant-time output compare.** Callers HMAC and then call
  `timingsafe_bcmp` themselves (e.g. `verify_client_proof` in
  auth-scram.c). A helper here would centralise the discipline.

## Potential issues

- **[ISSUE-secret-scrub: `shrinkbuf` not explicit_bzero'd before
  FREE]** `hmac.c:175, 186, 208, 213`. Holds shortened key material.
  Severity: maybe.
- **[ISSUE-secret-scrub: intermediate digest `h` not explicit_bzero'd]**
  `hmac.c:263, 275, 279`. Holds `H((K^ipad) || data)` — feeding-stage
  output that, combined with the opad-form, lets an attacker recover
  the final tag without seeing it. Severity: maybe.
- **[ISSUE-undocumented-invariant: `len > block_size` shrinks via
  same-algorithm hash]** RFC 2104 § says "if longer than B, key is
  hashed using H". PG does this. Documented in a comment
  (hmac.c:154-157) but not in the header — easy to miss.

## Cross-refs

- Public API: `knowledge/files/src/include/common/hmac.h.md`.
- OpenSSL peer: `knowledge/files/src/common/hmac_openssl.c.md`.
- Primary consumer: `knowledge/files/src/common/scram-common.c.md`.

## Tally

`[verified-by-code]=10 [from-comment]=2 [inferred]=1`
