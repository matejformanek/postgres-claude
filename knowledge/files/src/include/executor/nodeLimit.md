# `executor/nodeLimit.h` — LIMIT / OFFSET / FETCH FIRST declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeLimit.h`)

## Role
Declares entry points for `Limit` — implements `LIMIT n`, `OFFSET n`, `FETCH FIRST n {ROWS | PERCENT}` with `{ ONLY | WITH TIES }`. Also short-circuits child execution once the row count is satisfied.

## Public API
- `ExecInitLimit(Limit *, EState *, int eflags)` — nodeLimit.h:19
- `ExecEndLimit(LimitState *)` — nodeLimit.h:20
- `ExecReScanLimit(LimitState *)` — nodeLimit.h:21

## Cross-refs
- Plan node: `Limit` in `nodes/plannodes.h`
- State node: `LimitState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeLimit.c`
