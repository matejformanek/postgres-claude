---
path: src/include/common/sha2.h
anchor_sha: 4b0bf0788b0
loc: 32
---

# sha2.h

- **Source path:** `source/src/include/common/sha2.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 32

## Purpose

Length constants for SHA-224 / 256 / 384 / 512: block length, digest
length, and `*_DIGEST_STRING_LENGTH = digest*2+1` for hex-encoded
output buffers. [verified-by-code, sha2.h:19-30]

## Key declarations

- `PG_SHA256_DIGEST_LENGTH = 32`, `PG_SHA256_BLOCK_LENGTH = 64` — the
  pair SCRAM-SHA-256 depends on (`SCRAM_SHA_256_KEY_LEN`).
- `PG_SHA512_BLOCK_LENGTH = 128` — drives the `k_ipad`/`k_opad`
  stack arrays in `pg_hmac_ctx` (hmac.c:63-64): the fallback HMAC
  sizes for the largest block to avoid per-call allocation.

## Phase D notes

Pure compile-time constants; no state, no secrets. The `*_STRING_LENGTH`
variants suggest the historic API took hex output buffers; today
`pg_cryptohash_final` writes binary and callers
(`md5_common.c::pg_md5_hash`) do their own hex.

## Cross-refs

- Internal state header: `knowledge/files/src/common/sha2_int.h.md`.
- Fallback impl: `knowledge/files/src/common/sha2.c.md`.

## Tally

`[verified-by-code]=2`
