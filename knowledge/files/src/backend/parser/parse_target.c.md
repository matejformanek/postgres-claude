# parse_target.c

- **Source:** `source/src/backend/parser/parse_target.c` (2048 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Build the **target list** — the list of `TargetEntry` nodes that becomes
`Query.targetList`. This serves SELECT output, INSERT/UPDATE assignment
sources, RETURNING expressions, and the implicit targets the parser
synthesizes for ORDER BY / GROUP BY items that don't already appear in the
output list.

## Key exported entry points

| Line | Symbol | Role |
|---|---|---|
| 73 | `transformTargetEntry` | wrap any expression into a `TargetEntry` with `resno` / `colname` / `resjunk` |
| 119 | `transformTargetList` | walk a `List<ResTarget>` from SELECT/RETURNING, calling `transformTargetEntry` and `*`-expansion |
| (further down) | `transformAssignedExpr` | the UPDATE/INSERT side: coerce RHS to target column type, handle subscripts/fields |
| (further down) | `markTargetListOrigins` | tag each TLE with the underlying `Var`'s (resorigtbl, resorigcol) for `\d`-style introspection |
| (further down) | `FigureColname` / `FigureColnameInternal` `:57` | derive an output column name when no AS clause was given |

## Star expansion

| Static | Used for |
|---|---|
| `ExpandColumnRefStar` `:47` | `t.*` |
| `ExpandAllTables` `:49` | bare `*` — all tables in the namespace |
| `ExpandIndirectionStar` `:50` | `(rowexpr).*` |
| `ExpandSingleTable` `:52` | helper for `t.*` once the table is resolved |
| `ExpandRowReference` `:55` | helper for composite-typed expressions |

These all use the column-list machinery in `parse_relation.c`
(`expandRelation`, `expandTupleDesc`).

## Subscripted / indirected assignment

`transformAssignmentSubscripts` `:35-46` builds the
`SubscriptingRef` + `FieldStore` tree for `UPDATE t SET arrcol[3] = ...` or
`UPDATE t SET composite.field = ...`. The recursion threads through
`indirection` and `next_indirection` so nested subscripts compose correctly.

## TargetEntry shape

Each TLE carries:

- `expr` — the resolved expression.
- `resno` — assigned via `pstate->p_next_resno++`. Counts from 1.
- `resname` — the output column name (`AS x` or `FigureColname` default).
- `resjunk` — true means "needed for sorting/grouping but not in the final
  projection". This is how ORDER BY of a non-output expression works.
- `resorigtbl` / `resorigcol` — set by `markTargetListOrigin` for SELECT
  output when the expression is a bare `Var`. Drives `pg_class.relname`
  echoing in `\d` output and `pg_stat_statements` column tracking.

## Caveats

- `resjunk = true` items are dropped by the executor's final projection but
  *not* by the planner — sort keys legitimately use them. Forget the flag
  and the planner happily produces them in the output.
- `transformAssignedExpr` is the source-of-truth for "is this assignment
  allowed?" — it rejects assignments to RTEs that aren't the result rel,
  rejects writes to system columns, and emits the "column X is of type Y
  but expression is of type Z" error after attempting
  `coerce_to_target_type` from `parse_coerce.c`.
- INSERT's target list is *re-shaped* in the rewriter
  (`rewriteTargetListIU` in `rewriteHandler.c`) to fill in missing columns
  with defaults / nulls — `parse_target.c` only builds what the SQL text
  spelled out.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
