# EState — per-query executor state

`EState` is the **executor's per-Query workspace**, the runtime
counterpart of the planner's `PlannerInfo`. Every PlanState
points back to one shared EState; it holds the range table,
snapshot, parameter values, result-relation array, junk filter,
output command-id, partition-pruning state, and the per-query
memory context. Created by `CreateExecutorState`, populated by
`InitPlan`, torn down by `FreeExecutorState`.

Anchors:
- `source/src/include/nodes/execnodes.h:691-700` —
  EState struct head [verified-by-code]
- `source/src/include/nodes/execnodes.h:694-705` —
  basic-state fields (direction, snapshot, range_table)
  [verified-by-code]
- `source/src/include/nodes/execnodes.h:719-723` —
  output CID + result relations [verified-by-code]
- `source/src/backend/executor/execUtils.c` —
  CreateExecutorState / FreeExecutorState
- `knowledge/data-structures/plannerinfo.md` — planner-side
  counterpart
- `knowledge/data-structures/planstate.md` — companion;
  every PlanState points to one EState
- `knowledge/data-structures/exprcontext.md` — companion;
  ExprContext links to its EState
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The shape (selected fields)

```c
typedef struct EState
{
    NodeTag        type;

    /* Basic state for all query types */
    ScanDirection  es_direction;        /* current scan direction */
    Snapshot       es_snapshot;          /* visibility snapshot */
    Snapshot       es_crosscheck_snapshot;
    List          *es_range_table;       /* List of RangeTblEntry */
    Index          es_range_table_size;
    Relation      *es_relations;          /* per-RTE Relation pointers */
    ExecRowMark  **es_rowmarks;
    List          *es_rteperminfos;
    PlannedStmt   *es_plannedstmt;        /* link to top of plan tree */

    /* Partition pruning */
    List          *es_part_prune_infos;
    List          *es_part_prune_states;
    List          *es_part_prune_results;
    Bitmapset     *es_unpruned_relids;

    const char    *es_sourceText;         /* from QueryDesc */
    JunkFilter    *es_junkFilter;          /* top-level junk filter */

    /* DML state */
    CommandId      es_output_cid;          /* CID for INSERT/UPDATE/DELETE */
    ResultRelInfo **es_result_relations;
    List          *es_opened_result_relations;
    PartitionDirectory es_partition_directory;
    List          *es_tuple_routing_result_relations;
    List          *es_trig_target_relations;

    /* Parameter info */
    ParamListInfo  es_param_list_info;     /* PARAM_EXTERN values */
    ParamExecData *es_param_exec_vals;     /* PARAM_EXEC values */
    QueryEnvironment *es_queryEnv;

    /* Memory contexts */
    MemoryContext  es_query_cxt;           /* per-query alloc */

    /* Per-query timestamp / row count */
    TupleTableSlot *es_trig_tuple_slot;
    Tuplestorestate *es_tuple_returning_store;
    List          *es_subplanstates;       /* SubPlan PlanState list */
    /* ... ~30 more fields */
} EState;
```

[verified-by-code `execnodes.h:691-800`]

## es_range_table + es_relations — the RTE-indexed arrays

[verified-by-code `execnodes.h:694-703`]

Parallel arrays keyed by **range-table index** (1-based; entry 0
unused):

- **`es_range_table`** — list of RangeTblEntry (RTE) nodes.
- **`es_relations[rti]`** — opened Relation pointer for RTE rti;
  NULL until the executor calls `ExecGetRangeTableRelation`.
- **`es_rowmarks[rti]`** — ExecRowMark for SELECT FOR UPDATE /
  FOR SHARE; NULL if not marked.

The relations are opened lazily and held until executor end.

## es_snapshot — the visibility cutoff

```c
Snapshot   es_snapshot;
```

The MVCC snapshot used to test tuple visibility. Acquired at
plan start (per `xmin-horizon-management` rules) and held for
the entire execution. Important: snapshot is taken AT executor
start, NOT at query start; for repeatable-read isolation the
distinction matters.

`es_crosscheck_snapshot` is used during RI (referential
integrity) checks where a stricter snapshot is needed.

## es_output_cid — the DML command-id

```c
CommandId  es_output_cid;
```

For INSERT / UPDATE / DELETE queries, this is the `cmin` /
`cmax` written into new heap tuples. Comes from
`GetCurrentCommandId(true)` at executor start; advances when
the same transaction issues multiple DML statements.

`pg_xact_status` and visibility rules consult this to handle
"changes made in this command" semantics.

## es_result_relations — the DML target array

```c
ResultRelInfo **es_result_relations;
List          *es_opened_result_relations;
```

For INSERT / UPDATE / DELETE / MERGE statements, the target
tables get ResultRelInfo entries indexed by RT index.
`es_opened_result_relations` is a list of non-NULL entries (for
fast traversal during commit cleanup).

`es_tuple_routing_result_relations` holds ResultRelInfos
synthesized at runtime by partition-tuple-routing.

## es_query_cxt — the per-query memory pool

```c
MemoryContext  es_query_cxt;
```

All executor allocations that live for the duration of the
query (PlanState structs, ExprState compilations, ResultRelInfo,
etc.) go here. Distinct from per-tuple contexts (in ExprContext)
which reset per-row.

Freed wholesale by `FreeExecutorState`.

## es_param_list_info vs es_param_exec_vals

```c
ParamListInfo  es_param_list_info;     /* PARAM_EXTERN */
ParamExecData *es_param_exec_vals;     /* PARAM_EXEC */
```

Two parameter spaces:
- **EXTERN params** — bound from the client (e.g. `EXECUTE
  stmt(...)`); typically set once at start.
- **EXEC params** — internal slots set by InitPlan / SubPlan /
  nested-loop join (one slot per `PlannedStmt.paramExecTypes`
  entry).

ExprContext.ecxt_param_* fields point at these.

## Lifecycle

[from-code `execMain.c`]

```
QueryDesc → ExecutorStart
            ↓
            CreateExecutorState (sets up EState)
            InitPlan (populates fields, builds PlanState tree)
            ↓
           [tuples flow through ExecProcNode...]
            ↓
            ExecutorEnd
            ↓
            FreeExecutorState (frees es_query_cxt)
```

Snapshot pushed before ExecutorStart and popped after
ExecutorEnd by the caller (utility.c, SPI, portal).

## Common review-time concerns

- **`es_range_table` is 1-indexed** — entry 0 unused.
- **`es_relations[rti]` may be NULL** until opened lazily.
- **`es_snapshot` is shared** across the whole plan tree; don't
  replace mid-execution.
- **`es_output_cid` advances**; don't cache it.
- **`es_query_cxt` is reset wholesale** by FreeExecutorState;
  per-tuple state goes in ExprContext.
- **Adding a new EState field** requires init in
  `CreateExecutorState` AND cleanup in `FreeExecutorState`.

## Invariants

- **[INV-1]** One EState per top-level query execution.
- **[INV-2]** `es_range_table` indexed by RTE position; 0
  unused.
- **[INV-3]** `es_snapshot` held for entire execution.
- **[INV-4]** `es_output_cid` is the DML CID for written
  tuples.
- **[INV-5]** `es_query_cxt` is the long-lived alloc pool;
  per-tuple work uses ExprContext.

## Useful greps

- All EState field references:
  `grep -RIn 'estate->es_' source/src/backend/executor | head -20`
- EState constructors:
  `grep -n 'CreateExecutorState\|FreeExecutorState' source/src/backend/executor/execUtils.c | head -5`
- InitPlan:
  `grep -n '^InitPlan' source/src/backend/executor/execMain.c | head -5`

## Cross-references

- `knowledge/data-structures/planstate.md` — every PlanState
  points to one EState.
- `knowledge/data-structures/exprcontext.md` — ExprContext's
  ecxt_estate field links back to EState.
- `knowledge/data-structures/plannerinfo.md` — planner-side
  counterpart (PlannerInfo → EState transition at
  ExecutorStart).
- `knowledge/data-structures/tupletableslot.md` — slots live
  in es_tupleTable.
- `knowledge/idioms/snapshot-acquisition.md` — es_snapshot
  acquired here.
- `knowledge/idioms/commit-transaction-sequence.md` —
  es_query_cxt reset at xact end.
- `knowledge/subsystems/executor.md` — executor overview.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/include/nodes/execnodes.h` — full struct.
- `source/src/backend/executor/execMain.c` — ExecutorStart /
  InitPlan / ExecutorEnd.
- `source/src/backend/executor/execUtils.c` —
  CreateExecutorState / FreeExecutorState.
