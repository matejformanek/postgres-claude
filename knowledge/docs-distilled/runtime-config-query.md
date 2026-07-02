---
source_url: https://www.postgresql.org/docs/current/runtime-config-query.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Query Planning configuration

The planner GUC reference, distilled to non-obvious semantics. Serves the
heaviest `executor-and-planner` skill surface. Companion:
`knowledge/docs-distilled/planner-optimizer.md`,
`knowledge/subsystems/optimizer.md`.

## enable_* are cost penalties, not hard switches

- **`enable_seqscan`, `enable_nestloop`, `enable_sort`, `enable_material`
  cannot be truly turned off** — disabling them applies a large *disable-cost*
  penalty so the planner avoids the node when any alternative exists, but it
  will still use it when required for correctness. All default `on`. [from-docs]
- **`enable_indexonlyscan` requires `enable_indexscan`; `enable_parallel_hash`
  requires `enable_hashjoin`.** [from-docs]
- **`enable_partitionwise_join` and `enable_partitionwise_aggregate` default
  OFF** — they're gated because peak memory grows **linearly with partition
  count**. `enable_partition_pruning` (default on) is the cheap, always-on one.
  [from-docs]
- Newer default-on nodes worth knowing: `enable_memoize` (caches parameterized
  inner scans in nestloops), `enable_incremental_sort`,
  `enable_self_join_elimination`, `enable_group_by_reordering`,
  `enable_distinct_reordering`, `enable_presorted_aggregate`. [from-docs]

## Cost constants: ratios, not real units

- **Only ratios matter** — everything is relative to `seq_page_cost = 1.0`.
  `random_page_cost = 4.0` **assumes most random reads are already cached** (raw
  spinning-disk ratio would be ~40); on SSD/well-cached systems, lowering it
  toward 1.1 is standard. Overridable per tablespace. [from-docs]
- **`effective_cache_size` (default 4GB) is an ESTIMATE, not an allocation** —
  it tells the planner how much OS+PG cache a repeated index scan can expect.
  Higher favors index scans, lower favors seqscans. [from-docs]
- CPU costs: `cpu_tuple_cost` 0.01, `cpu_index_tuple_cost` 0.005,
  `cpu_operator_cost` 0.0025. Parallel: `parallel_setup_cost` 1000,
  `parallel_tuple_cost` 0.1, `min_parallel_table_scan_size` 8MB,
  `min_parallel_index_scan_size` 512kB (also used to size parallel vacuum).
  JIT gates: `jit_above_cost` 100000, `jit_inline_above_cost` /
  `jit_optimize_above_cost` 500000 (must be ≥ jit_above_cost). [from-docs]

## GEQO and join-order control

- **`geqo` on, `geqo_threshold` 12**: above 12 FROM items the planner switches
  from exhaustive search to the genetic optimizer (a FULL OUTER JOIN counts as
  one item). `geqo_effort` (5) only *computes defaults* for
  `geqo_pool_size`/`geqo_generations` (both 0 = auto); it has no direct effect.
  [from-docs]
- **`join_collapse_limit` (defaults to `from_collapse_limit` = 8) set to 1
  disables all reordering of explicit JOINs** — the planner honors the written
  join order verbatim (a manual optimization hint). [from-docs]

## Other planner options

- **`plan_cache_mode` (auto)** is evaluated **at execution time, not prepare
  time**: `force_generic_plan` reuses one plan, `force_custom_plan` re-plans
  every execute. [from-docs]
- `constraint_exclusion` default `partition` (only inheritance/UNION-ALL);
  `cursor_tuple_fraction` 0.1 biases cursors toward fast-start plans;
  `default_statistics_target` 100; `recursive_worktable_factor` 10.0 (lower for
  low-fanout graph queries). [from-docs]

## Links into corpus

- [[knowledge/subsystems/optimizer.md]] — path generation these costs drive.
- [[knowledge/docs-distilled/planner-optimizer.md]] — planner-stage overview.
- [[knowledge/docs-distilled/explicit-joins.md]] — join_collapse_limit in depth.
- [[knowledge/docs-distilled/parallel-plans.md]] — parallel cost constants.
- Skill: `executor-and-planner` — cost.h units, add_path pruning.

## Confidence note

All claims `[from-docs]` (Query Planning chapter, fetched 2026-07-01). Defaults
quoted from the page; the disable-cost mechanism lives in
`src/backend/optimizer/path/costsize.c` and is `[from-docs]`-only here.
