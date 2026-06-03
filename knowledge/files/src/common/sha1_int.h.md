---
path: src/common/sha1_int.h
anchor_sha: 4b0bf0788b0
loc: 81
---

# sha1_int.h

- **Source path:** `source/src/common/sha1_int.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 81

## Purpose

Internal header for the in-tree SHA-1 fallback (`sha1.c`). Defines
`pg_sha1_ctx` (hash state h, byte-count c, message buffer m,
`count` byte index) and the three init/update/final primitives.
Used only when `cryptohash.c` is built; OpenSSL path bypasses this
entirely. [verified-by-code, sha1_int.h:51-79]

## Key declarations

- `struct pg_sha1_ctx` (sha1_int.h:56-74):
  - `h.b8[20] / h.b32[5]` — 160-bit running hash, union-aliased.
  - `c.b8[8] / c.b64[1]` — message-length counter in bits.
  - `m.b8[64] / m.b32[16]` — current block.
  - `count` — within-block byte position (0..63).
- Prototypes: `pg_sha1_init / _update / _final` (sha1_int.h:77-79).

## Phase D notes

- Same on-stack-via-union story as MD5: lives inside
  `pg_cryptohash_ctx.data.sha1` and is scrubbed by
  `pg_cryptohash_free`.
- WIDE-project copyright; struct layout is load-bearing because the
  union aliases assume a specific endianness model (`sha1.c`
  byte-swaps explicitly in `sha1_step` for `!WORDS_BIGENDIAN`).

## Cross-refs

- Impl: `knowledge/files/src/common/sha1.c.md`.
- Public constants: `knowledge/files/src/include/common/sha1.h.md`.

## Tally

`[verified-by-code]=3`
