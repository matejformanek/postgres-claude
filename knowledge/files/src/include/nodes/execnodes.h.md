# execnodes.h

- **Source:** `source/src/include/nodes/execnodes.h` (~3500 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim (top comment + struct inventory)

## Purpose

**Executor state nodes** — the runtime mirror of the plan tree.
Most plan types in `plannodes.h` have a corresponding `*State` here.
Expression evaluation is mostly done via `ExprState`'s step program
(`execExpr*`) rather than per-Expr state nodes. `:5-16`
`[from-comment]`

## Critical invariant

**Executor state nodes have NO copy/equal/out/read support.** They're
not serialized — they live and die within one query execution.
gen_node_support.pl treats this whole file as `nodetag_only`. `:11-15,
gen_node_support.pl:80-85` `[from-comment]`

## Major struct families

### Expression evaluation

- `ExprState` `:98` — compiled program for an expression. Holds
  steps array, ExprContext pointer, evaluation flags.
- `ExprContext` `:281` — per-tuple eval context (ecxt_per_tuple,
  ecxt_per_query, scan/inner/outer slots, param arrays).
- `ExprContext_CB` `:251` — registerable callbacks (e.g. for
  per-tuple memory cleanup).
- `ReturnSetInfo` `:366` — SRF (set-returning function) return state.
- `ProjectionInfo` `:396`, `JunkFilter` `:429`.

### Result-relation machinery

- `ResultRelInfo` `:505` — per-target-relation execution state for
  INSERT/UPDATE/DELETE/MERGE.
- `OnConflictActionState` `:443`, `MergeActionState` `:460`,
  `ForPortionOfState` `:475`.

### EState — the top-level executor state `:690`

Per-query state: snapshot, range table, query env, ParamListInfo,
TupleTable, result rel info array, transition-tuple support,
async-request queue, parallel-mode flags.

### Row marking

- `ExecRowMark` `:831`, `ExecAuxRowMark` `:855` — FOR UPDATE/SHARE
  bookkeeping.

### Tuple-hash table

- `TupleHashEntryData *TupleHashEntry` `:880`,
  `TupleHashTableData *TupleHashTable` `:881`. Used by `Agg` and
  `SetOp` for hashing on a subset of attributes.

### PlanState — base for every executor node

`PlanState` `:55` (forward decl; full def later). Every plan-node
state inherits this. Fields include `plan`, `state`, `ExecProcNode`
function pointer, `ExecProcNodeReal` (used when instrumentation
wrappers are inserted), `instrument`, `ps_ResultTupleDesc`,
`ps_ResultTupleSlot`, `ps_ExprContext`, `ps_ProjInfo`, `qual`,
`lefttree`/`righttree`, `initPlan`/`subPlan`.

Subclasses follow for every Plan type: `SeqScanState`,
`IndexScanState`, `BitmapIndexScanState`, `BitmapHeapScanState`,
`HashJoinState`, `NestLoopState`, `MergeJoinState`, `SortState`,
`MaterialState`, `AggState`, `WindowAggState`, `AppendState`,
`MergeAppendState`, `GatherState`, `LimitState`, etc.

## Forward typedefs at the top `:48-72`

A lot of `typedef struct X X;` forward decls so the file can refer to
opaque externals (BufferUsage, ExecRowMark, ExprState, ExprContext,
HTAB, Instrumentation, PlanState, QueryEnvironment, Relation, Snapshot,
TIDBitmap, TriggerInstrumentation, TupleDesc, Tuplesortstate,
TupleTableSlot, TupleTableSlotOps, …).

## Cross-references

- Sibling: `plannodes.h` (the Plan side).
- Implementation: every `src/backend/executor/node*.c`.
- Idiom: `knowledge/idioms/node-types-and-lists.md`.

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->
