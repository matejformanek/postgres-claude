# `src/backend/lib/integerset.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1040
- **Source:** `source/src/backend/lib/integerset.c`

In-memory append-only set of 64-bit integers, packed using Simple-8b
on top of an in-memory B-tree. Density ranges from ~0.1 bytes per int
for long runs of consecutive values to ~8 bytes per int for very
sparse sets. Built originally as the dead-TID tracker for VACUUM
(pre-PG17). PG17's radix-tree-based TID store (`tidstore.c`) is the
current VACUUM choice, but `integerset` is still used in tests and
remains the canonical example of Simple-8b in the tree.
[verified-by-code §integerset.c:1-67]

## API / entry points

- `intset_create(void)` — creates set in `CurrentMemoryContext`;
  remembers the context so subsequent allocations stay there.
  [verified-by-code §integerset.c:282-309]
- `intset_add_member(set, x)` — values MUST be added in monotonically
  non-decreasing order; out-of-order or during-iteration adds throw
  ERROR. Adds go into a small `buffered_values` array (size
  `MAX_BUFFERED_VALUES = 482`) and only flush into the B-tree once
  full. [verified-by-code §integerset.c:368-389]
- `intset_is_member(set, x)` — first checks the unflushed buffer with
  binary search, then walks the B-tree to the right leaf and binary-
  searches the leaf items, finally checking the Simple-8b codeword
  via `simple8b_contains`. [verified-by-code §integerset.c:552-615]
- `intset_begin_iterate` / `intset_iterate_next` — in-order walk.
  Iteration stops new adds. [verified-by-code §integerset.c:622-699]
- `intset_num_entries` / `intset_memory_usage` — counters.

## Notable invariants / details

- **Append-only.** Limitations listed in the header: values added in
  order, no add while iterating, no removal. The limitations are
  documented as not fundamental but unimplemented.
  [from-comment §integerset.c:39-51]
- **No free function.** The header explicitly tells callers to wrap
  the set in a `MemoryContext` and reset that. The set tracks
  `mem_used` via `GetMemoryChunkSpace`. [from-comment §integerset.c:34-37]
- **MAX_TREE_LEVELS = 11.** With 64-fanout internal and leaf nodes,
  this gives `64 * 64^10 ~= 7e18 >= 2^62.5` capacity; you'll run out
  of RAM far before this. Reaching it throws ERROR
  "could not expand integer set". [verified-by-code §integerset.c:96-110, 495-497]
- **Simple-8b encoding** packs 1..240 integers into a single 64-bit
  codeword via a 4-bit selector picking among 16 "modes" (240/120
  zeroes, then groups of 60×1bit, 30×2bit, …, 1×60bit). Detailed
  table at `simple8b_modes` lines 820-847. Special
  `EMPTY_CODEWORD = 0x0FFFFFFFFFFFFFFF` marks "next delta > 2^60, no
  values packed here". [from-comment §integerset.c:777-856]
- **Leaf item layout** is `{ uint64 first; uint64 codeword; }`:
  `first` is the absolute value; `codeword` encodes deltas from
  `first`. Binary search on the leaf uses `first` only.
  [verified-by-code §integerset.c:160-164, 744-775]

## Potential issues

- **File-line `integerset.c:42-49`.** "Values must be added in order
  … None of these limitations are fundamental to the data structure,
  so they could be lifted if needed." Has been the state since this
  was added in PG 12. [ISSUE-stale-todo: random insertions / removal / iter-update unimplemented (nit)]
- **File-line `integerset.c:218-220`.** The `rightmost_nodes` array
  comment says `rightmost_parent[0]`/`rightmost_parent[1]` but the
  variable is actually `rightmost_nodes`. [ISSUE-doc-drift: comment names wrong variable (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `lib`](../../../../issues/lib.md)
<!-- issues:auto:end -->
