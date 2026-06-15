---
path: src/test/modules/test_binaryheap/test_binaryheap.c
anchor_sha: e18b0cb7344
loc: 275
depth: read
---

# src/test/modules/test_binaryheap/test_binaryheap.c

## Purpose

Regression-tests the `lib/binaryheap.h` max-heap implementation across a
range of sizes (1, 2, 3, 10, 100, 1000). Covers the canonical mix of
operations: `add` (with sift-up), `add_unordered` + `build` (Floyd's
heapify), `remove_first`, `remove_node`, `replace_first`, duplicates,
and `reset`. Validates the heap property after every mutation via a
brute-force parent-vs-children scan. `[verified-by-code]`
`test_binaryheap.c:75-96,254-275`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_binaryheap()` | `:257` | Runs all sub-tests at each size in `test_sizes[]` |

## Internal landmarks

- `int_cmp` (`:27`) — max-heap comparator using `pg_cmp_s32` on the
  Datum-encoded `int32`.
- `get_permutation` (`:49`) — inside-out Fisher-Yates from
  `pg_global_prng_state`. Comment explains the algorithm and why the
  swap-with-self case is necessary `[from-comment]` `:56-62`.
- `verify_heap_property` (`:79`) — linear scan; for each index `i`,
  checks `parent_val >= heap[2i+1]` and `>= heap[2i+2]`. ERRORs on
  violation.
- Sub-tests:
  - `test_basic` (`:101`) — add → repeated `remove_first` matches
    `get_max_from_heap`.
  - `test_build` (`:143`) — `add_unordered` ×N → `binaryheap_build`.
  - `test_remove_node` (`:162`) — random-index removals; verifies
    `size` decreases correctly.
  - `test_replace_first` (`:189`) — root replacement with smaller /
    middle / larger values.
  - `test_duplicates` (`:219`) — N copies of one value; all pop equal.
  - `test_reset` (`:238`) — `binaryheap_reset` returns empty heap.

## Invariants & gotchas

- TEST MODULE — measurement only, no hooks installed; safe to load.
- Each sub-test calls `binaryheap_allocate` then leaks the heap (no
  explicit free; relies on the surrounding memory context cleanup at
  function return). Acceptable for regression purposes; not a pattern
  to imitate in production code.
- The 1000-element ceiling is small enough for CI-time predictability;
  the heap-property scan is O(n) per operation, so the test's overall
  worst case is O(n²) per sub-test.
- Uses `pg_global_prng_state` directly — outcomes are deterministic
  across a single process but not across runs.

## Cross-refs

- `source/src/backend/lib/binaryheap.c` — the implementation under test.
- `source/src/include/lib/binaryheap.h` — public API:
  `binaryheap_allocate`, `binaryheap_add`, `binaryheap_add_unordered`,
  `binaryheap_build`, `binaryheap_first`, `binaryheap_remove_first`,
  `binaryheap_remove_node`, `binaryheap_replace_first`, `binaryheap_reset`.
