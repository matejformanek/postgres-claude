# Index-only scan + VM check — when the heap can be skipped

An **index-only scan** retrieves all needed values directly
from the index without visiting the heap — provided the
heap page is "all-visible" per the visibility map (VM). This
is the showcase optimization for covering indexes, but
correctness requires the VM check: if VM says
"all-visible," visibility is decidable without the heap; if
not, the heap must be consulted. The interplay between
index scan + VM check is the key to understanding when
index-only is faster than indexed-with-heap.

Anchors:
- `source/src/backend/executor/nodeIndexonlyscan.c` —
  implementation [verified-by-code]
- `knowledge/idioms/visibility-map-update.md` — companion;
  VM bit mechanics
- `knowledge/subsystems/contrib-pg_visibility.md` —
  diagnostics for VM state
- `knowledge/idioms/vacuum-skip-pages.md` — VACUUM sets the
  VM bits this scan reads

## The 4-step flow

[verified-by-code `nodeIndexonlyscan.c:50-62`]

```c
static TupleTableSlot *
IndexOnlyNext(IndexOnlyScanState *node);
```

1. **Index scan** — find the next index tuple matching the
   scan keys.
2. **VM check** — fetch the VM byte for the heap page of
   this TID.
3. **If VM says all-visible**:
   - Construct the result tuple from the **index entry**
     (no heap visit).
   - Output the tuple.
4. **If VM says NOT all-visible**:
   - Fetch the actual heap tuple.
   - Check visibility (HeapTupleSatisfiesMVCC).
   - If visible, output; else skip.

The optimization is step 3 — skipping the heap visit. On a
well-VACUUMed table, the VAST majority of pages are
all-visible; step 3 dominates and the scan is fast.

## The VM byte read

```c
visibilitymap_get_status(scanRel, blkno, &vmbuffer)
```

Returns a 2-bit value:
- `VISIBILITYMAP_ALL_VISIBLE` — all tuples on page are
  visible to all transactions.
- `VISIBILITYMAP_ALL_FROZEN` — additionally, all tuples are
  beyond XID wraparound concerns.

For index-only scan, `ALL_VISIBLE` is sufficient (the
stronger `ALL_FROZEN` isn't required).

## The 32-bit slot

[verified-by-code `nodeIndexonlyscan.c:51-52`]

```c
static void
StoreIndexTuple(IndexOnlyScanState *node, TupleTableSlot *slot, ...);
```

When the VM check passes, `StoreIndexTuple` populates a
`VirtualTupleTableSlot` from the index tuple's payload
(`itup->t_data`). This skips the buffer-pinned heap
representation that ordinary IndexScan uses.

## When does it fail to apply?

The "index-only scan returns 0 rows" trap:

- **Stale VM bits.** Between the planner's index-only
  selection (which assumed mostly-all-visible) and runtime,
  the VM bits are reset by recent UPDATEs. The scan now
  visits the heap for most TIDs.
- **Index missing required columns.** The planner might
  have chosen index-only assuming the index covers the
  WHERE/projection; if it doesn't, the plan is wrong (rare
  but happens with INCLUDE columns).
- **Heap-only-tuples (HOT).** Chain-walking in the heap is
  required for HOT-updated rows; the index points at the
  chain root.

For the third case: if any HOT chain is encountered, the
index-only optimization must consult the heap to walk to
the live version. So very-update-heavy tables get less
benefit.

## The "covering index" pattern

```sql
CREATE INDEX ON orders (customer_id) INCLUDE (status, amount);
SELECT customer_id, status, amount FROM orders WHERE customer_id = 42;
```

The `INCLUDE` columns are stored in the index leaf but NOT
in the index search structure. The query above is
"covered" — all 3 columns are in the leaf — so index-only
scan can return tuples without heap visits (assuming
all-visible).

`INCLUDE` indexes are PG 11+'s answer to "covering index"
performance.

## Heap fetch counters

`pg_stat_user_indexes.idx_tup_read` vs
`pg_stat_user_tables.idx_tup_fetch`:

- **`idx_tup_read`** — count of index tuples examined.
- **`idx_tup_fetch`** — count of heap tuples fetched via
  index scan.

For a pure index-only scan with all-visible VM bits,
`idx_tup_fetch` stays low while `idx_tup_read` rises. The
ratio is the index-only effectiveness.

If `idx_tup_fetch / idx_tup_read` is close to 1 on what
should be an index-only query, VACUUM the table — the VM
bits are stale.

## ANALYZE statistics matter

The planner's cost estimator uses
`pg_stats.relfilenode_size` and an estimate of "fraction
of pages all-visible" (from `pg_class.relallvisible`). VACUUM
updates this column.

Without recent VACUUM:
- `relallvisible` is stale.
- Planner over-estimates index-only scan cost.
- It picks a worse plan.

`ANALYZE` updates this. Routine vacuum + analyze keeps the
estimate fresh.

## Parallel index-only scan

[verified-by-code `nodeIndexonlyscan.c:24-29`]

Index-only scans support parallel execution via the
standard `Estimate/InitializeDSM/InitializeWorker`
callback set. The VM check happens per-worker; coordination
is via the standard parallel-scan position counter.

## Common review-time concerns

- **VM bits reset on every UPDATE/DELETE** to the page.
  Hot UPDATE workloads = low index-only effectiveness.
- **VACUUM cadence matters** — between VACUUMs, the VM
  bits decay; periodic VACUUM is the index-only-keeper.
- **Index-only is per-tuple-decision** — partial savings
  even when only some pages are all-visible.
- **INCLUDE columns** are the modern "covering index"
  syntax; prefer over packing search columns.
- **`enable_indexonlyscan = off`** disables the
  optimization; useful for debugging plan choices.

## Invariants

- **[INV-1]** Index-only valid iff the index covers all
  needed columns AND the heap page is all-visible.
- **[INV-2]** The VM byte read is the per-tuple decision
  point.
- **[INV-3]** All-visible VM bit suffices; all-frozen
  isn't required.
- **[INV-4]** HOT chains require heap visit; reduces
  benefit on update-heavy tables.
- **[INV-5]** Planner's cost estimate uses
  `pg_class.relallvisible`; VACUUM updates it.

## Useful greps

- The main loop:
  `grep -n 'IndexOnlyNext\|visibilitymap_get_status' source/src/backend/executor/nodeIndexonlyscan.c | head -10`
- The index-tuple construction:
  `grep -n 'StoreIndexTuple\|index_form_tuple' source/src/backend/executor/nodeIndexonlyscan.c | head -10`
- The cost model:
  `grep -RIn 'relallvisible\|enable_indexonlyscan' source/src/backend/optimizer | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/nodeIndexonlyscan.c`](../files/src/backend/executor/nodeIndexonlyscan.c.md) | — | implementation |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/visibility-map-update.md` — VM bits
  this scan reads.
- `knowledge/idioms/vacuum-skip-pages.md` — VACUUM
  sets the VM bits.
- `knowledge/subsystems/contrib-pg_visibility.md` —
  diagnostics for VM state.
- `knowledge/idioms/heaptuple-update-chain.md` — HOT
  chains that prevent pure index-only.
- `.claude/skills/executor-and-planner/SKILL.md` —
  planner cost model.
- `.claude/skills/access-method-apis/SKILL.md` — index
  AM contracts.
- `source/src/backend/executor/nodeIndexonlyscan.c` —
  implementation.
