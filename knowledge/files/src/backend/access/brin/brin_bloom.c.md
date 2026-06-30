# brin_bloom.c

- **Source path:** `source/src/backend/access/brin/brin_bloom.c` (844 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in **bloom** opclass for BRIN: summary is a per-range Bloom filter over hashes of indexed column values. Supports **equality only**, like a hash index, but is much smaller and bitmap-only. [from-comment, brin_bloom.c:1-22]

## Key design

- Values are first hashed via the type's hash function to uint32. The bloom filter stores hashes, not values. [from-comment, brin_bloom.c:24-32]
- Parameterizable via two reloptions: `n_distinct_per_range` (≈ expected distinct elements per range, default heuristic of pagesPerRange × 0.1 or similar) and `false_positive_rate` (default 0.01). Together they determine the filter's `m` (bits) and `k` (hashes). [verified-by-code, opcoptions handler near lines 130-180]
- A filter is dynamically sized at first `addValue`; once committed, it cannot grow. If a range receives many more distinct values than budgeted, FPR degrades but correctness holds (FP never causes wrong results, only extra heap fetches).

## Required + extra procs

| Procnum | Function/role |
|---|---|
| 1 opcInfo | one stored column of BYTEA (serialized BloomFilter) |
| 2 addValue | hash value, set bits in filter |
| 3 consistent | only `=`: probe the filter; return true if all `k` bits set |
| 4 union | bitwise OR the two filters (must have identical `(m, k)`) |
| 11 options | reloption parser for the two tunables |
| 12 hash | type-specific hash function |

## Notes

- Two filters with different `(m,k)` cannot be unioned. The build process enforces consistency by picking `(m,k)` deterministically from reloptions. [inferred]
- Equality only: scan keys with non-`=` operators are not even routed to the consistent function (filtered by the AM dispatcher via the operator-class strategy mapping).

Tags: [from-comment, brin_bloom.c:1-50]; reloption defaults [verified-by-code].

## Open questions

- The exact hash family used (`k` independent hashes derived from one 32-bit base via double-hashing?) — visible in the bit-setting loop but not deeply traced here.
- Whether `false_positive_rate=0` is treated specially (would imply infinite size). [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/brin-tuple-format.md](../../../../../idioms/brin-tuple-format.md)

