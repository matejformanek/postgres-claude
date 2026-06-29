# pathnodes.h

- **Source:** `source/src/include/nodes/pathnodes.h` (~5000 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim (struct inventory)

## Purpose

The planner's **internal data structures**, especially `Path` nodes
(the candidate-plan representations the planner considers before
picking the cheapest). RelOptInfo, IndexOptInfo, Path, and friends
do NOT support `copyObject` — they're per-planning-cycle scratch
state. `:5-8` `[from-comment]`

## Key struct families

### Top-level planner state

- `PlannerGlobal` `:168` — per-query planner global state
  (subroots, paramExecTypes, finalrtable, finalrteperminfos, …).
- `PlannerInfo` `:300` — per-subquery planner state. Holds
  `parse` (the Query), `glob`, `query_level`, `parent_root`,
  `plan_params`, `outer_params`, `simple_rel_array`, the eclass list,
  `canon_pathkeys`, `query_pathkeys`, `join_info_list`,
  `placeholder_list`, `fkey_list`, …

### Strategy enums

- `PGS_*` constants `:18-40` and `pgs_mask` are the per-relation
  enable_* GUC bitmaps. Newish (post-PG-17) — gives extensions a way
  to disable specific scan strategies per rel.

### Relation / index info

- `RelOptInfo` `:1009` — the planner's view of a relation
  (base/join/group/upper rel). Carries `relids`, `rows`,
  `consider_startup`, `reltarget`, `pathlist`, `partial_pathlist`,
  `cheapest_*`, joininfo, fkey_list, partitioning info.
- `RelAggInfo` `:1284`, `IndexOptInfo` `:1346`,
  `ForeignKeyOptInfo` `:1460`, `StatisticExtInfo` `:1510`
- `PartitionSchemeData` `:722` + `PartitionScheme` typedef.

### Pathkeys & equivalence

- `JoinDomain` `:1561`, `EquivalenceClass` `:1653`,
  `EquivalenceMember` `:1714`, `PathKey` `:1806`,
  `GroupByOrdering` `:1828`

### Path nodes (all inherit `Path` `:1964`)

Base `Path` has `pathtype`, `parent` (RelOptInfo *), `pathtarget`,
`param_info`, `parallel_aware`, `parallel_safe`, `parallel_workers`,
`rows`, `disabled_nodes`, `startup_cost`, `total_cost`, `pathkeys`.

Subclasses:
- `IndexPath` `:2053`, `IndexClause` `:2099`
- `BitmapHeapPath` `:2128`, `BitmapAndPath` `:2140`,
  `BitmapOrPath` `:2153`
- `TidPath` `:2167`, `TidRangePath` `:2179`
- `SubqueryScanPath` `:2193`, `ForeignPath` `:2213`,
  `CustomPath` `:2249`
- `AppendPath` `:2281`, `MergeAppendPath` `:2308`,
  `GroupResultPath` `:2323`
- `MaterialPath` `:2335`, `MemoizePath` `:2346`
- `GatherPath` `:2369`, `GatherMergePath` `:2381`
- `JoinPath` `:2393`, `NestPath` `:2420`, `MergePath` `:2466`,
  `HashPath` `:2487`
- ProjectionPath, ProjectSetPath, SortPath, IncrementalSortPath,
  GroupPath, UpperUniquePath, AggPath, GroupingSetsPath,
  WindowAggPath, SetOpPath, RecursiveUnionPath, LockRowsPath,
  ModifyTablePath, LimitPath (further down in the file).

### Quals and restriction info

- `RestrictInfo`, `MergeScanSelCache`, `JoinDomain`, `PlaceHolderVar`,
  `PlaceHolderInfo`, `SpecialJoinInfo`, `RowIdentityVarInfo`,
  `MinMaxAggPath`, `MinMaxAggInfo`, etc. — full enumeration runs
  through the rest of the file.

### Costs

- `QualCost` `:118`, `AggClauseCosts` `:131`, `Selectivity` /
  `Cost` / `Cardinality` typedefs (from `nodes.h`).

## "We don't support copying RelOptInfo, IndexOptInfo, or Path"

`:5-7` — these structs are per-planning-cycle scratch. Some
subsidiary structs (Path, PathTarget, ...) **are** supported by
copy/out for debugging.

## Cross-references

- Implementation: every file under `src/backend/optimizer/`.
- Path → Plan: `optimizer/plan/createplan.c`.
- Path generation: `optimizer/path/*.c`,
  `optimizer/util/pathnode.c`.

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/plannerinfo.md](../../../../data-structures/plannerinfo.md)
- [data-structures/reloptinfo.md](../../../../data-structures/reloptinfo.md)
- [data-structures/restrictinfo.md](../../../../data-structures/restrictinfo.md)
