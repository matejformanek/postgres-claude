# `src/backend/lib/pairingheap.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~350
- **Source:** `source/src/backend/lib/pairingheap.c`

A pairing-heap priority queue (Fredman/Sedgewick/Sleator/Tarjan 1986).
Amortized O(1) insert and find-min, amortized O(log n) delete-min.
Used by GEQO (genetic query optimizer), `MergeAppend`, `nodeIncrementalSort`,
and several other places that want a heap but don't want bulk
array growth. [verified-by-code §pairingheap.c:1-22]

Caller embeds a `pairingheap_node { first_child, next_sibling, prev_or_parent }`
inside their struct — intrusive, like `ilist`. The comparator is
`(a, b, arg) -> int`; positive means `a` greater. The heap is conceptually
a max-heap (root has the largest comparator value).

## API / entry points

- `pairingheap_allocate(compare, arg)` — palloc + initialize.
- `pairingheap_initialize(heap, compare, arg)` — in-place init,
  useful for shmem-resident heaps. [verified-by-code §pairingheap.c:53-67]
- `pairingheap_add(heap, node)` — O(1): merge new node with current
  root. [verified-by-code §pairingheap.c:125-134]
- `pairingheap_first(heap)` — returns root without modifying.
- `pairingheap_remove_first(heap)` — O(log n) amortized; replace root
  with `merge_children(root->first_child)`, which is the classic
  two-pass merging strategy (pair left-to-right, then merge pairs
  right-to-left). [verified-by-code §pairingheap.c:247-299]
- `pairingheap_remove(heap, node)` — O(log n) amortized; splices the
  node out of its parent/sibling list and merges its children into a
  replacement subheap. [verified-by-code §pairingheap.c:180-239]
- `pairingheap_free(heap)` — frees the heap struct only; the nodes
  belong to the caller (the comment is explicit).
  [from-comment §pairingheap.c:73-74]
- `pairingheap_dump(heap, dumpfunc, opaque)` — debug-only
  (`#ifdef PAIRINGHEAP_DEBUG`), produces a multi-line indented dump.
  [verified-by-code §pairingheap.c:308-346]

## Notable invariants / details

- **Garbage pointers after merge.** The `merge` helper documents
  "the next_sibling and prev_or_parent pointers of the input nodes
  are ignored. On return, the returned node's next_sibling and
  prev_or_parent pointers are garbage." Callers must fix them up
  (see `pairingheap_add` setting both to NULL after merge).
  [from-comment §pairingheap.c:84-91; §pairingheap.c:130-133]
- **`prev_or_parent` is overloaded** — points to the previous
  sibling for non-first-children, and to the parent for the first
  child. The remove path discriminates with
  `node->prev_or_parent->first_child == node`.
  [verified-by-code §pairingheap.c:212-216]

## Potential issues

- None observed; this is a textbook implementation that's been
  stable since PG 9.5.
