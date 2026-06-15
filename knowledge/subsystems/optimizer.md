# Optimizer — Path-enumeration, cost-based planner

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Richard Guo (85), Tom Lane (40), David Rowley (33), Robert Haas (25)
- **Top reviewers (last 24mo):** Tom Lane (40), David Rowley (23), Andrei Lepikhov (23), Tender Wang (18)
- **Recent landmark commits (12mo):**
  - `b8a1bdc458e (Tom Lane, 2025-08-28): Fix "variable not found in subplan target lists" in semijoin de-duplication.`
  - `a1b754558ae (Richard Guo, 2026-05-08): Consider opfamily and collation when removing redundant GROUP BY columns`
  - `f41ab51573a (Richard Guo, 2026-02-10): Teach planner to transform "x IS [NOT] DISTINCT FROM NULL" to a NullTest`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source root:** `source/src/backend/optimizer/` (≈ 1.7 MB of C across plan/,
  path/, prep/, util/, geqo/)
- **Last verified commit:** `ef6a95c7c64`
- **Companion docs:** `knowledge/architecture/planner.md` (higher-level
  narrative), `knowledge/architecture/query-lifecycle.md` (where the planner
  sits in the bigger pipeline), `knowledge/idioms/node-types-and-lists.md`
  (RelOptInfo / Path / Plan are all `Node` subtypes), and the per-file
  corpus under `knowledge/files/src/backend/optimizer/**/*.md`.

The architecture doc gives the high-level shape. This synthesis goes deeper on
subsystem-level cross-cutting concerns: the directory split, the
multi-pipeline ordering invariants, the four EC/pathkey/Path/RelOptInfo data
structures and how they bind together, the cost model knobs, and the load-
bearing surprises (PHI freeze window, EC opfamily silent mismatch, four-phase
join simplification, set_plan_references contract).

---

## 1. What it is — the directory split

`src/backend/optimizer/` is partitioned into **five sibling directories**, and
that split is not cosmetic: each captures a different *phase* of planning and
the dependencies flow one direction only [from-README
`source/src/backend/optimizer/README:1-12`].

| Dir | Role | Representative files |
|---|---|---|
| `prep/` | **Preprocessing.** Mutates the `Query` tree before path-search. Subquery pull-up, jointree flattening, qual canonicalization, targetlist build, setop expansion, aggregate CSE. | `prepjointree.c` (4742 lines), `prepqual.c`, `preptlist.c`, `prepunion.c`, `prepagg.c` |
| `plan/` | **Top-level pipeline drivers + final Plan production.** Owns `planner` → `subquery_planner` → `grouping_planner` → `query_planner` → `create_plan` → `set_plan_references`. Also `subselect.c` (SubLink/CTE → SubPlan/InitPlan), `analyzejoins.c` (join removal, SJE, semijoin reduce), `initsplan.c` (RelOptInfo/EC/SJI construction), `planagg.c` (MIN/MAX → indexscan). | `planner.c` (293 KB), `planmain.c`, `createplan.c` (219 KB), `setrefs.c`, `subselect.c`, `analyzejoins.c`, `initsplan.c`, `planagg.c` |
| `path/` | **Per-rel Path enumeration + costing.** For each RelOptInfo, generate candidate Paths and feed them through `add_path`. | `allpaths.c` (157 KB; baserel + driver), `joinpath.c`, `joinrels.c`, `indxpath.c`, `tidpath.c`, `equivclass.c`, `pathkeys.c`, `costsize.c` (220 KB), `clausesel.c` |
| `util/` | **Shared planner infrastructure.** Path/Plan node constructors, RelOptInfo lookup, expression utilities, system-catalog gateway, restrictinfo + joininfo + placeholder + paramassign bookkeeping. | `pathnode.c` (144 KB), `relnode.c`, `plancat.c`, `clauses.c` (192 KB), `restrictinfo.c`, `joininfo.c`, `placeholder.c`, `paramassign.c`, `var.c`, `tlist.c`, `predtest.c`, `orclauses.c`, `appendinfo.c`, `inherit.c`, `extendplan.c` |
| `geqo/` | **Genetic Query Optimizer.** Drop-in replacement for `standard_join_search`'s exhaustive DP, used when `levels_needed ≥ geqo_threshold`. Registers itself as a planner extension. | `geqo_main.c`, `geqo_eval.c`, `geqo_pool.c`, `geqo_selection.c`, and per-recombination-operator files (ERX/PMX/CX/PX/OX1/OX2/mutation). |

Flow direction: `prep/` runs before `plan/` enters `query_planner`; `path/`
fills RelOptInfo pathlists during `query_planner`; `plan/createplan.c`
converts the winning Path tree; `util/` is called from everywhere; `geqo/`
hangs off `make_rel_from_joinlist` as one of two join-search backends.

---

## 2. The pipeline (the ordering spec)

```
planner / standard_planner                  planner.c:333, 351
  setup PlannerGlobal
  └─ subquery_planner (top-level Query)     planner.c:775
       preprocess block (see §8):
         eval_const_expressions
         preprocess_relation_rtes / pull_up_sublinks / pull_up_subqueries
         flatten_simple_union_all
         expression preprocessing (canonicalize_qual, JOIN alias expand)
         reduce_outer_joins
         remove_useless_result_rtes
         preprocess_targetlist          preptlist.c:65
         preprocess_aggrefs              prepagg.c:109
         SS_process_ctes                 subselect.c:886
         SS_process_sublinks (top-qual)  subselect.c:2209
       └─ grouping_planner                planner.c:1775
            preprocess_minmax_aggregates  planagg.c:73
            ├─ query_planner (planmain.c:53)   ← canonical phase ordering
            │     setup_simple_rel_arrays
            │     add_base_rels_to_query
            │     build_base_rel_tlists
            │     find_placeholders_in_jointree
            │     find_lateral_references           (must be BEFORE deconstruct)
            │     deconstruct_jointree              (PHI freeze!)
            │     reconsider_outer_join_clauses
            │     generate_base_implied_equalities
            │     qp_callback → query_pathkeys
            │     fix_placeholder_input_needed_levels
            │     remove_useless_joins  (analyzejoins.c)
            │     reduce_unique_semijoins
            │     remove_useless_self_joins
            │     add_placeholders_to_base_rels
            │     create_lateral_join_info
            │     match_foreign_keys_to_quals
            │     extract_restriction_or_clauses   (orclauses.c)
            │     setup_eager_aggregation
            │     add_other_rels_to_query           (appendrel children, LATE)
            │     distribute_row_identity_vars
            │     make_one_rel (allpaths.c:179)
            │          set_base_rel_sizes
            │          set_base_rel_pathlists → set_rel_pathlist
            │          make_rel_from_joinlist
            │               if ≥ geqo_threshold: geqo()
            │               else: standard_join_search (allpaths.c:3948)
            ├─ apply_scanjoin_target_to_paths (planner.c:8213)
            ├─ create_grouping_paths           (planner.c:4121)
            ├─ create_window_paths             (planner.c:4867)
            ├─ create_distinct_paths           (planner.c:5124)
            ├─ create_ordered_paths            (planner.c:5642)
            └─ create_limit_path
  └─ create_plan(best_path)                  createplan.c:339
  └─ SS_finalize_plan
  └─ set_plan_references                     setrefs.c:290
  return PlannedStmt
```

[from-code `planner.c:333,351,775,1775,4121,4867,5124,5642,8213`;
`planmain.c:53-305`; `allpaths.c:179,3843,3948`; via
`knowledge/files/src/backend/optimizer/plan/planmain.c.md`,
`knowledge/files/src/backend/optimizer/prep/prepjointree.c.md`]

`query_planner` (`planmain.c:53-305`) is the **authoritative ordering spec.**
Many ordering invariants are stated *only* in its comments ("must be done
before join removal", "delay this to the end"). Anyone adding a new pass must
slot it into that list. [from-comment `planmain.c:53-305`; via
`knowledge/files/src/backend/optimizer/plan/planmain.c.md`]

The top-level `planner()` entry (`planner.c:333`) is a one-liner that
dispatches through `planner_hook` if set, else into `standard_planner`. This
is the extension hook every alternative planner (e.g., pg_hint_plan) replaces.

---

## 3. The two-currency model: Path vs Plan

The planner deals in **Paths**, not Plans. A Path is a lightweight record of
"here is one way to produce the rows for this RelOptInfo, with these
properties, at this cost." Only after the cheapest Path is chosen does
`create_plan` (`createplan.c:339`) convert the chosen Path subtree into an
executable Plan subtree [from-README `optimizer/README:20-26`].

```
RelOptInfo (one per set-of-base-rels considered)
  └─ pathlist                     ← Path candidates (Paths share children)
       ├─ Path { pathtype=T_SeqScan,    cost=…, pathkeys=NIL }
       ├─ Path { pathtype=T_IndexScan,  cost=…, pathkeys=… }
       └─ Path { pathtype=T_BitmapHeapScan, cost=…, pathkeys=NIL }

create_plan(best_path) ─→ Plan tree (executable)
```

A Path stores only what's needed to compare Paths against each other:
`pathtype`, `pathtarget`, `param_info` (which outer rels parameterize it),
`parallel_*`, `rows`, `startup_cost`, `total_cost`, `disabled_nodes`,
`pathkeys`. It **does not** store target-list expressions in evaluated form,
qual expressions, or anything else the executor needs but the cost model
doesn't [via `knowledge/architecture/planner.md` §1; from-code
`pathnodes.h:1964-2012`].

`create_plan_recurse` (`createplan.c:390`) is a giant switch on
`best_path->pathtype` that calls the matching `create_foo_plan`. For each
node type there's a Path constructor in `util/pathnode.c` and a Plan
constructor in `plan/createplan.c`:

| Pathtype | Path ctor | Plan ctor |
|---|---|---|
| T_SeqScan | `create_seqscan_path` (pathnode.c:1026) | `create_seqscan_plan` (createplan.c:2755) |
| T_IndexScan | `create_index_path` (1092) | `create_indexscan_plan` (2844) |
| T_BitmapHeapScan | `create_bitmap_heap_path` (1149) | `create_bitmap_scan_plan` (3040) |
| T_NestLoop | `create_nestloop_path` (2356) | `create_nestloop_plan` (4187) |
| T_MergeJoin | `create_mergejoin_path` (2453) | `create_mergejoin_plan` (4339) |
| T_HashJoin | `create_hashjoin_path` (2521) | `create_hashjoin_plan` (4693) |
| T_Sort | `create_sort_path` (2904) | `create_sort_plan` (2020) |
| T_Agg | `create_agg_path` (3057) | `create_agg_plan` (2156) |
| T_Append | `create_append_path` (1352) | (handled in createplan switch) |
| T_Memoize | `create_memoize_path` (1746) | … |
| T_Gather | `create_gather_path` (1865) | … |

[verified-by-code `pathnode.c:181,459,686,793,1026-…,3793`; `createplan.c:339,390,2755+`]

---

## 4. RelOptInfo, PlannerInfo, PlannerGlobal

Three structs scaffold the whole process [from-code `pathnodes.h:168,1009-1100`;
via `knowledge/architecture/planner.md` §2]:

- **`PlannerGlobal`** — one per `planner()` call, shared across all
  subqueries. Accumulates global outputs: `subplans`, `paramExecTypes`,
  `finalrtable`, `relationOids`, plan-cache invalidation items. The
  PARAM_EXEC slot table `paramExecTypes` is allocator-style append-only and
  never compacted [via
  `knowledge/files/src/backend/optimizer/util/paramassign.c.md`].
- **`PlannerInfo`** (alias `root`) — one per `Query` (one per call to
  `subquery_planner`). Holds the join-search state for that level: the
  `simple_rel_array` of baserel RelOptInfos, the jointree, `eq_classes`,
  `join_rel_list` of joinrels considered so far, the placeholder list, the
  SpecialJoinInfo list, the FK info, plus assorted bookkeeping lists.
- **`RelOptInfo`** — one per *considered* relation, where "relation" can be
  a baserel **or** any subset of baserels that we built a joinrel for, **or**
  one of the upper-rel pseudorels (UPPERREL_SETOP, UPPERREL_GROUP_AGG, …).
  Identified by a `Relids` bitmap of range-table indexes. Holds the
  `pathlist`, `partial_pathlist`, `joininfo`, `baserestrictinfo`,
  `cheapest_startup_path`/`cheapest_total_path`/`cheapest_parameterized_paths`
  after `set_cheapest`.

The **DP invariant**: the same set of baserels is represented by the same
`RelOptInfo`, regardless of which path of building it we explore. Build
`{A,B,C}` by joining `{A,B}` to `C`, or `A` to `{B,C}`, or `B` to `{A,C}` —
the resulting paths all `add_path` into the same pathlist, and compete on
cost [from-README `optimizer/README:31-42`].

RelOptInfo construction lives in `util/relnode.c` [via
`knowledge/files/src/backend/optimizer/util/relnode.c.md`]:
- `setup_simple_rel_arrays(root)` — index per-RTE arrays (relnode.c:113).
- `build_simple_rel(root, relid, parent)` — baserel ctor (relnode.c:211);
  populates from `get_relation_info` (plancat.c).
- `find_base_rel(root, relid)` (543) — lookup or `elog ERROR` "no relation
  entry for relid %d".
- `find_base_rel_ignore_join(root, relid)` (583) — returns NULL on outer-
  join phantom relids instead of erroring. **Use this when iterating relid
  sets that may include OJ relids.** [from-comment `relnode.c:573-580`]
- `build_join_rel(root, joinrelids, outer, inner, sjinfo, pushed_down_joins,
  restrictlist_ptr)` (794) — build (or fetch) the joinrel. Acknowledged
  "a little grotty" out-param for restrictlist saves recomputation
  [from-comment `relnode.c:782-788`].
- Joinrel lookup uses a hash table (`root->join_rel_hash`) when the list
  gets long.

The catalog gateway is `util/plancat.c:get_relation_info` (`plancat.c:120`),
called from `build_simple_rel` to populate `indexlist`, `pages`, `tuples`,
`allvisfrac`, `fkeylist`, `notnullattnums`. **No locks are taken here** — the
relation is assumed already locked by an earlier phase (rewriter or
`expand_inherited_rtentry`). Forgetting that would corrupt the lock pattern
[from-comment `plancat.c:128-132`; via
`knowledge/files/src/backend/optimizer/util/plancat.c.md`].

---

## 5. Equivalence classes and pathkeys

These are the planner's two abstractions for *interesting orderings* and
*provably-equal expressions*. Both are concentrated in `path/equivclass.c`
(3943 lines) and `path/pathkeys.c` (2299 lines).

### 5.1 EquivalenceClasses

An EC turns `a = b` quals into transitive-closure groups of expressions known
equal under some btree opfamily [from-README `optimizer/README` EC section;
via `knowledge/files/src/backend/optimizer/path/equivclass.c.md` §1]. Used to:

- generate derived implied-equality quals (`a=b ∧ b=c ⇒ a=c`),
- drive pathkey generation for sort/merge planning,
- match foreign keys to join clauses,
- enable join removal and outer-join reduction.

Construction is two-phase. **Phase 1** runs inside `deconstruct_jointree`:
`process_equivalence` (equivclass.c:178) folds `=` quals into ECs. **Phase 2**
is `generate_base_implied_equalities` (1186), which explodes ECs into single-
rel restrictinfos at scan level — *deliberately* generating duplicates because
deduping isn't worth it [from-comment `equivclass.c:1180-1184`]. A separate
late call to `reconsider_outer_join_clauses` (2133) handles OJ-postponed
quals.

**Surprises [via `equivclass.c.md` §3]:**

- **Opfamily mismatch is silent.** `process_equivalence` and
  `get_eclass_for_sort_expr` (735) must agree on the opfamily list chosen
  from the `=` operator. A mismatch produces correct-but-slow plans; no
  error fires. [from-comment `equivclass.c:728-734`]
- **EC processing does not run during GEQO exploration.** So
  `process_equivalence` ignores memory-context lifetime — it assumes it
  always runs in the planner's stable context. [from-comment
  `equivclass.c:174-176`]
- **`have_relevant_eclass_joinclause` deliberately overestimates.** False
  positives only waste planning time; false negatives could hide a legal
  plan. [from-comment `equivclass.c:3358-3367`]
- **Outer-join reconsideration leaves a constant-TRUE qual** in the jointree
  so the planner doesn't think the join became clauseless and avoid it.
  [from-comment `equivclass.c:2125-2131`]

### 5.2 PathKeys

PathKeys describe the *interesting* sort orders a Path produces. Each is
`(EquivalenceClass, opfamily, collation, strategy, nulls_first)`.
**Canonical PathKeys are pointer-comparable** — two PathKeys with the same
canonical EC pointer are equal, and that's the only allowed equality test
[from-comment `pathkeys.c:295-302`; via `knowledge/files/src/backend/optimizer/path/pathkeys.c.md` §1].

**Critical ordering invariant:** `make_canonical_pathkey` (pathkeys.c:55)
**must not be called before EC merging completes** — otherwise the wrong EC
will be found. This is why `query_planner` calls
`generate_base_implied_equalities` *before* the `qp_callback` that computes
`query_pathkeys`. [from-comment `pathkeys.c:50-54`]

Public surface includes [via `pathkeys.c.md` §2]:

- `make_pathkeys_for_sortclauses` (1335) — ORDER BY / GROUP BY → pathkeys.
- `build_index_pathkeys` (739) — what sort order an index can produce.
- `build_partition_pathkeys` (918) — sort order delivered by an Append over
  ordered partitioning.
- `build_join_pathkeys` (1294) — order preserved through a join.
- `convert_subquery_pathkeys` (1053) — bridge child Query pathkeys to
  parent's EC space.
- `pathkeys_contained_in`, `pathkeys_count_contained_in` — subset tests.
- `get_cheapest_path_for_pathkeys` (619) — pick cheapest path satisfying a
  required ordering, parameterization, parallel constraint.
- `get_cheapest_fractional_path_for_pathkeys` (665) — same but for LIMIT-
  style early termination.

**Mergejoin scaffolding is separately fragile.** `initialize_mergeclause_
eclasses` (1462) tentatively links a mergejoinable RestrictInfo to its
left/right EC *before* EC merging completes — and `update_mergeclause_
eclasses` (1509) must be called afterward to chase to the canonical EC.
Any code that consumes these links must `update_mergeclause_eclasses` first
[from-comment `pathkeys.c:1450-1507`].

---

## 6. Cost model

Defined in `path/costsize.c` (220 KB, 60+ cost functions). Costs are
arbitrary units anchored on `seq_page_cost = 1.0` [from-comment
`costsize.c:1-72`]. The runtime knobs:

| Knob | Default | Models |
|---|---|---|
| `seq_page_cost` | 1.0 | Sequential 8KB page read (anchor). |
| `random_page_cost` | 4.0 | Random 8KB page read. |
| `cpu_tuple_cost` | 0.01 | Per-tuple CPU overhead. |
| `cpu_index_tuple_cost` | 0.005 | Per-index-entry CPU. |
| `cpu_operator_cost` | 0.0025 | One operator/function call. |
| `parallel_tuple_cost` | 0.1 | Pass a tuple worker → leader. |
| `parallel_setup_cost` | 1000 | Spin up parallel workers. |
| `effective_cache_size` | (GUC) | OS+PG cache hint for index scan costing. |

Each Path stores **two** costs:
- `startup_cost` — work before the first tuple is available.
- `total_cost` — work to fetch all tuples.

Upper nodes assume linear interpolation when LIMIT/EXISTS truncates fetching:
`actual = startup + (total - startup) * fetched / rows` [from-comment
`costsize.c:40-50`].

### 6.1 The `disabled_nodes` lexicographic dimension

`enable_seqscan=off` and similar GUCs used to add a huge constant to
`startup_cost`. Modern PG (16+) stores `disabled_nodes` separately on every
Path: the count of disabled-by-GUC nodes at or below that Path. `add_path`
and `compare_path_costs_fuzzily` compare `(disabled_nodes, total_cost)`
**lexicographically**, so disabled nodes are avoided whenever possible
without distorting raw cost arithmetic [from-comment `costsize.c:53-62`,
`pathnode.c:181`].

### 6.2 Cost functions per node type

[verified-by-code `costsize.c:270,545,1012,1251,1478,2053,2201,2583,2641,2788,3301`]
[grep performed on source/src/backend/optimizer/path/costsize.c]

| Function | Line | Models |
|---|---|---|
| `cost_seqscan` | 270 | `seq_page_cost * pages + cpu_tuple_cost * tuples + per_tuple_qual * tuples`, plus per-tablespace overrides; parallel divides tuple-CPU and adds `parallel_tuple_cost`. |
| `cost_index` | 545 | Index AM `amcostestimate` callback + random-page-cost weighted toward `effective_cache_size`. |
| `cost_bitmap_heap_scan` | 1012 | BitmapAnd/Or trees + heap fetch (`random_page_cost` falling off toward `seq_page_cost` as the bitmap density rises). |
| `cost_tidscan` | 1251 | One random fetch per TID. |
| `cost_sort` | 2201 | n log n comparisons × `cpu_operator_cost`; spills if exceeds `work_mem`. |
| `cost_incremental_sort` | 2053 | Groups by the presorted prefix; each group sorted separately. |
| `cost_material` | 2583 | Tape spill if doesn't fit `work_mem`. |
| `cost_memoize_rescan` | 2641 | Hit-rate × cheap re-read vs miss-rate × full re-execute. |
| `cost_agg` | 2788 | Hash-agg (memory-bounded) vs sort+group; uses `prepagg.c`'s shared trans cost. |
| `cost_nestloop` / `cost_mergejoin` / `cost_hashjoin` | 3500+ | Inner-rescan, mergeclause selectivity, hash build/probe respectively. |

### 6.3 Selectivity — combination layer

`path/clausesel.c` is the **combiner** above the per-operator estimators in
`utils/adt/selfuncs.c` [via `knowledge/files/src/backend/optimizer/path/clausesel.c.md` §1]:

- `clauselist_selectivity` (99) — implicitly-ANDed list. Multiplies selectivities
  assuming independence — *but* extended-stats first, on as many clauses as
  possible, to capture cross-column dependency.
- `clause_selectivity` (666) — single clause.
- **Range query pairing** (clausesel.c:73-92): `x > 34 AND x < 42` is detected
  when both clauses use scalarltsel-family estimators on the same variable;
  selectivity is `hisel + losel + null_frac - 1` instead of `hisel * losel`,
  because the halves are not independent. Falls back to
  `DEFAULT_RANGE_INEQ_SEL` if either is `DEFAULT_INEQ_SEL` or result negative.

Size estimation flows: `set_baserel_size_estimates` (costsize.c:5493) →
`set_joinrel_size_estimates` (5572). Both call into `clauselist_selectivity`
plus FK selectivity overrides where applicable.

---

## 7. Path generation

### 7.1 Base-rel paths (`set_rel_pathlist`)

For each baserel, `set_rel_pathlist` (`allpaths.c:516`) dispatches on
`rte->rtekind` [via `knowledge/architecture/planner.md` §4]:

- `RTE_RELATION` plain → `set_plain_rel_pathlist` (allpaths.c:834): seqscan,
  parallel seqscan, index scans (`create_index_paths`), bitmap scans
  (`choose_bitmap_and`, `generate_bitmap_or_paths`), TID scans
  (`create_tidscan_paths`, tidpath.c:496).
- `RTE_RELATION` foreign → `set_foreign_pathlist` (allpaths.c:1004): FDW's
  `GetForeignPaths`.
- `RTE_RELATION` partitioned → expanded into appendrel children via
  `set_append_rel_size` / `set_append_rel_pathlist` (allpaths.c:1022, 1317).
- `RTE_FUNCTION` / `RTE_VALUES` / `RTE_TABLEFUNC` → one path each.
- `RTE_SUBQUERY` / `RTE_CTE` → already handled during `set_rel_size`, which
  recursively planned the subquery and stashed its result paths
  (`set_subquery_pathlist`, allpaths.c:2679).

### 7.2 Index paths

`path/indxpath.c` (4461 lines) classifies each baserel's quals into *index
clauses* (an op the index AM can evaluate), *predicate clauses* (matching
partial-index predicates), and *order-by clauses* (driving pathkey
generation) [via `knowledge/files/src/backend/optimizer/path/indxpath.c.md`]:

- `create_index_paths` (indxpath.c:238) — top-level: classify quals per
  index, call `build_index_paths`. Considers parameterized paths against
  lateral-predecessor rels.
- `check_index_predicates` (3939) — probe each *partial* index's predicate
  against `baserestrictinfo` + collected outer quals; sets `indrestrictinfo`
  and `predOK`. Recomputed at joins because new restrictions may make a
  partial index newly applicable. [from-comment `indxpath.c:3934-3940`]
- `relation_has_unique_index_for` (4143) — used by join removal / Memoize:
  does *some* unique index cover all the clauses? Returns `extra_clauses`
  derived from baserestrictinfos used in the proof.

### 7.3 OR-clause extraction

`util/orclauses.c:extract_restriction_or_clauses` (orclauses.c:74) walks the
join-clause list for `OR` clauses where every disjunct mentions some
baserel, and synthesizes single-rel restriction clauses for each. Example:
`(a.x=1 AND b.y=2) OR (a.x=3 AND b.y=4)` adds `a.x IN (1,3)` and
`b.y IN (2,4)` as scan-level quals — enabling index scans where the OR
itself wouldn't [verified-by-code; via
`knowledge/files/src/backend/optimizer/util/orclauses.c.md`].

### 7.4 Joinrel paths

`path/joinpath.c:add_paths_to_joinrel` (joinpath.c:122) is the **sole public
entry** for per-pair join path generation [via
`knowledge/files/src/backend/optimizer/path/joinpath.c.md`]. Dispatch is into
five strategies (all static helpers):

- `sort_inner_and_outer` — explicitly sort both sides for mergejoin.
- `match_unsorted_outer` — exploit pre-existing outer ordering (mergejoin
  or parameterized-inner nestloop).
- `hash_inner_and_outer` — hash join (only when hashable equijoin clauses).
- `consider_parallel_nestloop`, `consider_parallel_mergejoin` — partial
  variants for Gather above.
- `select_mergejoin_clauses` — pick eligible restrict clauses; also returns
  `mergejoin_allowed=FALSE` for some outer-join cases.

**JoinType subtleties:** `jointype` passed in may be *flipped* relative to
`sjinfo->jointype` when trying the other direction. `JOIN_UNIQUE_OUTER` /
`JOIN_UNIQUE_INNER` are local-only signals — outside this routine they
appear as `JOIN_INNER` plus `sjinfo->jointype == JOIN_SEMI`. [from-comment
`joinpath.c:110-120`]

---

## 8. Join-order search

If only one baserel, pick the cheapest path. Otherwise
`make_rel_from_joinlist` (allpaths.c:3843) enters the join search.

### 8.1 Standard DP — `standard_join_search`

`allpaths.c:3948`. Algorithm [from-README `optimizer/README:124-186`]:

```
level 1: initial_rels                              (base rels, pathlists ready)
level 2: every (A,B) pair with a usable clause or no other option,
         join_search_one_level → make_join_rel → add_paths_to_joinrel
...
level k: three sources of joinrels:                (joinrels.c:77)
    1. pair from level k-1 with level 1           (left-deep extension)
    2. bushy combinations joinrels[i] × joinrels[k-i] for i ∈ [2,k/2]
    3. "last ditch" for join-order restrictions    (have_join_order_restriction)
...
level N: the single joinrel containing all base rels.
```

[via `knowledge/files/src/backend/optimizer/path/joinrels.c.md` §3]

`join_search_one_level` (joinrels.c:77) populates `join_rel_level[k]` from
`join_rel_level[1..k-1]`. `make_join_rel` (698) may return NULL when the
attempted ordering is illegal (outer-join restrictions, IN/EXISTS-converted
joins). The "last ditch" third pass is gated by `have_join_order_restriction`
(1253) precisely so it isn't triggered for ordinary clauseless cases (which
would explode the search space) [from-comment `joinrels.c:1238-1249`].

`mark_dummy_rel` (1512) replaces a rel's pathlist with a single empty-rel
path when proven empty. Subtle: it must allocate in the same MemoryContext
the RelOptInfo lives in, to survive GEQO cycle teardown when marking a
baserel [from-comment `joinrels.c:1495-1505`].

### 8.2 GEQO branch

Trigger: `enable_geqo && levels_needed >= geqo_threshold` (default
`geqo_threshold = 12`) [verified-by-code `allpaths.c:3911`].

Standard DP is `O(3^N)` in the join-tree space (every base rel is either in
outer, inner, or not yet), which blows up around N=12 even with bitmap
pruning. GEQO trades optimality for tractable planning time.

GEQO runs a genetic algorithm over **join orders**: each individual is a
permutation of baserels representing a left-deep tree, fitness = total cost
of the cheapest path for the resulting top-level joinrel. The per-pair path
generation still uses the same `make_join_rel`/`add_paths_to_joinrel`
machinery — GEQO only replaces the exhaustive enumeration, not the costing.

**GEQO is a registered planner extension**, not hard-wired. It registers
itself via `Geqo_planner_extension_id = GetPlannerExtensionId("geqo")`
(`geqo_main.c:104-105`) and stashes per-call state in a `GeqoPrivateData`
hung off `PlannerInfo` through that extension id. This is the same hook
mechanism third-party plug-ins use (`util/extendplan.c`): a planner extension
gets an integer slot, can attach opaque private data to PlannerInfo, and can
be invoked where the core planner has wired in a call site. GEQO is the
in-core reference user of the pattern [verified-by-code `geqo_main.c:104-112,
geqo_main.c:74-112`; via
`knowledge/files/src/backend/optimizer/geqo/geqo_main.c.md` §4].

GEQO also sets `root->assumeReplanning = true` at line 112, signalling that
intermediate Path lists may be discarded between candidate join orders.

The shape (`geqo_main.c:74`):
1. `geqo_set_seed` — PRNG from `Geqo_seed` GUC.
2. `gimme_pool_size` / `gimme_number_generations` from `Geqo_effort` (1..10).
3. `alloc_pool` + `random_init_pool` + `sort_pool` — fitness = cheapest
   `total_cost` via `geqo_eval` (geqo_eval.c).
4. Generations loop: pick `momma`/`daddy` via `linear_rand`
   (`geqo_selection.c`), apply recombination operator (default ERX;
   compile-time selectable PMX/CX/PX/OX1/OX2), insert via `spread_chromo`.
5. Return best RelOptInfo from the cheapest tour.

`geqo_eval.c:gimme_tree` (geqo_eval.c:163) is the tour-to-tree builder,
which uses *Clumps* (already-joined subtrees) to handle join-order
constraints (LATERAL, outer joins) that pure permutation cannot
[verified-by-code; via `knowledge/files/src/backend/optimizer/geqo/geqo_eval.c.md`].

`geqo_eval` switches into a private memory context, calls `gimme_tree`,
computes fitness = `best_path->total_cost` or `DBL_MAX` on failure, **then
resets the context to free everything allocated during evaluation** — so a
million bad chromosomes don't leak the planner's heap.

### 8.3 `add_path` — the dominance filter

`add_path` (`pathnode.c:459`) is the heart of the pruning. A new path is
**dominated** (and discarded) if some existing path is no worse on **all
four** axes [from-comment `pathnode.c:400-430`; via
`knowledge/architecture/planner.md` §7]:

1. **Cost** — fuzzy compare of `(disabled_nodes, total_cost)` and
   `startup_cost`, `STD_FUZZ_FACTOR = 1.01`.
2. **Pathkeys** — sort order.
3. **Parameterisation** — `PATH_REQ_OUTER(path)`. A path requiring fewer
   outer-rel parameters can be used in more contexts.
4. **Parallel safety** — a parallel-safe path is strictly more useful.

Equivalently, the new path is **kept** if it beats the existing set on at
least one axis. The pathlist is maintained sorted by `(disabled_nodes,
total_cost)` ascending, which lets `add_path_precheck` (pathnode.c:686) bail
out cheaply when no existing path could possibly be dominated.

**Discarded Path objects are immediately `pfree`'d**, which is safe *because*
of the DP property: we finish all paths for a rel before any higher-level
rel references them. **The one exception is `IndexPath` objects**, which
can be referenced as children of `BitmapHeapPath` while their own rel's
pathlist is still being built — hence `add_path` doesn't free those
[from-comment `pathnode.c:438-451`].

---

## 9. Upper-rel paths

Once `make_one_rel` finishes the join search, `grouping_planner` builds a
*sequence* of "upper" RelOptInfos, each with its own pathlist
[from-code `planner.c:1775+`]:

```
UPPERREL_SETOP        UNION/INTERSECT/EXCEPT      prep/prepunion.c:plan_set_operations
UPPERREL_GROUP_AGG    GROUP BY, aggregation       planner.c:4121 create_grouping_paths
UPPERREL_WINDOW       window functions            planner.c:4867 create_window_paths
UPPERREL_DISTINCT     SELECT DISTINCT             planner.c:5124 create_distinct_paths
UPPERREL_ORDERED      ORDER BY                    planner.c:5642 create_ordered_paths
UPPERREL_FINAL        LockRows, LIMIT, ModifyTable
```

Each takes the previous upper rel's `cheapest_total_path` (and maybe its
`cheapest_startup_path` if there's a LIMIT below) and builds the relevant
sort/agg/limit paths on top. `add_path` still mediates competition among
multiple ways to compute (hash-agg vs sort+group-agg vs incremental sort).

The win/loss for an upper rel typically depends on whether a child path's
existing pathkeys already match what's needed — e.g., `create_distinct_paths`
prefers `unique` over `sort+unique` when the input is already sorted on the
DISTINCT keys.

**MIN/MAX special case:** `preprocess_minmax_aggregates` (planagg.c:73)
rewrites `SELECT MIN(col) FROM tab` as `SELECT col FROM tab WHERE col IS NOT
NULL AND <quals> ORDER BY col ASC LIMIT 1`, planning each MIN/MAX subquery
independently and wrapping them in a `MinMaxAggPath` attached to
`(UPPERREL_GROUP_AGG, NULL)`. Eligibility is strict: no GROUP BY, no
windows, no CTEs, exactly one table reference, every aggregate must be
MIN/MAX (all-or-nothing). [verified-by-code `planagg.c:73-154`; via
`knowledge/files/src/backend/optimizer/plan/planagg.c.md`]

---

## 10. Preprocessing (the `prep/` directory)

These passes mutate the `Query` tree *before* `query_planner`.

### 10.1 prepjointree.c — the big one (4742 lines)

Required ordering [from-comment `prepjointree.c:6-15`; via
`knowledge/files/src/backend/optimizer/prep/prepjointree.c.md` §2]:

```
preprocess_relation_rtes
replace_empty_jointree
pull_up_sublinks
preprocess_function_rtes
pull_up_subqueries
flatten_simple_union_all
[expression preprocessing — JOIN alias expand + canonicalize_qual]
reduce_outer_joins
remove_useless_result_rtes
```

Each step depends on earlier steps:

- `pull_up_sublinks` (669) — EXISTS / IN / NOT IN → semi/anti joins. Runs
  *before* qual canonicalization so traverses raw AND chains.
- `preprocess_function_rtes` (1172) — const-simplify FUNCTION RTE
  expressions so allpaths.c can recognize const args; scribbles on input.
- `pull_up_subqueries` (1219) — subselect-in-FROM → parent jointree merge;
  also UNION ALL → appendrel.
- `reduce_outer_joins` (3255) — detect strict quals above a nullable side
  → demote OJ → inner/anti. **Must run after expression preprocessing**
  (qual canonicalization + JOIN alias expansion). This enables many later
  EC and join-removal optimizations. [from-comment `prepjointree.c:3245-3253`]
- `remove_useless_result_rtes` (3886) — drop leftover RTE_RESULT nodes.

`transform_MERGE_to_join` (prepjointree.c:190) sits at the top of the file
because MERGE was added late; it fakes up a regular join so the rest of the
planner is unaware.

### 10.2 prepqual.c — qual canonicalization

`canonicalize_qual` (prepqual.c:292) pushes NOTs down via De Morgan, flattens
nested AND/OR, distributes OR-of-AND when it exposes more top-level AND
structure. Assumes input has already passed through `eval_const_expressions`
(which now owns the initial flattening) [from-comment `prepqual.c:7-19`; via
`knowledge/files/src/backend/optimizer/prep/prepqual.c.md`].

`negate_clause` applies De Morgan unconditionally even though it may
*increase* the NOT count, because exposing AND/OR structure pays off for
WHERE-clause planning and makes logically-equal exprs `equal()`-comparable.

### 10.3 preptlist.c — targetlist preprocessing

`preprocess_targetlist` (preptlist.c:65) builds `root->processed_tlist`.
**`processed_tlist` resnos are consecutive**, so column targets must be
discovered via `update_colnos` (for UPDATE) instead of by resno
[from-comment `preptlist.c:60-64`; via
`knowledge/files/src/backend/optimizer/prep/preptlist.c.md`].

### 10.4 prepunion.c — set-op planning

Two paths [via `knowledge/files/src/backend/optimizer/prep/prepunion.c.md`]:

1. **Pure UNION ALL** of simple subqueries → "append relation" handled by
   `pull_up_simple_union_all` (prepjointree.c) + `allpaths.c`.
2. **Everything else** (INTERSECT, EXCEPT, mixed) → `plan_set_operations`
   (prepunion.c:97) recursively plans each leaf SELECT via `subquery_planner`,
   builds Append / SetOp / HashSetOp paths bottom-up.

### 10.5 prepagg.c — aggregate CSE

Two optimizations [from-comment `prepagg.c:6-10`; via
`knowledge/files/src/backend/optimizer/prep/prepagg.c.md`]:

1. **Identical Aggrefs** computed only once (CSE on aggregates).
2. **Compatible aggregates share a transition state** (e.g. `sum(x)` +
   `avg(x)` reuse the running sum/count; only finals run separately).
   Sharing requires ORDER BY, DISTINCT, FILTER all equal and arguments
   non-volatile.

`preprocess_aggrefs` (prepagg.c:109) sets per-Aggref `aggno`/`transno`/
`aggtranstype`. **Wart:** `AggInfo`/`AggTransInfo` are thrown away after
planning, so executor startup duplicates some lookups.

---

## 11. The PHI freeze invariant

PlaceHolderVars (PHVs) wrap subquery-output expressions that need to keep
their identity across the join level where they're evaluated, so an outer
join above doesn't NULL-extend them prematurely. Each distinct PHV gets a
`PlaceHolderInfo` (PHI) tracking its eval level and required relids.

**The lifecycle window for PHI creation is narrow and load-bearing.** PHIs
may be created only between `find_placeholders_in_jointree` (the pre-
deconstruct walk) and `deconstruct_jointree`. **After `deconstruct_jointree`
begins, no new PHIs may be made** — downstream phases
(`fix_placeholder_input_needed_levels`, `add_placeholders_to_base_rels`,
join search, costing) all assume the PHI set is frozen [from-comment
`initsplan.c:1090-1092, 1521-1530`; via
`knowledge/files/src/backend/optimizer/util/placeholder.c.md`].

The freeze is why `find_lateral_references` must run *before*
`deconstruct_jointree` (LATERAL discovery can create PHIs), and why the
prepjointree/initsplan ordering in `query_planner` is rigid. The invariant
is spread across `initsplan.c`, `prepjointree.c`, and `placeholder.c`;
breaking it produces "PlaceHolderVar found where not expected" failures
deep in path generation [via `knowledge/architecture/planner.md` §3.2].

---

## 12. Four-phase join simplification

"Simplify the joins" is not one pass but four, run at different points in
the pipeline [via `knowledge/architecture/planner.md` §3.1]:

1. **`prepjointree.c:pull_up_*` + `reduce_outer_joins`** — runs *before*
   `query_planner`. Subquery pull-up, UNION-ALL flatten, OJ → inner/anti
   demotion. [from-comment `prepjointree.c:6-15, 3245-3253`]
2. **`reduce_outer_joins` (distinct phase within prepjointree)** — must run
   after expression preprocessing (qual canonicalization + JOIN alias
   expansion). [from-comment `prepjointree.c:3245-3253`]
3. **`analyzejoins.c:remove_useless_joins` + `remove_useless_self_joins`** —
   runs late, inside `query_planner` after ECs are frozen. Drops provably-
   redundant LEFT JOINs (`remove_useless_joins` requires LEFT join, inner
   is single baserel not referenced upward, inner is provably unique for
   the join clauses), then `remove_useless_self_joins` (SJE, gated by
   `enable_self_join_elimination`). [verified-by-code `analyzejoins.c:92-130,
   874-895, 2539-2553`; `planmain.c:218-243`; via
   `knowledge/files/src/backend/optimizer/plan/analyzejoins.c.md`]
4. **EC-driven SemiJoin reduction (`reduce_unique_semijoins`)** — rides on
   the EquivalenceClass machinery built by `deconstruct_jointree`; it
   *deletes the SpecialJoinInfo entry* rather than mutating jointree
   jointype (because nothing downstream reads it). [from-comment
   `analyzejoins.c:862-873`]

Conceptually all "make the join graph smaller / simpler" — but they live in
two different source files, run at two different pipeline points, and
depend on different upstream invariants. Mutation discipline for join
removal is tight: `remove_rel_from_query` must rewrite every RestrictInfo
(`remove_rel_from_restrictinfo`), every EquivalenceClass
(`remove_rel_from_eclass`), the joinlist, `simple_rel_array`,
`simple_rte_array`, row marks. The "Remember to keep the code in sync with
PlannerInfo" comment at `analyzejoins.c:1869` enumerates everything.

---

## 13. subquery_planner recursion

`subquery_planner` (planner.c:775) recurses once per `Query` node it sees
that wasn't pulled up. Recursion sites [via
`knowledge/architecture/planner.md` §9]:

- **Top-level query** — called once from `standard_planner`.
- **Surviving subselect RTEs** — `RTE_SUBQUERY` that couldn't be pulled up
  (own aggregation, DISTINCT, LIMIT, set operation). Triggered from
  `set_subquery_pathlist` during `set_rel_size`.
- **CTEs that weren't inlined** — multiply-referenced CTEs, recursive CTEs,
  CTEs with side effects, `MATERIALIZED` CTEs. Handled by `SS_process_ctes`
  (`subselect.c:886`); decision recorded in `cte_plan_ids` (parallel to
  `parse->cteList`, `-1 = no initplan`) for the rest of the planner to
  read. [from-comment `subselect.c:875-881`]
- **SubLinks** — correlated EXISTS/IN/expression subqueries that couldn't
  be flattened to joins by `SS_process_sublinks` (subselect.c:2209) become
  `SubPlan` nodes, each recursively planning its body.

Each recursive call gets its own `PlannerInfo` (own RelOptInfo array, own
join search) but **shares the single `PlannerGlobal`** so
`paramExecTypes`, `finalrtable`, `relationOids`, and `subplans` accumulate
across the whole plan tree [from-code `planner.c:775-836`].

**Correlated-Var → Param rewrite:** `SS_replace_correlation_vars`
(`subselect.c:2151`) walks expressions replacing upper-level Vars/PHVs/
Aggrefs with `PARAM_EXEC` Params. SubLinks inside uplevel-PHV/Aggref args
are *not touched at the intermediate level* — processing is deferred until
the expression is copied to the parent [from-comment `subselect.c:2140-2150`].

**Initplan cost:** `SS_charge_for_initplans` (`subselect.c:2428`) adds
initplan startup+total costs to **both** startup and total cost of every
Path of `final_rel` (because initplans run before the first tuple) and
marks paths parallel-unsafe if any initplan is [from-comment
`subselect.c:2484-2486`].

---

## 14. Path → Plan: `set_plan_references`

After `create_plan` recursion finishes, `set_plan_references` (`setrefs.c:290`,
entry comment at line 227-272) makes one final pass over the finished Plan
tree. **It does not change join order or cost — it adjusts representational
details the executor depends on** [from-comment `setrefs.c:227-229`].

The 9-item contract from the top comment [from-comment `setrefs.c:231-258`;
via `knowledge/files/src/backend/optimizer/plan/setrefs.c.md`]:

1. **Flatten subquery rangetables** into a single list; null out RTE fields
   the executor doesn't need.
2. **Rewrite Vars in scan nodes** to match the flat rangetable (varno fixup).
3. **Rewrite Vars in upper plan nodes** to reference subplan outputs
   (`varno = OUTER_VAR / INNER_VAR / INDEX_VAR`, `varattno` = subplan tlist
   position).
4. **Adjust Aggrefs** (partial aggregation, minmax replacement).
5. **`PARAM_MULTIEXPR` → `PARAM_EXEC`**.
6. **`AlternativeSubPlan` → pick one alternative** based on estimated calls.
7. **Compute regproc OIDs** for operators.
8. **Build plan dependency lists**: `relationOids` (relations) +
   `invalItems` (functions/domains) — fed to plancache for invalidation.
9. **Assign every plan node a unique `plan_node_id`**.

Plus an extra **"final optimization":** delete useless `SubqueryScan` /
`Append` / `MergeAppend` nodes. **This must happen here, not earlier**,
because earlier removal would break `set_upper_references` — the Var-
numbering rewrite in step 3 relies on the buffer those nodes provide
[from-comment `setrefs.c:260-272`].

**Mutation discipline:** Plan nodes are mutated in-place (single-referenced
post-planning). Expressions go through `expression_tree_mutator` because
they may be shared [from-comment `setrefs.c:285-289`]. Recursive walk; return
value is normally the same Plan but may differ when the node is dropped.

Plan dependency tracking has subtleties: `record_plan_function_dependency`
(setrefs.c:3631) skips built-in funcs (assumed never to change in plan-
invalidating ways), and `extract_query_dependencies` doesn't see inlined
funcs / elided CoerceToDomain [from-comment `setrefs.c:3705-3710`].

---

## 15. PARAM_EXEC slot allocation (`paramassign.c`)

Three data structures, three lifetimes [from-comment `paramassign.c:6-30`;
via `knowledge/files/src/backend/optimizer/util/paramassign.c.md`]:

| Structure | Holds | Lifetime |
|---|---|---|
| `root->glob->paramExecTypes` | List of OIDs; index = PARAM_EXEC number | Permanent for whole plan (never compacted) |
| `root->plan_params` | `PlannerParamItem` of Vars/PHVs this level supplies to subqueries | Reset to NIL after each subquery |
| `root->curOuterParams` | `NestLoopParam` of Vars/PHVs an outer nestloop must pass down | Cleared when the NestLoop that supplies them is built |

The `assign_param_for_*` family (Var, PHV, Aggref, GroupingFunc,
ReturningExpr, CachedExpr, Placeholder) allocates a new PARAM_EXEC slot if
none has been created for a given referent yet.

**`outer_params` is precomputed** (`SS_identify_outer_params`,
`subselect.c:2364`) because by the time final cleanup needs it, the upper
levels' `plan_params` lists are already gone [from-comment
`subselect.c:2358-2363`].

---

## 16. Common pitfalls and load-bearing details

A subsystem-level synthesis is only as useful as its pitfall list. These are
the ones the corpus repeatedly flags:

### 16.1 PHI freeze (§11)

No new PlaceHolderInfo after `deconstruct_jointree` begins. Most common
violation: adding a new pass that does some PHV-introducing transformation
after the freeze. The error "PlaceHolderVar found where not expected" deep
in path generation traces back to this. [via `placeholder.c.md` + `initsplan.c.md`]

### 16.2 EC-without-pathkey ordering (§5.2)

`make_canonical_pathkey` requires EC merging complete. Calling it from
inside a pass that runs before `generate_base_implied_equalities` will
silently produce a non-canonical pathkey that fails pointer equality
forever after. [from-comment `pathkeys.c:50-54`]

### 16.3 EC opfamily silent mismatch (§5.1)

`process_equivalence` and `get_eclass_for_sort_expr` must agree on the
opfamily list chosen from the `=` operator. Mismatch produces correct-but-
slow plans with no error. Symptom: a sort-merge plan that should be free
because the relations are already sorted comes out with explicit Sorts.
[from-comment `equivclass.c:728-734`]

### 16.4 Four-phase join simplification (§12)

Knowing which phase runs at which pipeline point is needed to slot a new
join-removal optimization correctly. Confusing `analyzejoins.c` (post-EC,
late) with `prepjointree.c` (pre-EC, early) is a common entry-level
mistake.

### 16.5 set_plan_references is *not* free (§14)

Step 9's "final optimization" (delete useless SubqueryScan/Append/
MergeAppend) is **only safe at this stage** — earlier removal breaks
upper-Var numbering. Patches that "simplify by removing the dead nodes
earlier" break the executor's Var resolution.

### 16.6 Discarded Path objects are `pfree`'d (§8.3)

A new pass that stashes a pointer to a Path *outside* the rel's pathlist
will use-after-free when `add_path` discards it. The one exception is
`IndexPath` (referenced by `BitmapHeapPath`).

### 16.7 `find_base_rel` ERRORs on OJ relids (§4)

Use `find_base_rel_ignore_join` when iterating relid sets that include
outer-join phantom relids. [from-comment `relnode.c:573-580`]

### 16.8 `pull_var_clause` does not descend into subqueries (`var.c`)

It requires sublink→subplan reduction first. Callers that pull Vars from a
not-yet-planned subquery silently get wrong results. [from-comment
`var.c:643-650`]

### 16.9 GEQO memory discipline

`mark_dummy_rel` allocates in the rel's own context, so a dummy on a
*baserel* survives GEQO cycle teardown while a dummy on a *joinrel* lives
in the join context [from-comment `joinrels.c:1495-1505`]. `geqo_eval` uses
a per-evaluation temp context that gets reset, so per-chromosome
allocations don't leak.

### 16.10 `plancat.c:get_relation_info` takes no locks

Caller (rewriter / `expand_inherited_rtentry`) is responsible. [from-comment
`plancat.c:128-132`]

### 16.11 `predtest.c` requires immutable functions

`predicate_implied_by` / `predicate_refuted_by` "dare not make deductions
based on non-immutable functions, because they might change answers between
plan time and execution time." Checked locally if not externally guaranteed
[from-comment `predtest.c:144-151`].

### 16.12 Range query pairing (§6.3)

`x > 34 AND x < 42` is handled as a single range, not as two independent
inequalities. Custom selectivity estimators that don't follow the
scalarltsel family will silently get `hisel * losel` instead of the range
formula and overestimate range selectivity. [from-comment `clausesel.c:73-92`]

---

## 17. Cross-references

- **Architecture:** `knowledge/architecture/planner.md` (high-level shape),
  `knowledge/architecture/query-lifecycle.md` (parser → rewriter → planner
  → executor pipeline).
- **Idioms:** `knowledge/idioms/node-types-and-lists.md` (Plan/Path/Node
  inheritance), `knowledge/idioms/memory-contexts.md` (planner memory
  contexts, GEQO temp contexts, `assumeReplanning`).
- **Subsystems:**
  - `knowledge/subsystems/executor.md` — consumer of `create_plan`'s output.
  - `knowledge/subsystems/access-methods.md` — `amcostestimate` callback
    used by `cost_index` (costsize.c:545).
  - `knowledge/subsystems/foreign.md` — FDW `GetForeignPaths` plugged in at
    `allpaths.c:1004`.
  - `knowledge/subsystems/partitioning.md` — partitionwise join paths via
    `generate_partitionwise_join_paths` (allpaths.c:4882), partition
    pruning via `predtest.c`.
- **Per-file corpus:** `knowledge/files/src/backend/optimizer/**/*.md`
  (47 files; missing per-file docs for `allpaths.c`, `costsize.c`,
  `pathnode.c`, `createplan.c`, `planner.c`, see §18).

---

## 18. Gaps flagged

Per-file knowledge docs **missing** under `knowledge/files/src/backend/
optimizer/`, despite being foundational [verified by `find` against the
corpus 2026-06-01]:

- `plan/planner.c` (293 KB) — `planner`, `standard_planner`,
  `subquery_planner`, `grouping_planner`, the upper-rel `create_*_paths`
  family (`create_grouping_paths`, `create_window_paths`,
  `create_distinct_paths`, `create_ordered_paths`),
  `apply_scanjoin_target_to_paths`. This is the single largest file in the
  optimizer.
- `plan/createplan.c` (219 KB) — the Path→Plan converter. We have line
  anchors for `create_plan` (339), `create_plan_recurse` (390), and the
  per-pathtype `create_*_plan` family, but no per-file synthesis covering
  the dispatch table, the `flags` argument semantics
  (CP_EXACT_TLIST / CP_SMALL_TLIST / CP_LABEL_TLIST), or the
  `make_*` helpers.
- `path/allpaths.c` (157 KB) — `make_one_rel`, `set_base_rel_sizes`,
  `set_base_rel_pathlists`, `set_rel_pathlist`, `set_plain_rel_pathlist`,
  `standard_join_search`, `generate_useful_gather_paths`,
  `generate_partitionwise_join_paths`. This is the join-search driver.
- `path/costsize.c` (220 KB) — the entire cost-function family. We
  reference it heavily in §6 but the canonical per-function notes
  (`cost_seqscan`, `cost_sort`, `cost_agg`, `set_baserel_size_estimates`,
  `set_joinrel_size_estimates`) live only in the source.
- `util/pathnode.c` (144 KB) — `add_path`, `add_path_precheck`,
  `add_partial_path`, `compare_path_costs_fuzzily`, and the
  `create_*_path` constructors for every pathtype. §8.3 leans on this.

Filling these is the obvious next slice of file-by-file work.

Some narrower gaps:

- **`extract_query_dependencies` corner cases** (setrefs.c:3712) — inlined
  funcs and elided CoerceToDomain are silently absent from plan-cache
  dependency lists. The implications for plan invalidation are unclear from
  the per-file doc.
- **Memoize cost model** (`cost_memoize_rescan`, costsize.c:2641) — the
  hit-rate estimate is a recent addition and the calibration approach
  isn't documented in the corpus.
- **Eager aggregation** (`setup_eager_aggregation` in `initsplan.c`,
  `enable_eager_aggregate` GUC) — referenced but not deep-read. This is a
  new optimization push-aggregation-below-joins and the safety preconditions
  are worth their own doc.
- **Partitionwise-join Path generation** (`generate_partitionwise_join_paths`
  allpaths.c:4882) is referenced but not deeply documented; intersects with
  `appendinfo.c` machinery.

---

## 19. Why this design

The bottom-up DP with `add_path` pruning is the right shape because [via
`knowledge/architecture/planner.md` §11]:

- **Subproblem reuse:** the same `{A,B,C}` joinrel is reachable many ways;
  caching the best paths to build it amortises that work.
- **Discard safety:** the DP order guarantees no higher rel has cached a
  reference to a path before that rel's own pathlist is finalised, so
  `pfree` of dominated paths is safe.
- **Property-aware caching:** Path keeps the few properties (cost, sort,
  parameterisation, parallel-safety) that *might* let a non-cheapest path
  win at a higher level. Anything else gets pruned.

The cost model is admittedly a model — it predicts what the executor *might*
do, given the row estimates from `set_rel_size` (which themselves come from
`pg_statistic` histograms and MCVs in `selfuncs.c`). The classic failure
mode is bad selectivity estimates feeding bad row counts feeding bad costs;
`EXPLAIN (ANALYZE)` shows the gap and `pg_stats` is where you look first.

The separation of Path vs Plan, EC vs PathKey, RelOptInfo vs Plan node, and
the strict ordering enforced by `query_planner` are what make this
intelligible at all — every cross-cutting concern (orderings, equivalences,
parameterisation, parallelism, subqueries, lateral) is expressed by *one*
data structure and *one* construction phase. The pitfall list (§16) is
mostly violations of that single-source-of-truth discipline.
