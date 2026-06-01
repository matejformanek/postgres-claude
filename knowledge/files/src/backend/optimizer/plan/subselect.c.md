# subselect.c — SubLink → SubPlan / InitPlan expansion + CTE handling

- **Source:** `source/src/backend/optimizer/plan/subselect.c` (3380 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read
- **Historical README:** `source/src/backend/optimizer/plan/README` (Vadim's
  1998 message — still describes the design)

## 1. Purpose

Plans SubLinks (subquery expressions in WHERE / SELECT lists / etc.) and
CTEs. Does *not* handle sub-SELECT-in-FROM (those are RTE_SUBQUERY and
go through `subquery_planner` recursion in planner.c). [from-comment:6-8]

## 2. Mental model (from the README)

- A correlated subquery's upper-level Vars get rewritten to
  `PARAM_EXEC` Params, with the lookup table held in PlannerInfo.
- The subquery's plan becomes a *SubPlan* attached to the parent's
  expression tree, OR an *InitPlan* (executed once, result stashed in a
  PARAM_EXEC slot) when uncorrelated or convertible to one.
- ALL/ANY/EXISTS SubLinks get specialized SubPlan subtypes
  (`ANY_SUBLINK`, `ALL_SUBLINK`, `EXISTS_SUBLINK`, …) processed by
  nodeSubplan.c at execution time.

## 3. Key entry points

| Line | Function | Role |
|---|---|---|
| 883 | `SS_process_ctes` | Per CTE: ignore (unreferenced SELECT), inline, or make an initplan; fills `root->cte_plan_ids` parallel to `parse->cteList` (-1 = no initplan) [from-comment:875-881] |
| 2151 | `SS_replace_correlation_vars` | Walk expr replacing upper-level Vars/PHVs/Aggrefs with Params; subtle handling of SubLinks inside uplevel PHV/Aggref args (deferred until after expression is copied) [from-comment:2143-2150] |
| 2206 | `SS_process_sublinks(expr, isQual)` | The main SubLink→SubPlan expander; `isQual=true` allows folding FALSE/UNKNOWN at top level [from-comment:2200-2204] |
| 2364 | `SS_identify_outer_params` | Compute paramIds the outer levels will expose to *this* level and descendants; stored in `root->outer_params` because upper plan_params lists are transient [from-comment:2356-2363] |
| 2428 | `SS_charge_for_initplans` | Add initplan startup+total costs to every Path of `final_rel`; mark Paths parallel-unsafe if any initplan is [from-comment:2420-2426] |
| 2492 | `SS_compute_initplan_cost` | Helper used by SS_charge_for_initplans and by re-attachment of initplans to other nodes |
| 2533 | `SS_attach_initplans` | Stick initplans on the topmost plan node; does NOT touch cost/parallel flags (assumed already done) [from-comment:2525-2532] |
| 2548 | `SS_finalize_plan` | Recursively compute `extParam`/`allParam` per Plan node; also processes `RangeTblFunction.funcparams`; assumes initplans/subplans already finalized [from-comment:2540-2547] |
| 3293 | `SS_make_initplan_output_param` | PARAM_EXEC slot for a scalar initplan result |
| 3309 | `SS_make_initplan_from_plan` | Wrap an existing Plan as an EXPR_SUBLINK SubPlan + push to parent's `init_plans` |

## 4. Subtle / surprising

- **SubLinks inside uplevel-PHV/Aggref args are not touched at the
  intermediate level**; processing is deferred until the expression is
  copied to the parent. [from-comment:2140-2150]
- **outer_params is precomputed** because by the time the final cleanup
  needs it, the upper levels' `plan_params` lists are already gone.
  [from-comment:2358-2363]
- **Initplan cost added to BOTH startup *and* total cost** of the plan
  node (because initplans run before the first tuple is produced).
  [from-comment:2484-2486]
- **CTE planning has three outcomes** (ignore/inline/initplan), and the
  decision is recorded in `cte_plan_ids` for the rest of the planner to
  read. [from-comment:875-881]

## 5. Tags
`[verified-by-code]` ×4, `[from-comment]` ×10
