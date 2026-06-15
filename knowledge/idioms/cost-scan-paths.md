# Cost scan paths — cost_seqscan / cost_index / cost_bitmap_heap_scan

For each base relation in a query, the planner enumerates **scan
paths**: sequential, index, index-only, bitmap-heap, tid, sample.
Each `cost_*` function in `costsize.c` computes the same shape:
`startup_cost + disk_run_cost + cpu_run_cost`. The differences
are in (a) which page-cost GUC applies (seq vs random), (b) how
many pages get touched (selectivity × table size, or the
Mackert-Lohman formula for index scans), and (c) the per-tuple
operator costs of any unused-by-index quals (qpquals). Parallel
variants divide CPU cost by the parallel divisor.

Anchors:
- `source/src/backend/optimizer/path/costsize.c:270` —
  cost_seqscan [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:299` —
  disk_run_cost = spc_seq_page_cost * baserel->pages
  [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:545` —
  cost_index [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:609-620` —
  amcostestimate dispatch [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:1012` —
  cost_bitmap_heap_scan [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:1251` —
  cost_tidscan [verified-by-code]
- `knowledge/idioms/cost-units-gucs.md` — companion
- `knowledge/idioms/cost-join-paths.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## cost_seqscan — the baseline

[verified-by-code `costsize.c:270-339`]

```c
void
cost_seqscan(Path *path, PlannerInfo *root,
             RelOptInfo *baserel, ParamPathInfo *param_info)
{
    /* row estimate */
    path->rows = param_info ? param_info->ppi_rows : baserel->rows;

    get_tablespace_page_costs(baserel->reltablespace,
                              NULL, &spc_seq_page_cost);

    /* disk costs */
    disk_run_cost = spc_seq_page_cost * baserel->pages;

    /* CPU costs */
    get_restriction_qual_cost(root, baserel, param_info, &qpqual_cost);
    startup_cost += qpqual_cost.startup;
    cpu_per_tuple = cpu_tuple_cost + qpqual_cost.per_tuple;
    cpu_run_cost = cpu_per_tuple * baserel->tuples;

    /* per-output-row tlist eval */
    startup_cost += path->pathtarget->cost.startup;
    cpu_run_cost += path->pathtarget->cost.per_tuple * path->rows;

    /* parallel divisor */
    if (path->parallel_workers > 0) {
        double parallel_divisor = get_parallel_divisor(path);
        cpu_run_cost /= parallel_divisor;
        path->rows = clamp_row_est(path->rows / parallel_divisor);
    }

    path->startup_cost = startup_cost;
    path->total_cost = startup_cost + cpu_run_cost + disk_run_cost;
}
```

The pattern repeats in every scan cost function:
1. **Resolve row estimate** (from baserel.rows or ppi_rows).
2. **Disk cost** — pages × page_cost.
3. **CPU cost** — tuples × (cpu_tuple_cost + qpqual.per_tuple).
4. **Per-row tlist** — output rows × per_tuple_target_cost.
5. **Parallel divisor** if applicable.

Note: disk cost is NOT divided by parallel workers — the
comment at `costsize.c:319-324` explains this is intentional (OS
prefetch already amortizes I/O).

## cost_index — the Mackert-Lohman formula

[verified-by-code `costsize.c:545+`]

cost_index is more complex because it delegates the index-AM-
specific work via `amcostestimate`:

```c
amcostestimate = (amcostestimate_function) index->amcostestimate;
amcostestimate(root, path, loop_count,
               &indexStartupCost, &indexTotalCost,
               &indexSelectivity, &indexCorrelation,
               &index_pages);
```

This callback (btcostestimate, hashcostestimate, etc.) returns:
- `indexStartupCost` / `indexTotalCost` — cost of traversing the
  index itself.
- `indexSelectivity` — fraction of base table tuples that will
  match.
- `indexCorrelation` — Spearman's rho between index and heap
  ordering. After a CLUSTER, ~1.0; for a random column, ~0.
- `index_pages` — number of index pages read.

Then cost_index figures out heap fetches:
```
tuples_fetched = indexSelectivity * baserel->tuples
pages_fetched  = index_pages_fetched(...)   /* Mackert-Lohman */
```

The Mackert-Lohman approximation models how many of the heap
pages we'll need to touch given (selectivity, table size, cache
size). With correlation = 1.0, pages_fetched ≈ pages * selectivity
and most are sequential. With correlation ≈ 0, pages_fetched is
larger (more pages touched, randomly).

I/O cost interpolates between two bounds based on
`indexCorrelation²`:

```
min_IO_cost = spc_random_page_cost                          /* perfect correlation */
            + (pages_fetched - 1) * spc_seq_page_cost
max_IO_cost = pages_fetched * spc_random_page_cost          /* zero correlation */

run_cost  += max_IO_cost + csquared * (min_IO_cost - max_IO_cost)
```

`csquared = indexCorrelation²`. Why squared: the literature
suggests the linear interpolation is more accurate that way.

## Index-only scan adjustment

[verified-by-code `costsize.c:661-666` comment]

> If it's an index-only scan, then we will not need to fetch any
> heap pages for which the visibility map shows all tuples are
> visible.

Index-only scans reduce `tuples_fetched` by the all-visible
fraction:
```
tuples_fetched *= 1.0 - all_visible_fraction
```

This is why CLUSTER + VACUUM + index-only scans show dramatic
speedups: post-VACUUM, the VM bits are mostly set, so heap
fetches drop to near-zero.

## cost_bitmap_heap_scan — bitmap path

[verified-by-code `costsize.c:1012+`]

A bitmap heap scan has a separate sub-path (BitmapIndexScan or
BitmapOr/BitmapAnd) that produces the TBM. cost_bitmap_heap_scan
takes that as input:

```
total_cost = bitmap_subpath_cost
           + per-page heap fetch cost (random_page_cost,
                                       reduced as bitmap density rises)
           + per-tuple CPU cost
```

Page-cost is reduced as the matched-pages fraction approaches 1:
a bitmap that touches every page becomes effectively
sequential. The interpolation is `(1 - density)² * (random_cost
- seq_cost) + seq_cost`.

## cost_tidscan — single-row by CTID

[verified-by-code `costsize.c:1251+`]

When the qual is `WHERE ctid = '(5,3)'` (rare in user code; common
in EvalPlanQual), cost_tidscan estimates one random page fetch
per distinct CTID. Cheap and bounded; usually not the bottleneck.

## qpquals — quals not handled by the access method

[verified-by-code `costsize.c:599-600`]

```c
qpquals = extract_nonindex_conditions(path->indexinfo->indrestrictinfo,
                                      path->indexclauses);
```

If the index covers `WHERE a = 5 AND b > 3` only via the
`a = 5` condition, `b > 3` becomes a qpqual — applied per-row
post-fetch. `get_restriction_qual_cost` evaluates each qpqual's
cost, accumulating into `cpu_per_tuple`.

## Path enable_mask + disabled_nodes

[verified-by-code `costsize.c:603-607`]

```c
enable_mask = (indexonly ? PGS_INDEXONLYSCAN : PGS_INDEXSCAN)
    | (partial_path ? 0 : PGS_CONSIDER_NONPARTIAL);
path->path.disabled_nodes =
    (baserel->pgs_mask & enable_mask) == enable_mask ? 0 : 1;
```

Each path tracks a count of disabled nodes in its sub-tree, plus
its own (if its kind is disabled). `add_path` uses both
`disabled_nodes` and `total_cost` to decide whether one path
dominates another. The fewer disabled-nodes always wins,
breaking ties by cost.

## Common review-time concerns

- **Disk cost is NOT divided by workers** — only CPU is.
- **Index correlation² matters** — CLUSTERed tables get dramatic
  index-scan cost reductions.
- **Index-only scan depends on VM bits** — VACUUM ANALYZE keeps
  them current.
- **qpquals are per-row CPU cost** — affect total CPU but NOT
  page fetches.
- **Mackert-Lohman caps pages_fetched at baserel.pages** —
  selectivity × tuples that exceeds the table is clamped.
- **Bitmap density reduces effective random cost** — densely-
  matching bitmaps approach seq cost.
- **loop_count > 1 changes index cost** — for parameterized
  inner-loop paths (the rescan cost amortizes index pages).

## Invariants

- **[INV-1]** All cost functions return `{startup_cost,
  total_cost, disabled_nodes, rows}` populated.
- **[INV-2]** Parallel scans divide CPU but NOT disk cost.
- **[INV-3]** Index scan I/O interpolates between min and max
  IO cost using indexCorrelation².
- **[INV-4]** Index-only scan reduces heap fetches by
  all-visible fraction.
- **[INV-5]** disabled_nodes accumulates from sub-paths +
  self-disable check.

## Useful greps

- The scan cost family:
  `grep -n '^cost_seqscan\|^cost_index\|^cost_bitmap_heap_scan\|^cost_tidscan\|^cost_samplescan' source/src/backend/optimizer/path/costsize.c | head -10`
- Mackert-Lohman:
  `grep -n 'index_pages_fetched\|indexCorrelation\|csquared' source/src/backend/optimizer/path/costsize.c | head -10`
- amcostestimate per-AM:
  `grep -RIn 'btcostestimate\|hashcostestimate\|gistcostestimate\|gincostestimate\|brincostestimate' source/src/backend/utils/adt source/src/backend/access | head -10`
- Per-tablespace cost lookup:
  `grep -n 'get_tablespace_page_costs' source/src/backend/optimizer/path/costsize.c | head -10`

## Cross-references

- `knowledge/idioms/cost-units-gucs.md` — the seq/random/cpu
  cost GUCs these functions consume.
- `knowledge/idioms/cost-join-paths.md` — initial / final
  cost_* for joins.
- `knowledge/idioms/visibility-map-heap.md` — VM bit governs
  index-only effectiveness.
- `knowledge/data-structures/plannerinfo.md` — Path /
  RelOptInfo / IndexOptInfo.
- `knowledge/idioms/index-am-callbacks.md` — amcostestimate
  callback.
- `knowledge/idioms/parallel-bitmap-heap.md` — executor side
  of bitmap scan.
- `knowledge/subsystems/optimizer.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/optimizer/path/costsize.c` — full module.
