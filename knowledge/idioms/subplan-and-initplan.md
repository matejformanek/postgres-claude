# SubPlan vs InitPlan — when subqueries run

A PostgreSQL `SubPlan` is the executor's representation of
a subquery embedded in an expression. The planner classifies
each into one of two execution regimes — **InitPlan** (run
once, before the parent node starts; result cached in a
PARAM_EXEC slot) or **regular SubPlan** (run per parent
tuple, with parameter pass-down). The split is the key to
understanding subquery cost AND correctness; misclassifying
makes EXPLAIN puzzling and can quietly hurt performance.

Anchors:
- `source/src/include/nodes/primnodes.h:1092-1142` —
  SubPlan struct [verified-by-code]
- `source/src/include/nodes/plannodes.h:242-253` —
  Plan.initPlan + extParam commentary [verified-by-code]
- `source/src/backend/executor/nodeSubplan.c:24-26` —
  interface routines header [verified-by-code]
- `source/src/backend/executor/nodeSubplan.c:55-91` —
  ExecSubPlan dispatcher [verified-by-code]
- `knowledge/data-structures/plannerinfo.md` — companion;
  plan_params / outer_params handshake
- `knowledge/data-structures/var-const-nodes.md` —
  PARAM_EXEC params replace Vars
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The two regimes

[verified-by-code `plannodes.h:242-253`]

```c
List       *initPlan;   /* SubPlan nodes that are InitPlans */
```

A `SubPlan` whose result depends only on **PARAM_EXEC slots
already evaluated** (or no params at all) can be lifted to
an InitPlan — pre-evaluated, result stashed in its
`setParam` slots — and the parent node treats the params
as constants.

A `SubPlan` that references the parent's per-tuple state
(via PARAM_EXEC slots set from the parent's loop) MUST run
per-parent-tuple.

Same struct, same node type — the placement (in `Plan.initPlan`
vs embedded in an expression) is the discriminator.

## SubPlan struct fields

[verified-by-code `primnodes.h:1092-1142`]

```c
typedef struct SubPlan
{
    Expr        xpr;
    SubLinkType subLinkType;     /* EXISTS_SUBLINK / ANY_SUBLINK / ... */
    Node       *testexpr;        /* OpExpr/BoolExpr embedded as test */
    List       *paramIds;        /* PARAM_EXEC slots consumed */

    int         plan_id;         /* index into PlannerGlobal->subplans */
    char       *plan_name;       /* EXPLAIN label */

    Oid         firstColType;
    int32       firstColTypmod;
    Oid         firstColCollation;

    bool        useHashTable;    /* hashed IN/NOT IN strategy */
    bool        unknownEqFalse;
    bool        parallel_safe;

    List       *setParam;        /* PARAM_EXEC slots this SubPlan sets */
    List       *parParam;        /* PARAM_EXEC slots this SubPlan reads */
    List       *args;            /* expressions for parParam */

    Cost        startup_cost;
    Cost        per_call_cost;
} SubPlan;
```

The three lists drive execution:
- **`paramIds`** — slot IDs the subquery REPORTS (testexpr
  consumes).
- **`setParam`** — slots SET when InitPlan finishes.
- **`parParam`** — slots READ from parent's loop state.

InitPlan ↔ `parParam == NIL`. Regular SubPlan ↔ `parParam != NIL`.

## subLinkType — the comparison shape

[verified-by-code `primnodes.h:1086-1090` via SubLinkType enum]

| Type | SQL form | Result |
|---|---|---|
| `EXISTS_SUBLINK` | `EXISTS (SELECT...)` | bool |
| `ALL_SUBLINK` | `x op ALL (...)` | bool |
| `ANY_SUBLINK` | `x op ANY (...)` / `IN (...)` | bool |
| `ROWCOMPARE_SUBLINK` | `(a,b) op (SELECT a,b...)` | bool |
| `EXPR_SUBLINK` | `(SELECT x...)` | scalar |
| `MULTIEXPR_SUBLINK` | `(SELECT a,b...) = ROW(c,d)` | row |
| `ARRAY_SUBLINK` | `ARRAY(SELECT...)` | array |
| `CTE_SUBLINK` | WITH-referenced | — |

The subLinkType determines the testexpr shape AND whether
the result is a scalar / bool / array.

## ExecSubPlan — the runtime dispatcher

[verified-by-code `nodeSubplan.c:55-91`]

```c
Datum
ExecSubPlan(SubPlanState *node, ExprContext *econtext, bool *isNull)
{
    SubPlan    *subplan = node->subplan;
    /* ... checks ... */

    if (subplan->useHashTable)
        retval = ExecHashSubPlan(node, econtext, isNull);
    else
        retval = ExecScanSubPlan(node, econtext, isNull);

    return retval;
}
```

Two strategies:
- **Hashed**: build hash table of subquery result, then
  probe per outer tuple. Used for `IN (...)` /
  `NOT IN (...)` when statistics suggest enough outer rows
  to amortize.
- **Scanned**: rescan subquery per outer-tuple change of
  parameters. The fallback.

## InitPlans — pre-evaluation + cache

[verified-by-code `plannodes.h:247-253`]

> extParam includes the paramIDs of all external PARAM_EXEC
> params affecting the node or its children. setParam
> params from the node's initPlans are not included, but
> their extParams are.

InitPlans run at parent-node start (via `ExecSetParamPlan`).
The setParam slots get filled; subsequent expression
evaluations referencing those slots see the cached value.

Common InitPlan triggers:
- `WHERE x > (SELECT MAX(y) FROM t)` — subquery uncorrelated
  → InitPlan.
- `WHERE EXISTS (SELECT 1 FROM bigtbl WHERE col = ?)` —
  with `?` from outer query → still might be InitPlan if
  the outer reference resolves at parent's start.

EXPLAIN shows InitPlans as separate nested boxes labelled
`InitPlan 1 (returns $0)` — the `$0` is the PARAM_EXEC slot.

## Hash subplan — the optimization for IN

For `WHERE col IN (subquery)` with a non-correlated
subquery, the planner can:
1. Run the subquery once at SubPlan-init.
2. Build a hash table keyed on the subquery output.
3. Per outer tuple, hash-lookup `col`.

The `useHashTable` flag drives this. Buckets sized via
`work_mem`; falls back to scanned if memory pressure.

NULL handling is subtle: `NOT IN (subquery)` with any NULL
in subquery → result is NULL or false depending on outer
match. The `unknownEqFalse` flag selects the SQL semantics.

## Why the distinction matters

- **InitPlan cost** is fixed-per-execution. EXPLAIN
  attributes it correctly.
- **Regular SubPlan cost** is per-parent-tuple — can be
  catastrophic if not realized.
- **AlternativeSubPlan** (`primnodes.h:1143`) wraps two
  candidates the executor can pick between at runtime.
- **Parallel-safe** — InitPlans are evaluated by the
  leader before launching workers; the workers see the
  cached value.

## Common review-time concerns

- **EXPLAIN labels** — `InitPlan N` is uncorrelated; `SubPlan N`
  embedded is correlated.
- **`parParam` non-empty → per-tuple rescans**. Look for
  these in slow EXPLAIN ANALYZE output.
- **`useHashTable` requires memory**; spillage matters.
- **MULTIEXPR_SUBLINK** (`(a,b) = (SELECT...)`) — special
  setParam pattern, sets multiple slots.
- **CTE_SUBLINK** — handled separately
  (CteScan node), NOT via ExecSubPlan.

## Invariants

- **[INV-1]** `parParam == NIL` → InitPlan-eligible;
  non-empty → regular SubPlan.
- **[INV-2]** `setParam` filled by InitPlan; consumed by
  parent expression.
- **[INV-3]** `useHashTable` is a one-shot evaluation
  strategy; uses work_mem.
- **[INV-4]** AlternativeSubPlan picks at runtime between
  candidates.
- **[INV-5]** CTE_SUBLINK NEVER goes through ExecSubPlan
  (sanity-checked in dispatcher).

## Useful greps

- The dispatcher + init:
  `grep -n 'ExecSubPlan\|ExecInitSubPlan' source/src/backend/executor/nodeSubplan.c | head -10`
- InitPlan walk in execMain:
  `grep -n 'InitPlan\|setParam\|paramIds' source/src/backend/executor/execMain.c | head -10`
- Planner side:
  `grep -RIn 'SS_process_sublinks\|SS_finalize_plan' source/src/backend/optimizer | head -10`

## Cross-references

- `knowledge/data-structures/plannerinfo.md` —
  plan_params + outer_params drive PARAM_EXEC numbering.
- `knowledge/data-structures/var-const-nodes.md` —
  Params replace Vars in subplan output.
- `knowledge/idioms/expression-evaluator-flow.md` —
  ExecSubPlan called as a step of an ExprState.
- `knowledge/idioms/cursor-and-portal.md` — CTE
  materialization (CTE_SUBLINK distinct from SubPlan).
- `knowledge/subsystems/executor.md` — executor overview.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/executor/nodeSubplan.c` — runtime.
- `source/src/backend/optimizer/plan/subselect.c` —
  planner side, classifies subqueries.
- `source/src/include/nodes/primnodes.h:1092-1142` — full
  SubPlan struct.
