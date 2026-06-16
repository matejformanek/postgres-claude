# plannodes.h

- **Source:** `source/src/include/nodes/plannodes.h` (~1700 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim (struct inventory)

## Purpose

Definitions of the **plan tree** — the planner's output and the
executor's input. Each Plan node typically has a sibling
`PlanState` in `execnodes.h`.

## Top-level

- `PlannedStmt` `:59` — wrapper around the root Plan, carrying
  `commandType`, `queryId`, `hasReturning`, `hasModifyingCTE`,
  `canSetTag`, `transientPlan`, `dependsOnRole`, `parallelModeNeeded`,
  `jitFlags`, `planTree`, `partPruneInfos`, `rtable`, `permInfos`,
  `resultRelations`, `appendRelations`, `subplans`, `rewindPlanIDs`,
  `rowMarks`, `relationOids`, `invalItems`, `paramExecTypes`,
  `utilityStmt`, `stmt_location`, `stmt_len`, `planOrigin`.
- `PlannedStmtOrigin` `:39` enum — UNKNOWN / INTERNAL / STANDARD /
  CACHE_GENERIC / CACHE_CUSTOM.

## `Plan` base struct `:191`

The common header for every plan node: `startup_cost`, `total_cost`,
`plan_rows`, `plan_width`, `parallel_aware`, `parallel_safe`,
`async_capable`, `plan_node_id`, `targetlist`, `qual`, `lefttree`,
`righttree`, `initPlan`, `extParam`, `allParam`.

## Plan node taxonomy

### Result / utility

- `Result` `:301`, `ProjectSet` `:315`, `ModifyTable` `:336`,
  `Append` `:398`, `MergeAppend` `:433`, `RecursiveUnion` `:479`,
  `BitmapAnd` `:510`, `BitmapOr` `:524`

### Scans (all inherit `Scan` `:538`)

- `SeqScan` `:551`, `SampleScan` `:560`
- `IndexScan` `:604`, `IndexOnlyScan` `:654`, `BitmapIndexScan` `:688`,
  `BitmapHeapScan` `:710`
- `TidScan` `:725`, `TidRangeScan` `:739`
- `SubqueryScan` `:773`, `FunctionScan` `:784`, `ValuesScan` `:797`,
  `TableFuncScan` `:808`, `CteScan` `:819`,
  `NamedTuplestoreScan` `:832`, `WorkTableScan` `:843`
- `ForeignScan` `:890`, `CustomScan` `:932`

### Joins (all inherit `Join` `:984`)

- `NestLoop` `:1006`, `NestLoopParam` `:1013`,
  `MergeJoin` `:1035`, `HashJoin` `:1064`

### Materialization / sort / aggregation / window / set ops

- `Material` `:1082`, `Memoize` `:1091`
- `Sort` `:1143`, `IncrementalSort` `:1167`
- `Group` `:1180`, `Agg` `:1209`, `WindowAgg` `:1251`
- `Unique`, `Gather`, `GatherMerge`, `Hash`, `SetOp`, `LockRows`,
  `Limit` follow further down.

### Auxiliary

- `PlanRowMark`, `PartitionPruneInfo`, `PartitionedRelPruneInfo`,
  `PartitionPruneStep*` — partition-pruning machinery.

## "Plan nodes never appear in stored parse trees"

So the README notes that altering a Plan node type does **not**
require a CATALOG_VERSION bump. `nodes/README:113-115` `[from-README]`

## Cross-references

- Sibling: `execnodes.h` (PlanState executor-state nodes).
- Path → Plan conversion: `optimizer/plan/createplan.c`.
- Idiom: `knowledge/idioms/node-types-and-lists.md`.

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->
