---
path: src/test/modules/test_radixtree/test_radixtree.c
anchor_sha: e18b0cb7344
loc: 458
depth: read
---

# src/test/modules/test_radixtree/test_radixtree.c

## Purpose

Drives the adaptive radix tree template in `src/include/lib/radixtree.h`
through every node-class size (RT_CLASS_4 / 16_LO / 16_HI / 48 / 256) at
multiple shift levels (single-node, two-level, max-depth) in both ascending
and descending key order, then runs a 100 000-key random-set test that also
checks negative lookups, iteration order, and deletion. `[verified-by-code]`

The radix tree is used by the heap vacuum's TID store and other hot-path
collections, so this test is the front-line correctness gate for those.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_radixtree` | `test_radixtree.c:430` | SQL-callable driver: runs `test_empty` + 30 `test_basic` parameterizations + `test_random` |
| `test_empty` (static) | `:120` | Empty-tree invariants: `rt_find` returns NULL, `rt_delete` returns false, iterator yields nothing |
| `test_basic` (static) | `:161` | Single-node-class workout — set/find/update/delete/re-insert/iterate |
| `test_random` (static) | `:292` | 100k random keys, negative lookups between/below/above the key range, ordered iteration with duplicate handling |

## Internal landmarks

- Custom `EXPECT_TRUE` / `EXPECT_FALSE` / `EXPECT_EQ_U64` macros (`:25-49`)
  produce one elog(ERROR) per failed expectation with file:line, so a
  buildfarm failure points to the exact assertion.
- The template is instantiated inline via the standard radixtree macro dance
  (`:94-104`): `RT_PREFIX rt`, `RT_VALUE_TYPE uint64`, `RT_USE_DELETE`,
  `RT_DEBUG`. The optional `RT_SHMEM` flag is wired up behind a manually
  toggled `#define TEST_SHARED_RT` for one-off DSA-backed runs.
- `rt_node_class_tests[]` (`:68`) drives the test by node-class. `nkeys` is
  chosen to push the tree into each size class — 2 for node-4, 15 for
  node-16-lo, 30 for node-16-hi, 60 for node-48, 256 for node-256.
- The `shift` parameter (0, 8, max_shift = 56) controls how many tree levels
  exist: shift=0 → all keys differ only in the low byte → tree has one
  child node under the root; max_shift → all keys differ only in the high
  byte → tree has the maximum 8 levels.
- `test_random` uses a `SlabContext` (`:313-316`) sized to `sizeof(TestValueType)`,
  matching the way real consumers (TID store) allocate.

## Invariants & gotchas

- **Test module — never load in production.**
- The choice of `TestValueType = uint64` (`:56`) is deliberate: on 64-bit
  platforms the value fits in the last-level child pointer (no leaf
  allocation); on 32-bit platforms it forces a `single-value leaf`. One
  type, two code paths — buildfarm coverage for both.
- `rt_set` returns `true` if the key was already present, `false` if newly
  inserted — the inverse of what some hash APIs use. `test_basic` exercises
  both `EXPECT_FALSE(rt_set(...))` on first insert and `EXPECT_TRUE` on
  update (`:200`, `:222`).
- Iteration is documented to return keys in ascending order; `test_basic`
  with `asc=false` verifies the iterator still yields ascending regardless
  of insertion order (`:253-264`).
- Random test deliberately filters keys to a small space (`0x07FF_FFFF`,
  `:300`) so that ~100k inserts produce dense + duplicate keys. Duplicate
  insert semantics: `rt_set` overwrites; the duplicate-handling logic in
  the iteration check (`:355-357`) skips successive equal keys.
- Negative-lookup tests (`:351-384`) cover the three boundary classes:
  between keys, below minimum, above maximum.
- The `#ifdef TEST_SHARED_RT` arms (`:127-131`, `:155-157`, etc.) require
  the module to be in `shared_preload_libraries` because DSA setup must
  happen before regular SQL access.

## Cross-refs

- `source/src/include/lib/radixtree.h` — the template under test.
- `source/src/backend/access/common/tidstore.c` — the heap-vacuum TID
  store, a real-world consumer of this template.
- `source/src/backend/utils/mmgr/dsa.c` — DSA backing for `RT_SHMEM` mode.
- `knowledge/files/src/include/lib/radixtree.h.md` — the implementation
  doc (when written).
