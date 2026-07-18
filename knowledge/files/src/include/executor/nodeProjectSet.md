# `executor/nodeProjectSet.h` — ProjectSet declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeProjectSet.h`)

## Role
Declares entry points for `ProjectSet` — evaluates a target list containing set-returning functions in the SELECT list (`SELECT generate_series(1,3), x FROM t`). Expands each input row into N output rows by ValuePerCall, advancing all SRFs together.

## Public API
- `ExecInitProjectSet(ProjectSet *, EState *, int eflags)` — nodeProjectSet.h:19
- `ExecEndProjectSet(ProjectSetState *)` — nodeProjectSet.h:20
- `ExecReScanProjectSet(ProjectSetState *)` — nodeProjectSet.h:21

## Cross-refs
- Plan node: `ProjectSet` in `nodes/plannodes.h`
- State node: `ProjectSetState` in `nodes/execnodes.h`
- SRF protocol: `funcapi.h` (`SRF_*` macros, `ExprMultipleResult`)
- `.c` impl: `source/src/backend/executor/nodeProjectSet.c`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
