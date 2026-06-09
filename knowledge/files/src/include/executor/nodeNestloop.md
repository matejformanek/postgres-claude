# `executor/nodeNestloop.h` — nested-loop join declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeNestloop.h`)

## Role
Declares entry points for `NestLoop` — the canonical join operator. Drives the inner subplan once per outer tuple, passing outer values as parameters when the inner is a parameterized scan (typical with index paths and `Memoize`).

## Public API
- `ExecInitNestLoop(NestLoop *, EState *, int eflags)` — nodeNestloop.h:19
- `ExecEndNestLoop(NestLoopState *)` — nodeNestloop.h:20
- `ExecReScanNestLoop(NestLoopState *)` — nodeNestloop.h:21

## Cross-refs
- Plan node: `NestLoop`, `NestLoopParam` in `nodes/plannodes.h`
- State node: `NestLoopState` in `nodes/execnodes.h`
- Siblings: `executor/nodeHashjoin.h`, `executor/nodeMergejoin.h`
- Common parameterized inner: `executor/nodeMemoize.h`
- `.c` impl: `source/src/backend/executor/nodeNestloop.c`
