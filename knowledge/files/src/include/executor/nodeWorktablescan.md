# `executor/nodeWorktablescan.h` — Recursive CTE worktable scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeWorktablescan.h`)

## Role
Declares entry points for `WorkTableScan` — appears inside the recursive term of a `WITH RECURSIVE` query and reads the previous iteration's results from the working tuplestore managed by the enclosing `RecursiveUnion`.

## Public API
- `ExecInitWorkTableScan(WorkTableScan *, EState *, int eflags)` — nodeWorktablescan.h:19
- `ExecReScanWorkTableScan(WorkTableScanState *)` — nodeWorktablescan.h:20

## Notes
No `ExecEnd*` — tuplestore is owned by the driving `RecursiveUnion`.

## Cross-refs
- Plan node: `WorkTableScan` in `nodes/plannodes.h`
- State node: `WorkTableScanState` in `nodes/execnodes.h`
- Driver: `executor/nodeRecursiveunion.h`
- `.c` impl: `source/src/backend/executor/nodeWorktablescan.c`
