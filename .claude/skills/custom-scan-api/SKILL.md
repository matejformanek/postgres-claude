---
name: custom-scan-api
description: PostgreSQL's Custom Scan / Custom Path API — the pluggable executor node interface that lets extensions add new physical operators (custom joins, custom aggregates, custom scan providers like columnar backends). Covers `CustomScanMethods` + `CustomExecMethods` + `CustomPathMethods` in `src/backend/executor/nodeCustom.c` + `src/backend/optimizer/util/plannodes.c` (for CustomPath / CustomScan). Loads when the user asks about custom scan providers, how citus / timescaledb / greenplum-style columnar backends integrate, CustomPath cost registration, `RegisterCustomScanMethods`, or "how does the planner know about my extension's node type". Skip when the ask is about extending the built-in AM (table AM / index AM — different pluggable interface) or about GetForeignPaths (FDW — sibling but has its own skill).
when_to_load: Build a custom-scan extension; understand how it plugs into the planner; extend cost model for new operators; investigate why the planner isn't picking a custom path.
companion_skills:
  - executor-and-planner
  - fdw-development
  - access-method-apis
---

# custom-scan-api — plug new executor nodes into the planner

Custom Scan lets you register a NEW EXECUTOR NODE from an extension. Unlike an FDW (which handles "foreign data"), Custom Scan is for entirely new operations: parallelization strategies, columnar processing, hardware acceleration (GPU joins), specialized aggregates. citus (distributed queries) and timescaledb (chunk elimination) both use it heavily.

Two-part registration:

- **CustomPath** — planner side. Register a Path shape the planner can consider during path generation.
- **CustomScan / CustomScanState** — executor side. Turn the picked Path into a runnable node.

## The file map

| File | Role |
|---|---|
| `src/backend/optimizer/util/pathnode.c` | Path construction — `create_customscan_path` for extensions. |
| `src/backend/optimizer/plan/createplan.c` | `create_customscan_plan` — converts CustomPath → CustomScan Plan node. |
| `src/backend/executor/nodeCustom.c` | Runtime — `ExecInitCustomScan` / `ExecCustomScan` / `ExecEndCustomScan` — dispatches to the extension's methods. |
| `src/include/commands/customexpr.h` | Public API — CustomPathMethods, CustomScanMethods, CustomExecMethods structs. |
| `src/backend/nodes/copyfuncs.c` / `readfuncs.c` / `outfuncs.c` | Serialization support for CustomPath / CustomScan. |

## The three method structs

### `CustomPathMethods` — planner-side

```c
typedef struct CustomPathMethods {
    const char *CustomName;

    /* Called when converting Path to Plan */
    Plan *(*PlanCustomPath)(PlannerInfo *, RelOptInfo *, CustomPath *, List *, List *);
} CustomPathMethods;
```

Only one required callback: `PlanCustomPath`, which produces the `CustomScan` Plan node.

### `CustomScanMethods` — plan-node-side

```c
typedef struct CustomScanMethods {
    const char *CustomName;

    /* Called at executor init to convert Plan → PlanState */
    Node *(*CreateCustomScanState)(CustomScan *);
} CustomScanMethods;
```

### `CustomExecMethods` — executor-side

```c
typedef struct CustomExecMethods {
    const char *CustomName;

    /* Init */
    void (*BeginCustomScan)(CustomScanState *, EState *, int);
    /* Iterate */
    TupleTableSlot *(*ExecCustomScan)(CustomScanState *);
    /* Cleanup */
    void (*EndCustomScan)(CustomScanState *);

    /* Rescan */
    void (*ReScanCustomScan)(CustomScanState *);

    /* Parallel */
    Size (*EstimateDSMCustomScan)(CustomScanState *, ParallelContext *);
    void (*InitializeDSMCustomScan)(CustomScanState *, ParallelContext *, void *);
    void (*ReInitializeDSMCustomScan)(...);
    void (*InitializeWorkerCustomScan)(CustomScanState *, shm_toc *, void *);

    /* Explain */
    void (*ExplainCustomScan)(CustomScanState *, List *, ExplainState *);

    /* etc */
} CustomExecMethods;
```

The full lifecycle: Begin → (Rescan?)* → Exec → End. Optional callbacks for parallel + explain.

## Registration

An extension registers its methods at `_PG_init` time:

```c
static const CustomPathMethods my_path_methods = { ... };
static const CustomScanMethods my_scan_methods = { ... };
static const CustomExecMethods my_exec_methods = { ... };

void _PG_init(void) {
    RegisterCustomScanMethods(&my_scan_methods);
    /* CustomPathMethods and CustomExecMethods don't have a global
     * registry — they're attached to the Path/PlanState directly. */
}
```

The `RegisterCustomScanMethods` global registry is required so that `readfuncs.c` can deserialize a stored plan (e.g., from prepared statements) and find the methods by name.

## How the planner chooses your path

You have to INSERT a CustomPath into the paths under consideration. Two hooks:

1. **`set_rel_pathlist_hook`** — called for each base relation after built-in paths are considered. Your extension can add CustomPaths here.
2. **`set_join_pathlist_hook`** — called for each join, letting you contribute custom join paths.
3. **Custom aggregate paths** — `create_upper_paths_hook` — for GROUP BY / DISTINCT / LIMIT stages.

The planner then picks the cheapest — so your CustomPath's `startup_cost` + `total_cost` matter. Register accurate costs or the planner won't pick you.

## Parallel-aware custom scans

If your operation can run in parallel:

- Set `path->parallel_aware = true`.
- Set `path->parallel_safe = true` (means "can appear below a Gather").
- Implement `EstimateDSMCustomScan`, `InitializeDSMCustomScan`, `InitializeWorkerCustomScan`.
- Coordinate with `shm_toc` for shared state between leader + workers.

Non-parallel-aware but parallel-safe means "runs in one worker" — no shared state needed.

## Common patch shapes

### Write a new custom-scan extension

1. Define 3 method structs at file scope.
2. In `_PG_init`, call `RegisterCustomScanMethods`.
3. In a hook (`set_rel_pathlist_hook`), create CustomPath instances and add via `add_path`.
4. Implement `PlanCustomPath` — produce a CustomScan node with tlist, cost, custom private fields.
5. Implement `CreateCustomScanState` — return a subclass of CustomScanState.
6. Implement executor callbacks.
7. Optional: implement Explain callback for `EXPLAIN VERBOSE`.
8. Optional: implement parallel-DSM callbacks.

### Extend CustomScan's flags / info

Rare — the API is stable. Adding new callbacks to the method struct is possible (backward compat: extensions using older ABI keep working).

### Debug "my custom scan isn't picked"

- `set_debug_pretty_print = on` + EXPLAIN — is your Path even considered?
- Set `SET custom_scan.debug = on` in your extension (define your own GUC).
- Check that your path cost is lower than the built-in alternatives.
- Check that your CustomPath is being added inside the RIGHT hook (not too late).
- Check `set_rel_pathlist_hook` is being called — some Path shapes bypass it (e.g. inheritance children).

## Pitfalls

- **Cost register faithfully** — inflating your CustomPath's cost hides it; deflating it locks you in even when built-in is better. Get selectivity right.
- **`parallel_safe` LIES cause wrong-results bugs** — a scan that appears safe but has hidden state = wrong results under parallel. Test with `force_parallel_mode = on` before shipping.
- **`RegisterCustomScanMethods` requires unique names** — collisions with another extension = crash. Use a namespaced name.
- **`readfuncs.c` deserialization requires the extension is loaded** — a prepared statement stored with your CustomScan needs your extension in `shared_preload_libraries`.
- **Extension unload leaves dangling function pointers** — even if PG allowed unload (it mostly doesn't), the CustomScan methods would crash on execution.
- **`copyObject` of a CustomScan requires the methods pointer to be stable** — usually is, but confirm your struct is a static const.
- **Tuple table slots must match** — `ExecCustomScan` returns a slot; that slot's TupleDesc must match what the planner expects (tlist).
- **Rescan is called MULTIPLE times** — for NestLoop-inner scans. Handle stateful cleanup between rescans.
- **Parallel worker state initialization order** — leader inits DSM, worker attaches. Race conditions possible if leader assumes worker is ready.
- **`ExplainCustomScan` must not allocate long-lived state** — runs in an ephemeral context.

## Real-world examples

- **citus** — distributed query engine. CustomPath for cross-node execution.
- **TimescaleDB** — hypertable chunk elimination via custom paths.
- **Greenplum-style column stores** — replace `SeqScan` with a columnar custom scan.
- **`pg_hint_plan`** — hints via custom-scan-adjacent hooks.

## Related corpus

- **Idioms**: `parallel-context-and-dsm` (parallel setup — CustomScan uses the same infra), `fdw-iterate-scan` (sibling Iterate pattern).
- **Subsystems**: `executor` (nodeCustom.c integration), `optimizer` (Path/Plan side).
- **Skills**: `executor-and-planner` (broader), `fdw-development` (sibling extension seam), `parallel-query` (parallel considerations).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/executor/nodeCustom.c
```

## Boundary

**Use this skill** for CustomScan/CustomPath integration + extension custom-node authoring.

**Don't use** for:
- **FDW** — sibling but different extension seam. See `fdw-development`.
- **Table AM** — different pluggable interface. See `access-method-apis`.
- **Index AM** — same.
- **Custom aggregates via CREATE AGGREGATE** — that's the SQL-level agg API, not the executor node level.
- **`ExecProcNode`-level modifications** — non-extensible; core executor only.
