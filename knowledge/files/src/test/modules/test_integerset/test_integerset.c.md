---
path: src/test/modules/test_integerset/test_integerset.c
anchor_sha: e18b0cb7344
loc: 619
depth: read
---

# src/test/modules/test_integerset/test_integerset.c

## Purpose

Comprehensive correctness + micro-benchmark harness for `src/include/lib/integerset.h`
— the **sparse uint64 set** built on Simple-8b run-length integer compression
over a B-tree. Historically used by VACUUM to remember dead-tuple TIDs encoded
as 64-bit identifiers; superseded for VACUUM by TidStore in PG17 but the data
structure is still around for other sparse-integer use cases. The harness runs
corner-case tests (empty, single-value, huge distances near 2^60 / 2^64) plus
nine repeating-pattern tests (`test_specs[]`) that populate up to 100 M
integers, then probe and iterate them for correctness and (optionally)
performance numbers. `[from-comment]` `test_integerset.c:21-32`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_integerset()` | `:103` | SQL-callable entry; runs `test_empty`, `test_huge_distances`, five `test_single_value` cases, five `test_single_value_and_filler` cases, then iterates over all `test_specs[]` patterns |

No `_PG_init`; no hooks. `intset_test_stats` (`:32`) is a compile-time bool —
flip it true and rebuild to get timing + memory printed to stderr.

## Internal landmarks

- `test_specs[]` (`:50-90`) — nine `(name, pattern_str, spacing, num_values)`
  rows. Patterns range from "all ones" (dense) to "one-every-64k" and "sparse"
  (pattern of one with spacing 10 M), plus three rows with
  spacing > 2^32 / > 2^60 to probe the Simple-8b boundary.
- `test_pattern(spec)` (`:131`) — pattern walker. Creates a private memory
  context (`:166-170`) so `MemoryContextStats` can attribute usage, populates
  via `intset_add_member`, asserts `intset_num_entries == spec->num_values`,
  random-probes 100 K positions with `intset_is_member` and recomputes the
  expected truth from the pattern (`:235-269`), then iterates the entire set
  and asserts ordered equality.
- `test_huge_distances` (`:515`) — the most interesting case. Adds 12 values
  with carefully chosen deltas around 2^60 (the Simple-8b encoding boundary —
  see `:510-512` from-comment) then pads to 1000 small-stride additions to
  force the staging buffer to flush into the tree. Probes `y-1`, `y`, `y+1`
  around each value to catch off-by-one in `intset_is_member`.
- `test_single_value_and_filler` (`:373`) — exists because
  `intset_add_member` buffers recent additions; adding a single integer never
  exercises the B-tree at all (`:367-371` from-comment). Filler forces the
  buffer to flush so the tree path is reached.
- `check_with_filler` (`:466`) — predicate oracle for the filler tests.
- `pg_prng_uint64_range(&pg_global_prng_state, ...)` (`:248`) — uses the
  process-global PRNG, so probe sequences are reproducible per backend startup
  but not across runs.

## Invariants & gotchas

- **TEST MODULE — never load in production.** The patterns can allocate
  100 M-entry sets which is fine for a regression run but huge for a normal DB.
- **Simple-8b max delta = 2^60.** The "clusters, distance > 2^60" spec and
  `test_huge_distances` exist specifically to probe this boundary; deltas at
  exactly 2^60 must fall through to a multi-block encoding rather than wrap.
- **`PG_UINT64_MAX` is in range.** `test_single_value(PG_UINT64_MAX)` and
  `test_single_value_and_filler(PG_UINT64_MAX, ...)` assert the implementation
  accepts the very top of the uint64 space without UB on `value + 1`.
- **Buffer-vs-tree code paths are distinct.** A single `intset_add_member`
  call lives entirely in the staging buffer; only after enough additions does
  it flush into the immutable B-tree. The filler tests force the flush so the
  tree code is actually covered.
- **Memory-usage sanity bound.** `test_single_value_and_filler` asserts
  `5000 <= intset_memory_usage(intset) <= 500_000_000` (`:455-456`) — coarse
  bounds, just enough to catch an unbounded leak or a zero-return bug.
- **Iterator must visit values in ascending uint64 order.** All
  iteration-based asserts compare against the in-order expected sequence
  (`:282-308`, `:443-452`, `:609-618`). A wrong-order iterator fails loudly.
- Failure modes caught: encode-decode asymmetry across the 2^60 boundary,
  off-by-one membership at value boundaries, lost values on buffer→tree flush,
  iterator dropping or duplicating entries, memory-usage accounting that
  zeroes or runs away.

## Cross-refs

- `knowledge/files/src/include/lib/integerset.h.md` — the API under test
  (`intset_create / intset_add_member / intset_is_member / intset_num_entries /
  intset_begin_iterate / intset_iterate_next / intset_memory_usage`).
- `knowledge/files/src/backend/lib/integerset.c.md` — Simple-8b + B-tree
  implementation.
- `knowledge/files/src/test/modules/test_tidstore/test_tidstore.c.md` — the
  successor data structure used by VACUUM since PG17.
- `knowledge/subsystems/vacuum.md` — historical context for why the data
  structure exists.
