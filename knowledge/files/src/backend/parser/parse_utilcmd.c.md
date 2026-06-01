# parse_utilcmd.c

- **Source:** `source/src/backend/parser/parse_utilcmd.c` (5222 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top + entry-point survey)

## Purpose

Parse analysis for **utility commands** (DDL). Runs at **execution time**,
not at original parse-analyze time, because utility-command parse analysis
depends on catalog state and the parser can't reliably hold locks across
plan-cache boundaries. [from-comment] `:6-12`

The original `parse_analyze_*` path simply wraps the raw `CreateStmt` /
`AlterTableStmt` / etc. in a `Query{commandType=CMD_UTILITY}`; later,
`ProcessUtility` calls the matching `transform*Stmt` here.

## Entry points (selection)

| Symbol | Used by |
|---|---|
| `transformCreateStmt(stmt, queryString)` | CREATE TABLE — expands LIKE clauses, partitioned-table options, generated columns, table-level constraints |
| `transformAlterTableStmt(relid, stmt, qstr, &beforeStmts, &afterStmts)` | ALTER TABLE — produces auxiliary statements (created indexes for ADD PRIMARY KEY, etc.) to run before/after the main ALTER |
| `transformCreateSchemaStmt` | CREATE SCHEMA — flattens contained CREATE statements |
| `transformIndexStmt` | CREATE INDEX — resolves expressions / opclasses |
| `transformRuleStmt` | CREATE RULE — runs full parse analysis on the rule's action queries |
| `transformCreateTrigStmt` | CREATE TRIGGER — resolves WHEN condition |
| `transformPartitionBound` | partition bound expressions |
| `transformCreateStatsStmt` | CREATE STATISTICS |

## Why DDL needs deferred analysis

Three reasons spelled out in the header `:6-12`:

1. **Plan caching:** a cached DDL Query against a since-altered catalog
   would silently produce wrong results.
2. **Lock holding:** parse analysis can't hold locks across the gap to
   execution.
3. **Plan-validity rechecks:** utility commands have no infrastructure for
   "the plan is still valid" checks like DML does.

Therefore the canonical lifecycle is:

```
raw_parser → analyze.c default branch (utility wrap)
           → plancache / portal stores the raw stmt
           → ProcessUtility runs
           → here: transformFooStmt produces a transformed stmt
           → executor or specific command implementation runs it
```

## Coupling

This file touches **every** catalog-affecting subsystem: `commands/`,
`catalog/`, `parser/parse_expr.c` for default-value expressions,
`parser/parse_relation.c` for the temporary RTE built to resolve column
references during expression analysis (e.g. for `GENERATED ALWAYS AS`),
`parser/parse_coerce.c` for type coercion of literal partition bounds,
etc.

## Caveats

- `transformAlterTableStmt` returns *three* lists (`beforeStmts`,
  `stmt->cmds` mutated in place, `afterStmts`). Skipping one in caller
  code breaks PRIMARY KEY/UNIQUE constraint creation.
- For partitioned tables, partition bound expressions are evaluated **at
  parse-analyze time here** (not deferred to execution) so that the
  bound is a constant value the catalog can store; this is one of the
  few cases where utility parse-analysis does real work.
- A common pattern when adding new DDL: add the raw stmt to gram.y,
  wrap-only in analyze.c (handled by the default branch), then add a
  `transformFooStmt` here that's called from
  `tcop/utility.c:ProcessUtility`.
