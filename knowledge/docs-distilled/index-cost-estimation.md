---
source_url: https://www.postgresql.org/docs/current/index-cost-estimation.html
fetched_at: 2026-06-12T20:47:00Z
anchor_sha: e18b0cb
chapter: "63.6 Index Cost Estimation Functions"
---

# Index Cost Estimation Functions (docs §63.6)

The `amcostestimate` contract: what the planner hands an AM and what five
outputs the AM must fill so `add_path` can compare index paths. `[from-docs]`
unless a `source/` cite is given.

## Non-obvious claims

- **Fixed signature, five out-params by reference:**
  ```c
  void amcostestimate(PlannerInfo *root, IndexPath *path, double loop_count,
                      Cost *indexStartupCost, Cost *indexTotalCost,
                      Selectivity *indexSelectivity, double *indexCorrelation,
                      double *indexPages);
  ```
  Every `path` field *except* the cost/selectivity outputs is already valid on
  entry. `[from-docs]`
- **`loop_count` > 1 means a parameterized (nestloop-inner) scan, but the
  returned costs must still be for a *single* scan** — averaged across the
  loops. The larger `loop_count` is the AM's cue that cross-scan caching may
  matter; it does not scale the returned numbers. `[from-docs]`
- **Scope line is sharp: cost the index scan *only*.** All disk+CPU of scanning
  the index itself is in; *retrieving or processing the heap rows the index
  points at is explicitly out* (the caller adds that separately). `[from-docs]`
- **`*indexSelectivity` is the fraction of *parent-table* rows retrieved, and for
  lossy index quals it is typically *higher* than the fraction that actually
  pass the quals** (the recheck filters the rest). `[from-docs]`
- **`*indexCorrelation` ∈ [-1.0, 1.0]** between index order and physical heap
  order; it feeds the *caller's* heap-fetch cost adjustment (sequential vs.
  random heap access). If unknown, use the conservative `0`. `[from-docs]`
- **`*indexPages` = number of leaf pages**, used specifically to size the worker
  count for a *parallel* index scan. `[from-docs]`
- **`*indexStartupCost` is usually zero**, nonzero only for high-startup index
  types (e.g. those that must do work before returning the first tuple).
  `[from-docs]`
- **Must be written in C** — the function touches planner/optimizer internals, so
  SQL/PL implementations are impossible. `[from-docs]`
- **The four costing units come from `costsize.c`:** `seq_page_cost`,
  `random_page_cost`, `cpu_index_tuple_cost`, `cpu_operator_cost`. The generic
  recipe deliberately charges **`seq_page_cost` (not random)** per index page,
  assuming leaf pages are read roughly sequentially. `[from-docs]`
- **Generic skeleton** (the docs' own worked example): selectivity via
  `clauselist_selectivity(root, path->indexquals, …, JOIN_INNER, NULL)`; index
  rows ≈ selectivity × index tuples; index pages ≈ selectivity × index pages;
  then `cost_qual_eval()` on the indexquals to get per-tuple qual cost, and
  `indexTotalCost = seq_page_cost*numIndexPages + (cpu_index_tuple_cost +
  qual.per_tuple)*numIndexTuples`. This skeleton does *not* amortize repeated
  scans — the AM refines that itself when `loop_count` warrants. `[from-docs]`
- Reference implementations live in `src/backend/utils/adt/selfuncs.c`
  (`genericcostestimate` + the per-AM `btcostestimate` etc.); index metadata is
  read from `path->indexinfo` (relid, pages, tuples). `[from-docs]`

## Links into corpus

- [[knowledge/subsystems/optimizer.md]] — where IndexPath costing fits in path
  generation and `add_path` dominance pruning.
- [[knowledge/files/src/backend/utils/adt/selfuncs.c.md]] — home of
  `genericcostestimate`, `btcostestimate`, `clauselist_selectivity`.
- [[knowledge/subsystems/access-nbtree.md]] — btree's `amcostestimate` is the
  worked example.
- Skill: `executor-and-planner` (cost_* units, IndexPath, add_path),
  `access-method-apis` (amcostestimate slot in IndexAmRoutine).

## Citations

- All claims `[from-docs]`. `amcostestimate` is dispatched via the
  `IndexAmRoutine.amcostestimate` slot (`source/src/include/access/amapi.h`); the
  generic helper is `genericcostestimate()` in
  `source/src/backend/utils/adt/selfuncs.c`; cost units in
  `source/src/backend/optimizer/path/costsize.c`. Verify line numbers at anchor
  e18b0cb before quoting.
