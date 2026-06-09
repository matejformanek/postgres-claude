# `executor/nodeTidrangescan.h` — TID-range scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeTidrangescan.h`)

## Role
Declares entry points for `TidRangeScan` — answers queries of the form `WHERE ctid >= '(a,b)' AND ctid <= '(c,d)'` by scanning a contiguous block range. Parallel-aware with full DSM + instrumentation split. Introduced PG 14.

## Public API
- Lifecycle — nodeTidrangescan.h:20-23: `ExecInitTidRangeScan` / `ExecEndTidRangeScan` / `ExecReScanTidRangeScan`
- Parallel scan — nodeTidrangescan.h:26-29: `ExecTidRangeScanEstimate` / `…InitializeDSM` / `…ReInitializeDSM` / `…InitializeWorker`
- Instrument split — nodeTidrangescan.h:32-38: `…InstrumentEstimate` / `…InstrumentInitDSM` / `…InstrumentInitWorker` / `…RetrieveInstrumentation`

## Cross-refs
- Plan node: `TidRangeScan` in `nodes/plannodes.h`
- State node: `TidRangeScanState` in `nodes/execnodes.h`
- Sibling (point-list): `executor/nodeTidscan.h`
- `.c` impl: `source/src/backend/executor/nodeTidrangescan.c`
