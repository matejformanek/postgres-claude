# execSRF.c

- **Source:** `source/src/backend/executor/execSRF.c` (983 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Two clients — `nodeFunctionscan` (FROM-clause function) and `nodeProjectSet`
(SRF in targetlist) — both need to call a set-returning function via the
`ReturnSetInfo` API. This file shares that code. [from-comment] `:5-9`

## Two return modes

The SRF API supports two modes (declared in `funcapi.h`):

- **ValuePerCall** — the function is re-entered for every row; it stores state
  in `fcinfo->flinfo->fn_extra`, signals "got a row" by setting
  `rsi->isDone = ExprMultipleResult`, "done" by `ExprEndResult`.
- **Materialize** — the function returns a fully-populated tuplestore in
  `rsi->setResult` plus a TupleDesc in `rsi->setDesc`; caller iterates.

execSRF handles both.

## Entry points

- `ExecMakeTableFunctionResult(setexpr, econtext, argContext, expectedDesc, randomAccess)` `:102`
  — used by FunctionScan. Returns a Tuplestorestate containing all rows.
  Internally either drains a ValuePerCall SRF into a freshly created
  tuplestore, or accepts the Materialize-mode tuplestore directly. Handles
  ordinality (`WITH ORDINALITY`), column expansion (`ROWS FROM (...)`).
- `ExecMakeFunctionResultSet(fcache, econtext, argContext, isNull, isDone)` `:499`
  — used by ProjectSet. Pulls **one row at a time** from the SRF;
  drives the per-call return-set protocol. Sets `*isDone` to indicate to
  ProjectSet whether more rows are coming for the current input row.

## Other helpers

- `init_sexpr(foid, collation, expr, parent, sexprCxt, allowSRF, needDescForSets)` `:698`
  — first-call setup: looks up the function, builds the `ReturnSetInfo`,
  decides whether the function will return a composite vs scalar.
- `ShutdownSetExpr(Datum arg)` `:813` — ExprContext callback that frees the
  SRF's tuplestore on rescan/shutdown.
- `ExecPrepareTuplestoreResult(sexpr, econtext, ...)` `:867` — when a
  function-RTE was already materialized in a tuplestore (e.g. via SQL
  function inlining), wrap it for consumption.

## Subtleties

- ProjectSet drives multiple SRFs in lockstep: it calls each, collects
  per-SRF isDone, and emits one combined output row per call until all
  SRFs report ExprEndResult; the LCM-of-cardinalities semantics. ProjectSet
  is where the deprecated "SRF in targetlist" semantics from pre-PG10 are
  emulated.
- `argContext` is a separate per-call MemoryContext for SRF arguments so
  argument evaluation doesn't leak into the SRF's per-call context.

## Tags

- [verified-by-code] entry points + the two-mode protocol.
- [from-comment] file purpose.
- [from-comment] ValuePerCall / Materialize semantics (funcapi.h).
