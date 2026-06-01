# functioncmds.c

- **Source path:** `source/src/backend/commands/functioncmds.c`
- **Lines:** 2431
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines for CREATE and DROP FUNCTION commands and CREATE and DROP CAST commands." [from-comment, functioncmds.c:3-5] Also handles CREATE PROCEDURE, CREATE TRANSFORM, ALTER FUNCTION / PROCEDURE / ROUTINE, and CREATE OPERATOR FAMILY.

## Public surface

- `CreateFunction` — main entry. Validates argument list, return type, language (PL/pgSQL etc.), volatility, parallel safety, set-returning flag; calls `ProcedureCreate` (in catalog/pg_proc.c) which writes pg_proc + pg_proc_lang link rows.
- `AlterFunction` — change volatility, strictness, cost, rows, parallel safety, leakproof, search_path GUC, security definer/invoker, etc. Many of these matter for the planner (volatility for inlining; parallel safety for parallel-plan eligibility) so AlterFunction invalidates the plan cache.
- `ExecuteDoStmt` — DO blocks; lookups the language's `inline_handler` and invokes it.
- `CallStmtResultDesc` / `ExecuteCallStmt` — CALL of a procedure; procedures can manage transactions (COMMIT/ROLLBACK inside), so CALL has special semantics around transaction boundaries.
- `CreateCast`, `DropCastById`, `AlterCast` — casts are pg_cast rows mapping (source type, target type, function) with castcontext = EXPLICIT/ASSIGNMENT/IMPLICIT.
- `CreateTransform` — for PL languages: how to convert a SQL type to/from the host language's native type.

## Procedure transaction control

A procedure called via `CALL` can issue COMMIT or ROLLBACK, which ends the calling transaction. The CALL infrastructure runs the procedure in an "atomic = false" context that PL/pgSQL detects and translates into actual SPI transaction control. See `ExecuteCallStmt` and PL/pgSQL's `_SPI_commit`/`_SPI_rollback`.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=1`
