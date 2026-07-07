---
scenario: add-new-plan-node
when_to_use: I want to add a brand-new executor node type — a fresh Path + Plan + PlanState triplet wired through createplan.c, execProcnode.c, EXPLAIN, and (if it can run in workers) the parallel-execution DSM hooks.
companion_skills: ["executor-and-planner", "parallel-query"]
related_scenarios: ["add-new-node-type", "add-new-expression-eval-step", "add-new-cost-model-knob"]
canonical_commit: 9eacee2e62d
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new plan node

## Scope — what's in / out

**In scope:**
- A new executor node type with the full triplet:
  `XxxPath` (planner cost-shape) → `XxxPlan` (post-plan structure) → `XxxState`
  (executor runtime). One `nodeXxx.c` plus its `nodeXxx.h`.
- Wiring through every dispatch site: `create_plan_recurse` /
  `create_scan_plan`, `ExecInitNode` / `ExecEndNode` / `ExecReScan`,
  `set_plan_refs`, `ExplainNode` (+ optional `show_xxx_info`).
- Optional parallel-aware support: `ExecXxxEstimate` /
  `ExecXxxInitializeDSM` / `ExecXxxReInitializeDSM` /
  `ExecXxxInitializeWorker` / `ExecShutdownXxx` and the
  dispatch sites in `execParallel.c`.
- Path constructor in `pathnode.c` (`create_xxx_path`) and the cost
  function in `costsize.c` (`cost_xxx`).

**Out of scope:**
- Adding a brand-new `NodeTag` enum value alone, without any executor
  semantics (parsetree / planner-only structures) — see
  `add-new-node-type`.
- New expression-eval steps inside `ExprState` programs (`EEOP_*`) —
  different machinery; see `add-new-expression-eval-step`.
- New cost GUC or `cost_*` constants without a new node — see
  `add-new-cost-model-knob`.
- Pluggable nodes via `CustomScan`: that uses the extensible-node
  hooks instead of these dispatch tables [verified-by-code](source/src/include/nodes/extensible.h:62-117).
  Use `add-new-extension` + `CustomScan` for that.

## Pre-flight

- **Companion skills:** load `executor-and-planner` (triplet shape,
  ExecProcNode dispatch, slot lifecycle) and `parallel-query` (DSM
  estimate/init/worker lifecycle, `parallel_aware` vs `parallel_safe`).
- **Canonical commit:** `9eacee2e62d` — *Add Result Cache executor
  node (take 2)* (David Rowley, 2021-04-02). The cleanest historical
  reference: one new `nodeXxx.c` (`nodeResultCache.c`, later renamed
  to `nodeMemoize.c` by `83f4fcc6550`), one new header
  (`nodeResultCache.h`), MemoizePath + Memoize Plan + MemoizeState
  triplet, joinpath.c integration, EXPLAIN `show_memoize_info`, a new
  GUC (`enable_resultcache`), regression test `resultcache.sql`. Read
  this commit and `83f4fcc6550` together — they show the canonical
  shape end-to-end. [verified-by-code](source/src/backend/executor/nodeMemoize.c:1-50)
- **Common pitfalls (one-line each):**
  - Forgot a dispatch site — `ExecInitNode` covers init but
    `ExecEndNode`, `ExecReScan`, `set_plan_refs`, `ExplainNode`,
    `ExecParallelEstimate`, and `ExecAmi`'s rescan-strategy switch
    each have their own switch on `nodeTag` and **all must learn the
    new tag** or you get "unrecognized node type" elog at runtime
    [verified-by-code](source/src/backend/executor/execProcnode.c:161-512).
  - Marked `parallel_safe = true` for a node holding non-shareable
    runtime state (hash tables, tuplestores) without writing the DSM
    hooks — silent wrong results in parallel plans.
  - `pathtype` (NodeTag stored in `Path.pathtype`) must match the
    tag of the `Plan` that `create_plan_recurse` returns; the dispatch
    keys off `pathtype` [verified-by-code](source/src/backend/optimizer/plan/createplan.c:397-516).
  - Skipped the gen_node_support annotation — copyfuncs / equalfuncs
    / outfuncs / readfuncs are now auto-generated from struct
    annotations in headers; if you omit `pg_node_attr()` or put the
    struct in the wrong header you get either no codegen or wrong
    codegen [from-comment](source/src/include/nodes/nodes.h:23-31).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/nodes/pathnodes.h` | Add `typedef struct XxxPath { Path path; … }` near other path types. `Path.pathtype` will hold `T_Xxx` (the *Plan* tag, not a separate path tag) [verified-by-code](source/src/include/nodes/pathnodes.h:1964-2000). Place the struct so `gen_node_support.pl` picks it up. | [pathnodes.h.md](../files/src/include/nodes/pathnodes.h.md) | executor-and-planner |
| 2 | `src/include/nodes/plannodes.h` | Add `typedef struct Xxx { Plan plan; … }`. Inherits cost/row/parallel_aware/parallel_safe from `Plan` [verified-by-code](source/src/include/nodes/plannodes.h:191-230). For scan-style nodes, inherit from `Scan` instead [verified-by-code](source/src/include/nodes/plannodes.h:538-560). | [plannodes.h.md](../files/src/include/nodes/plannodes.h.md) | executor-and-planner |
| 3 | `src/include/nodes/execnodes.h` | Add `typedef struct XxxState { PlanState ps; … }` — runtime fields, tuplestores, hash tables, instrumentation counters. Place near related State structs [verified-by-code](source/src/include/nodes/execnodes.h:2303-2360). | [execnodes.h.md](../files/src/include/nodes/execnodes.h.md) | executor-and-planner |
| 4 | `src/include/executor/nodeXxx.h` | (NEW) Public exec API: `ExecInitXxx`, `ExecEndXxx`, `ExecReScanXxx`; if parallel-aware also `ExecXxxEstimate`, `ExecXxxInitializeDSM`, `ExecXxxReInitializeDSM`, `ExecXxxInitializeWorker`, `ExecShutdownXxx`. Pattern from `nodeMemoize.h` / `nodeSeqscan.h` [verified-by-code](source/src/include/executor/nodeSeqscan.h:1-40). | — | executor-and-planner |
| 5 | `src/backend/executor/nodeXxx.c` | (NEW) The implementation. `ExecXxx` is the per-tuple driver registered as `ps.ExecProcNode`. `ExecInitXxx` builds projection info, sets `ps.ExecProcNode = ExecXxx`, recurses into `ExecInitNode` for child(ren) [verified-by-code](source/src/backend/executor/nodeSeqscan.c:140-250). Add to `src/backend/executor/meson.build` and `Makefile`. | — | executor-and-planner |
| 6 | `src/backend/optimizer/util/pathnode.c` | Add `create_xxx_path()` — allocates the path, fills `pathtype = T_Xxx`, calls `cost_xxx`, attaches to parent rel via `add_path` (or returned to caller). Place near related constructors [verified-by-code](source/src/backend/optimizer/util/pathnode.c:1021-1100). If the path holds reparameterizable subpaths, extend `reparameterize_path` too [verified-by-code](source/src/backend/optimizer/util/pathnode.c:4025-4036). | [pathnode.c.md](../files/src/backend/optimizer/util/pathnode.c.md) | executor-and-planner |
| 7 | `src/include/optimizer/pathnode.h` | Prototype for `create_xxx_path` so planner phases can build it [verified-by-code](source/src/include/optimizer/pathnode.h:1-50). | [pathnode.h.md](../files/src/include/optimizer/pathnode.h.md) | executor-and-planner |
| 8 | `src/backend/optimizer/path/costsize.c` | Add `cost_xxx()` — sets `startup_cost`, `total_cost`, `rows`. Read existing `cost_*` functions for the shape (cost-units, parallel-divisor, `disable_cost` for disabled-via-GUC) [verified-by-code](source/src/backend/optimizer/path/costsize.c:1-50). | [costsize.c.md](../files/src/backend/optimizer/path/costsize.c.md) | executor-and-planner |
| 9 | `src/include/optimizer/cost.h` | Prototype for `cost_xxx`. If you add a tunable cost knob, that's a separate change-class — see `add-new-cost-model-knob`. [verified-by-code](source/src/include/optimizer/cost.h:1-50) | [cost.h.md](../files/src/include/optimizer/cost.h.md) | executor-and-planner |
| 10 | `src/backend/optimizer/plan/createplan.c` | Two edits: (a) add `case T_Xxx:` to the dispatch in `create_plan_recurse` calling `create_xxx_plan(root, (XxxPath *) best_path, flags)` [verified-by-code](source/src/backend/optimizer/plan/createplan.c:397-516); (b) implement `create_xxx_plan` — recursively builds child Plan from `XxxPath->subpath`, copies cost from path, fills the Plan-specific fields. [verified-by-code](source/src/backend/optimizer/plan/createplan.c:1704-1800) | [createplan.c.md](../files/src/backend/optimizer/plan/createplan.c.md) | executor-and-planner |
| 11 | `src/backend/optimizer/plan/setrefs.c` | Add `case T_Xxx:` in `set_plan_refs` to fix Var references after RT-list flattening. Use `fix_scan_expr` / `fix_upper_expr` per the node's tlist semantics [verified-by-code](source/src/backend/optimizer/plan/setrefs.c:639-940). | [setrefs.c.md](../files/src/backend/optimizer/plan/setrefs.c.md) | executor-and-planner |
| 12 | `src/backend/executor/execProcnode.c` | Three edits: `case T_Xxx:` in `ExecInitNode` calling `ExecInitXxx` [verified-by-code](source/src/backend/executor/execProcnode.c:161-300); `case T_XxxState:` in `ExecEndNode` calling `ExecEndXxx` [verified-by-code](source/src/backend/executor/execProcnode.c:540-700); `#include "executor/nodeXxx.h"` at the top. | [execProcnode.c.md](../files/src/backend/executor/execProcnode.c.md) | executor-and-planner |
| 13 | `src/backend/executor/execAmi.c` | Add `case T_XxxState:` in `ExecReScan` calling `ExecReScanXxx` [verified-by-code](source/src/backend/executor/execAmi.c:78-260); add `case T_Xxx:` in `ExecMaterializesOutput` / `ExecSupportsBackwardScan` / `ExecSupportsMarkRestore` if the node has those properties [verified-by-code](source/src/backend/executor/execAmi.c:436-650). | [execAmi.c.md](../files/src/backend/executor/execAmi.c.md) | executor-and-planner |
| 14 | `src/backend/commands/explain.c` | Add `case T_Xxx:` in `ExplainNode`'s node-name switch (line ~1196) + optional `case T_Xxx:` in `ExplainTargetRel` (~1444), `ExplainNode` properties (~1670, 2023), runtime stats (~4109), `ExplainScanTarget` (~4609) [verified-by-code](source/src/backend/commands/explain.c:1196-4609). If the node has non-trivial runtime info, add a `show_xxx_info(XxxState *, ExplainState *)` modelled on `show_memoize_info` [verified-by-code](source/src/backend/commands/explain.c:137,3599). | [explain.c.md](../files/src/backend/commands/explain.c.md) | executor-and-planner |
| 15 | `src/backend/executor/execParallel.c` | (Parallel-aware nodes only) Add `case T_XxxState:` in `ExecParallelEstimate`, `ExecParallelInitializeDSM`, `ExecParallelReInitializeDSM`, `ExecParallelInitializeWorker`. Each dispatches to the per-node hook from `nodeXxx.h`. Non-parallel-aware nodes that still need worker-side instrumentation use the same dispatch with a `parallel_aware` guard [verified-by-code](source/src/backend/executor/execParallel.c:245-360,480-580,1020-1090,1380-1465). | [execParallel.c.md](../files/src/backend/executor/execParallel.c.md) | parallel-query |
| 16 | `src/backend/optimizer/path/allpaths.c` or `joinpath.c` | Wherever the planner decides to *generate* the new path: `set_<reltype>_pathlist`, `try_partial_<x>_path`, etc. For Memoize, this was `joinpath.c` (parameterized-NL injection) [verified-by-code](source/src/backend/optimizer/path/joinpath.c:1-50). Pick the site that matches the node's role. | [allpaths.c.md](../files/src/backend/optimizer/path/allpaths.c.md), [joinpath.c.md](../files/src/backend/optimizer/path/joinpath.c.md) | executor-and-planner |
| 17 | `src/backend/utils/misc/guc_tables.c` + `postgresql.conf.sample` | If the new node is gated by `enable_xxx`, add a `bool` GUC. Otherwise skip. See `enable_memoize` for the pattern [verified-by-code](source/src/backend/utils/misc/guc_tables.c). | — | gucs-config |
| 18 | `src/test/regress/sql/<name>.sql` + `expected/<name>.out` | A new test file or additions to an existing relevant file (e.g. `join.sql` for join helpers, `select.sql` for scan-shape nodes). Must exercise EXPLAIN output too so plan-shape regressions are caught. | — | testing |
| 19 | `src/test/regress/parallel_schedule` | Only if a brand-new test file was added — register it in a parallel group [verified-by-code](source/src/test/regress/parallel_schedule). | — | testing |
| 20 | `src/backend/nodes/copyfuncs.c` / `equalfuncs.c` / `outfuncs.c` / `readfuncs.c` | NOT edited directly — auto-regenerated by `src/backend/nodes/gen_node_support.pl` from struct annotations in the node headers [from-comment](source/src/include/nodes/nodes.h:23-31),[verified-by-code](source/src/backend/nodes/gen_node_support.pl). Confirm `gen_node_support.pl` picked up your new structs by grepping the built `copyfuncs.funcs.c` after a rebuild. Use `pg_node_attr(custom_copy_equal)` / `custom_read_write` only if defaults are wrong. | — | executor-and-planner |
| 21 | `src/include/nodes/nodetags.h` | NOT edited directly — regenerated by `gen_node_support.pl` from struct declarations. Your new `T_Xxx` (Plan) and `T_XxxState` (PlanState) tags appear here after rebuild. NOTE: inserting tags is fine in development, but **never reorder** in a released branch (ABI break for extensions) [from-comment](source/src/include/nodes/nodes.h:23-31). | [nodes.h.md](../files/src/include/nodes/nodes.h.md) | executor-and-planner |
| 22 | `src/backend/optimizer/README` | (Optional) Document the new node's planner role if it introduces a non-obvious concept (e.g. Memoize added a one-line entry) [verified-by-code](source/src/backend/optimizer/README). | — | — |
| 23 | `doc/src/sgml/` | (Optional) `using-explain.sgml` if the node has new EXPLAIN output users will see; `config.sgml` for any new GUC. | — | — |

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Struct triplet + node tags.** Files: [1, 2, 3, 4, 5
   (skeleton only), 21]. Define `XxxPath` in `pathnodes.h`, `Xxx` in
   `plannodes.h`, `XxxState` in `execnodes.h` with proper
   `pg_node_attr()` annotations; create `nodeXxx.h` with prototypes
   only; create `nodeXxx.c` with stub `ExecInitXxx` returning
   `elog(ERROR, "not implemented")` and stub `ExecXxx`, `ExecEndXxx`,
   `ExecReScanXxx`. Phase-end check: `meson compile -C dev/build-debug`
   succeeds; `T_Xxx` and `T_XxxState` appear in regenerated
   `nodetags.h`.

2. **Phase 2 — Planner wiring.** Files: [6, 7, 8, 9, 10, 11, 16].
   `create_xxx_path` + `cost_xxx` + `create_xxx_plan` + `set_plan_refs`
   case + path-generation site (allpaths/joinpath). Phase-end check:
   build green, plan generation reaches `create_xxx_plan` for a hand-
   crafted query that forces the new path (verify with EXPLAIN; node
   name will print as `???` until Phase 4).

3. **Phase 3 — Executor wiring.** Files: [5 (full implementation),
   12, 13]. Implement `ExecInitXxx` / `ExecXxx` / `ExecEndXxx` /
   `ExecReScanXxx`. Hook into `execProcnode.c` (init + end), `execAmi.c`
   (rescan + materialize/backward properties). Phase-end check: query
   that exercises the new node runs to completion and returns correct
   rows; `ExecProcNode` dispatches into `ExecXxx`.

4. **Phase 4 — EXPLAIN + parallel + tests + GUC.** Files: [14, 15, 17,
   18, 19, 22, 23]. Add EXPLAIN node-name + properties; add parallel
   DSM hooks if `parallel_safe`; add `enable_xxx` GUC if gated; add
   regression test exercising EXPLAIN, plain execution, and (if
   parallel-aware) a parallel-enabled query. Phase-end check:
   `meson test -C dev/build-debug --suite regress` clean, including
   the new test; EXPLAIN shows the node name correctly.

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`aggregate-grouping-sets`](../idioms/aggregate-grouping-sets.md) | shares files: `src/include/nodes/plannodes.h` |
| [`aggregate-partial-finalize`](../idioms/aggregate-partial-finalize.md) | shares files: `src/backend/optimizer/plan/createplan.c`, `src/include/nodes/nodes.h` |
| [`cost-join-paths`](../idioms/cost-join-paths.md) | shares files: `src/backend/optimizer/path/costsize.c` |
| [`cost-parallel-adjustments`](../idioms/cost-parallel-adjustments.md) | shares files: `src/backend/optimizer/path/costsize.c` |
| [`cost-scan-paths`](../idioms/cost-scan-paths.md) | shares files: `src/backend/optimizer/path/costsize.c` |
| [`cost-units-gucs`](../idioms/cost-units-gucs.md) | shares files: `src/backend/optimizer/path/costsize.c`, `src/include/optimizer/cost.h` |
| [`epq-multi-table`](../idioms/epq-multi-table.md) | shares files: `src/backend/optimizer/plan/createplan.c` |
| [`expression-evaluator-flow`](../idioms/expression-evaluator-flow.md) | direct reference |
| [`node-types`](../idioms/node-types.md) | shares files: `src/backend/nodes/gen_node_support.pl` |
| [`node-types-and-lists`](../idioms/node-types-and-lists.md) | direct reference |
| [`parallel-gather-merge`](../idioms/parallel-gather-merge.md) | shares files: `src/backend/executor/execParallel.c` |
| [`parallel-state-propagation`](../idioms/parallel-state-propagation.md) | direct reference |
| [`parser-pipeline`](../idioms/parser-pipeline.md) | shares files: `src/include/nodes/plannodes.h` |
| [`subplan-and-initplan`](../idioms/subplan-and-initplan.md) | shares files: `src/include/nodes/plannodes.h` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Dispatch-site amnesia** — the worst trap: `ExecInitNode` is
  obvious, but `ExecEndNode` / `ExecReScan` / `set_plan_refs` /
  `ExplainNode` / `ExecParallelEstimate` each have their own switch.
  Forgetting any one of them causes `elog(ERROR, "unrecognized node
  type: %d", ...)` at the corresponding lifecycle point — often
  during EXPLAIN ANALYZE or a rescan deep into testing. Grep
  `case T_SeqScan` across the tree before declaring done — every
  hit is a site you probably need to touch [verified-by-code](source/src/backend/executor/execAmi.c:166-650).
- **Wrong `pathtype` value** — `create_xxx_path` must set
  `path.pathtype = T_Xxx` (the *Plan* tag, not a path-specific tag).
  `create_plan_recurse` dispatches on `pathtype` [verified-by-code](source/src/backend/optimizer/plan/createplan.c:397).
  Get this wrong and the planner silently routes your path to the
  wrong `create_*_plan`.
- **`parallel_aware` vs `parallel_safe` confused** — `parallel_safe`
  = "OK to appear in a worker's plan tree at all"; `parallel_aware`
  = "actively cooperates with siblings via DSM" (e.g. Parallel
  SeqScan vs SeqScan-under-Gather). Setting `parallel_aware = true`
  without DSM hooks is a crash; setting `parallel_safe = false` for
  a safe node disables parallel plans needlessly [verified-by-code](source/src/include/nodes/plannodes.h:215-222).
- **Missing `ExecMaterializesOutput` / `ExecSupportsBackwardScan` /
  `ExecSupportsMarkRestore` entry** — if the node *does* support
  any of these but isn't listed in `execAmi.c`'s switches, the
  planner won't place it where it should and / or a Material node
  will be inserted unnecessarily. If the node *doesn't*, you don't
  need to add anything (default = false) [verified-by-code](source/src/backend/executor/execAmi.c:436-650).
- **Auto-gen drift** — `copy/equal/out/read/jumble/nodetags` are
  regenerated from header annotations. If your build fails because
  these files reference a missing field, the fix is in the *header*
  (annotation or field name), not in the generated `.c`. Don't edit
  the generated files by hand [from-comment](source/src/include/nodes/nodes.h:23-31).
- **ABI break in back-branches** — `gen_node_support.pl` assigns
  NodeTag values by position in `nodetags.h`. Inserting a new tag
  in `master` is fine, but if you have to backport, append at the
  end of the list to avoid renumbering existing tags (extensions
  link to specific tag values) [from-comment](source/src/include/nodes/nodes.h:21-31).

- **Synchronization traps** (sibling files that must change together):
  - `nodeXxx.c` ↔ `executor/meson.build` ↔ `executor/Makefile`
    (both build systems must list the new `.c`).
  - `XxxPath.pathtype` value ↔ `case T_Xxx:` in
    `create_plan_recurse` (same tag).
  - `ExecInitXxx` registers `ps.ExecProcNode = ExecXxx` ↔
    `ExecEndNode` knows about `T_XxxState` (init and end paired).
  - `parallel_aware = true` ↔ all four `ExecParallel*` dispatch
    sites in `execParallel.c` carry a case for `T_XxxState`.

## Verification (exact test invocations)

```bash
# Force codegen regen + full rebuild
meson compile -C dev/build-debug

# Verify the new tags landed in generated nodetags.h
grep -E "T_Xxx\b|T_XxxState\b" dev/build-debug/src/include/nodes/nodetags.h

# Verify copyfuncs / outfuncs picked up the new structs
grep -E "_copyXxx\b|_outXxx\b" dev/build-debug/src/backend/nodes/*.funcs.c

# Re-initdb only if you bumped catversion (this scenario usually doesn't)
# Otherwise restart and smoke-test:
dev/install-debug/bin/pg_ctl -D dev/data-debug -l logfile restart
psql -c "EXPLAIN <query that forces the new path>"
psql -c "EXPLAIN (ANALYZE, VERBOSE) <same query>"   # exercises show_xxx_info

# Regression — full suite (parallel + non-parallel paths)
meson test -C dev/build-debug --suite regress

# Specifically the new test file (if added)
meson test -C dev/build-debug --suite regress --test <new_test_name>

# Parallel-aware nodes: force parallel plans
psql -c "SET min_parallel_table_scan_size = 0;
         SET parallel_setup_cost = 0;
         SET parallel_tuple_cost = 0;
         EXPLAIN ANALYZE <query>"
```

If the node introduces new EXPLAIN output, add the EXPLAIN cases to
the regression test (in `parallel_schedule`-included files) so that
`pg_regress` catches format drift.

## Cross-refs

- Companion skills: `.claude/skills/executor-and-planner/SKILL.md`,
  `.claude/skills/parallel-query/SKILL.md`.
- Related scenarios: `scenarios/add-new-node-type.md` (the parsetree-
  only sibling — most plan nodes implicitly use that machinery for
  their structs), `scenarios/add-new-expression-eval-step.md` (when
  the change is to expression interpretation, not a Plan node),
  `scenarios/add-new-cost-model-knob.md` (when only the cost formula
  changes, no new node).
- Idioms: `knowledge/idioms/node-types-and-lists.md`,
  `knowledge/idioms/expression-evaluator-flow.md`,
  `knowledge/idioms/parallel-state-propagation.md`.
- Subsystems: `knowledge/subsystems/executor.md`,
  `knowledge/subsystems/optimizer.md`,
  `knowledge/subsystems/include-executor.md`.
- Issues: `knowledge/issues/executor.md` (if present; otherwise
  search `knowledge/issues/` for parallel/executor traps).
- Reference patch (canonical_commit): `git -C source show 9eacee2e62d`
  (Result Cache / Memoize, take 2); also `git -C source show
  83f4fcc6550` (the rename to Memoize, smaller and easier to diff).
