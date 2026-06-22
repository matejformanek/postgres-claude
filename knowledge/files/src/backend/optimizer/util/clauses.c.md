# clauses.c — expression-tree utilities + eval_const_expressions

- **Source:** 6348 lines · **Last verified commit:** `dc5116780846`
- **Depth:** read

## Purpose

A grab-bag of expression-tree analyses and transformations the planner
uses: contain-X checks, mutability/parallel-safety/leakproofness probes,
and — most importantly — `eval_const_expressions`, the constant-folding
+ function-inlining pass that runs at the start of `subquery_planner`.

## Public surface (predicates)

| Line | Function |
|---|---|
| 194 | `contain_agg_clause` |
| 231 | `contain_window_function` |
| 343 | `contain_subplans` |
| 383 | `contain_mutable_functions` |
| 503 | `contain_mutable_functions_after_planning` (post-eval_const_expressions) |
| 551 | `contain_volatile_functions` |
| 766 | `is_parallel_safe` |
| 1006 | `contain_nonstrict_functions` |
| 1194 | `contain_context_dependent_node` |
| 1278 | `contain_leaked_vars` |
| 2333 | `is_pseudo_constant_clause` |

`double expression_returns_set_rows(...)` (302) — estimate the row-set
cardinality of a SRF-bearing expression.

## Heavy hitters

- `eval_const_expressions(root, node)` — constant-folds, simplifies, and
  inlines SQL functions; also flattens AND/OR which `prepqual.c` used to
  do. Must walk every expression at least once, so it's expensive to
  skip. [from-comment in prepqual.c:14-18]
- `inline_function`, `inline_set_returning_function` — used by
  `preprocess_function_rtes` (prepjointree.c) and `eval_const_expressions`.
- `recheck_cheap_revalidation_needed` — used by partition pruning /
  RLS rechecking.

## Tags
`[verified-by-code]` ×6, `[from-comment]` ×1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
