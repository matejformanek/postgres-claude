# equivclass.c — EquivalenceClass machinery

- **Source:** `source/src/backend/optimizer/path/equivclass.c` (3943 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read
- **Canonical narrative:** `source/src/backend/optimizer/README` (EC section)

## 1. Purpose

EquivalenceClasses turn `a = b` quals into transitive-closure groups of
expressions known equal under some btree opfamily. Used to (a) generate
derived implied-equality quals (`a = b AND b = c` → `a = c`),
(b) drive pathkey generation for sort/merge planning, (c) match foreign
keys to join clauses, (d) enable join removal and outer-join reduction.
[from-README]

## 2. Spine functions

| Line | Function | Role |
|---|---|---|
| 178 | `process_equivalence` | Called during qual distribution to fold `=` quals into ECs. Lists are simple because EC graphs are tiny. [from-comment:170-176] |
| 544 | `canonicalize_ec_expression(expr, req_type, req_collation)` | Wraps RelabelType to ensure all member exprs have identical exposed type/collation (some callers expect `exprCollation()` to be precise). [from-comment:530-540] |
| 735 | `get_eclass_for_sort_expr` | Look up or create an EC for a sort key. **Critical caller constraint:** opfamilies must be chosen consistently with how `process_equivalence` did, i.e. from a mergejoinable `=` operator — else miss valid equivalences. [from-comment:728-734] |
| 915 | `find_ec_member_matching_expr` | "Equal after stripping RelabelTypes" matcher; child EC members skipped unless they belong to given relids [from-comment:908-914] |
| 990 | `find_computable_ec_member` | Like above but checks if the EC member is computable from a Var source tlist; honours `require_parallel_safe` [from-comment:982-988] |
| 1075 | `relation_can_be_sorted_early` | Predicate used to push a desired sort below the scan/join boundary [from-comment:1067-1073] |
| 1186 | `generate_base_implied_equalities` | Explode ECs into single-rel restrictinfos at scan level; *deliberately* generates duplicates (not worth deduping) [from-comment:1180-1184] |
| 1548 | `generate_join_implied_equalities` | Join-level derived clauses; needs sjinfo for outer joins; `join_relids` must include OJ-introduced relids [from-comment:1535-1545] |
| 1648 | `generate_join_implied_equalities_for_ecs` | Filtered variant; current sole caller passes sjinfo=NULL |
| 2133 | `reconsider_outer_join_clauses` | Re-examine outer-join quals after EC merging; may derive replacement clause + leave constant-TRUE in jointree so the join isn't seen as clauseless [from-comment:2125-2132] |
| 2572 | `rebuild_eclass_attr_needed` | Post-join-removal attr_needed fixup; mirrors `generate_base_implied_equalities_no_const` |
| 2646 | `exprs_known_equal(item1, item2, opfamily)` | Equality probe; InvalidOid opfamily = "any opfamily", fuzzy but OK for estimation [from-comment:2638-2644] |
| 2708 | `match_eclasses_to_foreign_key_col` | Annotate FK info with the matching EC + member [from-comment:2700-2706] |
| 2831 | `add_child_rel_equivalences` | Propagate parent EC members down to appendrel children (uses AppendRelInfo for speed when applicable) |
| 2939 | `add_child_join_rel_equivalences` | Same for joinrels; only called when planner already wants child EC members [from-comment:2932-2937] |
| 3082 | `add_setop_child_rel_equivalences` | UNION ALL children: add target tlist exprs as EC members matching setop_pathkeys |
| 3154 | `setup_eclass_member_iterator` / 3173 `eclass_member_iterator_next` | Standard iterator skipping unrelated child members |
| 3237 | `generate_implied_equalities_for_column` | Per-column parameterized-path clause generation; one outer ref is enough per column (more wouldn't improve cost) [from-comment:3227-3234] |
| 3368 | `have_relevant_eclass_joinclause` | Quick yes/no for join-search pruning; false negatives only discourage, never break correctness [from-comment:3360-3367] |

## 3. Surprises / load-bearing details

- **Process at startup only.** EC processing is *not* invoked during
  GEQO exploration, so process_equivalence et al. ignore memory-context
  questions. [from-comment:174-176]
- **EC opfamily list is the only equality semantics that count.** A
  mismatch between `process_equivalence` and `get_eclass_for_sort_expr`
  is silent: plans are correct but possibly slow. [from-comment:728-734]
- **Duplicate derived clauses are intentional.**
  `generate_base_implied_equalities` does not check existing source/
  derived clauses for matches. [from-comment:1182-1184]
- **Outer-join handling leaves a constant-TRUE qual** so the optimizer
  doesn't think the join is clauseless and avoid it. [from-comment:2125-2131]
- **`have_relevant_eclass_joinclause` may say "yes" wrongly.** A false
  positive triggers extra planning work; a false negative could hide a
  legal plan, so the function deliberately overestimates. [from-comment:3358-3367]
- **Outer-join clause reconsideration** is the second EC pass invoked by
  `query_planner` (planmain.c line 201).

## 4. Tags
`[verified-by-code]` ×4, `[from-comment]` ×15, `[from-README]` ×1
