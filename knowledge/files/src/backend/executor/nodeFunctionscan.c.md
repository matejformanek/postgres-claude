# nodeFunctionscan.c

- **Source:** `source/src/backend/executor/nodeFunctionscan.c` (≈530 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Scans a `FROM`-clause function call (set-returning or composite-returning).
Supports `ROWS FROM (f(), g(), h())` (multiple functions zipped column-wise)
and `WITH ORDINALITY` (synthetic last column of row numbers).

## Mechanics

- Init: build a `FunctionScanPerFuncState` per function entry. Each holds
  a `SetExprState` (built via execSRF.c's `ExecInitTableFunctionResult`),
  a target TupleDesc, and a position cursor.
- First call: invoke `ExecMakeTableFunctionResult` on each function to
  drain it fully into a per-function Tuplestorestate (Materialize mode).
- Per subsequent call: read one row from each function's tuplestore;
  combine columns; possibly append ordinality counter.

## ROWS FROM zipping

When functions return different counts, the shorter ones produce NULLs
once exhausted; output length = max() of cardinalities.

## Tags

- [verified-by-code] per-function tuplestore + zipping.
- [from-comment] interface list at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
