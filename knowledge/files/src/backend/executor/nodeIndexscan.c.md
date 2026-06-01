# nodeIndexscan.c

- **Source:** `source/src/backend/executor/nodeIndexscan.c` (≈1750 lines, 54 KB)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Index-driven heap scan. Calls `index_beginscan`/`index_getnext_slot` from
`access/index/indexam.c` and uses ExecScan for qual/projection. Supports
ORDER BY index, ordered/parameterized scans, and parallel coordination.
[from-comment INTERFACE ROUTINES]

## Key callbacks

- `IndexNext` — the access method for ExecScan; calls index_getnext_slot,
  which delegates to the index AM (`amgettuple`). Returns next visible heap
  tuple via the table AM.
- `IndexNextWithReorder` — special variant for index-ordered scans where
  the index returns *approximate* ordering (e.g. kNN with GIST distance
  operators); the node maintains a reorder heap to deliver tuples in true
  ORDER BY order, rechecking actual distances against the latest heap row.
  Used by `<->` operator over GIST/SP-GiST.

## ScanKey setup

`ExecInitIndexScan` calls `ExecIndexBuildScanKeys` to translate the
planner-provided `indexqual` (List<OpExpr>) into runtime `ScanKey`s plus
optional `IndexRuntimeKeyInfo` for keys whose RHS is a Param/SubPlan/non-
constant (must be re-evaluated at each scan start). Order-by keys are
encoded as `ScanKey` array `orderByData[]` and passed via index AM's
`amrescan` so kNN AMs return rows in distance order.

## Parallel index scan

- `ExecIndexScanEstimate` — DSM space for the AM-specific shared scan state.
- `ExecIndexScanInitializeDSM` — calls `index_parallelscan_initialize` to
  let the AM lay out its shared state (btree's "block to scan next" cursor).
- Workers call `index_parallelrescan` then standard `index_getnext`, with
  the AM serializing access to the next-leaf-page cursor.

## ReScan handling

If runtime keys reference Params that changed, recompute their Datum values
into the ScanKey array. If only the snapshot or position changed, just
`index_rescan` with the same ScanKey.

## Tags

- [verified-by-code] entry-point names + kNN reorder mechanism.
- [from-comment] INTERFACE ROUTINES list at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
