# `src/backend/lib/rbtree.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~830
- **Source:** `source/src/backend/lib/rbtree.c`

Generic red-black tree, adapted from Thomas Niemann's "Sorting and
Searching Algorithms" cookbook. Used by GIN's pending-list builder,
range-type indexing, the executor's RelationStats and a couple of
contrib modules. [verified-by-code §rbtree.c:1-26]

The node payload is caller-controlled: `rbt_create(node_size, …)`
takes the total size of `RBTNode + caller-extra-data`, and the
comparator/combiner/alloc/free callbacks treat the extra-data tail
as opaque. The combiner is invoked when `rbt_insert` finds an equal
key and merges the proposed node into the existing one. [verified-by-code §rbtree.c:101-123]

## API / entry points

- `rbt_create(node_size, comparator, combiner, allocfunc, freefunc, arg)` —
  `node_size > sizeof(RBTNode)` (asserted). `freefunc` may be NULL
  if caller doesn't need retail reclamation. [verified-by-code §rbtree.c:101-123]
- `rbt_find(rbt, data)` / `rbt_find_great(rbt, data, equal_match)` /
  `rbt_find_less(...)` / `rbt_leftmost(rbt)` — searches.
- `rbt_insert(rbt, data, *isNew)` — O(log n); merges via combiner on
  duplicate, else allocates via allocfunc and rebalances via
  `rbt_insert_fixup` (rotations + recoloring).
  [verified-by-code §rbtree.c:453-519]
- `rbt_delete(rbt, node)` / `rbt_delete_node(rbt, z)` — full RB delete
  with `rbt_delete_fixup` rebalancing. [verified-by-code §rbtree.c:521-700]
- `rbt_begin_iterate(rbt, ctrl, iter)` / `rbt_iterate(iter)` —
  in-order (LeftRight) or reverse (RightLeft) iteration; iterator
  state is caller-allocated. [verified-by-code §rbtree.c:802-826]

## Notable invariants / details

- **RBTNIL sentinel.** A single static `RBTNode sentinel = { .color =
  RBTBLACK, .left = RBTNIL, .right = RBTNIL, .parent = NULL }` is
  shared across all RB-trees in the backend. Leaf nodes point at
  `RBTNIL`, not `NULL`, which simplifies the rotation/fixup code.
  Named `RBTNIL` rather than `NIL` to avoid collision with
  `nodes/pg_list.h`'s `NIL` (= NULL List).
  [from-comment §rbtree.c:57-66]
- **No explicit destroy.** Trees are typically freed by resetting
  the surrounding `MemoryContext`. The `RBTree` struct itself can
  also just be pfree'd. [from-comment §rbtree.c:93-100]
- **`rbt_copy_data` uses `memcpy(dest+1, src+1, node_size - sizeof(RBTNode))`**
  to move the trailing payload bytes during rotations/swaps without
  disturbing the RBTNode header. [verified-by-code §rbtree.c:126-130]
- **Combiner's righthand argument has invalid RBTNode fields.** The
  header comment is explicit: callers must only touch the caller-
  extra-data fields. Same applies to comparator inputs.
  [from-comment §rbtree.c:80-86]
- **freefunc gets a node with possibly-invalid extra data.** "Should
  just be pfree or equivalent; it should NOT attempt to free any
  subsidiary data, because the node passed to it may not contain
  valid data!" [from-comment §rbtree.c:88-91]

## Potential issues

- None — long-stable file, last meaningful change was the API
  rename in 2020.
