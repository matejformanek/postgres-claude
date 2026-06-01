# parse_utilcmd.h

- **Source:** `source/src/include/parser/parse_utilcmd.h` (~45 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

API for utility-command parse analysis. Called from `commands/*.c` and
`tcop/utility.c` at execution time (not at original parse-analyze time —
see `parse_utilcmd.c`'s top comment for why).

## Exported entries

- `transformCreateStmt` — CREATE TABLE.
- `transformAlterTableStmt` — ALTER TABLE; returns extra `beforeStmts` /
  `afterStmts` to run around the main ALTER.
- `transformCreateSchemaStmt` — CREATE SCHEMA flattening.
- `transformIndexStmt` — CREATE INDEX.
- `transformRuleStmt` — CREATE RULE (action queries get parse-analyzed
  here with NEW/OLD pseudo-RTEs).
- `transformCreateTrigStmt` — CREATE TRIGGER WHEN clause.
- `transformPartitionBound` — partition bound expressions.
- `transformCreateStatsStmt` — CREATE STATISTICS expressions.
- `expandTableLikeClause` — used by both CREATE TABLE and ALTER TABLE for
  LIKE handling.
