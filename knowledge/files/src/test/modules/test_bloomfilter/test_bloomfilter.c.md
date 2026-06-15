---
path: src/test/modules/test_bloomfilter/test_bloomfilter.c
anchor_sha: e18b0cb7344
loc: 138
depth: read
---

# src/test/modules/test_bloomfilter/test_bloomfilter.c

## Purpose

Exercises `lib/bloomfilter.h` — populates a Bloom filter with synthetic
strings, then probes a disjoint set of strings to measure the false
positive rate, emitting a WARNING if the empirical rate exceeds 1%. Used
to regression-check the filter's sizing math and hash quality.
`[verified-by-code]` `test_bloomfilter.c:24-25,95-98`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_bloomfilter(power int4, nelements int8, seed int4, tests int4)` | `:113` | Runs `tests` iterations, each creating a Bloom filter sized `2^power` bits |

## Internal landmarks

- `populate_with_dummy_strings` (`:32`) — adds elements of form `iN`.
- `nfalsepos_for_missing_strings` (`:52`) — probes elements of form `MN`,
  counting `!bloom_lacks_element` hits (i.e. probable-positives) — every
  hit is a false positive by construction.
- `create_and_test_bloom` (`:72`) — converts `power` (bit count) to
  `bloom_work_mem` (KB), seeds via `pg_prng_int32p` if caller passed a
  negative seed (`:88`), and emits WARNING vs DEBUG1 based on the 1%
  threshold check `(nfalsepos > nelements * FPOSITIVE_THRESHOLD)`.
- Argument validation (`:121-128`) — `power ∈ [23, 32]`, `tests > 0`,
  `nelements >= 0`.

## Invariants & gotchas

- TEST MODULE — pure measurement, no side effects on shared state, no
  hooks installed. Safe to load anywhere, but exists for regression
  measurement, not production use.
- The 1% threshold (`FPOSITIVE_THRESHOLD`, `:25`) defines test failure;
  a tightly-tuned `bloom_create` should comfortably beat this.
- Seeds always re-creatable: `seed` argument echoed in WARNING/DEBUG1
  message so a flake can be reproduced bit-exactly `[from-comment]`
  `:83-87`.

## Cross-refs

- `source/src/backend/lib/bloomfilter.c` — the implementation under test.
- `source/src/include/lib/bloomfilter.h` — public API: `bloom_create`,
  `bloom_add_element`, `bloom_lacks_element`, `bloom_prop_bits_set`,
  `bloom_free`.
