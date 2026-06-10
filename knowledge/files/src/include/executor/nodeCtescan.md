# `executor/nodeCtescan.h` — CTE scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeCtescan.h`)

## Role
Declares entry points for `CteScan` — reads from a tuplestore materialized by a non-recursive WITH-CTE's `RecursiveUnion` / plain producer. Each `CteScan` referencing the same CTE shares one tuplestore.

## Public API
- `ExecInitCteScan(CteScan *, EState *, int eflags)` — nodeCtescan.h:19
- `ExecEndCteScan(CteScanState *)` — nodeCtescan.h:20
- `ExecReScanCteScan(CteScanState *)` — nodeCtescan.h:21

## Cross-refs
- Plan node: `CteScan` in `nodes/plannodes.h`
- State node: `CteScanState` in `nodes/execnodes.h`
- Producer: `executor/nodeRecursiveunion.h` (recursive case)
- `.c` impl: `source/src/backend/executor/nodeCtescan.c`
- Tuplestore: `utils/tuplestore.h`
