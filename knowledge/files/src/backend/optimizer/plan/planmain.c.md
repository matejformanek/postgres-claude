# planmain.c — query_planner: the basic-query pipeline

- **Source:** `source/src/backend/optimizer/plan/planmain.c` (305 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## 1. Purpose

Contains exactly one function — `query_planner` — which is the "inner"
planner responsible for joining a Query whose subselect/groupby/sort/
inheritance preprocessing is already done. Despite the filename, the
top-level entry is `planner.c:standard_planner`, not this file.
[from-comment:7-11]

## 2. The pipeline (every step is load-bearing; cite later when needed)

`query_planner` at line 53 executes, in order:

1. **Zero out planner lists** on PlannerInfo (join_rel_list, hash, levels,
   pathkeys, EC, SJI, placeholders, …). [verified-by-code:67-83]
2. **`setup_simple_rel_arrays`** — index `simple_rel_array` and
   `simple_rte_array` by rti. [verified-by-code:88]
3. **RTE_RESULT shortcut** — if the jointree is exactly one
   `RTE_RESULT`, build a `GroupResultPath` directly and return. Used for
   `SELECT 2+2`, `INSERT … VALUES()`. [verified-by-code:96-162]
4. **`add_base_rels_to_query`** — build a RelOptInfo per baserel by
   recursing the jointree (NOT the rangetable — RTEs for views must not
   become rels). [verified-by-code:173, from-comment:168-172]
5. **`remove_useless_groupby_columns`** — strip redundant GROUP BY cols.
6. **`build_base_rel_tlists`** — populate baserel target lists from
   processed_tlist Vars. [verified-by-code:188]
7. **`find_placeholders_in_jointree`** — PlaceHolderInfo discovery.
8. **`find_lateral_references`** — LATERAL Vars.
9. **`deconstruct_jointree`** → returns joinlist; *also* builds
   `join_info_list` (SpecialJoinInfos) and starts populating
   EquivalenceClasses + classified qual lists. [verified-by-code:194]
10. **`reconsider_outer_join_clauses`** — second EC pass for OJ-postponed
    quals. [from-comment:197-200]
11. **`generate_base_implied_equalities`** — explode ECs into
    single-rel restrictinfos. [verified-by-code:208]
12. **`qp_callback`** — caller (grouping_planner) computes
    `query_pathkeys` now that ECs are frozen. [from-comment:47-51]
13. **`fix_placeholder_input_needed_levels`**.
14. **`remove_useless_joins`** → `reduce_unique_semijoins` →
    `remove_useless_self_joins` (all in `analyzejoins.c`). Order matters:
    placeholder fixup must come first. [from-comment:218-243]
15. **`add_placeholders_to_base_rels`**, **`create_lateral_join_info`**,
    **`match_foreign_keys_to_quals`**, **`extract_restriction_or_clauses`**,
    **`setup_eager_aggregation`**.
16. **`add_other_rels_to_query`** — appendrel children expanded *late* so
    restriction clauses are available for partition pruning.
    [from-comment:278-284]
17. **`distribute_row_identity_vars`** — UPDATE/DELETE/MERGE row idents.
18. **`make_one_rel(root, joinlist)`** — the join search (allpaths.c).
19. Post-check: must have produced a usable, non-parameterized
    cheapest_total_path or it ERRORs ("failed to construct the join
    relation"). [verified-by-code:300-302]

## 3. Mental model

`query_planner` is the *ordering* spec for the planner's internal phases.
Many comments here are the only place an ordering invariant is stated
("must be done before join removal", "delay this to the end"); anyone
adding a new pass needs to slot it into this list. [inferred]

## 4. Tags
`[verified-by-code]` ×10, `[from-comment]` ×7
