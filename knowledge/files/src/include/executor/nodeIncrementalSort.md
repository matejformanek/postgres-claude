# `executor/nodeIncrementalSort.h` — incremental sort declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeIncrementalSort.h`)

## Role
Declares entry points for `IncrementalSort` — used when input is already sorted on a prefix of the requested keys; sorts each "group" of equal-prefix rows separately, dramatically reducing peak memory vs full `Sort`. Parallel-aware for instrumentation.

## Public API
- Lifecycle — nodeIncrementalSort.h:18-20: `ExecInitIncrementalSort` / `ExecEndIncrementalSort` / `ExecReScanIncrementalSort`
- Parallel instrumentation — nodeIncrementalSort.h:23-26: `ExecIncrementalSortEstimate` / `…InitializeDSM` / `…InitializeWorker` / `…RetrieveInstrumentation`

## Cross-refs
- Plan node: `IncrementalSort` in `nodes/plannodes.h`
- State node: `IncrementalSortState` in `nodes/execnodes.h`
- Sibling (full sort): `executor/nodeSort.h`
- `.c` impl: `source/src/backend/executor/nodeIncrementalSort.c`
- Sort engine: `utils/tuplesort.h`
