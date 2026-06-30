# nodeIndexonlyscan.c

- **Source:** `source/src/backend/executor/nodeIndexonlyscan.c` (≈900 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Like IndexScan but reads tuple values **directly from the index entry**,
avoiding heap I/O — provided the visibility map says the page is
all-visible. If not, falls back to fetching the heap tuple. Win is huge on
covering indexes for OLAP/aggregate queries. [from-comment INTERFACE ROUTINES]

## Visibility map check

For each index entry returned by `index_getnext_tid`:

1. Consult `VM_ALL_VISIBLE(rel, blkno, &vmbuffer)` on the heap block the
   TID points to.
2. If all-visible: synthesize a result row from the IndexTuple's
   `xs_itup`/`xs_itupdesc` values. Counters `ntuples_fetched_heap = 0`,
   `ntuples_fetched_index += 1`.
3. Else: call `table_index_fetch_tuple` to load the heap row, then project
   from there.

Counter ratios appear in EXPLAIN ANALYZE as "Heap Fetches: N".

## Constraints

The index AM must support `amcanreturn` (btree, hash, …). Per-column,
`amcanreturn` is queried so the planner only chooses index-only scan when
every output column is "indexable" — see `check_index_only` in
optimizer/path/indxpath.c.

## Parallel

Same DSM hooks as nodeIndexscan; the all-visible check is read-only and
needs no coordination.

## Tags

- [verified-by-code] visibility-map check + fallback path.
- [from-comment] INTERFACE list at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/index-only-scan-vm-check.md](../../../../idioms/index-only-scan-vm-check.md)

