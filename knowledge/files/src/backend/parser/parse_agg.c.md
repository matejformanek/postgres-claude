# parse_agg.c

- **Source:** `source/src/backend/parser/parse_agg.c` (2410 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Two responsibilities:

1. **Validate and finish aggregate/window-function calls** that the
   expression transformer routed here (called from
   `parse_func.c:ParseFuncOrColumn`).
2. **Run the post-build aggregate / GROUP BY sanity pass** over the
   finished SELECT: enforce that all non-aggregated columns are in
   GROUP BY (or in a grouping set), validate ordered-set aggs, check
   that aggregate / window-func usage is appropriate to the surrounding
   `ParseExprKind`.

## Key entries

- `transformAggregateCall` — wrap `Aggref` with FILTER, ORDER BY (inside
  the agg), DISTINCT, ordered-set / hypothetical-set bookkeeping, set
  `Query.hasAggs = true`.
- `transformWindowFuncCall` — analogous for `WindowFunc`; sets
  `Query.hasWindowFuncs = true`; resolves the named window definition.
- `parseCheckAggregates(pstate, qry)` — the post-pass that catches
  `SELECT a, sum(b) FROM t` without `GROUP BY a`. Runs from
  `transformSelectStmt` after the whole tree is built.
- `check_ungrouped_columns_walker` — recursive enforcement helper.
- `expand_grouping_sets` — turn the user's GROUPING SETS / ROLLUP / CUBE
  spec into the canonical list-of-grouping-sets form the planner expects.

## Where aggregates may appear

`check_agglevels_and_constraints` keys off `ParseExprKind`. Aggs are
forbidden in WHERE, JOIN ON, GROUP BY of their own query level, CHECK
constraints, etc. — the table of `errkind`/`err_already_in` cases is the
spec compliance matrix.

## Caveats

- An aggregate can legally reference outer-query columns (a "level-up
  aggregate"); `min_varlevel` accounting in `Aggref.agglevelsup` is how
  the planner knows.
- `Query.groupingSets` is non-NIL only when the user wrote GROUPING
  SETS/ROLLUP/CUBE; otherwise `Query.groupClause` carries plain GROUP BY.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
- [idioms/aggregate-grouping-sets.md](../../../../idioms/aggregate-grouping-sets.md)

