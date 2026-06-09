# src/include/common/hashfn.h

## Purpose
Public, **on-disk-stable** hash function API. Declares the externs for
`hash_bytes` / `hash_bytes_extended` / `hash_bytes_uint32` (impl in
`src/common/hashfn.c`) plus a handful of inline helpers:

- `Datum hash_any(...)` / `Datum hash_any_extended(...)` /
  `Datum hash_uint32(...)` — backend-only `Datum`-returning wrappers
- `string_hash`, `tag_hash`, `uint32_hash` — dynahash key callbacks
- `oid_hash` — `#define`d as `uint32_hash` ("Remove me eventually",
  `hashfn.h:59`)
- `hash_combine(a, b)` (`hashfn.h:67`) — boost-style 32-bit combiner
- `hash_combine64(a, b)` (`hashfn.h:79`) — 64-bit variant
- `murmurhash32(uint32)` (`hashfn.h:91`), `murmurhash64(uint64)`
  (`hashfn.h:105`) — fast inline scalar mixers
- `ROTATE_HIGH_AND_LOW_32BITS(v)` macro (`hashfn.h:18`) — special rotation
  used by extended hash functions to stay compatible with the non-extended
  result when seed = 0

## Role in PG
- Hash indexes use the per-type `hashtext`/`hashint8`/... functions which
  call into these via fmgr.
- Hash partitioning (`partbounds.c`, `partprune.c`) uses `hash_combine64`
  to fold per-column extended hashes into a row hash.
- Bloom filter (`lib/bloomfilter.c`) uses `hash_combine64` for double
  hashing.
- dynahash uses `string_hash`/`tag_hash`/`uint32_hash` as default
  callbacks.
- `murmurhash32`/`murmurhash64` are used by `simplehash.h`, `dynahash.c`
  hash-resize logic, plan-cache key mixing.

## State / globals
None.

## Phase D notes
- **Stability contract.** Output of `hash_bytes` is part of the on-disk
  format for hash indexes and the catalog representation of hash
  partitioning. Any change here is a catversion bump and a hash-index
  rebuild requirement.
- **`murmurhash32`/`murmurhash64`** are inline finalizers from the
  Murmur3 family. Fast bit mixers, not full hash functions — they
  expect the input to already be 32 or 64 bits of partially-mixed
  randomness. Used as scrambling steps inside hash-table indexing, NOT
  as the primary hash of variable-length keys.
- **`hash_combine` is order-sensitive** — `hash_combine(a, b) !=
  hash_combine(b, a)`. Important for callers iterating tuple columns.
- **Same hash-flooding caveat as hashfn.c** — no per-process keying.

## Cross-refs
- Stable impl: `knowledge/files/src/common/hashfn.c.md`.
- Unstable companion: `knowledge/files/src/include/common/hashfn_unstable.h.md`.
- Hash-collision DoS: A11 / A13 / A14 echo this in pgcrypto and
  fuzzystrmatch contexts. See `knowledge/issues/pgcrypto.md` and
  `knowledge/issues/contrib/fuzzystrmatch.md`.

## Issues
1. `[ISSUE-documentation: header doesn't declare "stable, on-disk safe"
   contract; reviewers must infer from companion-header naming
   (likely)]` — `source/src/include/common/hashfn.h:1-119`.
2. `[ISSUE-audit-gap: no header-level distinction between
   security-grade vs general-purpose hash; murmurhash32/64 inline
   helpers are not security-grade and have no warning (maybe)]` —
   `source/src/include/common/hashfn.h:91-117`.
3. `[ISSUE-stale-todo: \`#define oid_hash uint32_hash /* Remove me
   eventually */\` has been there since 2017 (nit)]` —
   `source/src/include/common/hashfn.h:59`.
4. `[ISSUE-defense-in-depth: no per-process keying; hash-flood DoS
   surface on attacker-controlled inputs to dynahash tables (maybe)]` —
   `source/src/include/common/hashfn.h:23`.
