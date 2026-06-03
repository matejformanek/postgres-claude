# src/common/binaryheap.c

## Purpose
A simple array-backed binary heap (max-heap by comparator return). Used as
the priority-queue primitive throughout PG: merge-append node, gather-merge,
parallel tuplesort merge phase, logical replication reorderbuffer transaction
ordering, autovacuum work scheduling.

## Role in PG
The `binaryheap *` type lives in `src/include/lib/binaryheap.h`. The impl
is in `src/common/` (not `src/backend/lib/`) because it's shared with
some frontend tools that link `src/common/`.

Callers include:
- `nodeMergeAppend.c` — heap over child subplans ordered by their next tuple
- `nodeGatherMerge.c` — heap over parallel worker tuple queues
- `tuplesort` merge phase — heap over runs
- `reorderbuffer.c` (logical decoding) — heap over in-flight transactions
- `autovacuum.c` — heap over candidate work items in some paths

## Key functions
- `binaryheap_allocate(capacity, compare, arg)` (`binaryheap.c:37`) —
  palloc a `binaryheap` struct with flexible-array tail of `bh_node_type`
  (a `Datum`-sized slot). Capacity is **fixed at allocation time** —
  there's no auto-grow.
- `binaryheap_reset(heap)` (`binaryheap.c:61`) — drop contents, keep capacity.
- `binaryheap_free(heap)` (`binaryheap.c:73`) — `pfree`.
- `binaryheap_add_unordered(heap, d)` (`binaryheap.c:114`) — O(1) append,
  invalidates heap property. Caller must follow with `binaryheap_build`.
  ERRORs (`elog ERROR` backend, `pg_fatal` frontend) if at capacity —
  **no auto-grow** (`binaryheap.c:116-123`).
- `binaryheap_build(heap)` (`binaryheap.c:136`) — O(n) heapify; sift_down
  from the last non-leaf upward.
- `binaryheap_add(heap, d)` (`binaryheap.c:152`) — O(log n) insert with
  sift_up. Same capacity check.
- `binaryheap_first(heap)` (`binaryheap.c:175`) — O(1) peek root.
- `binaryheap_remove_first(heap)` (`binaryheap.c:190`) — O(log n) pop;
  moves last element to root + sift_down.
- `binaryheap_remove_node(heap, n)` (`binaryheap.c:223`) — O(log n)
  removal of arbitrary index; sift up or down based on comparator.
- `binaryheap_replace_first(heap, d)` (`binaryheap.c:253`) — O(log n)
  replace root + sift_down. Hot path for merge-append (replace exhausted
  child's next tuple, re-heapify).
- `sift_up` / `sift_down` (`binaryheap.c:268, 311`) — hole-promotion
  technique: don't write the moving node until the final position is
  known, saving copies.

## State / globals
None. Each `binaryheap *` is its own self-contained struct in some
MemoryContext. The struct layout (`binaryheap.h`):

```
struct binaryheap {
    int                   bh_space;     // capacity
    int                   bh_size;      // current count
    bool                  bh_has_heap_property;
    binaryheap_comparator bh_compare;
    void                 *bh_arg;       // opaque arg for comparator
    bh_node_type          bh_nodes[FLEXIBLE_ARRAY_MEMBER];
};
```

## Phase D notes
- **No auto-grow / fixed capacity.** Overflow ERRORs out (or
  `pg_fatal`s in frontend). Callers must size correctly. For merge-append
  this is `list_length(subplans)`; for gather-merge it's `nworkers + 1`.
  This means **a buggy caller passing too small a capacity = ERROR at
  insert time**, but not a crash. [verified-by-code: binaryheap.c:116-123]
- **Element-pointer ownership.** `bh_node_type` is a `Datum`-sized slot
  (typically a pointer). The heap **does not own** the pointed-to memory
  — callers are responsible. Merge-append stores `TupleTableSlot *`
  pointers that live in the executor's own memory.
- **Comparator transitivity.** Sift logic assumes a strict weak ordering.
  A non-transitive comparator silently breaks the heap (no assertion
  checks transitivity). Each caller's comparator is small and inlined,
  reducing risk.
- **`bh_has_heap_property` flag.** Set false by `add_unordered`, asserted
  true by `first` / `remove_first` / `remove_node` / `replace_first`.
  Catches the pattern of `add_unordered` followed by a non-build
  operation. [verified-by-code: binaryheap.c:177, 194, 227, 255]
- **Resize policy.** None — caller must call `binaryheap_allocate` again
  if they need more space (no realloc helper). For long-lived heaps in
  reorderbuffer this is fine because capacity is bounded by
  `max_replication_slots * max_changes_in_memory`.

## Potential issues
- [ISSUE-undocumented-invariant: comparator must be transitive; no
  Assertions verify this. (low)]
- [ISSUE-correctness: a caller that calls binaryheap_first immediately
  after binaryheap_add_unordered (without _build) will trip the Assert in
  debug builds, but in release builds will read the wrong root. The
  Assert is the only safety net. (low)]
- [ISSUE-dead-code: no — every entry point appears used by at least one
  caller in the tree.]
