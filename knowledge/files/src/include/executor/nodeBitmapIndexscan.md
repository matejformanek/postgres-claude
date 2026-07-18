# `executor/nodeBitmapIndexscan.h` — bitmap index-scan producer declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeBitmapIndexscan.h`)

## Role
Declares executor entry points for the `BitmapIndexScan` plan node — produces a TID bitmap from one index, to be combined by `BitmapAnd`/`BitmapOr` and consumed by `BitmapHeapScan`. Parallel-aware (workers share the bitmap via DSM).

## Public API
- `ExecInitBitmapIndexScan(BitmapIndexScan *, EState *, int eflags)` — nodeBitmapIndexscan.h:20
- `MultiExecBitmapIndexScan(BitmapIndexScanState *)` — nodeBitmapIndexscan.h:21 (emits bitmap, not slot)
- `ExecEndBitmapIndexScan(BitmapIndexScanState *)` — nodeBitmapIndexscan.h:22
- `ExecReScanBitmapIndexScan(BitmapIndexScanState *)` — nodeBitmapIndexscan.h:23
- Parallel: `ExecBitmapIndexScanEstimate` / `…InitializeDSM` / `…InitializeWorker` / `…RetrieveInstrumentation` — nodeBitmapIndexscan.h:24-28

## Cross-refs
- Plan node: `BitmapIndexScan` in `nodes/plannodes.h`
- State node: `BitmapIndexScanState` in `nodes/execnodes.h`
- Consumer: `executor/nodeBitmapHeapscan.h`
- Index AM bitmap path: `access/amapi.h` (`amgetbitmap`)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
