---
name: planner-cost-model
description: PostgreSQL's cost model — how the planner estimates query cost to pick among candidate plans. Covers `src/backend/optimizer/path/costsize.c` (the cost functions: `cost_seqscan`, `cost_index`, `cost_bitmap_heap_scan`, `cost_nestloop`, `cost_mergejoin`, `cost_hashjoin`, `cost_sort`, `cost_hashagg`, `cost_windowagg`, etc.) plus the cost GUCs (`seq_page_cost`, `random_page_cost`, `cpu_tuple_cost`, `cpu_index_tuple_cost`, `cpu_operator_cost`, `parallel_setup_cost`, `parallel_tuple_cost`, `jit_*_cost`). Loads when the user asks about cost estimation, why a plan differs from expected, how to tune cost GUCs, what units the numbers are in, or when to touch a specific `cost_*` function. Skip when the ask is about selectivity estimation (that's `clauselist_selectivity` and extended-stats territory) or about the actual EXPLAIN output rendering.
when_to_load: Debug bad plan choices; touch cost functions; tune cost GUCs; understand parallel cost adjustment; add a new cost mode for a new node type.
companion_skills:
  - executor-and-planner
  - extended-statistics
  - custom-scan-api
---

# planner-cost-model — how the planner chooses among plans

The planner generates many candidate Paths for a query. Each Path has a **cost** — a numeric estimate of how expensive it is to execute. The planner picks the cheapest.

Cost isn't in seconds or bytes — it's in "arbitrary units where `seq_page_cost = 1.0`". The RATIO matters, not the absolute value.

## The file map

| File | Role |
|---|---|
| `optimizer/path/costsize.c` | **The main file.** All the `cost_*` functions live here. 4000+ lines. |
| `optimizer/path/allpaths.c` | Path-generation orchestrator — calls the cost functions during path enumeration. |
| `optimizer/path/joinpath.c` | Join-specific path generation (calls cost_nestloop / _mergejoin / _hashjoin). |
| `optimizer/path/pathkeys.c` | Sort-order tracking — cheaper paths often preserve useful pathkeys. |
| `include/optimizer/cost.h` | The cost GUC declarations + planner-cost-related types. |

## The cost function family

Every path-shape has its cost function. A partial list:

| Function | Node |
|---|---|
| `cost_seqscan` | SeqScan — read all pages sequentially |
| `cost_index` | IndexScan / IndexOnlyScan |
| `cost_bitmap_heap_scan` | BitmapHeapScan — after bitmap-index accumulator |
| `cost_bitmap_and_or_node` | BitmapAnd / BitmapOr |
| `cost_tidscan` | TidScan — direct block+offset access |
| `cost_subqueryscan` | SubqueryScan |
| `cost_functionscan` | FunctionScan (SRF-in-FROM) |
| `cost_valuescan` | ValuesScan (VALUES-in-FROM) |
| `cost_gather` / `cost_gather_merge` | Parallel gather |
| `cost_recursive_union` | Recursive CTE |
| `initial_cost_nestloop` / `final_cost_nestloop` | 2-stage nestloop cost |
| `initial_cost_mergejoin` / `final_cost_mergejoin` | Mergejoin |
| `initial_cost_hashjoin` / `final_cost_hashjoin` | Hash join |
| `cost_sort` | Sort node |
| `cost_hashagg` / `cost_agg` | Aggregate |
| `cost_windowagg` | Window function |
| `cost_incremental_sort` | Incremental sort |
| `cost_memoize_rescan` | Memoize (PG 14+) |
| `cost_material` | Materialize |
| `cost_ctecan` | CTE Scan |

Each computes `startup_cost` (time to first row) + `total_cost` (time to last row).

## The 2-stage join cost pattern

Join paths use TWO cost functions:

- `initial_cost_*` — cheap; called during path enumeration to prune non-viable joins early.
- `final_cost_*` — expensive (selectivity + qual-cost); called only for paths that survive initial filtering.

This is O(N²) potential paths but O(N) expensive evaluations. The `JoinCostWorkspace` carries state between phases.

## The cost GUCs

Configuration knobs (in `postgresql.conf`):

| GUC | Default | Meaning |
|---|---|---|
| `seq_page_cost` | 1.0 | Cost of a sequential page read. The reference unit. |
| `random_page_cost` | 4.0 | Cost of a random page read. Lower for SSDs (2.0 or less common). |
| `cpu_tuple_cost` | 0.01 | CPU cost per tuple processed. |
| `cpu_index_tuple_cost` | 0.005 | CPU cost per index tuple. |
| `cpu_operator_cost` | 0.0025 | CPU cost per operator/function call. |
| `parallel_setup_cost` | 1000 | Fixed cost of starting workers — high, deters parallel for tiny queries. |
| `parallel_tuple_cost` | 0.1 | Cost of communicating a tuple from worker to leader. |
| `min_parallel_table_scan_size` | 8MB | Threshold for considering parallel seqscan. |
| `min_parallel_index_scan_size` | 512KB | Threshold for parallel index scan. |
| `jit_above_cost` | 100000 | JIT compilation threshold for total cost. |
| `jit_optimize_above_cost` | 500000 | JIT full optimization threshold. |
| `jit_inline_above_cost` | 500000 | JIT inlining threshold. |
| `effective_cache_size` | 4GB | Estimate of OS+shmem cache — affects index-scan cost. |
| `effective_io_concurrency` | 1 | Estimated concurrent I/O — affects bitmap heap scan cost. |

## The typical cost pattern

A cost function generally accumulates:

```
startup_cost = seq_or_random_page_cost * pages_read_before_first_tuple
             + cpu_tuple_cost * tuples_before_first
             + qual_cost.startup

total_cost = startup_cost
           + (seq_or_random_page_cost * pages_read_after)
           + (cpu_tuple_cost * tuples_produced)
           + (cpu_operator_cost * total_operator_calls)
           + qual_cost.per_tuple * tuples_produced
```

Selectivity comes from `clauselist_selectivity` (which consults per-column stats + extended stats).

## Parallel cost adjustment

Parallel paths get costs adjusted:

- `path->parallel_workers > 0`: divide the per-tuple work by parallel_workers.
- Then add `parallel_setup_cost` (once) + `parallel_tuple_cost` * (tuples returned to leader).
- Only paths with `parallel_safe = true` are eligible.

The tradeoff: parallel adds fixed overhead but divides per-row work. Only wins for larger inputs.

## Common patch shapes

### Add a cost function for a new node

- Function in costsize.c following the naming convention.
- Match the pattern (startup / per-page / per-tuple / per-operator).
- Register in the path-generation code that produces the new node.
- Test against existing similar nodes to validate.

### Change a cost function's algorithm

- Very impactful — plan choices shift.
- Compare EXPLAIN output before + after on a diverse workload (regression suite + your own).
- pgsql-hackers discussion recommended.

### Tune a cost GUC for a specific workload

- Not a code change; user-level.
- SSD workloads: `random_page_cost = 1.1` (close to seq).
- Very large working set: `effective_cache_size` = 75-90% of RAM.
- Parallel-heavy: `parallel_tuple_cost = 0.05` (allows parallel for smaller queries).

### Debug "planner picking the wrong plan"

- EXPLAIN ANALYZE — compare estimates to actual.
- If cost is WAY off but rows are close: cost function issue.
- If rows are WAY off: selectivity issue — see `extended-statistics` skill.
- Check if a specific GUC would fix it (random_page_cost is most common culprit).

## Pitfalls

- **Cost isn't in seconds** — it's a unit. Comparing costs across queries is meaningful (same units); interpreting a cost as time is not (varies with hardware).
- **`random_page_cost` too high locks in SeqScan** — a common Rate Limit on modern SSD systems. Reducing to 1.1-1.5 fixes many "why SeqScan on a small filtered range" problems.
- **`effective_cache_size` too low deters IndexScan** — the planner estimates repeat reads; a low value assumes cache misses.
- **`parallel_setup_cost` too low → over-parallelization** — small queries pay the worker startup + coordination for negative net gain.
- **JIT thresholds too aggressive → planning-time spike** — extremely large queries hit JIT compilation which is CPU-heavy in the planning path.
- **Cost of `qual_cost` includes function calls** — for user-defined functions marked as VOLATILE / EXPENSIVE, the planner assumes worst case. Marking IMMUTABLE where truly IMMUTABLE gives better plans.
- **`cost_sort` uses `work_mem`** — under memory pressure, sort spills to disk; the cost function accounts for this.
- **`enable_seqscan = off` doesn't remove the option, just penalizes** — the planner still considers SeqScan but with `disable_cost` added. Sometimes needed anyway.
- **Cross-partition-pruning costs are per-partition** — hitting many partitions accumulates cost; `enable_partition_pruning = on` (default) removes irrelevant ones early.

## Related corpus

- **Idioms** (many hits): `cost-scan-paths`, `cost-join-paths`, `cost-parallel-adjustments`, `cost-units-gucs`.
- **Subsystem**: `optimizer` (the parent — cost is one aspect of path generation).
- **Related skills**: `extended-statistics` (selectivity side), `custom-scan-api` (registering costs for custom paths).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom cost-scan-paths
python3 scripts/corpus-chain.py --file src/backend/optimizer/path/costsize.c
```

## Boundary

**Use this skill** for cost estimation + cost function additions + cost GUC tuning.

**Don't use** for:
- **Selectivity** — different concept. See `extended-statistics` and `analyze-mcv-histogram-correlation` idiom.
- **EXPLAIN output rendering** — that's `explain.c`, uses the cost as an input.
- **Actual runtime performance** — cost is an estimate; measure real perf with `EXPLAIN (ANALYZE, BUFFERS, TIMING)`.
- **Query rewriter cost** — the rewriter doesn't consult a cost model; it's rule-based.
