# optimizer.h — external planner API

- **Source:** 220 lines · **Last verified commit:** `ef6a95c7c64`

## Role

The *only* optimizer header non-planner code is supposed to include.
Defines the public API to invoke the planner and to ask common
expression-level questions. FDW planning code is the documented exception
that's allowed to reach deeper. [from-comment:6-13]

## Surface (highlights)

- `PlannedStmt *planner(Query *parse, const char *query_string, int cursorOptions, ParamListInfo boundParams)` — the top entry hook.
- `Expr *eval_const_expressions(PlannerInfo *root, Node *node)`.
- `Node *estimate_expression_value(...)`.
- Expression-classification probes: `contain_*`, `is_parallel_safe`,
  `expression_returns_set_rows`, `get_relation_info_hook` typedef.
- `extern PGDLLIMPORT planner_hook_type planner_hook` — load-time plug.

## Tags
`[verified-by-code]` ×2, `[from-comment]` ×1

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new cost-model constant (and optional GUC)](../../../../scenarios/add-new-cost-model-knob.md)

<!-- scenarios:auto:end -->
