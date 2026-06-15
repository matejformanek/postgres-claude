---
path: src/test/modules/test_rbtree/test_rbtree.c
anchor_sha: e18b0cb7344
loc: 516
depth: read
---

# src/test/modules/test_rbtree/test_rbtree.c

## Purpose

Regression-tests the `lib/rbtree.h` red-black tree implementation across
a configurable size. Exercises the canonical operations: in-order
left-right and right-left traversals, `rbt_find`, `rbt_find_less` /
`rbt_find_great` with `equal_match` and "key just deleted" semantics,
`rbt_leftmost`, and `rbt_delete` (including reducing the tree back to
empty). Also confirms that re-inserting an existing key invokes the
`combine` callback and that the library never combines unequal keys.
`[verified-by-code]` `test_rbtree.c:158-162,238-242,405-407`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_rb_tree(size int4)` | `:503` | Runs all sub-tests at the given size; `delsize = max(size/10, 1)` for deletion test |

## Internal landmarks

- Node type `IntRBTreeNode` (`:27-31`) — embeds an `RBTNode` followed by
  an `int key`. The library's intrusive-list convention.
- Helpers:
  - `irbt_cmp` (`:39`) — subtractive int comparator; safe because keys
    are non-negative `[from-comment]` `:35-36`.
  - `irbt_combine` (`:52`) — sanity check that the library never tries
    to combine *different* keys; raises ERROR if so.
  - `irbt_alloc` / `irbt_free` (`:64,71`) — palloc/pfree wrappers.
- `rbt_populate` (`:127`) — inserts a random permutation of
  `0, step, 2*step, ..., (size-1)*step`, then re-inserts index-0 to
  exercise the `combine` path.
- Sub-tests:
  - `testleftright` / `testrightleft` (`:164,204`) — in-order
    traversals must be strictly monotonic and visit all keys.
  - `testfind` (`:243`) — inserts even keys, looks up evens (must
    find) and odds + out-of-range values (must miss).
  - `testfindltgt` (`:287`) — randomly walks `rbt_find_less` /
    `rbt_find_great` outward from a pivot, randomly deleting the
    found key to exercise the "deleted-key equal_match" path.
  - `testleftmost` (`:387`) — checks empty-tree case + smallest-key
    case.
  - `testdelete` (`:409`) — deletes `delsize` random keys, verifies
    presence/absence, then deletes the rest to empty.

## Invariants & gotchas

- TEST MODULE — measurement only; no hooks installed.
- Tree allocator/deallocator are palloc/pfree; the entire test runs
  inside a SQL function's memory context which is cleaned up at return
  — explicit `rbt_create` results are not freed.
- `size` is capped at `MaxAllocSize / sizeof(int)` (`:507`).
- `combine` callback's ERROR is a defensive trip-wire: the library is
  supposed to call it only on equal-key re-insert, so a violation is a
  library bug, not a test bug.

## Cross-refs

- `source/src/backend/lib/rbtree.c` — implementation under test.
- `source/src/include/lib/rbtree.h` — public API: `rbt_create`,
  `rbt_insert`, `rbt_find`, `rbt_find_less`, `rbt_find_great`,
  `rbt_leftmost`, `rbt_delete`, `rbt_begin_iterate`, `rbt_iterate`,
  `RBTOrderControl` enum (LeftRightWalk / RightLeftWalk).
