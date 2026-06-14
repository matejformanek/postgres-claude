# PlanState — the executor's per-node runtime state

`PlanState` is the **runtime mirror of a `Plan` node**: every
plan-node type (`SeqScan`, `HashJoin`, `Agg`, ...) has a
`<Type>State` C struct whose first member is a `PlanState`.
Together they form a tree that parallels the `Plan` tree, sharing
the same parent-child links. Tuples flow up the tree via
`ExecProcNode` dispatch; each node's state holds the local
per-tuple workspace (compiled qual / projection, child links,
result slot, ExprContext).

Anchors:
- `source/src/include/nodes/execnodes.h:1196-1260` —
  PlanState struct head [verified-by-code]
- `source/src/include/nodes/execnodes.h:1198` —
  `pg_node_attr(abstract)` (designed for inheritance)
  [verified-by-code]
- `source/src/include/nodes/execnodes.h:1208-1209` —
  ExecProcNode function pointer [verified-by-code]
- `knowledge/data-structures/estate.md` — companion;
  PlanState.state points here
- `knowledge/data-structures/exprcontext.md` — companion;
  per-node ExprContext in ps_ExprContext
- `knowledge/data-structures/tupletableslot.md` — companion;
  ps_ResultTupleSlot
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The shape (selected fields)

```c
typedef struct PlanState
{
    pg_node_attr(abstract)
    NodeTag         type;

    Plan           *plan;                  /* associated Plan node */
    EState         *state;                  /* shared per-query EState */

    ExecProcNodeMtd ExecProcNode;          /* return-next-tuple function */
    ExecProcNodeMtd ExecProcNodeReal;       /* unwrapped */

    /* Instrumentation */
    NodeInstrumentation *instrument;
    WorkerNodeInstrumentation *worker_instrument;
    struct SharedJitInstrumentation *worker_jit_instrument;

    /* Common structural data */
    ExprState      *qual;                   /* boolean qual */
    PlanState      *lefttree;                /* inner / outer / left */
    PlanState      *righttree;
    List           *initPlan;                /* InitPlan SubPlanStates */
    List           *subPlan;                 /* embedded SubPlanStates */

    /* Param-driven rescan */
    Bitmapset      *chgParam;

    /* Result tuple */
    TupleDesc       ps_ResultTupleDesc;
    TupleTableSlot *ps_ResultTupleSlot;
    ExprContext    *ps_ExprContext;          /* node's ExprContext */
    ProjectionInfo *ps_ProjInfo;             /* projection (if any) */

    bool            async_capable;

    /* Slot-type metadata for ExprState compilation */
    TupleDesc       scandesc;
    /* + slot ops fixed/set per inner/outer/scan ... */
} PlanState;
```

[verified-by-code `execnodes.h:1196-1280`]

## The Plan ↔ PlanState pairing

[verified-by-code `execnodes.h:1202`]

```c
Plan      *plan;     /* associated Plan node */
```

For each `Plan` node type there's a `<Type>State`:

| Plan | PlanState |
|---|---|
| `SeqScan` | `SeqScanState` |
| `IndexScan` | `IndexScanState` |
| `BitmapHeapScan` | `BitmapHeapScanState` |
| `NestLoop` / `HashJoin` / `MergeJoin` | `NestLoopState` / `HashJoinState` / `MergeJoinState` |
| `Agg` | `AggState` |
| `Sort` | `SortState` |
| `Gather` | `GatherState` |
| `Limit` | `LimitState` |

Every subtype's first field is a `PlanState ps;`. Use
`outerPlanState(ps)` / `innerPlanState(ps)` to navigate.

## ExecProcNode — the tuple pull

[verified-by-code `execnodes.h:1208-1209`]

```c
ExecProcNodeMtd ExecProcNode;
ExecProcNodeMtd ExecProcNodeReal;
```

The function pointer for "return the next tuple". Initialized by
`ExecInitNode` per node type. Dispatch is one indirect call per
tuple per node — modest overhead.

`ExecProcNodeReal` holds the underlying function when
`ExecProcNode` is wrapped (e.g., by instrumentation). Without
instrumentation, both point at the same function.

## qual + ps_ProjInfo — compiled expression state

```c
ExprState     *qual;
ProjectionInfo *ps_ProjInfo;
```

`qual` is the WHERE / JOIN qual as a compiled ExprState (see
`expression-evaluator-flow`). `ps_ProjInfo` projects the node's
inner tuple into the final output shape.

Set up during `ExecInitNode` for the node type; consulted
per-tuple in `ExecScan` / the node's per-type processing.

## lefttree / righttree — the input plans

[verified-by-code `execnodes.h:1224-1225`]

```c
PlanState *lefttree;
PlanState *righttree;
```

Inner / outer (or left / right) child PlanStates. Conventions:
- Scan nodes: both NULL.
- Aggregation / Sort / Limit / Unique: only `lefttree`.
- Join nodes: `lefttree` = outer relation, `righttree` = inner.
- Append / MergeAppend / ModifyTable: use an explicit subplans
  list in the subclass, not lefttree/righttree.

## initPlan vs subPlan

```c
List *initPlan;      /* uncorrelated, run once at start */
List *subPlan;       /* per-tuple */
```

Per `subplan-and-initplan` idiom: InitPlans set their PARAM_EXEC
slots at ExecInitNode time; correlated SubPlans evaluate as part
of expression evaluation.

## ps_ExprContext — the per-node ExprContext

```c
ExprContext *ps_ExprContext;
```

The node's primary expression-evaluation context. Created lazily
on first use via `ExecAssignExprContext`. Holds the per-tuple
memory context that gets reset on each `ExecQual` /
`ExecProject` call.

Nodes that need additional contexts (e.g. Agg's tmpcontext +
aggcontext) own them as subclass fields.

## chgParam — rescan trigger

```c
Bitmapset *chgParam;
```

Set of PARAM_EXEC IDs that changed since the last call to this
node. Drives rescanning: when the parent calls `ExecReScan`,
nodes propagate `chgParam` to children and skip rescanning if
the relevant params haven't changed.

Nested-loop joins use this heavily: the inner side rescans only
when the outer-side params change.

## scandesc + slot-type metadata

[verified-by-code `execnodes.h:1253-1280`]

```c
TupleDesc  scandesc;
TupleTableSlotOps *outerops, *innerops, *scanops, *resultops;
bool       outeropsfixed, inneropsfixed, scanopsfixed, resultopsfixed;
bool       outeropsset, inneropsset, scanopsset, resultopsset;
```

ExprState compilation can optimize when the slot types for
inner/outer/scan are known. These fields let `ExecInitNode`
declare the slot ops, and the expression compiler emits
specialized opcodes if `*opsfixed` is true.

## Common review-time concerns

- **Every `<Type>State` MUST start with `PlanState ps;`** —
  generic code does pointer-cast assumption.
- **`state` is the shared EState** — never NULL after
  ExecInitNode.
- **`ExecProcNode` dispatch is hot** — instrumentation wraps it
  via ExecProcNodeReal.
- **`lefttree` / `righttree` conventions** vary by node type;
  Append-style uses subclass lists.
- **`chgParam` propagation** is the rescan correctness gate;
  forgetting it = stale tuples.
- **`ps_ExprContext` is lazy** — call ExecAssignExprContext
  before first use.

## Invariants

- **[INV-1]** Every `<Type>State` C struct starts with
  `PlanState ps;`.
- **[INV-2]** `state` field shared across all PlanStates in
  the tree.
- **[INV-3]** `ExecProcNode` returns next tuple or NULL.
- **[INV-4]** `chgParam` propagated through rescan boundaries.
- **[INV-5]** `initPlan` runs once at start; `subPlan`
  per-tuple.

## Useful greps

- All PlanState subclass definitions:
  `grep -n 'typedef struct.*State$' source/src/include/nodes/execnodes.h | head -30`
- ExecInitNode dispatch:
  `grep -n 'ExecInitNode\|ExecInitNodeMtd' source/src/backend/executor/execProcnode.c | head -10`
- ExecProcNode wrapping:
  `grep -n 'ExecProcNodeFirst\|ExecProcNodeInstr' source/src/backend/executor/execProcnode.c | head -5`

## Cross-references

- `knowledge/data-structures/estate.md` — every PlanState
  points to one shared EState.
- `knowledge/data-structures/exprcontext.md` — ps_ExprContext
  is the node's primary ExprContext.
- `knowledge/data-structures/tupletableslot.md` —
  ps_ResultTupleSlot.
- `knowledge/idioms/expression-evaluator-flow.md` — qual /
  projection compile to ExprState.
- `knowledge/idioms/subplan-and-initplan.md` — initPlan /
  subPlan attach here.
- `knowledge/idioms/bitmap-heap-scan-flow.md` —
  BitmapHeapScanState specialization.
- `knowledge/idioms/aggregate-trans-state.md` — AggState
  specialization.
- `knowledge/subsystems/executor.md` — executor overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/include/nodes/execnodes.h` — full struct +
  subclasses.
- `source/src/backend/executor/execProcnode.c` —
  ExecInitNode / ExecEndNode dispatch.
