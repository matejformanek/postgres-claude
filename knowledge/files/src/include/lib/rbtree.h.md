# `src/include/lib/rbtree.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 82

## Role

Generic red-black tree. Caller embeds `RBTNode` as the *first*
field of its larger struct (line 17-22) and supplies size +
comparator + combiner + alloc/free. Used by GiST buffering build,
range types' intersection cache, and the planner's STATS slot cache.
[from-comment] `source/src/include/lib/rbtree.h:17-22`

## Public API

- `rbt_create(node_size, compare, combine, alloc, free, arg)`
- `rbt_find` / `rbt_find_great` / `rbt_find_less` / `rbt_leftmost`
- `rbt_insert(rbt, data, *isNew)` — combiner is called when an
  equal key already exists (lines 58, 74)
- `rbt_delete`
- `rbt_begin_iterate(rbt, RBTOrderControl, *iter)` /
  `rbt_iterate(iter)` — orderings `LeftRightWalk` (inorder) and
  `RightLeftWalk` (reverse inorder)

## Invariants

- INV-1: `RBTNode` must be the **first** field of the containing
  struct (line 17-22) — backwards-compat with rbt_alloc's casting.
- INV-2: caller-supplied `alloc/free` lets clients pool memory
  inside a MemoryContext.
- INV-3: `combiner` is invoked on duplicate-key insertion; if
  NULL, behavior is to drop the new one. [from
  `src/backend/lib/rbtree.c:rbt_insert`]

## Trust boundary (Phase D)

None.

## Cross-refs

- `knowledge/files/src/include/lib/pairingheap.h.md` — alternative
  intrusive structure

## Issues

None.
