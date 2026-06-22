# Utility-statement planning — `pg_plan_query` vs `expression_planner`

Any utility-statement code path that builds a hand-rolled `PlannedStmt`
and feeds its RHS expressions through `expression_planner` instead of
`pg_plan_query` will leak unprocessed parse-tree nodes (notably
`SubLink`, sometimes `CollateExpr`) into `ExecInitExprRec` and crash at
run time with `unrecognized node type: N`. `expression_planner` is
deliberately narrow — it const-folds, fills opfuncids, and strips a
few wrappers, but it never invokes `SS_process_sublinks`. The fix is
not "patch `expression_planner`"; it is to route through a synthetic
one-shot `CMD_SELECT` Query and let the full planner do its job.

Anchors:
- `source/src/backend/optimizer/plan/planner.c:7080-7095` —
  `expression_planner` definition; the comment explicitly says
  "we disallow sublinks in standalone expressions" [from-comment]
- `source/src/backend/optimizer/plan/planner.c:7061-7062` —
  "Currently, we disallow sublinks in standalone expressions, so
  there's no real 'planning' involved here" [from-comment]
- `source/src/backend/tcop/postgres.c:898-917` — `pg_plan_query`,
  thin wrapper around `planner()`; refuses `CMD_UTILITY` Querys
  [verified-by-code]
- `source/src/backend/optimizer/plan/subselect.c:2208-2216` —
  `SS_process_sublinks`, the `SubLink → SubPlan/Param(PARAM_EXEC)`
  rewrite, only reachable from inside `subquery_planner`
  [verified-by-code]
- `source/src/backend/executor/execExpr.c:2657-2660` —
  `ExecInitExprRec` default arm: `elog(ERROR, "unrecognized node
  type: %d", ...)` [verified-by-code]

## The two planning paths

[verified-by-code `source/src/backend/optimizer/plan/planner.c:7080-7095`]:

```c
Expr *
expression_planner(Expr *expr)
{
    Node    *result;

    /* Convert named-argument function calls, insert default arguments
     * and simplify constant subexprs */
    result = eval_const_expressions(NULL, (Node *) expr);

    /* Fill in opfuncid values if missing */
    fix_opfuncids(result);

    return (Expr *) result;
}
```

That is the entire body. Two passes, no PlannerInfo, no sublink
handling. The function header comment is explicit:

> Currently, we disallow sublinks in standalone expressions, so
> there's no real "planning" involved here.

[from-comment `source/src/backend/optimizer/plan/planner.c:7061-7062`]

`pg_plan_query` is the opposite extreme: a thin wrapper that delegates
to `planner()`, which fans out into `subquery_planner` and runs the
full pipeline — `SS_process_sublinks` (rewrites every `SubLink` into
a `SubPlan` referencing the outer plan's `subplans` list, and replaces
correlated references with `Param(PARAM_EXEC)`), `CollateExpr`
stripping into `RelabelType`, target-list expansion, const-fold,
fix_opfuncids, init-plan extraction, the lot
[verified-by-code `source/src/backend/tcop/postgres.c:898-917`].

The key fact `SS_process_sublinks` only runs from within
`subquery_planner` [verified-by-code
`source/src/backend/optimizer/plan/subselect.c:2208-2216`]. There is
no stand-alone entry point for "expand sublinks on this expression";
the planner reaches it via the Query-level walk. That is why
`expression_planner` can never grow sublink support without growing
a full PlannerInfo construction next to it — at which point it has
become `pg_plan_query`.

## Why utility statements often skip planning

Utility statements (`SET`, `DECLARE`, `ALTER SYSTEM`, `VACUUM`, etc.)
usually do not run through the planner because their semantics are
not "produce a result tuple set." Two patterns are common:

1. **Pure handler** — `ProcessUtility` dispatches to a `commands/`
   function that evaluates side-effects directly. `ExecSetVariableStmt`
   at `source/src/backend/utils/misc/guc_funcs.c:45`
   [verified-by-code] is the canonical example; its RHS is typically
   already a string literal at parse-analysis.
2. **Hand-rolled `PlannedStmt`** — to piggyback on the executor's
   expression-evaluation machinery (`ExecInitExprRec`), the handler
   builds a `PlannedStmt` around a custom plan node with a per-target
   expression list and runs it through `CreateQueryDesc` +
   `ExecutorStart`/`Run`/`End`. This avoids constructing a parsed
   Query and avoids the rewriter.

The hand-rolled pattern is the trap. Safe when RHS is constants or
pre-resolved expressions; unsafe the moment RHS may contain a
`SubLink`, a `CollateExpr`, or anything else the analyzer leaves for
the planner to lower.

## The SubLink trap

sesvars phase 9 added a per-RHS `expression_planner(e)` to close a
`unrecognized node type: 32` (T_CollateExpr) crash. That worked for
`SET @x := 'a'::text COLLATE "C"` because `eval_const_expressions`
inside `expression_planner` strips `CollateExpr` for constants
[inferred]. Phase 10 then surfaced `SET @v := (SELECT 53)` in
utility form, which errored with `unrecognized node type: 23` —
`T_SubLink` reaching the `ExecInitExprRec` default arm
[verified-by-code `source/src/backend/executor/execExpr.c:2657-2660`].
The inline form `SELECT @v := (SELECT 53)` worked, because that
path went through a real Query and through `pg_plan_query` like any
other SELECT.

Fix: replace the per-RHS `expression_planner` loop with a single
synthetic `pg_plan_query` call processing all RHS targets at once.

## The `pg_plan_query` fallback pattern

The canonical implementation lives at
`postgresql-dev-feature-sesvars/src/backend/commands/sessvar_cmd.c:60-164`
in `BuildSessionVarSetPlannedStmt` [verified-by-code]. The shape:

```c
Query       *q;
List        *tlist = NIL;
PlannedStmt *inner;
AttrNumber   resno = 1;

foreach(lc, stmt->exprs)
{
    Expr *e = (Expr *) lfirst(lc);
    tlist = lappend(tlist, makeTargetEntry(e, resno++, NULL, false));
}

q = makeNode(Query);
q->commandType = CMD_SELECT;
q->canSetTag   = false;
q->jointree    = makeFromExpr(NIL, NULL);
q->targetList  = tlist;
q->hasSubLinks = true;        /* conservative; planner re-derives */

inner = pg_plan_query(q, NULL, 0, boundParams, NULL);

/* Harvest processed expressions, subplans, and initPlan. */
foreach(lc, inner->planTree->targetlist)
    planned_exprs = lappend(planned_exprs,
                            ((TargetEntry *) lfirst(lc))->expr);

harvested_subplans       = inner->subplans;
harvested_paramExecTypes = inner->paramExecTypes;
mnode->plan.initPlan     = inner->planTree->initPlan;
```

Five non-obvious requirements behind that shape:

1. **One synthetic Query, not one per RHS.** A single planner pass
   gives a single `PARAM_EXEC` paramid namespace shared across all
   targets. Per-target planning would produce overlapping paramids
   and require offsetting at glue time.
2. **`commandType = CMD_SELECT`, not `CMD_UTILITY`.** `pg_plan_query`
   returns `NULL` for `CMD_UTILITY` Querys
   [verified-by-code `source/src/backend/tcop/postgres.c:904-906`].
3. **Harvest from `inner->planTree->targetlist`, not from `q->targetList`.**
   `pg_plan_query` is allowed to scribble (its preamble copies if
   `Debug_copy_parse_plan_trees` is set, otherwise it mutates).
4. **Copy `inner->subplans` and `inner->paramExecTypes` onto the
   outer hand-rolled `PlannedStmt`.** The executor's `InitPlan` reads
   these from the top-level `PlannedStmt`, not from the plan node
   it dispatches on. `Param.paramid` values inside the harvested
   expressions index directly into the outer pstmt's `subplans` list
   — no offsetting because the inner pass was the only paramid
   producer.
5. **Reparent `inner->planTree->initPlan` onto the custom node.**
   Uncorrelated scalar subqueries are converted into `InitPlan`s
   hung off the outer `Result` node. If the InitPlan list stays on
   the inner Result (which is then discarded), the
   `Param(PARAM_EXEC)` reads stale zeros or crashes on a dangling
   planstate lookup.

**Thread `ParamListInfo` end-to-end.** PL/pgSQL `PARAM_EXTERN`
references in the RHS must be visible both to the planner (so it can
look up types) and to the executor (so it can resolve values at
runtime). Pass the same `boundParams` to `pg_plan_query` (planning)
and to `CreateQueryDesc` (execution). The sesvars implementation
exposes a no-param `BuildSessionVarSetPlan` for EXPLAIN at
`postgresql-dev-feature-sesvars/src/backend/commands/sessvar_cmd.c:273-284`
and a param-threading `ExecSessionVarSetStmt` for execution at
`:240-266` [verified-by-code].

## When to use which

| Path | Cost | Handles SubLink | Handles CollateExpr | Needs PlannerInfo | Use when |
|---|---|---|---|---|---|
| `expression_planner(Expr *)` | cheapest | no | partial (const-fold strips it) | no | RHS is provably SubLink-free; standalone-expression DDL evaluation; one-off const-fold |
| `pg_plan_query` on a synthetic `CMD_SELECT` | one planner pass | yes | yes | created internally | utility statement that hand-rolls a `PlannedStmt` and may see SubLinks, PARAM_EXEC, or PL/pgSQL-driven extern params |
| `transformStmt` returning a `CMD_SELECT` Query (no hand-roll) | one planner pass + standard executor | yes | yes | created internally | feature has no reason to hand-roll a custom plan node; standard `INSERT`/`SELECT` plumbing is enough |

Decision rule: if the utility statement evaluates ANY user-written
expression that the parser leaves in raw `SubLink` form, route through
`pg_plan_query`. The cost of one synthetic planner pass at SET time
is invisible next to the cost of debugging a runtime
`unrecognized node type` four phases later.

## Anti-patterns

- **"`expression_planner` plus a SubLink walker."** Replicating
  `SS_process_sublinks` outside `subquery_planner` has no stable
  extension surface. Just call the real planner.
- **Per-RHS `pg_plan_query` in a loop.** Each call returns its own
  `subplans` with paramids starting at 1; gluing them onto one outer
  `PlannedStmt` requires per-target offsetting that breaks the first
  time a target produces multiple SubPlans.
- **Forgetting to reparent `initPlan`.** Harvested expressions
  reference `Param.paramid` slots whose values come from InitPlans
  on the inner Result. Discard that Result without lifting its
  `initPlan` and the values never materialize.
- **EXPLAIN that skips the planner pass.** Keep `pg_plan_query` on
  the EXPLAIN path too; pass `boundParams = NULL` rather than gating
  the call, otherwise `EXPLAIN VERBOSE` may emit raw SubLinks.

## Cross-references

- `knowledge/idioms/node-types.md` — parse-tree vs Expr-flavored
  shapes; `SubLink` is parse-tree, `SubPlan` is Expr-flavored
- `knowledge/idioms/plan-cache.md` — `CachedPlanSource` lifecycle
- `source/src/backend/optimizer/plan/planner.c` —
  `expression_planner`, `expression_planner_with_deps`
- `source/src/backend/tcop/postgres.c` — `pg_plan_query`
- `source/src/backend/optimizer/plan/subselect.c` —
  `SS_process_sublinks`
- `source/src/backend/executor/execExpr.c` — `ExecInitExprRec`
  default arm

## Origin

F21 graduate from the sesvars_v3 retro
(`sessions/2026-06-22-sesvars-v3-retro.md`, §F21). Phase 10's
benchmark surfaced `SET @v := (SELECT 53)` crashing in utility form;
phase 9's `expression_planner` had fixed a `T_CollateExpr` gap but
masked the deeper one — hand-rolled `PlannedStmt` paths are a
planner-bypass, so any RHS needing planner-only lowering reaches the
executor raw. Follow-up #1, commit `98321c74bef` on branch
`feature_sesvars` in `postgresql-dev-feature-sesvars/`, replaced
the per-RHS `expression_planner` loop with the single synthetic
`pg_plan_query` pattern documented above.

## Open questions / unverified

- `expression_planner_with_deps`
  (`source/src/backend/optimizer/plan/planner.c:7108`
  [verified-by-code]) shares the SubLink limitation — its body is
  "identical to `expression_planner` except it also returns deps"
  per the comment [inferred].
- Whether `SS_process_sublinks` could be exposed as a stand-alone
  entry usable from utility handlers without a full
  `subquery_planner` [unverified — would require a real PlannerInfo].
