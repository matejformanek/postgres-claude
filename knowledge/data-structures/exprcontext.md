# ExprContext — per-node expression-evaluation context

`ExprContext` is the **per-node workspace consumed by the
expression evaluator** (compiled `ExprState` programs). It
collects the inputs Var nodes can reference (inner/outer/scan
slots), the parameter-substitution tables, the aggregate /
window precomputed values, the CASE/DOMAIN test-value slots,
and the per-tuple memory context that gets reset on every call.
Every `PlanState` typically owns at least one ExprContext
(`ps_ExprContext`); some node types own more.

Anchors:
- `source/src/include/nodes/execnodes.h:281-332` —
  ExprContext struct head [verified-by-code]
- `source/src/include/nodes/execnodes.h:285-289` —
  scantuple/innertuple/outertuple [verified-by-code]
- `source/src/include/nodes/execnodes.h:293-294` —
  per_query_memory + per_tuple_memory [verified-by-code]
- `source/src/include/nodes/execnodes.h:328` —
  ecxt_estate link back [verified-by-code]
- `knowledge/data-structures/estate.md` — companion;
  ecxt_estate points back here
- `knowledge/data-structures/planstate.md` — companion;
  PlanState.ps_ExprContext owns this
- `knowledge/data-structures/tupletableslot.md` — companion;
  ecxt_*tuple are slot pointers
- `knowledge/data-structures/datum-nullabledatum.md` —
  ecxt_aggvalues / caseValue etc. are Datums
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The shape (selected fields)

```c
typedef struct ExprContext
{
    NodeTag         type;

    /* Tuples that Var nodes in expressions may refer to */
    TupleTableSlot *ecxt_scantuple;     /* SCAN_VAR target */
    TupleTableSlot *ecxt_innertuple;    /* INNER_VAR target */
    TupleTableSlot *ecxt_outertuple;    /* OUTER_VAR target */

    /* Memory contexts */
    MemoryContext   ecxt_per_query_memory;   /* long-lived */
    MemoryContext   ecxt_per_tuple_memory;   /* reset per tuple */

    /* Param substitution */
    ParamExecData  *ecxt_param_exec_vals;    /* PARAM_EXEC */
    ParamListInfo   ecxt_param_list_info;    /* PARAM_EXTERN etc. */

    /* Aggregate / WindowAgg precomputed values */
    Datum          *ecxt_aggvalues;
    bool           *ecxt_aggnulls;

    /* CaseTestExpr substitution */
    Datum           caseValue_datum;
    bool            caseValue_isNull;

    /* CoerceToDomainValue substitution */
    Datum           domainValue_datum;
    bool            domainValue_isNull;

    /* RETURNING OLD / NEW */
    TupleTableSlot *ecxt_oldtuple;
    TupleTableSlot *ecxt_newtuple;

    /* Link back to containing EState */
    struct EState  *ecxt_estate;

    /* Reset / shutdown callbacks */
    ExprContext_CB *ecxt_callbacks;
} ExprContext;
```

[verified-by-code `execnodes.h:281-332`]

## The three Var-target slots

[verified-by-code `execnodes.h:285-289`]

```c
TupleTableSlot *ecxt_scantuple;
TupleTableSlot *ecxt_innertuple;
TupleTableSlot *ecxt_outertuple;
```

Per `var-const-nodes` idiom, after planning Vars carry special
`varno` values (`INNER_VAR`, `OUTER_VAR`, `SCAN_VAR` and friends)
indicating which slot to read from at runtime. The expression
evaluator dereferences:

- `INNER_VAR` (-1) → `ecxt_innertuple`
- `OUTER_VAR` (-2) → `ecxt_outertuple`
- `SCAN_VAR` (-3 in modern PG; or positive rti for base rel) →
  `ecxt_scantuple`

These slots must be populated by the caller BEFORE
`ExecEvalExpr` is invoked.

## The two memory contexts

[verified-by-code `execnodes.h:293-294`]

```c
MemoryContext ecxt_per_query_memory;
MemoryContext ecxt_per_tuple_memory;
```

- **`per_query_memory`** — long-lived; usually the EState's
  query context. Holds compiled ExprState programs and stable
  per-query data.
- **`per_tuple_memory`** — short-lived; reset by
  `ResetExprContext` on every per-tuple call. Holds intermediate
  results of function calls, scratch palloc'd Datums, etc.

The reset-per-tuple discipline is what lets expression evaluation
leak palloc'd results without growing memory unboundedly.

## ResetExprContext — the per-tuple boundary

```c
void ResetExprContext(ExprContext *econtext);
```

Single line:
```c
MemoryContextReset(econtext->ecxt_per_tuple_memory);
```

Called by every ExecQual / ExecProject before evaluating the
qual or projection on the next tuple. The pattern:

```c
foreach tuple:
    ResetExprContext(econtext);
    if (!ExecQual(node->qual, econtext))
        continue;
    output = ExecProject(node->projInfo);
    yield output
```

## ParamExecData + ParamListInfo

```c
ParamExecData  *ecxt_param_exec_vals;
ParamListInfo   ecxt_param_list_info;
```

Per `subplan-and-initplan` idiom:
- **`ecxt_param_exec_vals`** — array of `ParamExecData`, one per
  PARAM_EXEC slot allocated by the planner. SubPlan/InitPlan
  output, NestLoop param pass-down, etc.
- **`ecxt_param_list_info`** — PARAM_EXTERN bindings from the
  client (PREPARE + EXECUTE arguments).

Both inherited from the EState; pointing the ExprContext at them
makes evaluator opcodes one indirection cheaper.

## ecxt_aggvalues / ecxt_aggnulls — aggregate substitution

```c
Datum *ecxt_aggvalues;
bool  *ecxt_aggnulls;
```

For expressions evaluated by an `Agg` node (the targetlist /
having qual), Aggref nodes are replaced at compile time with
references into these arrays — the aggregate's current result.
AggState fills them before evaluating each output expression.

WindowAgg uses them the same way for WindowFunc nodes.

## caseValue + domainValue — special substitutions

```c
Datum caseValue_datum;  bool caseValue_isNull;
Datum domainValue_datum; bool domainValue_isNull;
```

`CaseTestExpr` nodes (the "input" placeholder inside `CASE x
WHEN ...` branches) substitute the caseValue at evaluation time.
Likewise `CoerceToDomainValue` for domain check constraints.

Both are stack-like: set by the outer evaluator before recursing
into the branch / check expression, restored after.

## ecxt_oldtuple / ecxt_newtuple — RETURNING-clause OLD/NEW

[verified-by-code `execnodes.h:323-325`]

```c
TupleTableSlot *ecxt_oldtuple;
TupleTableSlot *ecxt_newtuple;
```

For `RETURNING old.col, new.col` after UPDATE / DELETE / MERGE,
these slots hold the pre-image and post-image of the modified
row.

NULL for non-RETURNING contexts.

## ecxt_callbacks — shutdown / reset hooks

```c
ExprContext_CB *ecxt_callbacks;
```

Linked list of callbacks invoked when the ExprContext is reset
or freed. Used by SRF accumulators, aggregate state cleanup,
TupleHashTable shutdown, etc.

Register via `RegisterExprContextCallback`; runs LIFO.

## Standalone ExprContexts

[from-comment `execnodes.h:327`]

> Link to containing EState (NULL if a standalone ExprContext)

Standalone usage: code paths outside an executor PlanState
(e.g., SPI helpers, constraint evaluation) create an ExprContext
via `MakeStandaloneExprContext` or `CreateExprContext(estate)`.
A standalone one has `ecxt_estate = NULL` and its own
per-tuple memory context detached from any EState.

## Common review-time concerns

- **Populate ecxt_*tuple BEFORE calling ExecEvalExpr** — Var
  evaluation will dereference whichever slot the Var's varno
  selects.
- **per_tuple_memory MUST be reset between tuples** —
  forgetting = memory growth in long scans.
- **Aggregate values come from AggState**, not from the
  evaluator's call stack.
- **CaseTestExpr / CoerceToDomainValue stack semantics** — save
  + restore around recursion.
- **Standalone ExprContexts** have NULL ecxt_estate; code that
  assumes estate must check.

## Invariants

- **[INV-1]** ecxt_*tuple set by caller before ExecEvalExpr.
- **[INV-2]** per_tuple_memory reset on every per-tuple call.
- **[INV-3]** ecxt_aggvalues populated by AggState before
  aggref evaluation.
- **[INV-4]** ecxt_callbacks run LIFO on reset / shutdown.
- **[INV-5]** Standalone ExprContexts have ecxt_estate ==
  NULL.

## Useful greps

- ExprContext constructors:
  `grep -RIn 'CreateExprContext\|MakeStandaloneExprContext' source/src/backend/executor | head -10`
- per_tuple_memory resets:
  `grep -RIn 'ResetExprContext' source/src/backend/executor | head -10`
- Callback users:
  `grep -RIn 'RegisterExprContextCallback' source/src/backend | head -10`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execUtils.c`](../files/src/backend/executor/execUtils.c.md) | — | CreateExprContext, ResetExprContext |
| [`src/include/nodes/execnodes.h`](../files/src/include/nodes/execnodes.h.md) | 281 | ExprContext struct head |
| [`src/include/nodes/execnodes.h`](../files/src/include/nodes/execnodes.h.md) | 285 | scantuple/innertuple/outertuple |
| [`src/include/nodes/execnodes.h`](../files/src/include/nodes/execnodes.h.md) | 293 | per_query_memory + per_tuple_memory |
| [`src/include/nodes/execnodes.h`](../files/src/include/nodes/execnodes.h.md) | 328 | ecxt_estate link back |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/estate.md` — ecxt_estate points
  back here.
- `knowledge/data-structures/planstate.md` — owned by
  PlanState.ps_ExprContext.
- `knowledge/data-structures/tupletableslot.md` —
  ecxt_*tuple are slot pointers.
- `knowledge/data-structures/datum-nullabledatum.md` —
  caseValue / domainValue / aggvalues are Datums.
- `knowledge/data-structures/var-const-nodes.md` — Var.varno
  selects which ecxt slot to read.
- `knowledge/idioms/expression-evaluator-flow.md` — ExprState
  programs consume this.
- `knowledge/idioms/aggregate-trans-state.md` — Agg populates
  ecxt_aggvalues.
- `knowledge/subsystems/executor.md` — executor overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/include/nodes/execnodes.h:281` — full struct.
- `source/src/backend/executor/execUtils.c` —
  CreateExprContext, ResetExprContext.
