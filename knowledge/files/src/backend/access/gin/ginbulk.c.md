# `src/backend/access/gin/ginbulk.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~292
- **Source:** `source/src/backend/access/gin/ginbulk.c`

Build-time accumulator that buffers `(key, attnum, category) →
[heap-TID...]` mappings in an in-memory red-black tree (`rbtree.c`),
ready to be flushed to the GIN posting tree(s) at end of build. Used by
both `CREATE INDEX` (gininsert.c) and the pending-list cleanup path
(ginfast.c). Maintains a memory accounting counter
(`accum->allocatedMemory`) that drives the
`maintenance_work_mem`-vs-spill decision in callers.
[verified-by-code]

## API / entry points

- `ginInitBA(BuildAccumulator *accum)` — initialize. Caller-owned
  `accum->ginstate` is left untouched. Creates the rbtree with custom
  combiner (`ginCombineData`), comparator (`cmpEntryAccumulator`), and
  allocator (`ginAllocEntryAccumulator`). [verified-by-code]
- `ginInsertBAEntries(accum, heapptr, attnum, entries[], categories[],
  nentries)` — insert all keys for one heap tuple. Uses a
  divide-and-conquer insertion order (middle, then quarters, etc.) to
  avoid worst-case rebalancing when the input array is already sorted
  (which it typically is, since GIN extract functions normalize keys).
  See block comment at lines 192-207. [verified-by-code]
- `ginBeginBAScan(accum)` — set up an in-order rbtree iteration via
  `rbt_begin_iterate(LeftRightWalk, ...)`. [verified-by-code]
- `ginGetBAEntry(accum, *attnum, *key, *category, *n)` — return the
  next accumulator entry; the TID list is sorted lazily on demand
  (only if `entry->shouldSort` was set during insertion). Returns NULL
  when exhausted. [verified-by-code]

## Notable invariants / details

- `GinEntryAccumulator` lifetime: never freed individually; the
  rbtree's `freefunc` is NULL (line 119). Nodes come in chunks of
  `DEF_NENTRY = 2048` from `ginAllocEntryAccumulator` (lines 84-106),
  and the chunk pointer is overwritten when full — so the per-chunk
  array is leaked until the surrounding memory context is reset. This
  is intentional: GIN build runs in a short-lived context. [from-comment]
- Posting-list growth: `eo->list` doubles on overflow via `repalloc_huge`
  (line 50). The check `if (eo->maxcount > INT_MAX)` (line 41) is the
  doubling guard — when `maxcount > INT_MAX`, the *next* doubling would
  overflow `int32`. With `DEF_NPTR = 5` start and 12 bytes per
  `ItemPointerData`, this allows up to ~25 GB per single-key posting
  list before erroring. Error hints `Reduce "maintenance_work_mem"`,
  which is misleading because the underlying cause is one key being
  extremely common, not memory pressure per se. [verified-by-code]
  [ISSUE-doc-drift: errhint "Reduce maintenance_work_mem" doesn't
  actually help when one single key has > 2^31 TIDs (nit)]
- `accum->allocatedMemory` is updated on every `palloc`/`repalloc` to
  count `GetMemoryChunkSpace()` of all the per-entry posting arrays
  plus every 2048-chunk allocator block plus by-reference key datums.
  Caller polls this counter to know when to flush vs continue
  accumulating. [verified-by-code]
- Sorted-input optimisation: `ginInsertBAEntries` step-rotates so the
  middle element goes first, then both quarters, then eighths, etc.
  (lines 214-241). This produces a near-balanced rbtree from already-
  sorted input without rebalances. The `step >>= 1` step computes the
  largest power of 2 ≤ nentries via the bit-fill trick on lines
  224-230. [from-comment]
- `ginCombineData` (combiner callback): assumes `newdata` always carries
  exactly one item pointer (line 36-38). It appends to the existing
  posting list, growing if needed, and sets `shouldSort = true` if the
  new TID is out of order vs the previous tail (line 62-63). The
  `Assert(res != 0)` (line 60) enforces no duplicate TIDs at insert
  time. [verified-by-code]
- `cmpEntryAccumulator` (line 71-81) routes through
  `ginCompareAttEntries` so the ordering matches the on-disk entry-tree
  ordering — important so the eventual posting tree write hits the
  index in the right order. [verified-by-code]

## Potential issues

- Line 41. `if (eo->maxcount > INT_MAX)` — `maxcount` is declared
  `uint32` in `gin_private.h`, so this branch can fire. Once the
  doubling caps out at ~2 G entries, the error message advises tuning
  `maintenance_work_mem`, which is not actually the right knob; the
  underlying issue is one extremely common key. Cosmetic. [ISSUE-doc-drift:
  unhelpful errhint for a posting-list-too-long error (nit)]
- Line 84-106. `ginAllocEntryAccumulator` retains the *last* allocated
  chunk pointer in `accum->entryallocator` and overwrites it once the
  chunk fills — earlier chunks become unreachable from `accum` but
  still consume memory in the build context. Comment says "no need to
  reclaim RBTNodes individually" so this is intentional, but it means
  `accum->allocatedMemory` correctly tracks them only because it's
  bumped at allocation time, not via traversal. Documented in comment.
  [verified-by-code]
- Line 287-289. `qsort` is invoked unconditionally when `shouldSort` is
  true even if the posting list might already be sorted by coincidence.
  Minor — `shouldSort` is set only when an out-of-order insert was
  observed, so this is bounded. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `access`](../../../../../issues/access.md)
<!-- issues:auto:end -->
