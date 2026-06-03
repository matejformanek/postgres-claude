---
path: src/include/common/sha1.h
anchor_sha: 4b0bf0788b0
loc: 21
---

# sha1.h

- **Source path:** `source/src/include/common/sha1.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 21

## Purpose

Constants for SHA-1 (`SHA1_DIGEST_LENGTH = 20`, `SHA1_BLOCK_SIZE =
64`). Both pulled in by `cryptohash.c` / `cryptohash_openssl.c` and
`hmac.c` / `hmac_openssl.c` for digest-size validation in `_final`.
[verified-by-code, sha1.h:16-19]

## Phase D notes

SHA-1 is broken; PG uses it only as a building block inside
`pg_cryptohash` (never as the SCRAM hash; that's SHA-256). No public
`pg_sha1_*` typedef leaks here — those live in `sha1_int.h` for the
fallback impl only.

## Cross-refs

- Internal state header: `knowledge/files/src/common/sha1_int.h.md`.
- Fallback impl: `knowledge/files/src/common/sha1.c.md`.

## Tally

`[verified-by-code]=1`
