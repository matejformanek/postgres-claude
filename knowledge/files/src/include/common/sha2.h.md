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

- **Pure compile-time constants; no state, no secrets.** Same
  `_int.h` split as sha1.h — the fallback's `pg_sha256_ctx` lives in
  `sha2_int.h`, not here. Good compartmentalization.
- **`*_STRING_LENGTH` constants are vestigial** for the cryptohash
  API (which writes binary); they remain because some callers
  (notably md5_common.c's `pg_md5_hash`) write hex into a stack
  buffer and need the size. No header note explaining the split.
- **SCRAM-SHA-512 readiness.** `SCRAM_MAX_KEY_LEN` in scram-common.h
  is sized for SHA-256 only. Adding SHA-512 would require bumping
  `SCRAM_MAX_KEY_LEN`. The `PG_SHA512_*` constants here support that,
  but no `SCRAM_SHA_512_*` mechanism is wired.

## Cross-refs

- Internal state header: `knowledge/files/src/common/sha2_int.h.md`.
- Fallback impl: `knowledge/files/src/common/sha2.c.md`.
- SCRAM key-len dep: `knowledge/files/src/include/common/scram-common.h.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Issues

1. `[ISSUE-documentation: *_STRING_LENGTH variants are hex-output
   sizes used only by md5_common.c; their presence here without
   explanation invites confusion (nit)]` —
   `source/src/include/common/sha2.h:21-30`.

## Tally

`[verified-by-code]=2`
