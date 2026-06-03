# planner.c — top-level planner pipeline and upper-rel construction

- **Source:** `source/src/backend/optimizer/plan/planner.c` (9345 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## 1. Purpose

The "query optimizer external interface" [from-comment:3]. Three intertwined
responsibilities:

1. **Outer shell** — `planner()` and `standard_planner()` set up the
   `PlannerGlobal`, decide parallel-mode eligibility, drive
   `subquery_planner()` on the top Query, pick the best Path off
   `(UPPERREL_FINAL, NULL)`, and hand it to `createplan.c`.
2. **Per-Query setup** — `subquery_planner()` does everything that must
   happen exactly once per Query node (prep passes, rewrites, hoisting,
   sublink/CTE handling) before calling `grouping_planner()`.
3. **Grouping/window/distinct/limit pipeline** — `grouping_planner()` and
   its many `create_*_paths()` helpers build the chain of upper RelOptInfos
   above the scan/join rel.

## 2. Public entry points

| Line | Function | Role |
|---|---|---|
| 333 | `planner` | Hook-respecting wrapper; calls `pgstat_report_plan_id` and returns `PlannedStmt *` [verified-by-code:333-348] |
| 351 | `standard_planner` | Sets up `PlannerGlobal`, computes `maxParallelHazard`/`parallelModeOK`, calls `subquery_planner`, picks `best_path`, runs `set_plan_references` and `SS_finalize_plan`, builds the `PlannedStmt` [verified-by-code:350-773] |
| 775 | `subquery_planner` | Per-Query: prep, sublink/CTE, expand_inherited_tables, pull-up subqueries, preprocess targetlist/qual, then `grouping_planner` [from-comment:758-771] |
| 1775 | `grouping_planner` | Per-Query upper pipeline: setops → group → window → distinct → order → limit → final [verified-by-code:1775-2521] |
| 1741 | `preprocess_phv_expression` | Used by `pullup_replace_vars` for PHV expressions [verified-by-code:1741] |
| 2851 | `select_rowmark_type` | Map `LockClauseStrength` → `RowMarkType`, used by `preprocess_rowmarks` and inheritance expansion [verified-by-code:2851] |
| 3102 | `limit_needed` | Probe Query for any non-trivial LIMIT/OFFSET; lets callers skip Limit-node planning when both are constant-0/NULL [verified-by-code:3102] |
| 6079 | `mark_partial_aggref` | Public helper: set `aggsplit` on an Aggref [verified-by-code:6079] |
| 6918 | `get_cheapest_fractional_path` | Best path for partial fetch (cursor/EXISTS); interpolates startup→total [verified-by-code:6918] |
| 7081 | `expression_planner` | Plan a standalone Expr (no Query): fix_opfuncids + eval_const_expressions [verified-by-code:7081] |
| 7108 | `expression_planner_with_deps` | Same + invalidation deps for cached plans [verified-by-code:7108] |
| 7161 | `plan_cluster_use_sort` | CLUSTER chooser: sort-then-write or indexscan [verified-by-code:7161] |
| 7282 | `plan_create_index_workers` | Parallel CREATE INDEX worker count [verified-by-code:7282] |
| 8733 | `create_unique_paths` | Public so FDWs etc. can request DISTINCT-on-join paths [verified-by-code:8733] |
| 9285 | `choose_plan_name` | Pick a unique name for a CachedPlan; respects `always_number` [verified-by-code:9285] |

## 3. Pipeline at a glance — `standard_planner`

`PlannerGlobal` zero-init [verified-by-code:371-395] →
parallel-hazard probe (skipped if not SELECT, modifying CTE,
parallel worker, etc.) [verified-by-code:418-434] →
`debug_parallel_query` may force `parallelModeNeeded=true`
[from-comment:436-451] → `subquery_planner(glob, parse, …, top-level
tuple_fraction)` → fetch `final_rel = fetch_upper_rel(root, UPPERREL_FINAL,
NULL)` → `best_path = final_rel->cheapest_total_path` → `create_plan` →
`set_plan_references` → `SS_finalize_plan` → wrap into PlannedStmt with
relationOids/invalItems/paramExecTypes.

### Hooks
- `planner_hook` — wraps the whole standard_planner [verified-by-code:74,338]
- `planner_setup_hook` / `planner_shutdown_hook` — fire around PlannerGlobal
  lifecycle [verified-by-code:77-80]
- `create_upper_paths_hook` — called by `grouping_planner` after each upper
  rel is built; lets extensions add custom paths to grouped/window/distinct/
  ordered/final rels [verified-by-code:83]

## 4. `subquery_planner` — what runs once per Query

In order, the load-bearing passes (see comment block at line 758-771 and
function body 775-1405):

1. Allocate PlannerInfo, link to parent_root for subqueries
2. Inherit `query_level`, snap `placeholdersFrozen=false`
3. Prep: `transform_MERGE_to_join`, `replace_empty_jointree`,
   `pull_up_sublinks`, `preprocess_function_rtes`,
   `expand_inherited_tables`, `pull_up_subqueries`,
   `flatten_simple_union_all`, `reduce_outer_joins`,
   `remove_useless_result_rtes`
4. `preprocess_qual_conditions` (recurse jointree, eval_const_expressions
   each qual)
5. `preprocess_expression` per top-level expression kind
   (`EXPRKIND_QUAL`, `EXPRKIND_TARGET`, etc. — 14 kinds defined at lines
   87-100) [verified-by-code:1407]
6. `inline_set_returning_functions`, `contain_subplans` shortcuts
7. Eventually `grouping_planner(root, tuple_fraction, setops)` (the inner
   loop)
8. Finalize: `find_minmax_aggs_walker` etc., attach `final_rel` paths

## 5. `grouping_planner` — upper-rel chain (line 1775)

Builds, in this order, RelOptInfos at well-known kinds (`UPPERREL_*`):

```
UPPERREL_SETOP        (setops only)
UPPERREL_GROUP_AGG    (grouping/aggregation)
UPPERREL_WINDOW       (window functions)
UPPERREL_PARTIAL_DISTINCT + UPPERREL_DISTINCT
UPPERREL_ORDERED      (final ORDER BY)
UPPERREL_FINAL        (LIMIT/LockRows/ModifyTable)
```

Each step takes the previous `current_rel` and produces the next by calling
the matching `create_*_paths`:

| Line | Helper | UPPERREL |
|---|---|---|
| 4121 | `create_grouping_paths` | GROUP_AGG [verified-by-code:4120] |
| 4374 | `create_ordinary_grouping_paths` | GROUP_AGG (non-degenerate) |
| 4866 | `create_window_paths` | WINDOW |
| 5124 | `create_distinct_paths` | DISTINCT |
| 5194 | `create_partial_distinct_paths` | PARTIAL_DISTINCT (for parallel) |
| 5642 | `create_ordered_paths` | ORDERED |
| 4234 | `make_grouping_rel` | construct the grouped RelOptInfo |

Subroutines worth knowing:
- `create_ordinary_grouping_paths` decides among sort/hash/partial-agg
  and may call `create_partitionwise_grouping_paths` (line 8454)
  [verified-by-code:8454].
- `add_paths_to_grouping_rel` (line 7416) is where each sort-based and
  hash-based agg path actually gets constructed via
  `create_agg_path`/`create_group_path`. Called from
  `create_ordinary_grouping_paths`.
- `gather_grouping_paths` (line 8088) generates Gather/Gather Merge above
  partial-aggregation paths.
- `apply_scanjoin_target_to_paths` (line 8213) is the critical step that
  pushes the final scan/join PathTarget through every path in the input
  rel before grouping; also drives final-pathtarget Gather generation.

### Key flag/condition macros

- `GROUPING_CAN_USE_SORT` / `GROUPING_CAN_USE_HASH` /
  `GROUPING_CAN_PARTIAL_AGG` — flags assembled in `create_grouping_paths`
  to gate which strategies are tried [verified-by-code:4166-4197].
- `PARTITIONWISE_AGGREGATE_FULL` / `_PARTIAL` / `_NONE` — gating from
  `enable_partitionwise_aggregate` GUC [verified-by-code:4211-4214].

## 6. Window function planning

- `optimize_window_clauses` (line 6152): rewrite eligible window-defined
  aggregates (`min/max`-of-window-context) to use inverse aggregation when
  the WindowAgg has a frame end clause.
- `select_active_windows` (line 6292) + `name_active_windows` (line 6375)
  + `common_prefix_cmp` (line 6426): sort WindowClauses to maximize
  pathkeys reuse.
- `make_pathkeys_for_window` (line 6615): pathkeys representing a
  WindowClause's PARTITION+ORDER.
- `make_window_input_target` (line 6495): build the PathTarget the
  window's input must produce.
- `create_one_window_path` (line 4954): build a single WindowAgg path
  from an input subpath.

## 7. SRF handling — `adjust_paths_for_srfs` (line 6965)

When any tlist contains set-returning functions, each Path in `rel` is
wrapped with one or more `ProjectSetPath`s, splitting the tlist into
SRF-free targets and SRF-bearing levels. The `targets` /
`targets_contain_srfs` machinery in `grouping_planner` is what feeds this.

## 8. Partition-wise grouping

- `create_partitionwise_grouping_paths` (line 8454): recurses through
  `rel->part_rels`, creates a grouped child rel per partition, merges via
  `add_paths_to_append_rel`.
- `group_by_has_partkey` (line 8591): tested to choose between
  PARTITIONWISE_AGGREGATE_FULL and PARTITIONWISE_AGGREGATE_PARTIAL.

## 9. Invariants and surprises

- **`parallelModeOK` cannot change after the prelude.** Comment is explicit
  ("Note that parallelModeOK can't change after this point.")
  [from-comment:444]. `parallelModeNeeded` flips later inside
  `create_gather_plan` / `create_gather_merge_plan` [from-comment:436-439].
- **Parallel CTAS/SELECT INTO/CMV is safe only because the new heap is
  invisible to workers.** Comment 404-411 flags that we'd have to fix
  group-locking before allowing parallel inserts in general
  [from-comment:404-411].
- **`subquery_planner` must NOT be re-entered on the same Query** (only on
  a sub-Query). `grouping_planner` is kept separately so it could be
  invoked recursively if we ever needed to, but currently isn't
  [from-comment:758-762].
- **`UPPERREL_FINAL` always exists** post-planner. The hook
  `create_upper_paths_hook` is called for every upper kind in turn.
- **`debug_parallel_query`** can force parallelization globally to exercise
  worker paths during regression — controls Gather insertion regardless of
  cost [from-comment:436-451].
- **`processed_tlist` vs `parse->targetList`** — Plan's `targetList` is
  rebuilt from PathTarget repr but the original `processed_tlist` carries
  resnames / decorative info that must be transferred at the end (see
  `apply_tlist_labeling` in createplan.c). [from-comment:1902-1907]

## 10. Cross-refs

- Inner pipeline ordering: `knowledge/files/src/backend/optimizer/plan/planmain.c.md`
- Architectural overview: `knowledge/architecture/planner.md`
- Subsystem index: `knowledge/subsystems/optimizer.md`
- Path→Plan translation: `knowledge/files/src/backend/optimizer/plan/createplan.c.md`
- Path-adding mechanics: `knowledge/files/src/backend/optimizer/util/pathnode.c.md`

## 11. Tags
`[verified-by-code]` ×19, `[from-comment]` ×10

## Synthesized by
<!-- backlinks:auto -->
- [idioms/parser-pipeline.md](../../../../../idioms/parser-pipeline.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
