# Bitmap heap scan flow — TBM-driven heap fetch

A `BitmapHeapScan` plan node consumes a **TIDBitmap** built
by one-or-more `BitmapIndexScan` children (combined with
`BitmapAnd` / `BitmapOr`) and **fetches the matching heap
pages in physical order**. The pattern lets the planner
union multiple indexes' results without per-tuple back-and-
forth, and turns potentially random IO into sequential.

Anchors:
- `source/src/backend/executor/nodeBitmapHeapscan.c:30-38` —
  module header [verified-by-code]
- `source/src/backend/executor/nodeBitmapHeapscan.c:174-260` —
  BitmapHeapNext + ExecBitmapHeapScan [verified-by-code]
- `source/src/include/nodes/tidbitmap.h` — TIDBitmap API
- `knowledge/data-structures/tupletableslot.md` — output
  goes via slot
- `knowledge/idioms/index-only-scan-vm-check.md` —
  companion (different scan flavor)
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The three-piece pipeline

```
BitmapAnd / BitmapOr
   ├── BitmapIndexScan (idx_a)
   └── BitmapIndexScan (idx_b)
            ↓ TIDBitmap
       BitmapHeapScan
            ↓ heap tuples
```

[verified-by-code `nodeBitmapHeapscan.c:30-38`]

> ExecBitmapHeapScan scans a relation using bitmap info
> ExecBitmapHeapNext workhorse for above

Each leaf BitmapIndexScan returns a TIDBitmap (set of
heap tuple IDs satisfying its index predicate). The
combiner nodes intersect/union them. The heap scan then
fetches each tuple, applies the heap-level recheck quals,
and emits to the parent.

## The TIDBitmap structure

[from `tidbitmap.h`]

Two representations:
- **Exact**: per-page bitmap of slot numbers (when tuple
  count is small).
- **Lossy**: per-page flag only "this page has matches"
  (when bitmap would grow too large to fit
  `work_mem`).

When a lossy page is fetched, the heap scan must re-apply
the **full original predicate** to each tuple — because
the index didn't preserve which specific slots qualified.

## BitmapHeapNext — the fetch loop

[verified-by-code `nodeBitmapHeapscan.c:174-260`]

Simplified:

```c
static TupleTableSlot *
BitmapHeapNext(BitmapHeapScanState *node)
{
    /* Lazily build the bitmap on first call */
    if (!node->initialized) {
        tbm = (TIDBitmap *) MultiExecProcNode(outerPlanState(node));
        /* Iterator + first page setup */
    }

    for (;;) {
        /* Fetch next heap page in TID order */
        tup = table_scan_bitmap_next_tuple(node->ss.ss_currentScanDesc,
                                           &recheck, ...);
        if (!tup) {
            /* Page exhausted; advance to next bitmap page */
            if (!table_scan_bitmap_next_block(...)) break;
            continue;
        }

        /* If page was lossy OR index couldn't fully filter,
           reapply the qual at the heap level */
        if (recheck) {
            ExprContext_GetTupleSlot(econtext) = slot;
            if (!ExecQual(node->bitmapqualorig, econtext))
                continue;
        }

        return slot;
    }
    return NULL;
}
```

(abstracted)

## Why "in physical order"

[from-comment `nodeBitmapHeapscan.c` header]

The TIDBitmap is consumed in **block-number order**.
Combined with the table AM's `bitmap_next_block` —
typically a `prefetch + read-and-pin` sequence — this turns
what would have been per-tuple random IO into largely
sequential scan, modulo gaps.

Modern PG also uses the **read stream** (`read_stream.h`) to
queue up future block reads in parallel with current-block
processing. See `read-stream-prefetch` companion.

## The `recheck` flag and lossy pages

```c
bool recheck;
table_scan_bitmap_next_tuple(scan, tbmres, &recheck, slot);
```

`recheck` is set by the table AM when:
- The bitmap page is **lossy** (no per-tuple bits).
- The index returned **possibly-qualifying** TIDs that
  must be re-checked against the actual tuple (e.g.,
  index predicate ≠ heap predicate, GiST/SP-GiST lossy
  return).

When set, the executor re-runs `bitmapqualorig` (the
original WHERE qual) over the heap tuple.

## VACUUM + concurrent updates

[from-comment in source]

Between the index scan (which captured TIDs) and the heap
scan (which fetches them), the tuples may have been
HOT-updated or vacuumed. The heap fetch follows the chain;
the recheck handles the case where the visible tuple no
longer satisfies the predicate.

## Parallel bitmap heap scan

Multiple workers share the TIDBitmap (built by the leader)
and divide pages among themselves via a shared iterator.
See `nodeBitmapHeapscan.c` parallel path; each worker
fetches its share, applies recheck independently, emits
tuples through the Gather node.

## Common review-time concerns

- **`bitmapqualorig` must be the full original qual** —
  used on recheck.
- **The TIDBitmap consumes `work_mem`** — lossy fallback
  when full.
- **Page-order iteration matters** for IO cost — DON'T
  re-shuffle.
- **`recheck` is set per-page or per-tuple** — branch on it.
- **Parallel bitmap scan needs shared iterator state** —
  not just shared bitmap.
- **HOT-chain follow** is the AM's responsibility on
  fetch; the bitmap doesn't track HOT.

## Invariants

- **[INV-1]** Bitmap is built first (MultiExecProcNode),
  then iterated.
- **[INV-2]** TIDs consumed in block-number order.
- **[INV-3]** Lossy pages or index-recheck → reapply
  full qual.
- **[INV-4]** Parallel scan partitions pages, not tuples.
- **[INV-5]** TIDBitmap obeys `work_mem`; lossy fallback
  preserves correctness.

## Useful greps

- The main flow:
  `grep -n 'BitmapHeapNext\|BitmapHeapInitializeWorker' source/src/backend/executor/nodeBitmapHeapscan.c | head -10`
- TIDBitmap API:
  `grep -n 'tbm_create\|tbm_add_tuples\|tbm_iterate' source/src/backend/nodes/tidbitmap.c | head -10`
- AM hooks:
  `grep -n 'bitmap_next_block\|bitmap_next_tuple' source/src/include/access/tableam.h | head -10`

## Cross-references

- `knowledge/idioms/index-only-scan-vm-check.md` —
  different scan flavor (uses VM, not bitmap).
- `knowledge/idioms/read-stream-prefetch.md` — IO
  prefetching used by bitmap heap.
- `knowledge/data-structures/tupletableslot.md` — output
  slot.
- `knowledge/idioms/expression-evaluator-flow.md` —
  bitmapqualorig is evaluated via ExprState.
- `knowledge/subsystems/executor.md` — executor overview.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/executor/nodeBitmapHeapscan.c` —
  full source.
- `source/src/backend/nodes/tidbitmap.c` — TIDBitmap
  implementation.
