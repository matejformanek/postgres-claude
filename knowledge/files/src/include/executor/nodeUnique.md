# `executor/nodeUnique.h` — adjacent-duplicate elimination declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeUnique.h`)

## Role
Declares entry points for `Unique` — drops adjacent duplicate rows from a presorted child. Used to implement `SELECT DISTINCT` and `UNION` when the planner picks a sort-based path. Hash-based DISTINCT goes through `Agg` instead.

## Public API
- `ExecInitUnique(Unique *, EState *, int eflags)` — nodeUnique.h:19
- `ExecEndUnique(UniqueState *)` — nodeUnique.h:20
- `ExecReScanUnique(UniqueState *)` — nodeUnique.h:21

## Cross-refs
- Plan node: `Unique` in `nodes/plannodes.h`
- State node: `UniqueState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeUnique.c`
- Related (hash DISTINCT): `executor/nodeAgg.h`
