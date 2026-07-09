---
name: executor-and-planner
description: Edit the PostgreSQL executor or planner — covers src/backend/executor/ (nodeXxx.c, ExecInitNode/ExecProcNode/ExecEndNode/ExecReScan dispatch, PlanState lifecycle, EXPLAIN wiring) and src/backend/optimizer/ (Path → Plan via createplan.c, RelOptInfo lifecycle, add_path cost-dominance pruning, cost_* units in cost.h). Use whenever a PG patch adds or modifies a plan-node executor, introduces a new Path or Plan type, changes cost-model fields in cost.h, adds EXPLAIN output for a node, plumbs a node into execParallel.c, or tweaks join-path enumeration. Skip for end-user query tuning, EXPLAIN ANALYZE of a production query, work_mem / shared_buffers tuning, MySQL / MongoDB / BigQuery / Snowflake / DuckDB / Spark / Trino query engines, ORM query-builder optimization, and pandas / polars dataframe operations.
when_to_load: Edit a plan-node executor; add a new Path or Plan type; change cost-model fields in `cost.h`; add EXPLAIN output for a new node; plumb a node into `execParallel.c`.
companion_skills:
  - parser-and-nodes
  - access-method-apis
  - parallel-query
  - memory-contexts
  - locking
  - testing
---

# Executor & Planner — operational

Companion docs: `knowledge/architecture/executor.md`, `knowledge/architecture/planner.md`,
`knowledge/architecture/query-lifecycle.md`.

The executor and planner are coupled by the Path-then-Plan handoff and by the
1:1 correspondence between plan-node types and executor node types. If you add
a new way to execute something, you almost always touch both subsystems.

---

## Part A — Adding a new executor node

A node type has **four** trees to keep in sync: `Plan` (plannodes.h),
`PlanState` (execnodes.h), the Path that builds it (pathnodes.h, optional if
your node is only emitted by a special-case planner path), and the dispatch
switches in `execProcnode.c`. Skipping any one of these compiles cleanly and
fails at run time with `unrecognized node type`.

### A.1 The five-or-six functions to implement

For a new node `Foo`, in `src/backend/executor/nodeFoo.c` plus header
`src/include/executor/nodeFoo.h` (see `parser-and-nodes` skill for the
NodeTag / copy / equal / out / read machinery you'll need before any of
this compiles — also recapped in A.6):

| Function | Purpose | Pattern |
|----------|---------|---------|
| `ExecInitFoo(Foo *node, EState *estate, int eflags)` | Build `FooState`, recursively init children, allocate ExprContext, init quals/projection, set `ExecProcNode`. | See `ExecInitSeqScan` (`nodeSeqscan.c:220`). |
| `ExecFoo(PlanState *pstate)` | The pull-iterator. Return next `TupleTableSlot *`, or empty slot when exhausted. Static; assigned to `state->ps.ExecProcNode`. | See `ExecNestLoop` (`nodeNestloop.c:60`). |
| `ExecEndFoo(FooState *node)` | Close relations/scans, free anything the memory-context teardown won't. Memory itself is reclaimed by `FreeExecutorState`. | See `ExecEndSeqScan` (`nodeSeqscan.c:303`). |
| `ExecReScanFoo(FooState *node)` | Reset for re-execution (e.g., when a parameter changed). | See `ExecReScanSeqScan` (`nodeSeqscan.c:347`). |
| `ExecMarkPosFoo` / `ExecRestrPosFoo` | Only if the node will sit under a mergejoin (needs to mark and restore a position). Most nodes don't. | See `ExecMaterialMarkPos` for the canonical example. |
| (parallel) `ExecFooEstimate` / `ExecFooInitializeDSM` / `ExecFooInitializeWorker` / `ExecFooReInitializeDSM` | If the node is parallel-aware. | See `ExecSeqScanEstimate` etc. (`nodeSeqscan.c:373+`). |

The `ExecProcNode` field of `PlanState` is **set inside `ExecInitFoo`** by
assigning `scanstate->ps.ExecProcNode = ExecFoo;` (`nodeSeqscan.c:281` is the
canonical example — seqscan even picks one of four specialised variants
depending on qual/projection presence). `ExecInitNode` then wraps it via
`ExecSetExecProcNode` so stack-depth and instrumentation hooks layer on
transparently (`execProcnode.c:391, 430`).

### A.2 Wiring into the central dispatch

`execProcnode.c` has three switches on `nodeTag(node)` that must learn about
the new type:

1. **`ExecInitNode`** (`execProcnode.c:142`) — add `case T_Foo:` calling
   `ExecInitFoo`.
2. **`ExecEndNode`** (`execProcnode.c:543`) — add `case T_FooState:` calling
   `ExecEndFoo`.
3. **`ExecReScan`** in `execAmi.c` — add `case T_FooState:` calling
   `ExecReScanFoo`.
4. **`MultiExecProcNode`** (`execProcnode.c:488`) — **only if** the node
   returns something other than tuples (Hash builds a hashtable, Bitmap
   nodes build a TIDBitmap). Tuple-returning scans and joins do NOT need
   a case here.

> **Tag asymmetry — the #1 cause of "unrecognized node type" after adding
> a new node**: `ExecInitNode` switches on the **Plan** tag (`T_Foo`)
> because its input is a `Plan *`. `ExecEndNode` and `ExecReScan` switch
> on the **PlanState** tag (`T_FooState`) because their input is a
> `PlanState *`. `MultiExecProcNode` also switches on the PlanState tag.
> Mixing them compiles cleanly and dies at run time.

And include your new header in `execProcnode.c` (alphabetical block at
`execProcnode.c:77-119`). Also add the .c file to `src/backend/executor/meson.build`
and `Makefile`.

### A.3 The Plan ↔ PlanState shape rule

The executor builds a **PlanState tree mirroring the Plan tree** (executor
README §Plan Trees and State Trees, lines 47-79). The Plan tree is read-only;
all mutable runtime data lives on `PlanState`. Concretely:

- Embed `Plan plan;` as the first field of `Foo` (plannodes.h) so the
  `lefttree`/`righttree`/`qual`/`targetlist` links work generically.
- Embed `ScanState ss;` (which embeds `PlanState ps;`) in `FooState` if it's
  a scan; otherwise embed `PlanState ps;` directly. `ScanState` adds a scan
  slot and current-relation pointer that the generic scan helpers expect
  (`execnodes.h:1657`).

### A.4 Memory & ExprContext discipline

`ExecInitFoo` runs in the per-query memory context (set up by
`standard_ExecutorStart` at `execMain.c:180`). Call `ExecAssignExprContext` to
get a per-tuple context for evaluating quals and projections — see
`memory-contexts` skill. The per-tuple context is reset before each call to
`ExecFoo` produces a tuple (typically by the parent node calling
`ResetExprContext` — nestloop does this at `nodeNestloop.c:92`).

### A.5 EXPLAIN integration

`src/backend/commands/explain.c` is the dispatcher. For a new node you need
to:

1. Add a label in `ExplainNode` (the giant `switch (nodeTag(plan))` near the
   top) — usually just a string like `"Foo Scan"`.
2. If the node has per-node detail to print (sort keys, hash buckets, …),
   add a helper like `show_foo_info(FooState *, ExplainState *)` and call it
   from `ExplainNode` after the generic prefix.
3. If the node has VERBOSE-only output (output columns, etc.), use
   `ExplainPropertyText` / `ExplainPropertyInteger` so JSON/XML/YAML format
   variants get it for free.

### A.6 NodeTag, copy/equal/out/read

Both `Foo` (in plannodes.h or execnodes.h) and `FooState` (execnodes.h) need
NodeTags. The `gen_node_support.pl` machinery generates them automatically as
long as the header is in `@all_input_files`. PlanState nodes are typically
declared `pg_node_attr(no_copy_equal, no_read, no_query_jumble, nodetag_only)`
— see how every `*State` struct in `execnodes.h` is annotated. See the
`parser-and-nodes` skill for the full node-type checklist.

---

## Part B — Working in the planner

### B.1 The five-stage pipeline

```
planner / standard_planner    planner.c:333 / 351
  └─ subquery_planner         planner.c:775         (recurses per subquery)
       ├─ pull_up_subqueries, preprocess_expression, … (prep/)
       ├─ deconstruct_jointree            (initsplan.c)
       └─ grouping_planner                planner.c:1704
            ├─ query_planner              (planmain.c) — builds base RelOptInfos
            │     └─ make_one_rel
            │           ├─ set_base_rel_pathlists → set_rel_pathlist (allpaths.c:516)
            │           └─ make_rel_from_joinlist
            │                 └─ standard_join_search (allpaths.c:3948) OR geqo
            ├─ apply_scanjoin_target_to_paths   (upper rels)
            ├─ create_grouping_paths, create_window_paths, create_distinct_paths, …
            └─ create_ordered_paths, create_limit_path
  └─ create_plan                createplan.c:339    (Path → Plan)
  └─ set_plan_references         setrefs.c          (final Var renumbering)
```

Trigger condition for GEQO: `enable_geqo && levels_needed >= geqo_threshold`
(`allpaths.c:3911`). Default `geqo_threshold = 12`, so up to 11 base rels you
get the exhaustive DP search; at 12+ you get a genetic algorithm. Per-pair
path generation still goes through the same per-rel routines in `path/` either
way.

### B.2 The Path → Plan handoff

The planner explores alternatives as **Paths** (lightweight, share structure)
and only the chosen Path is converted to a **Plan** by `create_plan_recurse`
(`createplan.c:390`). The dispatch is a `switch (best_path->pathtype)` —
adding a new Path-type means adding a `create_foo_plan` function alongside it.

Rule of thumb:
- Path = "could we do it this way? at what cost?"
- Plan = "this is what the executor will run."
- Path types omit fields the executor doesn't need; Plan types omit fields
  the planner used only for cost/ordering reasoning.

### B.3 RelOptInfo lifecycle

For each base rel and each *considered* joinrel, exactly **one** RelOptInfo
exists in the PlannerInfo (optimizer README lines 31-42). The DP algorithm
guarantees that when we finish populating `rel.pathlist` for a rel, no
higher-level rel has cached a reference yet — so `add_path` is free to
`pfree` dominated paths (README lines 174-182).

Key fields you'll touch (`pathnodes.h:1009`):

- `pathlist` — candidate Paths, sorted by `(disabled_nodes, total_cost)`.
- `cheapest_startup_path` / `cheapest_total_path` — set after path generation
  is complete by `set_cheapest`. Higher levels read these.
- `partial_pathlist` — Paths usable by parallel workers.
- `rows`, `reltarget` — size and output column estimates.
- `consider_startup`, `consider_param_startup` — gates that let `add_path`
  ignore startup-cost-only wins for upper rels that don't care.

### B.4 Cost units

`costsize.c` top comment (lines 1-72) is the spec. Costs are in **arbitrary
units** anchored on:

| GUC | Default | Meaning |
|-----|---------|---------|
| `seq_page_cost` | 1.0 | Sequential page fetch (the anchor). |
| `random_page_cost` | 4.0 | Non-sequential page fetch. |
| `cpu_tuple_cost` | 0.01 | Per-tuple CPU work. |
| `cpu_index_tuple_cost` | 0.005 | Per index entry. |
| `cpu_operator_cost` | 0.0025 | Per operator/function call. |
| `parallel_tuple_cost` | 0.1 | Pass a tuple worker→leader. |
| `parallel_setup_cost` | 1000 | Spin up parallel workers. |

Every Path stores **two** costs (`pathnodes.h:2007`):

- `startup_cost` — work done before the first tuple is available (sort fill,
  hash build, parameter binding).
- `total_cost` — work to fetch all tuples.

Interpolation `actual = startup + (total-startup) * fetched/rows` is what
upper plan nodes assume when a LIMIT or EXISTS truncates fetching (costsize.c
lines 40-50).

Additionally each Path tracks `disabled_nodes` — the number of disabled-by-
GUC nodes at or below it. `add_path` compares `(disabled_nodes, total_cost)`
lexicographically, so `enable_seqscan=off` is respected as far down the tree
as possible without distorting raw costs (costsize.c lines 53-62).

### B.5 Adding a Path candidate

In `set_rel_pathlist` (or a join-search routine), after computing the cost,
call `add_path(rel, (Path *) new_path)`. Skeleton:

```c
Path *path = create_foo_path(root, rel, ...);
/* cost_foo() fills startup_cost, total_cost, rows */
add_path(rel, path);
```

`add_path` (`pathnode.c:459`) keeps `pathlist` sorted and prunes any path
dominated on **all four** dimensions: cost, sort order (`pathkeys`),
parameterization (`PATH_REQ_OUTER`), and parallel-safety
(`pathnode.c:407-412`). Conversely, a new path is rejected only if some
existing path dominates *it* on all four. This is why a path that's slightly
more expensive but produces sorted output, or that requires a different outer
relid set, will still be kept — they may win later when a merge join or a
nestloop-with-param wants them.

For an early-bail check before doing the full cost computation, use
`add_path_precheck` (`pathnode.c:686`) — it walks the already-sorted
`pathlist` and returns false if no path could possibly survive.

For partial paths (parallel workers), use `add_partial_path` instead.

### B.6 Adding a new scan path for a base rel

If your work introduces a new way to scan a single relation (e.g., a new
table-AM-aware scan):

1. Add a `case` to `set_rel_pathlist` (`allpaths.c:516`) — for plain
   relations that's `set_plain_rel_pathlist`. Or hook it in
   `set_plain_rel_pathlist` directly.
2. Implement `create_foo_path` in `pathnode.c` (mirror `create_seqscan_path`
   at line 1026).
3. Implement `cost_foo` in `costsize.c` (mirror `cost_seqscan` at line 270).
4. Implement `create_foo_plan` in `createplan.c` (mirror
   `create_seqscan_plan` at line 2755) and wire it into the
   `switch (best_path->pathtype)` in `create_plan_recurse` (`createplan.c:390`).
5. Then the executor side: see Part A.

### B.7 Adding a new join path

Mirror the structure of one of `nodeNestloop`/`nodeHashjoin`/`nodeMergejoin`.
Join path generation happens in `joinpath.c` (`add_paths_to_joinrel`); add a
helper there that calls your `create_foo_join_path` and `add_path`s the
result. Costing lives in `costsize.c` under `initial_cost_*` / `final_cost_*`
pairs (the two-stage costing lets `add_path_precheck` short-circuit early).

### B.8 What `subquery_planner` recursing actually means

`subquery_planner` is called once per `Query` node — that's once at the top
level, plus once per RTE_SUBQUERY that wasn't pulled up, plus once per CTE
that wasn't inlined, plus once per SubLink that survived
`SS_process_sublinks`. Each call gets its own `PlannerInfo` (`root`) but
shares the single `PlannerGlobal` (`glob`) so things like `paramExecTypes`,
`finalrtable`, `relationOids` accumulate across the whole plan tree
(`planner.c:775-836`).

---

## Common mistakes

- **Forgetting `set_plan_references`.** After `create_plan`, the planner runs
  `set_plan_references` (`setrefs.c`) which renumbers Vars from per-subquery
  numbering to executor-global slot numbering (INNER_VAR / OUTER_VAR / scan
  attno). A new plan node that holds expressions must be added to
  `fix_*_references_walker` cases or your Vars will not resolve at run time.
  Concretely: see `set_plan_refs` (`setrefs.c:642`, the big switch on
  `nodeTag`) and the `fix_scan_expr` (`setrefs.c:160`) /
  `fix_join_expr` (`setrefs.c:186`) / `fix_upper_expr` (`setrefs.c:196`)
  walkers below it. New scan-like nodes plug into `fix_scan_expr`; new
  join-like nodes plug into `fix_join_expr`; new nodes operating above
  joins (Agg/Window/Sort-like) use `fix_upper_expr`. `set_plan_references`
  itself (`setrefs.c:291`) is the entry point that also assembles
  `finalrtable`, accumulates `relationOids`, and records `invalItems` for
  plan-cache invalidation.

- **Allocating with `malloc` in `ExecInit*`.** Use `palloc` so the per-query
  context reclaims it on `FreeExecutorState`. See `memory-contexts` skill.

- **Forgetting to free buffer pins / close relations in `ExecEnd*`.** The
  memory context will reclaim memory but **not** relation refs, buffer pins,
  or open scans. Executor README lines 324-327.

- **Touching the Plan tree at run time.** Plan trees are shared across
  executions (plan caching) and must stay read-only. Mutable state goes on
  PlanState. README lines 56-59.

- **Adding a Path without `add_path`.** Always go through `add_path` (or
  `add_partial_path`) — directly `lappend`ing to `rel->pathlist` skips the
  dominance pruning and inflates planning memory.

- **Setting cost manually instead of calling `cost_foo`.** The cost helpers
  encode the model assumptions; bypassing them desynchronises your path's
  cost from comparable paths and produces nonsense `EXPLAIN` plans.

## Files-examined

- `source/src/backend/executor/README` (1-450) — definitive on Plan/PlanState
  split, memory contexts, control flow, EvalPlanQual.
- `source/src/backend/executor/execMain.c:120-275, 308-475` —
  `standard_ExecutorStart` / `_Run` / `_End`.
- `source/src/backend/executor/execProcnode.c:1-590` — dispatch switches.
- `source/src/backend/executor/nodeSeqscan.c:1-360` — simple scan template.
- `source/src/backend/executor/nodeNestloop.c:1-400` — simple join template.
- `source/src/include/nodes/execnodes.h:281-1295` — `ExprContext`, `EState`,
  `PlanState`, `ScanState`.
- `source/src/backend/optimizer/README` (1-200) — Paths, RelOptInfo, DP join
  search.
- `source/src/backend/optimizer/plan/planner.c:333-855, 1704+` —
  `standard_planner`, `subquery_planner`, `grouping_planner`.
- `source/src/backend/optimizer/path/allpaths.c:80-3950` —
  `set_rel_pathlist`, `make_rel_from_joinlist`, `standard_join_search`.
- `source/src/backend/optimizer/path/costsize.c:1-300` — cost model anchors,
  `cost_seqscan`.
- `source/src/backend/optimizer/util/pathnode.c:400-690, 1020-1060` —
  `add_path`, `add_path_precheck`, `create_seqscan_path`.
- `source/src/backend/optimizer/plan/createplan.c:339-410, 2755+` —
  `create_plan`, `create_seqscan_plan`.
- `source/src/include/nodes/pathnodes.h:1009-2015` — `RelOptInfo`, `Path`.

## Cross-references

- `.claude/skills/parser-and-nodes/SKILL.md` — upstream of this skill: Query tree → Plan tree pipeline; node-tag conventions; mutators / walkers.
- `.claude/skills/access-method-apis/SKILL.md` — `amcostestimate` interaction with the planner; `IndexAmRoutine`/`TableAmRoutine` callback shape for new AMs.
- `.claude/skills/parallel-query/SKILL.md` — per-node parallel hooks (`ExecXXXInitializeDSM` / `ExecXXXInitializeWorker`); Gather / GatherMerge.
- `.claude/skills/memory-contexts/SKILL.md` — per-query / per-tuple contexts; `es_query_cxt`; `ExprContext`.
- `.claude/skills/locking/SKILL.md` — buffer-pin / content-lock rules for executor scan nodes.
- `.claude/skills/testing/SKILL.md` — `EXPLAIN (COSTS OFF)` for portable test output; isolation specs for concurrency.
- `knowledge/architecture/executor.md`, `knowledge/architecture/planner.md` — long-form architecture.
- `knowledge/subsystems/optimizer.md`, `knowledge/subsystems/executor.md` — deep-dive corpus docs.
