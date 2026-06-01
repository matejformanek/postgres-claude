# utility.c

- **Source:** `source/src/backend/tcop/utility.c` (3823 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + dispatch structure)

## Purpose

The **utility-statement dispatcher**. Every non-DML statement (DDL, COPY,
VACUUM, EXPLAIN, transaction control, REPACK, SET, SECURITY LABEL, CREATE
EXTENSION, …) lands here. `ProcessUtility` → `standard_ProcessUtility` does
a big `switch (nodeTag(parsetree))` and calls into the relevant
`commands/*.c` module. [from-comment] `:3-9`

## Two-tier split

- **`standard_ProcessUtility`** (`:548`) handles commands for which there is
  **no event-trigger support** (transaction control, SET, etc.). Done inline.
- **`ProcessUtilitySlow`** (`:1094`) handles commands that **do** have event-
  trigger support. Necessary split: the event-trigger cache may need refresh,
  which itself needs a transaction context that's not safe to assume during
  `START TRANSACTION`. [from-comment] `:533-545`

## Hook point

`ProcessUtility_hook` (`:519-526`) — extensions like pg_stat_statements wrap
this to see every utility statement. Default falls through to
`standard_ProcessUtility`.

## Read-only / parallel / recovery gates

- `CommandIsReadOnly(pstmt)` (`:96`) for DML PlannedStmts.
- `ClassifyUtilityCommandAsReadOnly(parsetree)` (`:130`) returns a bitmask:
  `COMMAND_OK_IN_READ_ONLY_TXN`, `COMMAND_OK_IN_PARALLEL_MODE`,
  `COMMAND_OK_IN_RECOVERY`. `:577-591` then calls the matching
  `PreventCommandIf*` helpers (`:409, :427, :446`).
- `CheckRestrictedOperation` (`:464`) — gates operations forbidden in
  security-restricted contexts.

## Other public helpers

| Line | Symbol | Role |
|---|---|---|
| 1971 | `ProcessUtilityForAlterTable` | re-entry from tablecmds for sub-statements |
| 2008 | `ExecDropStmt` | shared drop dispatch (object_type → drop func) |
| 2042 | `UtilityReturnsTuples` | does this stmt produce tuples? (EXPLAIN, FETCH, …) |
| 2101 | `UtilityTupleDescriptor` | matching TupleDesc |
| 2157 | `QueryReturnsTuples` | similar for a `Query` |
| 2199 | `UtilityContainsQuery` | does it have a nested `Query`? (for DECLARE CURSOR / CREATE TABLE AS / EXPLAIN) |
| 2236 | `AlterObjectTypeCommandTag` | tag for ALTER on a given object type |
| 2385 | `CreateCommandTag` | the central node-tag → `CommandTag` mapper |
| 3290 | `GetCommandLogLevel` | log level for a given parse tree |

## Routing table

The `switch (nodeTag(parsetree))` inside `standard_ProcessUtility` (`:597+`)
is the canonical map from `Stmt` node to handler. Examples:

- `T_TransactionStmt` → inline transaction-control handling.
- `T_VariableSetStmt`, `T_VariableShowStmt` → `commands/variable.c`.
- `T_VacuumStmt` → `commands/vacuum.c::ExecVacuum`.
- `T_CopyStmt` → `commands/copy.c::DoCopy`.
- `T_ExplainStmt` → `commands/explain.c::ExplainQuery`.
- `T_CreateStmt`, `T_AlterTableStmt`, etc. → `ProcessUtilitySlow`
  → `commands/tablecmds.c`.

## Interactions

Called from `tcop/pquery.c::PortalRunUtility` and `::PortalRunMulti`.
Calls every `commands/*` module. Header: `tcop/utility.h`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
