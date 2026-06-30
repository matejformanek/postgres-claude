# costsize.c — cost and size estimation for every Path

- **Source:** `source/src/backend/optimizer/path/costsize.c` (6774 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

"Routines to compute (and set) relation sizes and path costs."
[from-comment:3-5]. Owns every `cost_*` function called by `pathnode.c`
constructors and `joinpath.c`, and every `set_*_size_estimates` helper
called from `allpaths.c`.

## 2. Cost model — the GUCs

Costs are in arbitrary units anchored by these tunables
[from-comment:6-30, verified-by-code:131-167]:

| GUC | Default | Meaning |
|---|---|---|
| `seq_page_cost` | 1.0 | sequential page fetch |
| `random_page_cost` | 4.0 | non-sequential page fetch |
| `cpu_tuple_cost` | 0.01 | per-tuple CPU |
| `cpu_index_tuple_cost` | 0.005 | per-index-tuple CPU |
| `cpu_operator_cost` | 0.0025 | per-operator/function CPU |
| `parallel_tuple_cost` | 0.1 | tuple shipped worker→leader |
| `parallel_setup_cost` | 1000.0 | per-Gather setup |
| `recursive_worktable_factor` | 10.0 | worktable size multiplier |
| `effective_cache_size` | (pages) | OS+PG cache for index correlation/Mackert-Lohman |
| `disable_cost` | 1e10 | legacy huge constant; now *only* used as a step-cost cap, see "disabled_nodes" below |

Per-tablespace `seq_page_cost` / `random_page_cost` overrides are honored
via `get_tablespace_page_costs` (in spccache.c) — but never for temp work
files (sort/material spill) [from-comment:32-36].

## 3. The "disabled_nodes" mechanism

[from-comment:53-62] — Every Path carries an integer count of disabled
plan nodes at or below it. `add_path` (in pathnode.c) treats this as a
**lexicographic primary key** for cost comparison: a path with fewer
disabled nodes always wins, regardless of fuzzy total_cost. This replaced
the old "add `disable_cost` (1e10) to startup_cost" hack which "distorted
planning in other ways" [from-comment:60-62].

Each `cost_*` function computes `path->disabled_nodes` by checking the
matching `pgs_mask` bit against the corresponding `enable_*` GUC. Pattern
(from `cost_seqscan` lines 279, 335-336) [verified-by-code:269-339]:

```c
uint64 enable_mask = PGS_SEQSCAN;
...
if (path->parallel_workers == 0)
    enable_mask |= PGS_CONSIDER_NONPARTIAL;
path->disabled_nodes =
    (baserel->pgs_mask & enable_mask) == enable_mask ? 0 : 1;
```

## 4. Two-cost model

Every Path stores `startup_cost` and `total_cost` [from-comment:37-45].
Partial fetches are linearly interpolated:

```
actual = startup_cost + (total_cost - startup_cost) * tuples_fetched / rows
```

LIMIT applies as a top-level plan node, so `path->rows` is set without
regard to LIMIT [from-comment:46-50]. `rows == 0` only for
provably-empty rels (dummy paths) — beware division-by-zero
[from-comment:48-50].

## 5. Public cost functions (every Path type)

### Base-rel scans

| Line | Function | Notes |
|---|---|---|
| 270 | `cost_seqscan` | disk = seq_page_cost * baserel->pages; tlist cost paid per output row [verified-by-code:269-339] |
| 349 | `cost_samplescan` | TableSample-aware, random vs seq depending on `NextSampleBlock` |
| 545 | `cost_index` | Mackert-Lohman cache model; uses index am-specific `amcostestimate` [verified-by-code:543-578]; central + complex |
| 1012 | `cost_bitmap_heap_scan` | Heap fetch after bitmap; cap selectivity ≥ 1 page |
| 1115 | `cost_bitmap_tree_node` | Per-leaf indexscan cost (used by And/Or) |
| 1158 | `cost_bitmap_and_node` | Multiply selectivities; sum costs |
| 1203 | `cost_bitmap_or_node` | OR-of-selectivities |
| 1251 | `cost_tidscan` | TID list scan |
| 1361 | `cost_tidrangescan` | TID range scan |
| 1478 | `cost_subqueryscan` | Add cpu_tuple_cost per row |
| 1563 | `cost_functionscan` | Per-RangeFunction tuple-and-page cost |
| 1629 | `cost_tablefuncscan` | XMLTABLE, JSON_TABLE |
| 1690 | `cost_valuesscan` | VALUES list |
| 1745 | `cost_ctescan` | Materialized CTE |
| 1791 | `cost_namedtuplestorescan` | trigger transition tables |
| 1833 | `cost_resultscan` | RTE_RESULT |
| 1875 | `cost_recursive_union` | rterm + nrterm * recursive_worktable_factor scaling |

### Sort/Material/Memoize

| Line | Function | Notes |
|---|---|---|
| 1951 | `cost_tuplesort` | Internal; N log N cmp model; disk-sort blocks via `relation_byte_size` |
| 2053 | `cost_incremental_sort` | Per-group cost based on `presorted_keys` |
| 2201 | `cost_sort` | Thin wrapper around `cost_tuplesort` |
| 2583 | `cost_material` | Spool subpath; sort-disk math when over work_mem |
| 2641 | `cost_memoize_rescan` | Per-rescan hit/miss expectation |

### Joins (split: initial / final)

Each join cost is computed in two phases — `initial_cost_*` produces a
JoinCostWorkspace cheap enough to use as an early-cut threshold inside
joinpath.c, then `final_cost_*` re-uses the workspace and fills the Path:

| Lines | Pair | Notes |
|---|---|---|
| 3373 / 3455 | `initial_cost_nestloop` / `final_cost_nestloop` | uses `has_indexed_join_quals` (5355) for inner-rescan cost |
| 3658 / 3955 | `initial_cost_mergejoin` / `final_cost_mergejoin` | uses `cached_scansel` (4217) per merge clause |
| 4297 / 4416 | `initial_cost_hashjoin` / `final_cost_hashjoin` | Estimates batches, bucket-fill, parallel hash sharing |

`MergeScanSelCache` (line 4217) caches `mergejoinscansel` lookups per
RestrictInfo/pathkey combo to avoid redundant selectivity work.

### Aggregation/Window/Group/Append/MergeAppend/Gather

| Line | Function |
|---|---|
| 430 | `cost_gather` |
| 470 | `cost_gather_merge` |
| 2234 | `append_nonpartial_cost` (helper) |
| 2310 | `cost_append` |
| 2525 | `cost_merge_append` |
| 2787 | `cost_agg` (Plain/Hash/Sorted) |
| 2989 | `get_windowclause_startup_tuples` |
| 3203 | `cost_windowagg` |
| 3300 | `cost_group` |

### SubPlan / Re-scan / Qual eval

| Line | Function |
|---|---|
| 4676 | `cost_subplan` — SubLink/sub-SELECT |
| 4784 | `cost_rescan` — Material/Memoize/CTE rescan factor |
| 4899 | `cost_qual_eval` |
| 4925 | `cost_qual_eval_node` |
| 4939 | `cost_qual_eval_walker` |
| 5215 | `get_restriction_qual_cost` |

### Selectivity helpers for joins

- `compute_semi_anti_join_factors` (line 5257) — match_count/match_frac
  for SEMI/ANTI joins
- `has_indexed_join_quals` (line 5354) — used to amortize nestloop inner
  rescan
- `approx_tuple_count` (line 5447) — rough joincount estimate (no real
  selectivity computation) used by predicate/inheritance heuristics

## 6. Size estimation entry points

`set_*_size_estimates` write `rel->rows`, `rel->reltarget->width`
[verified-by-code:5492-6324]:

| Line | Function | Caller |
|---|---|---|
| 5492 | `set_baserel_size_estimates` | allpaths.c set_plain_rel_size etc |
| 5522 | `get_parameterized_baserel_size` | joinpath.c when building param paths |
| 5571 | `set_joinrel_size_estimates` | joinrels.c build_join_rel |
| 5603 | `get_parameterized_joinrel_size` | joinpath.c |
| 5644 | `calc_joinrel_size_estimate` | inner core — uses FK shortcuts |
| 5794 | `get_foreign_key_join_selectivity` | Drops FK-matching clauses, uses FK semantics |
| 6046 | `set_subquery_size_estimates` | allpaths.c after subquery planning |
| 6126 | `set_function_size_estimates` | |
| 6164 | `set_tablefunc_size_estimates` | |
| 6186 | `set_values_size_estimates` | |
| 6218 | `set_cte_size_estimates` | |
| 6256 | `set_namedtuplestore_size_estimates` | |
| 6289 | `set_result_size_estimates` | |
| 6318 | `set_foreign_size_estimates` | (just calls FDW GetForeignRelSize) |
| 6353 | `set_rel_width` | per-rel width from per-attr stats / typmod |

### Outer-join handling in `calc_joinrel_size_estimate`

Separates `joinquals` (JOIN/ON conditions) from `pushedquals` (down from
WHERE) by `RINFO_IS_PUSHED_DOWN` test, then applies `clauselist_selectivity`
to each list independently [verified-by-code:5686-5717]. This is what
gives outer joins their "left-side-rows × inner-selectivity + nulled rows"
estimate.

## 7. Clamping and helpers

| Line | Function | Purpose |
|---|---|---|
| 214 | `clamp_row_est` | `max(MIN_TUPLES=1.0, round(nrows)) ≤ MAXIMUM_ROWCOUNT (1e100)` to keep `add_path` sane [from-comment:123-128] |
| 243 | `clamp_width_est` | Cap tuple width to MaxAllocSize-ish |
| 896 | `index_pages_fetched` | Mackert-Lohman effective-cache model |
| 962 | `get_indexpath_pages` | Pages touched by a bitmap subtree |
| 6510 | `set_pathtarget_cost_width` | Compute PathTarget.cost from its `exprs` |
| 6597 | `relation_byte_size` | tuples × width, used for sort-tape calc |
| 6608 | `page_size` | bytes / BLCKSZ |
| 6618 | `get_parallel_divisor` | Effective worker count counting leader-participation discount [verified-by-code:6618] |
| 6658 | `compute_bitmap_pages` | Heap pages a bitmap will visit |
| 6769 | `compute_gather_rows` | Per-leader rows produced by Gather |

## 8. Foreign-key selectivity (the FK shortcut)

`get_foreign_key_join_selectivity` (line 5794) is the optimization that
keeps FK joins on full PKs from over-estimating: if every column of an
FK constraint is matched by `=` operators in `restrictlist`, those
clauses are removed and one consolidated selectivity = `1.0 / outer_rows`
is applied. Significantly fixes the n-way join blowup for star schemas.

## 9. Invariants & surprises

- **Most cost_* helpers receive a Path only as output:** "the passed
  result Path [is used] only to store their results … input data … is
  passed as separate parameters" [from-comment:64-71]. **Exception:**
  `cost_index` and the `cost_<join>` family expect the Path filled in
  except for output fields.
- **`MAXIMUM_ROWCOUNT = 1e100`** is the cap that prevents Infinity/NaN
  in cost math: comment "add_path() wouldn't act sanely given infinite
  or NaN cost values" [from-comment:124-127, verified-by-code:129].
- **Tlist cost is per output row, not per scanned tuple** — every
  cost_*scan helper adds `pathtarget->cost.startup` to startup and
  `pathtarget->cost.per_tuple * path->rows` to run cost
  [verified-by-code:307-309 cost_seqscan, repeated everywhere].
- **Parallel divisor is fractional** — leader participation discount
  approximation. See `get_parallel_divisor` for the formula
  (worker count - leader-cost-fraction).
- **`disable_cost` is still defined (1.0e10)** but with disabled_nodes,
  it's mostly a step ceiling rather than a tiebreaker. Some legacy
  call sites still add it directly; the lexicographic disabled_nodes
  test trumps it.
- **`approx_tuple_count`** uses a simpler model than full clauselist
  selectivity — explicit "fast-but-wrong" approximation
  [verified-by-code:5447].

## 10. Cross-refs

- Idiom: `knowledge/idioms/optimizer-costing.md` (to be written)
- Selectivity functions: `source/src/backend/utils/adt/selfuncs.c`
- Path-adding mechanics: `knowledge/files/src/backend/optimizer/util/pathnode.c.md`
- Join enumeration that consumes these costs: `knowledge/files/src/backend/optimizer/path/joinpath.c.md`
- Architecture: `knowledge/architecture/planner.md`,
  `knowledge/subsystems/optimizer.md`

## 11. Tags
`[verified-by-code]` ×13, `[from-comment]` ×13

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/aggregate-hash-vs-sort.md](../../../../../idioms/aggregate-hash-vs-sort.md)
- [idioms/cost-join-paths.md](../../../../../idioms/cost-join-paths.md)
- [idioms/cost-parallel-adjustments.md](../../../../../idioms/cost-parallel-adjustments.md)
- [idioms/cost-scan-paths.md](../../../../../idioms/cost-scan-paths.md)
- [idioms/cost-units-gucs.md](../../../../../idioms/cost-units-gucs.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new cost-model constant (and optional GUC)](../../../../../scenarios/add-new-cost-model-knob.md)
- [Scenario — Add a new plan node](../../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->

