# `executor/nodeRecursiveunion.h` — Recursive CTE driver declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeRecursiveunion.h`)

## Role
Declares entry points for `RecursiveUnion` — drives the WITH RECURSIVE iteration. Computes the non-recursive term once, then repeatedly executes the recursive term against the previous iteration's working table until empty. Pairs with `executor/nodeWorktablescan.h`.

## Public API
- `ExecInitRecursiveUnion(RecursiveUnion *, EState *, int eflags)` — nodeRecursiveunion.h:19
- `ExecEndRecursiveUnion(RecursiveUnionState *)` — nodeRecursiveunion.h:20
- `ExecReScanRecursiveUnion(RecursiveUnionState *)` — nodeRecursiveunion.h:21

## Cross-refs
- Plan node: `RecursiveUnion` in `nodes/plannodes.h`
- State node: `RecursiveUnionState` in `nodes/execnodes.h`
- Iteration source: `executor/nodeWorktablescan.h`
- `.c` impl: `source/src/backend/executor/nodeRecursiveunion.c`
