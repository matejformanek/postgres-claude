# allpaths.c — base-rel pathlists + join search driver

- **Source:** `source/src/backend/optimizer/path/allpaths.c` (4972 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

"Routines to find possible search paths for processing a query"
[from-comment:3-4]. Two coupled responsibilities:

1. **Base-rel path generation:** for every baserel, build size estimates,
   parallel-eligibility flags, and the initial `pathlist` (seqscan,
   index paths via `indxpath.c`, tid/bitmap, subquery pushdown for
   RTE_SUBQUERY, function/values/CTE access paths).
2. **Join search:** drive the dynamic-programming search over `joinlist`
   (or fall back to GEQO or a plugin), producing the single final
   RelOptInfo for the whole jointree.

## 2. Sole top-level entry

`make_one_rel(root, joinlist)` at line 179 — called from `planmain.c:
query_planner`. Returns the joined RelOptInfo whose
`cheapest_total_path` represents the cheapest scan/join plan.
[verified-by-code:178-248]

Sequence inside [verified-by-code:185-247]:

1. `set_base_rel_consider_startup` — set `consider_param_startup` on
   SEMI/ANTI-RHS base rels
2. `set_base_rel_sizes` — for each baserel: maybe
   `set_rel_consider_parallel`, then `set_rel_size`
3. `setup_simple_grouped_rels` — eager-aggregation grouped variants
4. Compute `root->total_table_pages` (skip dummy rels; appendrels are
   double-count-safe because parents have pages=0) [from-comment:204-207]
5. `set_base_rel_pathlists` — for each baserel: `set_rel_pathlist`
6. `rel = make_rel_from_joinlist(root, joinlist)` — runs join search
7. Assert `rel->relids == root->all_query_rels`

## 3. Per-rel size / pathlist dispatch

`set_rel_size` (line 407) and `set_rel_pathlist` (line 516) dispatch on
`rel->rtekind` and `rte->inh`:

| rtekind / case | size helper | pathlist helper |
|---|---|---|
| `rte->inh` (appendrel parent) | `set_append_rel_size` (1022) | `set_append_rel_pathlist` (1317) |
| RELATION + foreign | `set_foreign_size` (980) | `set_foreign_pathlist` (1004) |
| RELATION + tablesample | `set_tablesample_rel_size` (892) | `set_tablesample_rel_pathlist` (932) |
| RELATION (plain) | `set_plain_rel_size` (627) | `set_plain_rel_pathlist` (834) |
| SUBQUERY | (handled inline in `set_rel_size`) | `set_subquery_pathlist` (2679) |
| FUNCTION | — | `set_function_pathlist` (2948) |
| TABLEFUNC | — | `set_tablefunc_pathlist` (3035) |
| VALUES | — | `set_values_pathlist` (3015) |
| CTE | — | `set_cte_pathlist` (3059) |
| NAMEDTUPLESTORE | — | `set_namedtuplestore_pathlist` (3138) |
| RESULT | — | `set_result_pathlist` (3165) |
| WORKTABLE | — | `set_worktable_pathlist` (3192) |

If `rel->reloptkind == RELOPT_BASEREL` and rel is not the topmost
scan/join rel, `generate_useful_gather_paths(root, rel, false)` runs at
the end of `set_rel_pathlist` (line 604), then `set_cheapest`.
[verified-by-code:602-607]

The `set_rel_pathlist_hook` fires after core but before gather/cheapest
— extensions can add/delete paths via `add_path`/`add_partial_path`
[verified-by-code:585-587, from-comment:580-586].

## 4. Plain rel: `set_plain_rel_pathlist` (line 834)

```
create_seqscan_path(root, rel, NULL, 0)  → add_path
create_plain_partial_paths(rel)           → add_partial_path (line 872)
create_index_paths(root, rel)             → indxpath.c
create_tidscan_paths(root, rel)           → tidpath.c
```

## 5. Subquery pushdown machinery

Pre-`set_subquery_pathlist` qual-pushdown logic:

- `subquery_is_pushdown_safe` (line 4143) — recurses subquery; sets
  `pushdown_safety_info` flags per output column
  (UNSAFE_HAS_VOLATILE_FUNC / SET_FUNC /
  NOTIN_DISTINCTON_CLAUSE / NOTIN_PARTITIONBY_CLAUSE / TYPE_MISMATCH;
  bitmask defined at lines 54-59) [verified-by-code:54-69]
- `recurse_pushdown_safe` (line 4199) — set-op walk
- `check_output_expressions` (line 4267)
- `compare_tlist_datatypes` (line 4368)
- `targetIsInAllPartitionLists` (line 4402)
- `qual_is_pushdown_safe` (line 4444) — final per-qual verdict
  (PUSHDOWN_UNSAFE / PUSHDOWN_SAFE / [there's also a tagged third
  state — see enum at line 72]) [verified-by-code:71-77]
- `subquery_push_qual` (line 4545) / `recurse_push_qual` (line 4593) —
  rewrite quals onto subquery's `jointree->quals` (or set-op branches)
- `remove_unused_subquery_outputs` (line 4645) — drop unreferenced
  subquery tlist entries when safe

Window-runcondition optimization (lines 2415-2677):
`find_window_run_conditions` / `check_and_push_window_quals` lets
quals like `row_number() OVER ... <= N` be pushed below the window
to enable shortcut termination.

## 6. Appendrel handling

- `set_append_rel_size` (line 1022) — recurse children:
  `set_rel_size` each, then `set_baserel_size_estimates` for parent
  using totals. Marks parent dummy if every child is dummy.
- `set_append_rel_pathlist` (line 1317) — recurse children, then call
  `add_paths_to_append_rel` (line 1416) to produce union AppendPath /
  MergeAppendPath / parallel-aware variants.
- `add_paths_to_append_rel` is the **biggest function in the file**
  (~430 lines): considers parallel append, ordered append via pathkeys,
  partition-wise eligibility, fractional-cost cheapest-startup paths.
- `generate_orderedappend_paths` (line 1848) — choose MergeAppend or
  Append-of-sorted-children depending on per-child sort cost.
- `get_cheapest_parameterized_child_path` (line 2164) — for parameterized
  AppendPaths, each child must produce a same-parameterization path
  (reparameterize if needed).
- `accumulate_append_subpath` (line 2252) — append/flatten Append/MergeAppend
  trees so we don't end up with nested Appends.

## 7. Join search

`make_rel_from_joinlist` (line 3843) — entry point, decides between
plugin, GEQO, and standard search [verified-by-code:3909-3914]:

```c
if (join_search_hook)
    return (*join_search_hook)(root, levels_needed, initial_rels);
else if (enable_geqo && levels_needed >= geqo_threshold)
    return geqo(root, levels_needed, initial_rels);
else
    return standard_join_search(root, levels_needed, initial_rels);
```

`standard_join_search` (line 3948) — the DP algorithm:
[verified-by-code:3948-4099]

```
join_rel_level = palloc0((levels_needed+1) * sizeof(List*));
join_rel_level[1] = initial_rels;
for lev in 2..levels_needed:
    join_search_one_level(root, lev);        # joinrels.c
    foreach rel in join_rel_level[lev]:
        generate_partitionwise_join_paths(root, rel);
        if (!is_top_rel) generate_useful_gather_paths(root, rel, false);
        set_cheapest(rel);
        if rel has grouped_rel and !is_top_rel:
            generate_grouped_paths(...); set_cheapest(grouped);
```

The function **must not be re-entered** within one planning problem —
asserted via `Assert(root->join_rel_level == NULL)`
[verified-by-code:3957, from-comment:3953-3955].

`join_search_one_level` itself lives in `joinrels.c` — see that file's
doc.

## 8. Gather-path generation

- `generate_gather_paths` (line 3251): simple Gather on top of every
  partial path (unordered).
- `generate_useful_gather_paths` (line 3388): also tries GatherMerge for
  each "useful" pathkey list returned by `get_useful_pathkeys_for_relation`
  (line 3320).
- Both bypass when there are no partial paths.
- For the topmost scan/join rel, gather generation is **postponed** until
  the final tlist is applied (see `apply_scanjoin_target_to_paths` in
  planner.c) — comment at line 599-601 explains why.

## 9. Partition-wise join

`generate_partitionwise_join_paths` (line 4882) — called from the join
search loop after each level is done [from-comment:4877-4880]. Recurses
through `rel->part_rels`, calls `set_cheapest` on each live child, then
`add_paths_to_append_rel(rel, live_children)`. If all children dummy,
parent is marked dummy. Must not be called before all child-join paths
are added (it could otherwise hold references to paths `add_path` later
deletes).

## 10. Parallel-worker count

`compute_parallel_worker` (line 4794) — log-base-3 scaling for both heap
and index pages: starting from `min_parallel_table_scan_size`, double…
actually multiply threshold by 3 each step until pages no longer fit;
capped at `max_workers`. [verified-by-code:4826-4869] Returns 0 below
the minimum unless rel is an inheritance child (sibling totals may
still justify it) [from-comment:4807-4814].

## 11. `set_rel_consider_parallel` — eligibility rules

Line 644-832 walks every RTE type and disqualifies it if any of:

- parse->parallelModeOK false
- volatile/parallel-unsafe expressions in `reltarget` / `baserestrictinfo`
- table-AM is not parallel-safe (per `relation_is_parallel_safe`)
- foreign table not advertising `IsForeignScanParallelSafe`
- SubqueryScan whose subquery has parallel-unsafe parts
- CTE / WorkTable (no parallel support)

## 12. Invariants & surprises

- **Pruning happens during `set_append_rel_size`**: partition pruning
  with constant quals reduces `live_parts` before sizes are summed
  [inferred from inherit.c interaction].
- **Dummy rel propagation:** `set_dummy_rel_pathlist` (line 2366)
  installs a single empty AppendPath; later code uses `IS_DUMMY_REL`
  macro to skip these.
- **`recurse_push_qual` vs `subquery_push_qual`:** set-op subqueries
  must push a copy to each branch (`recurse_push_qual`); plain ones
  push once (`subquery_push_qual`).
- **`set_subquery_pathlist` is in `set_rel_size`**, not in
  `set_rel_pathlist` — paths are added during sizing because subquery
  planning produces both at once.
- **Window-quals optimization can drop quals from baserestrictinfo
  but leave selectivity in place** — the runcondition is enforced
  inside the WindowAgg.

## 13. Cross-refs

- Join enumeration mechanism: `knowledge/files/src/backend/optimizer/path/joinrels.c.md`
- Per-pair path generation: `knowledge/files/src/backend/optimizer/path/joinpath.c.md`
- Index paths: `knowledge/files/src/backend/optimizer/path/indxpath.c.md`
- Cost functions: `knowledge/files/src/backend/optimizer/path/costsize.c.md`
- Path-add discipline: `knowledge/files/src/backend/optimizer/util/pathnode.c.md`
- Architecture: `knowledge/architecture/planner.md`, `knowledge/subsystems/optimizer.md`

## 14. Tags
`[verified-by-code]` ×13, `[from-comment]` ×7, `[inferred]` ×1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [data-structures/plannerinfo.md](../../../../../data-structures/plannerinfo.md)
- [data-structures/reloptinfo.md](../../../../../data-structures/reloptinfo.md)

