---
source_url: https://www.postgresql.org/docs/current/using-explain.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "14.1 Using EXPLAIN"
maps_to_skills: [executor-and-planner, planner-cost-model, testing]
---

# 14.1 Using EXPLAIN — reading the plan tree

Distilled from the official docs §14.1. The page is the operator-facing
description of the planner's output, but the mechanics it exposes (cost
units, `rows` = emitted-not-scanned, child-cost inclusion, per-node loop
averaging) are load-bearing when reading `EXPLAIN` inside a backend-hacking
or regression-diff context.

## Non-obvious claims

- **Cost is in an arbitrary unit conventionally pinned to one sequential
  page fetch.** `seq_page_cost` is conventionally `1.0` and every other
  `cpu_*`/`random_page_cost` parameter is expressed relative to it. The unit
  is *not* milliseconds. [from-docs §14.1.1]
- **The worked cost formula** for a plain seq scan is
  `(disk_pages × seq_page_cost) + (rows_scanned × cpu_tuple_cost)`. Doc
  example: 345 pages, 10000 rows, defaults `seq_page_cost=1.0`,
  `cpu_tuple_cost=0.01` → `345 + 100 = 445`. [from-docs §14.1.1]
- **Two cost numbers per node: startup cost then total cost.** Startup is
  the estimated work before the first row can be emitted (e.g. the whole
  input of a `Sort`); total assumes the node runs to completion. A `LIMIT`
  parent means total cost is *not* actually paid. [from-docs §14.1.1]
- **`rows` is the number of rows the node EMITS, not the number it scans.**
  It is already reduced by that node's `WHERE`/filter conditions. This is the
  single most misread field. [from-docs §14.1.1]
- **A parent node's cost already includes all its children's costs.** You do
  not sum siblings up the tree — the root total is the whole-query estimate.
  [from-docs §14.1.1]
- **Cost deliberately ignores output-conversion and network transmission
  time** — "the planner ignores those costs because it cannot change them by
  altering the plan." So `width` (bytes/row) feeds memory/sort estimates but
  the text-encoding cost is invisible. [from-docs §14.1.1]
- **`EXPLAIN ANALYZE` actually executes the query.** Side effects happen;
  wrap DML in `BEGIN … ROLLBACK`. Output adds `(actual time=start..end
  rows=N loops=L)` beside the estimate. [from-docs §14.1.2]
- **`loops` averages, it does not total.** For a node executed L times (e.g.
  the inner side of a nested loop), the shown `actual time` and `rows` are
  *per-execution averages*; multiply by `loops` for the true total. [from-docs §14.1.2]
- **`BUFFERS` is implicitly enabled by `ANALYZE`** (disable with
  `(ANALYZE, BUFFERS OFF)`); counts are non-distinct buffers hit / read /
  dirtied / written for planning and execution. [from-docs §14.1.2]
- **`BitmapAnd` / `BitmapOr` nodes always report `actual rows=0`** — an
  implementation limitation, not a real zero. Don't read it as "no rows".
  [from-docs §14.1.3]
- **`Join Filter` vs plain `Filter` differ under outer joins.** A row failing
  a `Join Filter` (from the outer join's `ON`) can still be emitted
  null-extended; a plain `Filter` removes rows unconditionally. [from-docs §14.1.2]
- **Execution Time includes BEFORE-trigger time but excludes AFTER-trigger
  time** (AFTER fires after the plan completes) and excludes parse/rewrite/
  plan and — unless `SERIALIZE` — output serialization. Planning Time
  excludes parse/rewrite. [from-docs §14.1.2]
- **`gettimeofday()` overhead can dominate `EXPLAIN ANALYZE`** on machines
  with slow clocks — the measured actual times carry that tax (see
  `pg_test_timing`). [from-docs §14.1.2] [[knowledge/docs-distilled/pgtesttiming.md]]

## Links into corpus

- Node taxonomy the plan tree prints — `Seq Scan`/`Index Scan`/`Bitmap Heap
  Scan`/`Nested Loop`/`Hash Join`/`Sort`/`Append` — is the executor
  `ExecProcNode` dispatch: [[knowledge/subsystems/executor.md]],
  [[knowledge/docs-distilled/executor.md]].
- Cost-parameter provenance (`seq_page_cost`, `cpu_tuple_cost`,
  `random_page_cost`): [[knowledge/docs-distilled/runtime-config-query.md]],
  [[knowledge/subsystems/optimizer.md]].
- The estimated-`rows` selectivity path: [[knowledge/docs-distilled/planner-stats.md]],
  [[knowledge/docs-distilled/row-estimation-examples.md]].
- Bitmap-scan `actual rows=0` quirk ↔ the bitmap-scan mechanics:
  [[knowledge/docs-distilled/indexes-bitmap-scans.md]].
- Contrib EXPLAIN extenders: [[knowledge/subsystems/contrib-auto_explain.md]],
  [[knowledge/subsystems/contrib-pg_overexplain.md]].

## Citations

- All bullets: source-URL §14.1.1 / §14.1.2 / §14.1.3 above.
- `cpu_tuple_cost=0.01`, `seq_page_cost=1.0` defaults corroborated by the
  cost GUCs in `source/src/backend/optimizer/path/costsize.c` (the
  `DEFAULT_*_COST` macros); doc-stated values used here. [from-docs]
