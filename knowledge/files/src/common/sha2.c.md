---
path: src/common/sha2.c
anchor_sha: 4b0bf0788b0
loc: 1018
---

# sha2.c

- **Source path:** `source/src/common/sha2.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1018

## Purpose

In-tree fallback SHA-224 / SHA-256 / SHA-384 / SHA-512 (FIPS PUB
180-2 / -3). Aaron D. Gifford / OpenBSD lineage. Implements four
init/update/final triples over `pg_sha256_ctx` (also used for
SHA-224 via truncation) and `pg_sha512_ctx` (also used for SHA-384
via truncation). Selected only in non-OpenSSL builds. [from-comment,
sha2.c:1-51]

## Role in PG

The most important fallback in this directory because **SCRAM-SHA-256
is the production PG password protocol since v10**. When PG is built
without OpenSSL, every SCRAM exchange and every `ALTER USER ...
PASSWORD` runs through these routines via `pg_cryptohash_*`.

## Key functions

- `pg_sha256_init / _update / _final` — standard FIPS-180 SHA-256.
  `_final` writes 32 bytes and `memset(context, 0,
  sizeof(pg_sha256_ctx))` at the end (sha2.c around the SHA256_Last
  helper).
- `pg_sha512_init / _update / _final` — standard SHA-512.
- `pg_sha224_init / _update / _final` — uses `pg_sha256_*` internally
  via cast; only `_init` seeds different IVs and `_final` truncates to
  28 bytes (sha2.c:978-1018).
- `pg_sha384_init / _update / _final` — uses `pg_sha512_*` with
  different IVs, truncates to 48 bytes (sha2.c:950-975).
- Two compile-time switches: `SHA2_UNROLL_TRANSFORM` for an unrolled
  inner loop (per the header comment around sha2.c:74-80).

## OpenSSL vs fallback dispatch

Build-time. Peer is `cryptohash_openssl.c::EVP_sha{224,256,384,512}()`.

## State / globals

- Static SHA-256 / SHA-512 round constants (K array) and initial-hash
  arrays for each variant. All read-only.

## Concurrency

Reentrant.

## Phase D notes

- **All four `_final` functions explicitly `memset(context, 0,
  sizeof(*context))` before returning** (e.g. sha2.c:974, 1017).
  This is unusually good discipline — even before
  `pg_cryptohash_free` scrubs the union, the algorithm has already
  scrubbed its own state at finalisation. **Model for the rest of
  this directory.** [verified-by-code, sha2.c:974, 1017 and the
  analogous lines in SHA-256 / SHA-512 finals]
- This file is the production hash for SCRAM-SHA-256 password
  derivation in non-OpenSSL builds. Performance-critical path on
  systems that haven't enabled OpenSSL.

## Potential issues

- **[ISSUE-dead-code (eventual): SHA-2 fallback exists only for
  no-OpenSSL builds]** Same parity story as MD5/SHA-1. But SHA-2
  removal is unlikely because SCRAM-SHA-256 still needs a
  no-OpenSSL fallback. Severity: nit.
- **[ISSUE-undocumented-invariant: `pg_sha224_update` casts
  `pg_sha224_ctx *` to `pg_sha256_ctx *`]** `sha2.c:989-991`. Safe
  by typedef equivalence (sha2_int.h:67), but a future struct
  divergence between 224/256 would silently break. Documented at
  typedef site but easy to miss. Severity: nit.

## Cross-refs

- Internal header: `knowledge/files/src/common/sha2_int.h.md`.
- Public constants: `knowledge/files/src/include/common/sha2.h.md`.
- Dispatch facade: `knowledge/files/src/common/cryptohash.c.md`.
- The SCRAM primitives that depend on it:
  `knowledge/files/src/common/scram-common.c.md`.

## Tally

`[verified-by-code]=6 [from-comment]=2 [inferred]=2`
