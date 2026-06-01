# planagg.c — MIN/MAX → indexscan ORDER BY ... LIMIT 1

- **Source:** `source/src/backend/optimizer/plan/planagg.c` (518 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

Recognize MIN(col) / MAX(col) aggregate queries and rewrite them as
`SELECT col FROM tab WHERE col IS NOT NULL AND <quals> ORDER BY col
ASC/DESC LIMIT 1`, which can use a btree index when available. Generates
one subquery per MIN/MAX, then a MinMaxAggPath that wires them up.
[from-comment:5-18]

## 2. Entry point

`void preprocess_minmax_aggregates(PlannerInfo *root)` (line 73). Called
by `grouping_planner()` *just before* `query_planner()` so that the
subquery state can be cloned from the parent. `preprocess_aggrefs()`
must have run first (provides `root->agginfos`). [from-comment:66-72]

## 3. Eligibility gates

- `parse->hasAggs` (else nothing to do) [verified:88]
- No GROUP BY, no GROUPING SETS >1, no window funcs [verified:101]
- No CTEs [verified:110]
- Exactly one table reference (may be buried through FromExpr nesting; can
  be an inheritance parent or flattened UNION-ALL subquery via `rte->inh`)
  [verified:114-138]
- Every aggregate must be MIN or MAX (`can_minmax_aggs`) — gives up
  entirely otherwise [verified:144-146]
- Each MIN/MAX must produce a usable indexscan path
  (`build_minmax_path`) — partial-success gives up [verified:154-…,
  from-comment:148-153]

## 4. Mechanism

For each `MinMaxAggInfo`, fetches the ordering operator's equality op
(`get_equality_op_for_ordering_op`), then clones planner state and runs
`query_planner` on a tweaked parse tree. Result is wrapped in a
`MinMaxAggPath` added to `(UPPERREL_GROUP_AGG, NULL)`. [verified-by-code]

## 5. Surprising

- All-or-nothing: cannot mix optimized + scan aggregates because the
  unoptimized one would force a full table scan anyway. [from-comment:151-153]
- The single-table restriction means a join with MIN/MAX cannot use this
  optimization even if the indexed column is from one side. [from-comment:114-117]

## 6. Tags
`[verified-by-code]` ×6, `[from-comment]` ×4
