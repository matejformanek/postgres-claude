# `src/backend/lib/bloomfilter.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~295
- **Source:** `source/src/backend/lib/bloomfilter.c`

Space-efficient probabilistic set-membership filter, parameterised by
an estimate of the final set size and a `work_mem` budget. Aims for a
false-positive rate of 1-2% in normal sizing. Two real 32-bit hashes
are derived from one 64-bit `hash_any_extended`, then "enhanced double
hashing" produces up to `MAX_HASH_FUNCS = 10` hash values per element.
Used by amcheck (`verify_nbtree.c`) and was originally written for
parallel CREATE INDEX bloom filtering. [verified-by-code]

## API / entry points

- `bloom_create(int64 total_elems, int bloom_work_mem, uint64 seed)` —
  bitset size rounded down to a power of two ≤ `bloom_work_mem * 1024`
  bytes; capped at 2^32 bits (512MB) so we can use 32-bit hash
  arithmetic and stay below `MaxAllocSize`. Always ≥ 1 MB.
  [verified-by-code §bloomfilter.c:86-120]
- `bloom_add_element(filter, elem, len)` — `O(k)` bit-sets.
- `bloom_lacks_element(filter, elem, len)` — true ⇒ definitely not
  in set; false ⇒ probably in set.
- `bloom_prop_bits_set(filter)` — debug instrumentation; computes via
  `pg_popcount` over the bitset bytes. Documented as "the only
  instrumentation low enough overhead to appear in debug traces."
  [from-comment §bloomfilter.c:183-185]
- `bloom_free(filter)`.

## Notable invariants / details

- Bitset size `m` is always a power of two, so `mod_m` uses `val &
  (m-1)` and avoids modulo bias. [verified-by-code §bloomfilter.c:287-294]
- `optimal_k = round(ln(2) * m / n)` clamped to `[1, MAX_HASH_FUNCS]`.
  [verified-by-code §bloomfilter.c:228-234]
- Seed is caller-supplied; a fresh seed per fingerprinting pass makes
  it unlikely the same false positive recurs — useful for amcheck's
  retry strategy. [from-comment §bloomfilter.c:80-85]
- The cap of 2^32 bits is documented as deliberate: leaves headroom
  below the 1 GB `MaxAllocSize` for the small `bloom_filter` header
  that precedes the flexible array member. [from-comment §bloomfilter.c:201-208]

## Potential issues

- File-line `bloomfilter.c:42`. `MAX_HASH_FUNCS = 10` is a hard cap;
  `optimal_k` happily computes much larger values for tiny `n` /
  large `m` ratios, so the clamp can degrade the false-positive rate
  silently in the very-low-cardinality regime. Not a bug — documented
  by the references — but worth noting.
  [ISSUE-undocumented-invariant: silent k clamp when m/n is very large (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `lib`](../../../../issues/lib.md)
<!-- issues:auto:end -->
