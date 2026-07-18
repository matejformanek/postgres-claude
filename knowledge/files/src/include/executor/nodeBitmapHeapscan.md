# `executor/nodeBitmapHeapscan.h` — bitmap heap-scan consumer declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeBitmapHeapscan.h`)

## Role
Declares executor entry points for `BitmapHeapScan` — consumes a TID bitmap (built by underlying `BitmapIndexScan` + `BitmapAnd`/`Or`) and fetches qualifying heap tuples in physical order, honoring lossy bitmap pages by re-checking quals. Parallel-aware with full DSM/instrumentation split.

## Public API
- `ExecInitBitmapHeapScan(BitmapHeapScan *, EState *, int eflags)` — nodeBitmapHeapscan.h:20
- `ExecEndBitmapHeapScan` / `ExecReScanBitmapHeapScan` — nodeBitmapHeapscan.h:21-22
- Parallel scaffolding (DSM init/re-init/worker): `ExecBitmapHeapEstimate` / `…InitializeDSM` / `…ReInitializeDSM` / `…InitializeWorker` — nodeBitmapHeapscan.h:23-30
- Instrumentation split (separate estimate/init/retrieve so per-worker accounting survives): `…InstrumentEstimate` / `…InstrumentInitDSM` / `…InstrumentInitWorker` / `…RetrieveInstrumentation` — nodeBitmapHeapscan.h:31-37

## Notes
The dual-track DSM init (regular state + instrumentation) is unusual versus most parallel-aware nodes which fold instrumentation in. Pattern is shared by `nodeSeqscan.h` and `nodeIndexonlyscan.h`.

## Cross-refs
- Plan node: `BitmapHeapScan` in `nodes/plannodes.h`
- State node: `BitmapHeapScanState` in `nodes/execnodes.h`
- Producers: `executor/nodeBitmapIndexscan.h`, `executor/nodeBitmapAnd.h`, `executor/nodeBitmapOr.h`
- TID bitmap impl: `nodes/tidbitmap.h`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
