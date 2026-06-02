# parse_jsontable.c

- **Source:** `source/src/backend/parser/parse_jsontable.c` (541 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Parse analysis for `JSON_TABLE(context_item, path_expression COLUMNS (...))
[PASSING ...] [ON ERROR ...]`. Produces a `TableFunc` node (the
table-function RTE shape shared with XMLTABLE) whose `functype ==
JSTYPE_JSON_TABLE`.

## Entry

- `transformJsonTable(pstate, jt)` — called from
  `parse_clause.c:transformRangeTableFunc` when the FROM item is a
  `RangeTableFunc` of JSON_TABLE flavor.

## What it builds

The COLUMNS clause is parsed into:

- regular columns (`name type PATH ...`),
- formatted columns (`name type FORMAT JSON ...`),
- exists columns (`name EXISTS PATH ...`),
- ordinality columns,
- nested `NESTED PATH ... COLUMNS (...)` blocks (recursive).

Each column gets its path expression parse-analyzed (compiled to a
`JsonPath` constant via `transformJsonValueExpr` plumbing) and its
ON EMPTY / ON ERROR behaviors resolved.

## PASSING clause

`PASSING value AS name [, ...]` arguments are routed through
`transformJsonPassingArgs` (shared with the other JSON functions in
`parse_expr.c`) and stored as a parallel list on the `TableFunc`.

## Caveats

- JSON_TABLE is a function in FROM, so the result columns become a
  composite-typed RTE that callers can column-pick from. The TupleDesc is
  built from the COLUMNS clause, not from any catalog.
- Errors during evaluation can be suppressed via the ON ERROR clause —
  the parser stores the policy; the executor (`executor/execJsonExpr.c`)
  enforces it.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
