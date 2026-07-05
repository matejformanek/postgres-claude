# Planner — bottom-up Path enumeration

Companion: `executor.md` (what consumes the planner's output),
`query-lifecycle.md` (where the planner sits in the bigger pipeline).

The planner turns a (rewritten) `Query` tree into a `PlannedStmt`. Its core
algorithm is **bottom-up dynamic programming over RelOptInfos**, where each
node in the DP table caches the best ways to materialise some set of base
relations [from-README `optimizer/README:124-182`]. Paths are the candidate
records, RelOptInfos are the DP cells, and `add_path` is the dominance
filter.

## 1. The two-currency model: Path vs Plan

The planner deals in **Paths**, not Plans. A Path is a lightweight record of
"here is one way to produce the rows for this RelOptInfo, with these
properties, at this cost." Only after the cheapest path is chosen does
`create_plan` (`createplan.c:339`) convert the chosen Path subtree into an
executable Plan subtree [from-README `optimizer/README:20-26`].

```
  RelOptInfo  (one per set-of-base-rels considered)
    └─ pathlist                  ← Path candidates (Paths share children)
         ├─ Path { pathtype=T_SeqScan,  cost=…, pathkeys=NIL }
         ├─ Path { pathtype=T_IndexScan, cost=…, pathkeys=… }
         └─ Path { pathtype=T_BitmapHeapScan, cost=…, pathkeys=NIL }

  create_plan(best_path)  ─→  Plan tree (executable)
```

A Path stores enough to compare it against other Paths: `pathtype`,
`pathtarget` (output columns), `param_info` (which outer rels it depends
on), `parallel_*`, `rows`, `startup_cost`, `total_cost`, `disabled_nodes`,
and `pathkeys` (sort ordering) [from-code `pathnodes.h:1964-2012`]. It does
**not** store target-list expressions in evaluated form, qual expressions,
or anything else the executor needs but the cost model doesn't.

## 2. PlannerInfo, PlannerGlobal, RelOptInfo

Three structs scaffold the whole process:

- **`PlannerGlobal`** — one per `planner()` call, shared across all
  subqueries. Accumulates global outputs: `subplans`, `paramExecTypes`,
  `finalrtable`, `relationOids`, plan-cache invalidation items
  [`pathnodes.h:168`].
- **`PlannerInfo`** (alias `root`) — one per `Query` (i.e., one per call to
  `subquery_planner`). Holds the join search state for that level: the
  `simple_rel_array` of base-rel RelOptInfos, the join-tree, the
  `eq_classes` list, the `join_rel_list` of joinrels considered so far.
  Each PlannerInfo points back to the same `glob`.
- **`RelOptInfo`** — one per *considered* relation, where "relation" can be
  a base rel **or** any subset of base rels that we built a joinrel for.
  Identified by a `Relids` bitmap of range-table indexes. Holds the
  `pathlist` (and `partial_pathlist` for parallel), and after `set_cheapest`
  the precomputed `cheapest_startup_path` / `cheapest_total_path` /
  `cheapest_parameterized_paths` [`pathnodes.h:1009-1100`].

The **central invariant** of the DP scheme: the same set of base rels is
represented by the same `RelOptInfo`, regardless of which path of building
it we explore [from-README `optimizer/README:31-42`]. Build `{A,B,C}` by
joining `{A,B}` to `C`, or `A` to `{B,C}`, or `B` to `{A,C}` — the resulting
paths all `add_path` into the same `pathlist`, and they compete on cost.

## 3. The pipeline

```
planner / standard_planner                    planner.c:333 / 351
  setup PlannerGlobal
  └─ subquery_planner (top-level Query)       planner.c:775
       preprocess: pull-up subqueries, expand inheritance, simplify
                   quals (see §3.1 for the four-phase join simplification)
       └─ grouping_planner                    planner.c:1775
            ├─ query_planner (planmain.c:53)  ← authoritative phase ordering
            │     └─ make_one_rel (allpaths.c)
            │           ├─ set_base_rel_sizes      (rowcount estimates)
            │           ├─ set_base_rel_pathlists  → set_rel_pathlist
            │           └─ make_rel_from_joinlist
            │                 ├─ if ≥ geqo_threshold base rels: geqo()
            │                 └─ else: standard_join_search   (allpaths.c:3948)
            ├─ apply_scanjoin_target_to_paths (push final tlist down)
            ├─ create_grouping_paths / create_window_paths /
            │   create_distinct_paths / create_ordered_paths
            └─ create_limit_path
  └─ create_plan(best_path)                   createplan.c:339
  └─ set_plan_references (setrefs.c:291)      ← see §10 for its 9-item contract
  return PlannedStmt
```

[from-code `planner.c:333-855, 1775+`; `allpaths.c:3902-3950`]

**Authoritative ordering spec.** `query_planner` (`planmain.c:53-305`) is the
canonical phase ordering for the planner's internal passes — many ordering
invariants are stated *only* in its comments ("must be done before join
removal", "delay this to the end"). Anyone adding a new pass must slot it
into that list. See `knowledge/files/src/backend/optimizer/plan/planmain.c.md`
for the per-step enumeration. [from-comment `planmain.c:53-305`]

### 3.1 Join simplification is four distinct phases

"Simplify the joins" is not one pass but four, run at different points in
the pipeline:

1. **`prepjointree.c`** — subquery pull-up (`pull_up_sublinks`,
   `pull_up_subqueries`), UNION-ALL flattening, and `reduce_outer_joins`
   (demote OJ → inner/anti when a strict qual above the nullable side
   proves no NULL-extension is observable). Runs in `subquery_planner`
   *before* `query_planner`. [from-comment `prepjointree.c:6-15, 3245-3253`]
2. **`reduce_outer_joins`** (within prepjointree, but a distinct phase) —
   must run after expression preprocessing (qual canonicalization + JOIN
   alias expansion). [from-comment `prepjointree.c:3245-3253`]
3. **`analyzejoins.c` join removal + self-join elimination** — runs late,
   inside `query_planner` after ECs are frozen: `remove_useless_joins`
   (drop provably-redundant LEFT JOINs), `reduce_unique_semijoins`
   (SEMI → INNER when inner is unique for the clauses), then
   `remove_useless_self_joins` (SJE, gated by
   `enable_self_join_elimination`). [verified-by-code `analyzejoins.c:92-130,
   961-974, 2603-2639`; `planmain.c:218-243`]
4. **EC-driven SemiJoin reduction** — `reduce_unique_semijoins` rides on
   the EquivalenceClass machinery built by `deconstruct_jointree`; it
   deletes the SpecialJoinInfo entry rather than mutating jointree
   jointype. [from-comment `analyzejoins.c:961-972`]

Conceptually they're all "make the join graph smaller / simpler", but they
live in two different source files, run at two different pipeline points,
and depend on different upstream invariants.

### 3.2 PlaceHolderInfo freeze invariant

PlaceHolderVars (PHVs) wrap subquery-output expressions that need to keep
their identity across the join level where they're evaluated, so an outer
join above doesn't NULL-extend them prematurely. Each distinct PHV gets a
`PlaceHolderInfo` (PHI) tracking its eval level and required relids.

**The lifecycle window for PHI creation is narrow and load-bearing.** PHIs
may be created only between `find_placeholders_in_jointree` (the
pre-deconstruct walk) and `deconstruct_jointree`. After
`deconstruct_jointree` begins, *no new PHIs may be made* — downstream
phases (`fix_placeholder_input_needed_levels`, `add_placeholders_to_base_rels`,
join search, costing) all assume the PHI set is frozen.
[from-comment `placeholder.c` invariant; `initsplan.c:1090-1092, 1521-1530`]

The freeze is why `find_lateral_references` must run *before*
`deconstruct_jointree` (LATERAL discovery can create PHIs), and why the
prepjointree / initsplan ordering in `query_planner` is rigid. This
invariant is spread across `initsplan.c`, `prepjointree.c`, and
`placeholder.c`; breaking it produces "PlaceHolderVar found where not
expected" failures deep in path generation.

## 4. Stage 1: base-rel paths (`set_rel_pathlist`)

For each base rel in the query, `set_rel_pathlist` (`allpaths.c:516`)
generates all interesting access paths and `add_path`s them into the rel's
pathlist. The dispatch is on `rte->rtekind`:

- `RTE_RELATION` plain table → `set_plain_rel_pathlist` (seqscan, parallel
  seqscan, index scans for each useful index, bitmap scans for combinable
  predicates, TID scans for `ctid` quals).
- `RTE_RELATION` with `tablesample` → `set_tablesample_rel_pathlist`.
- `RTE_RELATION` foreign table → `set_foreign_pathlist` (FDW's `GetForeignPaths`).
- `RTE_FUNCTION` / `RTE_VALUES` / `RTE_TABLEFUNC` → exactly one path each.
- `RTE_SUBQUERY` / `RTE_CTE` → already handled during `set_rel_size`, which
  recursively planned the subquery and stashed its result paths.

What "interesting" means: anything that might win on at least one of
(cost, sort order, parameterisation, parallel-safety). `add_path` discards
the rest.

## 5. Stage 2: join search

If the query has only one base rel, we're done — pick the cheapest path. If
multiple, `make_rel_from_joinlist` enters the join search. The non-GEQO
path goes through `standard_join_search` (`allpaths.c:3948`).

The algorithm [from-README `optimizer/README:124-186`]:

```
level 1: initial_rels  (the base rels themselves, with their pathlists ready)
level 2: for each pair (A, B) with a usable join clause OR no other option,
         build joinrel {A,B}, generate nestloop/hash/merge paths, add_path them
level 3: for each (level-2 joinrel, level-1 rel) pair with a usable clause,
         build the union, generate join paths …
...
level N: the single joinrel containing all base rels.
```

Per-level pair enumeration is done by `join_search_one_level`
(`joinrels.c`); for each pair it calls `make_join_rel` (which finds or
creates the joinrel) and then `add_paths_to_joinrel` (which costs every
applicable join method and `add_path`s the candidates).

The DP shape considered is **bushy by default**: at level N, both inner and
outer can be joinrels of any smaller size, as long as their relid bitmaps
are disjoint and there's a legal way to glue them. Left-deep, right-deep,
and bushy plans all fall out of this.

### 5.1 The GEQO branch

The trigger is `enable_geqo && levels_needed >= geqo_threshold` (default
`geqo_threshold = 12`) [verified-by-code `allpaths.c:3911`]. GEQO runs a
genetic algorithm over **join orders**: each individual is a permutation of
base rels representing a left-deep tree, fitness = total cost of the
cheapest path for the resulting top-level joinrel. The per-pair path
generation still uses the same `make_join_rel`/`add_paths_to_joinrel`
machinery — GEQO only replaces the exhaustive enumeration, not the costing.

The reason for the threshold: standard DP is O(3^N) in the join-tree
explored space (every base rel is either in the outer, in the inner, or
not yet), which blows up around N=12 even with bitmap pruning. GEQO trades
optimality for tractable planning time.

**GEQO is a registered planner extension.** As of recent PG, GEQO is not
hard-wired; it registers itself via
`Geqo_planner_extension_id = GetPlannerExtensionId("geqo")`
(`geqo_main.c:104-105`) and stashes per-call state in a `GeqoPrivateData`
hung off `PlannerInfo` through that extension id. This is the same hook
mechanism third-party plug-ins use: a planner extension gets an integer
slot, can attach opaque private data to `PlannerInfo`, and can be invoked
where the core planner has wired in a call site. GEQO is the in-core
reference user of the pattern. [verified-by-code `geqo_main.c:104-112`]
GEQO also sets `root->assumeReplanning = true` to signal that intermediate
Path lists may be discarded between candidate join orders.

## 6. Cost model

Defined in `costsize.c`. Costs are arbitrary units anchored on `seq_page_cost
= 1.0` [from-code `costsize.c:1-72`]. The runtime knobs:

| Knob | Default | Models |
|------|---------|--------|
| `seq_page_cost` | 1.0 | Sequential 8KB page read (anchor). |
| `random_page_cost` | 4.0 | Random 8KB page read. |
| `cpu_tuple_cost` | 0.01 | Per-tuple CPU overhead in the executor. |
| `cpu_index_tuple_cost` | 0.005 | Per-index-entry CPU work. |
| `cpu_operator_cost` | 0.0025 | One operator/function call. |
| `parallel_tuple_cost` | 0.1 | Pass a tuple from worker to leader. |
| `parallel_setup_cost` | 1000 | Spin up parallel workers. |
| `effective_cache_size` | (GUC) | OS+PG cache hint for index scan costing. |

Each Path stores **two** costs:
- `startup_cost` — work expended before the first tuple is available (sort
  fill, hash build, materialise children).
- `total_cost` — work to fetch all tuples.

Upper nodes assume linear interpolation when a LIMIT or EXISTS truncates
fetching: `actual = startup + (total - startup) * fetched / rows`
[from-comment `costsize.c:40-50`].

### 6.1 Worked example: `cost_seqscan`

`cost_seqscan` (`costsize.c:270`) is the simplest costing function and a
fair template for understanding the model:

- **IO**: `seq_page_cost * pages` (every page is read sequentially).
- **CPU**: `cpu_tuple_cost * tuples` + `qual_cost.per_tuple * tuples`.
- Add per-relation tablespace overrides for `seq_page_cost`.
- For parallel workers, divide tuple-count work by an effective worker
  count, and add `parallel_tuple_cost` per output tuple to model the leader
  ↔ worker shuffling.

Path costs are not normalised against wall-clock; they're a relative metric
the planner sorts on. You can dump them with `EXPLAIN` and they line up
roughly with millicent-style numbers, but a "cost of 100" doesn't directly
mean "100 ms."

### 6.2 The `disabled_nodes` lexicographic dimension

`enable_seqscan=off` and friends used to be implemented by adding a huge
constant to `startup_cost`, which leaked into upper-level cost arithmetic
and produced absurd plans when the disabled choice was unavoidable.

Modern PG (16+) stores `disabled_nodes` separately on every Path: the count
of disabled-by-GUC nodes at or below that Path. `add_path` and
`compare_path_costs_fuzzily` compare `(disabled_nodes, total_cost)` in
lexicographic order, so disabled nodes are avoided whenever possible
without distorting raw cost arithmetic [from-comment `costsize.c:53-62`].

## 7. `add_path` — the dominance filter

`add_path` (`pathnode.c:459`) is the heart of the pruning. A new path is
**dominated** (and discarded) if some existing path is no worse on **all
four** axes:

1. **Cost** — fuzzy compare of `(disabled_nodes, total_cost)` and
   `startup_cost`, with `STD_FUZZ_FACTOR = 1.01`.
2. **Pathkeys** — sort order. If new is unsorted and old is sorted, old may
   dominate on this axis only if its cost is competitive.
3. **Parameterisation** — `PATH_REQ_OUTER(path)`. A path that requires
   fewer outer-rel parameters can be used in more contexts.
4. **Parallel safety** — a parallel-safe path is strictly more useful than
   one that isn't.

Equivalently, the new path is **kept** if it beats the existing set on at
least one of these axes [from-comment `pathnode.c:400-430`]. The pathlist
is maintained in sorted order by `(disabled_nodes, total_cost)` ascending,
which lets `add_path_precheck` (`pathnode.c:686`) bail out cheaply when no
existing path could possibly be dominated.

Discarded Path objects are immediately `pfree`'d, which is safe **because**
of the DP property: we finish all paths for a rel before any higher-level
rel can reference them, so a discarded path can't have lingering refs. The
one exception is `IndexPath` objects, which can be referenced as children
of `BitmapHeapPath` while their own rel's pathlist is still being built —
hence `add_path` doesn't free those [from-comment `pathnode.c:438-451`].

## 8. Upper-rel paths: aggregation, distinct, order, limit

Once `make_one_rel` finishes the join search, `grouping_planner` builds a
*sequence* of "upper" RelOptInfos for each post-scan/join transformation
[verified-by-code `planner.c:1775+`]:

```
UPPERREL_SETOP        (UNION/INTERSECT/EXCEPT)
UPPERREL_GROUP_AGG    (GROUP BY, plain aggregation)
UPPERREL_WINDOW       (window functions)
UPPERREL_DISTINCT     (SELECT DISTINCT)
UPPERREL_ORDERED      (ORDER BY)
UPPERREL_FINAL        (LockRows, LIMIT, ModifyTable)
```

Each upper rel has its own pathlist, populated by `create_grouping_paths` /
`create_window_paths` / etc. Each takes the previous upper rel's
`cheapest_total_path` (and maybe its `cheapest_startup_path` if there's a
LIMIT below) and builds the relevant sort/agg/limit paths on top. `add_path`
still mediates competition among multiple ways to compute, e.g., a GROUP BY
(hash-agg vs sort+group-agg vs incremental sort).

`UPPERREL_FINAL`'s cheapest path is what goes into `create_plan`.

## 9. `subquery_planner` recursion

The planner recurses (via `subquery_planner`) once per `Query` node it sees
that wasn't pulled up. The recursion sites:

- **The top-level query.** Called once from `standard_planner`.
- **Surviving subselect RTEs.** A `RTE_SUBQUERY` that couldn't be pulled
  up — typically because it has its own aggregation, DISTINCT, LIMIT, or
  a set operation, or because pulling up would change semantics. Triggered
  from `set_subquery_pathlist` during `set_rel_size`.
- **CTEs that weren't inlined.** Multiply-referenced CTEs, recursive CTEs,
  CTEs with side effects, and CTEs the user wrote `WITH foo AS MATERIALIZED`
  on. Handled by `SS_process_ctes` (`planner.c:849`).
- **`SubLink`s that survived sublink processing.** Correlated EXISTS/IN/
  expression subqueries that couldn't be flattened to joins or semijoins by
  `SS_process_sublinks` are turned into `SubPlan` nodes, each of which
  recursively plans its body.

Each recursive call gets its own `PlannerInfo` (own RelOptInfo array, own
join search) but **shares the single `PlannerGlobal`** so things like
`paramExecTypes`, `finalrtable`, `relationOids`, and `subplans` accumulate
across the whole plan tree [from-code `planner.c:775-836`].

## 10. Path → Plan: `create_plan`

`create_plan_recurse` (`createplan.c:390`) is a switch on `best_path->pathtype`
that calls the matching `create_foo_plan`. For `T_SeqScan` →
`create_seqscan_plan` (`createplan.c:2755`), which:

1. Builds the executor's view of qual and tlist from the Path's
   `parent->reltarget` and the rel's `baserestrictinfo`.
2. Recursively does `create_plan_recurse` on any child paths.
3. Calls `make_seqscan` to allocate the `SeqScan` Plan node.
4. Copies cost numbers from Path to Plan.

After all `create_plan` recursion, `set_plan_references`
(`setrefs.c:291`; the 9-item contract is enumerated in the function's
header comment at `setrefs.c:224-272`) makes one final pass over the
finished Plan tree. It does *not* change join order or cost — it adjusts
representational details the executor depends on. That header comment
enumerates a 9-item contract:

1. **Flatten subquery rangetables** into a single list; null out RTE fields
   the executor doesn't need.
2. **Rewrite Vars in scan nodes** to match the flat rangetable (varno fixup).
3. **Rewrite Vars in upper plan nodes** to reference subplan outputs
   (`varno = OUTER_VAR / INNER_VAR / INDEX_VAR`, `varattno` = subplan tlist
   position).
4. **Adjust Aggrefs** (partial aggregation, minmax replacement).
5. **`PARAM_MULTIEXPR` → `PARAM_EXEC`**.
6. **`AlternativeSubPlan`** — pick one alternative based on estimated calls.
7. **Compute regproc OIDs** for operators.
8. **Build plan dependency lists**: `relationOids` (relations) +
   `invalItems` (functions/domains) — fed to plancache for invalidation.
9. **Assign every plan node a unique `plan_node_id`**.

Plus an extra "final optimization", documented as a closing step in the
same comment: **delete useless `SubqueryScan` / `Append` / `MergeAppend`
nodes**. This must happen here, not earlier, because earlier removal would
break `set_upper_references` — the Var-numbering rewrite in step 3 relies
on the buffer those nodes provide. [from-comment `setrefs.c:260-272`]

The Var-renumbering in steps 2-3 is the most visible change: per-subquery
RTE indexes get replaced by executor-global slot conventions, which is the
final, executor-ready form.

## 11. Why this design

The bottom-up DP with `add_path` pruning is the right shape because:

- **Subproblem reuse**: the same `{A,B,C}` joinrel is reachable many ways;
  caching the best paths to build it amortises that work.
- **Discard safety**: the DP order guarantees no higher rel has cached a
  reference to a path before that rel's own pathlist is finalised, so
  `pfree` of dominated paths is safe.
- **Property-aware caching**: Path keeps the few properties (cost, sort,
  parameterisation, parallel-safety) that *might* let a non-cheapest path
  win at a higher level. Anything else gets pruned.

The cost model is admittedly a model — it predicts what the executor *might*
do, given the row estimates from `set_rel_size` (which themselves come from
`pg_statistic` histograms and MCVs). The classic failure mode is bad
selectivity estimates feeding bad row counts feeding bad costs; `EXPLAIN
(ANALYZE)` shows the gap and `pg_stats` is where you look first.
