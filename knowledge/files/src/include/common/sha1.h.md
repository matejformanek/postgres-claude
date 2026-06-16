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

- **SHA-1 is cryptographically broken.** The header still exposes its
  constants because `pg_cryptohash_type` includes `PG_SHA1` (and
  hence the legacy MD5-SCRAM-style code paths and any extension
  passing `PG_SHA1`). No header-level deprecation note steers callers
  away.
- **Bare-state vs opaque-ctx split.** Unlike OpenSSL's
  `EVP_MD_CTX`, the in-tree fallback's `pg_sha1_ctx` lives in
  `src/common/sha1_int.h` (`_int.h` = internal); only the constants
  leak here. That's correct compartmentalization. But the lack of a
  `pg_sha1_*` typedef means callers cannot embed a SHA-1 ctx on the
  stack and scrub it themselves — they must go through cryptohash,
  which is good.
- **Header is constant-only; zero state, zero secrets.** Trust-boundary
  surface is purely the cryptohash dispatch (see cryptohash.h.md).

## Cross-refs

- Internal state header: `knowledge/files/src/common/sha1_int.h.md`.
- Fallback impl: `knowledge/files/src/common/sha1.c.md`.
- Dispatcher: `knowledge/files/src/include/common/cryptohash.h.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Issues

1. `[ISSUE-documentation: no deprecation note that SHA-1 is broken
   for collision resistance and should not be used in new MAC /
   signature constructions (nit)]` — `source/src/include/common/sha1.h:1-21`.
2. `[ISSUE-defense-in-depth: PG_SHA1 still routable through cryptohash
   API; a deprecated-runtime warning at cryptohash_create(PG_SHA1)
   would surface accidental use (nit)]` — `source/src/include/common/sha1.h:17`.

## Tally

`[verified-by-code]=2`
