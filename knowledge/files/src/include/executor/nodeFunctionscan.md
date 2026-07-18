# `executor/nodeFunctionscan.h` — SRF-in-FROM declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeFunctionscan.h`)

## Role
Declares entry points for `FunctionScan` — the executor node for set-returning functions in the `FROM` clause (`SELECT … FROM unnest(arr)`, `FROM generate_series(...)`, `FROM contrib_function(...)`). Materializes the function's output into a tuplestore (or uses value-per-call for single-function plans).

## Public API
- `ExecInitFunctionScan(FunctionScan *, EState *, int eflags)` — nodeFunctionscan.h:19
- `ExecEndFunctionScan(FunctionScanState *)` — nodeFunctionscan.h:20
- `ExecReScanFunctionScan(FunctionScanState *)` — nodeFunctionscan.h:21

## Phase D
User-function trust surface. `FROM function()` invokes any callable SRF, including SQL-language and PL/* functions. Cross-link A14 `tablefunc.connectby_text` — historically vulnerable to SQL injection through string interpolation of column/relation names. Anything reachable from `FROM` runs in the calling backend's role unless `SECURITY DEFINER`.

## Cross-refs
- Plan node: `FunctionScan` in `nodes/plannodes.h`
- State node: `FunctionScanState` in `nodes/execnodes.h`
- SRF protocol: `funcapi.h` (`ReturnSetInfo`, `SRF_RETURN_NEXT`)
- `.c` impl: `source/src/backend/executor/nodeFunctionscan.c`
- Idiom doc: `knowledge/idioms/fmgr-and-spi.md` (SRF section)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
