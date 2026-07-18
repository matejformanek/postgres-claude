# `executor/nodeSubqueryscan.h` — Subquery range-table scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeSubqueryscan.h`)

## Role
Declares entry points for `SubqueryScan` — wraps a sub-`PlannedStmt` that appears in the range table (e.g. `FROM (SELECT … FROM t) sub`). Pure pass-through of the sub-plan's output; exists mostly so the range-table-index machinery has a node to bind.

## Public API
- `ExecInitSubqueryScan(SubqueryScan *, EState *, int eflags)` — nodeSubqueryscan.h:19
- `ExecEndSubqueryScan(SubqueryScanState *)` — nodeSubqueryscan.h:20
- `ExecReScanSubqueryScan(SubqueryScanState *)` — nodeSubqueryscan.h:21

## Cross-refs
- Plan node: `SubqueryScan` in `nodes/plannodes.h`
- State node: `SubqueryScanState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeSubqueryscan.c`
- Related: `executor/nodeSubplan.h` (uncorrelated/correlated sub-SELECTs as expressions)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
