# paramassign.c — PARAM_EXEC slot allocator

- **Source:** 761 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Three data structures managed (top comment lines 6-30)

| Structure | What it holds | Lifetime |
|---|---|---|
| `root->glob->paramExecTypes` | List of OIDs; index = PARAM_EXEC number | Permanent for whole plan (never compacted) |
| `root->plan_params` | `PlannerParamItem` of Vars/PHVs this level supplies to subqueries | Reset to NIL after each subquery |
| `root->curOuterParams` | `NestLoopParam` of Vars/PHVs an outer nestloop must pass down | Cleared when the NestLoop that supplies them is built |

## Public entries

`Param *assign_param_for_*` (120, 197, 224, 270, 317, 367, 413, 462) —
canonical Param-for-{Var, PHV, Aggref, GroupingFunc, ReturningExpr,
CachedExpr, Placeholder, …}. Each allocates a new PARAM_EXEC slot if
needed.

`process_subquery_nestloop_params` (526), `generate_subquery_params`
(621), `assign_special_exec_param` (726), `SS_assign_special_param` (753).

## Tags
`[verified-by-code]` ×2, `[from-comment]` ×3
