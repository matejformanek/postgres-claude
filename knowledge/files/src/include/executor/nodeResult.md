# `executor/nodeResult.h` — Result node declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeResult.h`)

## Role
Declares entry points for `Result` — emits a single row from constant or compile-time-evaluated expressions (`SELECT 1+2`), or projects on top of a child when target-list filtering is the only operation. Also serves as the "gating" node when a quals-against-constants check would short-circuit the whole plan.

## Public API
- `ExecInitResult(Result *, EState *, int eflags)` — nodeResult.h:19
- `ExecEndResult(ResultState *)` — nodeResult.h:20
- `ExecResultMarkPos` / `ExecResultRestrPos` — nodeResult.h:21-22
- `ExecReScanResult(ResultState *)` — nodeResult.h:23

## Cross-refs
- Plan node: `Result` in `nodes/plannodes.h`
- State node: `ResultState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeResult.c`
