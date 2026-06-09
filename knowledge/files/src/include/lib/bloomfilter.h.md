# `src/include/lib/bloomfilter.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 27 (impl 294)

## Role

In-tree Bloom-filter primitive: opaque `bloom_filter` + 5-function
API for caller-seeded probabilistic set-membership testing. The
canonical example consumer in core is `amcheck` (heap/btree
verification: `contrib/amcheck/verify_heapam.c`, `verify_nbtree.c`)
and `tidstore` building. Distinct from the `contrib/bloom/` Bloom
*index access method*, though both rely on bits-per-element
parameterisation. [verified-by-code] `source/src/include/lib/bloomfilter.h:16-25`

## Public API

- `bloom_create(int64 total_elems, int bloom_work_mem, uint64 seed)`
  — sizes bitset; seed is caller-supplied to vary false-positive
  pattern across runs. `source/src/backend/lib/bloomfilter.c:87-118`
- `bloom_add_element(filter, elem, len)` — adds raw bytes.
  `source/src/backend/lib/bloomfilter.c:135-149`
- `bloom_lacks_element(filter, elem, len)` — returns true iff
  *definitely not present*; false → maybe present.
  `source/src/backend/lib/bloomfilter.c:153-172`
- `bloom_prop_bits_set(filter)` — diagnostic.

## Invariants

- INV-1: bitset size is rounded to a power of two so modulo is a
  bit-AND. [verified-by-code]
  `source/src/backend/lib/bloomfilter.c:280-294` (`mod_m`)
- INV-2: k (number of hash functions) is clamped to
  `Max(1, Min(k, MAX_HASH_FUNCS))` where `MAX_HASH_FUNCS = 10`.
  [verified-by-code] `source/src/backend/lib/bloomfilter.c:200-234`
- INV-3: Only TWO real 32-bit hashes are computed per element via
  `hash_any_extended(elem, len, filter->seed)`; the other k-2 are
  derived by "enhanced double hashing"
  (`x = mod_m(x+y, m); y = mod_m(y+i, m)`). [verified-by-code]
  `source/src/backend/lib/bloomfilter.c:249-276`

## Notable internals

- `hash_any_extended` is the same 64-bit hash family used by
  `hashfn.h` consumers — so the in-tree bloom filter's collision
  surface is whatever `hash_any_extended` produces, seed-mixed.
- Caller-provided `seed` is the *only* line of defence against
  adversarial input crafting collisions when the filter is exposed
  to attacker-influenced data. Most internal callers pass `0`.

## Trust boundary (Phase D)

This file joins the **A11/A13/A14 signature-collision cluster**.
The cluster currently spans:

- `contrib/hstore/hstore_gin.c` — GIN signature
- `contrib/ltree/_ltree_gist.c` — GiST signature
- `contrib/intarray/_intbig_gist.c` — GiST signature
- `contrib/pg_trgm/trgm_gist.c` — GiST signature
- `contrib/bloom/blutils.c` — Bloom AM (different bloom, ad-hoc)

**Relationship to `contrib/bloom/`:** the contrib Bloom AM does
NOT use this library; it implements its own multi-hash via
`hashfn.h` in `contrib/bloom/blutils.c:hashValue`. So
`lib/bloomfilter.h` is the **second** in-tree Bloom implementation,
used by amcheck and verify paths rather than indexing.
[verified-by-code] `contrib/bloom/blutils.c:hashValue`

**Adversarial angle:** if an extension exposes
`bloom_lacks_element` to user-influenced bytes with a fixed seed
(e.g. seed=0 like most callers), an attacker who knows the seed
can craft collisions to inflate the false-positive rate, e.g. to
*hide* heap corruption from amcheck. Seed must be PRNG-derived
when used adversarially. [inferred from
`source/src/backend/lib/bloomfilter.c:80-85` comment]

## Cross-refs

- `knowledge/files/contrib/bloom/blutils.c.md` (A13) — sibling
  implementation
- `knowledge/files/contrib/hstore/hstore_gin.c.md` (A11/A13) —
  signature-collision peer
- `knowledge/files/contrib/amcheck/` (A14) — primary consumer

## Issues

- ISSUE-DESIGN: 5 separate Bloom implementations in-tree
  (lib + bloom-AM + hstore + ltree + intarray + pg_trgm signatures);
  no unified abstraction. (Low — historical, by-design.)
- ISSUE-TRUST: default seed=0 in all internal callers of
  `bloom_create`; if exposed to user data via an extension, an
  attacker can craft collisions. (Low — no current exposure.)
