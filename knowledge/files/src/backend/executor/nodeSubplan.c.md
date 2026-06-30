# nodeSubplan.c

- **Source:** `source/src/backend/executor/nodeSubplan.c` (≈1300 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Implements the **SubPlan** expression node (a subquery embedded in an
expression: scalar subquery, EXISTS, ANY/ALL, MULTIEXPR, plus
"InitPlan" subqueries that run once at executor start). NOT to be confused
with `nodeSubqueryscan.c` which is for FROM-clause subqueries.

## SubLink types handled

`subLinkType` switch in `ExecSubPlan` `:59`:

- `EXISTS_SUBLINK` — returns boolean: true if subplan produces any row.
- `ALL_SUBLINK` / `ANY_SUBLINK` — `expr op ALL/ANY (subquery)`. Uses
  ExecScanSubPlan or ExecHashSubPlan.
- `ROWCOMPARE_SUBLINK` — `(a,b) op (subquery)`.
- `EXPR_SUBLINK` — scalar subquery returning at most one row.
- `MULTIEXPR_SUBLINK` — `(a,b) = (subquery)` returning multiple Params at
  once. The expression-level Params (`PARAM_MULTIEXPR`) are wired up so each
  references its respective output column of the same single execution.
- `ARRAY_SUBLINK` — collect all subplan rows into an array.

## Hashed vs scanned

If `useHashTable` (set by planner when ANY/ALL applies an equality and
the subplan output fits hash-mem), `buildSubPlanHash` `:474` drains the
subplan once into a TupleHashTable, then per-probe does O(1) lookup
(`ExecHashSubPlan` `:98`). Otherwise `ExecScanSubPlan` `:201` runs/replays
the subplan for each outer row.

## InitPlan path: `ExecSetParamPlan(node, econtext)` `:1118`

Runs an InitPlan subplan to completion exactly **once** per query (or per
outer Param change), stashing its output into one or more PARAM_EXEC slots
in the EState. The expression-level reference to those Params then reads
the cached value. `ExecSetParamPlanMulti` `:1294` is the batch version.

## Init: `ExecInitSubPlan` `:850`

Allocates the SubPlanState, builds the per-Param ExprState list for
parameter passing (`args` → `setParams`), opens the subplan via
`ExecInitNode`. Note that the subplan's `PlanState` is allocated as a child
of the **EState**, not the parent PlanState — this is what lets one InitPlan
serve many sibling expressions.

## Tags

- [verified-by-code] all SubLinkType handlers + InitPlan caching.
- [from-comment] file header dispatches.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/subplan-and-initplan.md](../../../../idioms/subplan-and-initplan.md)

