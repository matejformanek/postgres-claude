# `executor/nodeValuesscan.h` — VALUES list scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeValuesscan.h`)

## Role
Declares entry points for `ValuesScan` — produces rows from a `VALUES (...), (...), …` literal list. Lightweight; row exprs evaluated per row at scan time, allowing parameter references.

## Public API
- `ExecInitValuesScan(ValuesScan *, EState *, int eflags)` — nodeValuesscan.h:19
- `ExecReScanValuesScan(ValuesScanState *)` — nodeValuesscan.h:20

## Notes
No `ExecEnd*` decl — cleanup folds into per-row expression context reset.

## Cross-refs
- Plan node: `ValuesScan` in `nodes/plannodes.h`
- State node: `ValuesScanState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeValuesscan.c`
