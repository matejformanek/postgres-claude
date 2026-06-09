# `executor/nodeSetOp.h` — set-operator (INTERSECT / EXCEPT) declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeSetOp.h`)

## Role
Declares entry points for `SetOp` — implements `INTERSECT`, `INTERSECT ALL`, `EXCEPT`, `EXCEPT ALL`. Two strategies: sorted (read sorted child) or hashed (build hash table over one side). `UNION` itself flows through `Append` + `Unique`, not here.

## Public API
- `ExecInitSetOp(SetOp *, EState *, int eflags)` — nodeSetOp.h:19
- `ExecEndSetOp(SetOpState *)` — nodeSetOp.h:20
- `ExecReScanSetOp(SetOpState *)` — nodeSetOp.h:21
- `EstimateSetOpHashTableSpace(double nentries, Size tupleWidth)` — nodeSetOp.h:23 (planner-side cost helper for the hashed strategy)

## Cross-refs
- Plan node: `SetOp` in `nodes/plannodes.h`
- State node: `SetOpState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeSetOp.c`
- Related: `executor/nodeUnique.h` (UNION dedup)
