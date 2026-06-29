# relnode.c — RelOptInfo construction and lookup

- **Source:** 3219 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## 1. Purpose

All RelOptInfo creation (baserel, otherrel, joinrel, grouped-rel, upper)
and lookup (`find_base_rel`, `find_join_rel`) lives here. This is the
"database of rels" the rest of the planner queries.

## 2. Spine functions

| Line | Function | Role |
|---|---|---|
| 113 | `setup_simple_rel_arrays(root)` | Allocate `simple_rel_array` / `simple_rte_array` indexed by rti. Called from `query_planner`. |
| 182 | `expand_planner_arrays(root, add_size)` | Grow per-RTE arrays when inheritance children are added; allocates `append_rel_array` even if previously NULL [from-comment:175-180] |
| 211 | `build_simple_rel(root, relid, parent)` | Construct baserel RelOptInfo; populates from `get_relation_info` (plancat.c) |
| 447 | `build_simple_grouped_rel` | Grouped-rel for eager aggregation |
| 498 | `build_grouped_rel` | Flat-copy + reset for a grouped variant |
| 543 | `find_base_rel(root, relid)` | Lookup or **elog ERROR** "no relation entry for relid %d" |
| 583 | `find_base_rel_ignore_join(root, relid)` | Returns NULL on outer-join relids instead of erroring — convenient when relid sets mix base + OJ ids [from-comment:573-580] |
| 656 | `find_join_rel(root, relids)` | Returns NULL if not yet built |
| 794 | `build_join_rel(root, joinrelids, outer, inner, sjinfo, pushed_down_joins, restrictlist_ptr)` | Build (or fetch) the joinrel; returns restrictlist via out-param [from-comment:780-790] |
| 1025 | `build_child_join_rel` | Partitionwise join child |
| 1180 | `min_join_parameterization(root, joinrelids, outer, inner)` | Lateral-required-rels for a prospective joinrel; split from build_join_rel because join_is_legal needs it earlier [from-comment:1170-1180] |

## 3. Subtleties

- **find_base_rel ERRORs** if the relid is absent, but
  `find_base_rel_ignore_join` is the right call when iterating relid
  sets that include outer-join "phantom" relids. [from-comment:573-580]
- **build_join_rel's API takes a result-pointer for restrictlist.**
  Acknowledged as "a little grotty" but saves recomputation. [from-comment:782-788]
- **Joinrel cache.** Larger queries get a hash table
  (`root->join_rel_hash`) instead of a list scan; threshold managed
  inside `build_join_rel`.

## 4. Tags
`[verified-by-code]` ×4, `[from-comment]` ×5

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [data-structures/reloptinfo.md](../../../../../data-structures/reloptinfo.md)

