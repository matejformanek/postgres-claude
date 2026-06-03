---
path: src/common/sha2_int.h
anchor_sha: 4b0bf0788b0
loc: 91
---

# sha2_int.h

- **Source path:** `source/src/common/sha2_int.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 91

## Purpose

Internal header for the in-tree SHA-2 fallback (`sha2.c`). Defines
two state structs (`pg_sha256_ctx`, `pg_sha512_ctx`) and two typedef
aliases (`pg_sha224_ctx = pg_sha256_ctx`,
`pg_sha384_ctx = pg_sha512_ctx`) reflecting the spec's
"truncated-output" relationship. Each algorithm has its own
init/update/final triple. [verified-by-code, sha2_int.h:55-89]

## Key declarations

- `struct pg_sha256_ctx` (sha2_int.h:55-60):
  - `state[8]` — eight 32-bit hash words.
  - `bitcount` — single uint64 message-bit counter.
  - `buffer[PG_SHA256_BLOCK_LENGTH]` — 64-byte working block.
- `struct pg_sha512_ctx` (sha2_int.h:61-66):
  - `state[8]` — eight 64-bit hash words.
  - `bitcount[2]` — 128-bit counter.
  - `buffer[PG_SHA512_BLOCK_LENGTH]` — 128-byte block.
- Twelve prototypes (init/update/final × 4 algorithms,
  sha2_int.h:71-89). SHA-224 reuses SHA-256 update; SHA-384 reuses
  SHA-512 update — the truncation happens in the algorithm-specific
  `_final`.

## Phase D notes

- All four ctx variants are unioned into `pg_cryptohash_ctx.data` in
  cryptohash.c — same `explicit_bzero`-on-free story.
- `sha2.c::pg_sha224_final` does an explicit `memset(context, 0,
  sizeof(pg_sha224_ctx))` at the end (sha2.c:1017) — finalisation
  scrubs even before `pg_cryptohash_free` does. Good defensive
  pattern; all four `_final`s do it.

## Cross-refs

- Impl: `knowledge/files/src/common/sha2.c.md`.
- Public constants: `knowledge/files/src/include/common/sha2.h.md`.

## Tally

`[verified-by-code]=5`
