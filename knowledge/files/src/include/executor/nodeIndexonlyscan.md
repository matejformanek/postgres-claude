# `executor/nodeIndexonlyscan.h` — index-only scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeIndexonlyscan.h`)

## Role
Declares entry points for `IndexOnlyScan` — answers a query entirely from the index when the visibility map confirms heap tuples are all-visible (no heap fetch). Parallel-aware with full DSM + instrumentation split.

## Public API
- Lifecycle + mark/restore — nodeIndexonlyscan.h:20-24: `ExecInitIndexOnlyScan` / `ExecEndIndexOnlyScan` / `ExecIndexOnlyMarkPos` / `ExecIndexOnlyRestrPos` / `ExecReScanIndexOnlyScan`
- Parallel scan — nodeIndexonlyscan.h:27-34: `ExecIndexOnlyScanEstimate` / `…InitializeDSM` / `…ReInitializeDSM` / `…InitializeWorker`
- Instrument split — nodeIndexonlyscan.h:35-41: `…InstrumentEstimate` / `…InstrumentInitDSM` / `…InstrumentInitWorker` / `…RetrieveInstrumentation`

## Cross-refs
- Plan node: `IndexOnlyScan` in `nodes/plannodes.h`
- State node: `IndexOnlyScanState` in `nodes/execnodes.h`
- Sibling: `executor/nodeIndexscan.h`
- Visibility map: `access/visibilitymap.h`
- `.c` impl: `source/src/backend/executor/nodeIndexonlyscan.c`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
