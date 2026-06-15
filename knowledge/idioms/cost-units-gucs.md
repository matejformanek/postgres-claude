# Cost units and GUCs — the cost.h calibration constants

PostgreSQL's planner expresses every path's cost in **abstract
units** keyed off `seq_page_cost = 1.0`. All other costs are
defined relative: a `random_page_cost = 4.0` page fetch is 4×
the cost of a sequential one, `cpu_tuple_cost = 0.01` means
processing 100 tuples equals reading one sequential page,
`cpu_operator_cost = 0.0025` puts function evaluations at 1/400
of a page. The numbers are calibrated to historical spinning
disks; SSDs typically warrant tuning `random_page_cost` toward
`seq_page_cost` (1.1–2.0). All cost-related GUCs are double-typed
globals in `costsize.c`, defaulted from `cost.h` macros, with
per-tablespace overrides via pg_tablespace options.

Anchors:
- `source/src/include/optimizer/cost.h:24-30` — default
  cost macros [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:131-138` —
  global double declarations [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:7-19` —
  the "what these mean" header comment [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:142` —
  disable_cost = 1.0e10 [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:146-167` —
  enable_* booleans [verified-by-code]
- `knowledge/idioms/cost-scan-paths.md` — companion
- `knowledge/idioms/cost-join-paths.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The seven cost GUCs

[verified-by-code `cost.h:24-30` + `costsize.c:131-137`]

| GUC | Default | What it represents |
|---|---|---|
| `seq_page_cost` | 1.0 | Cost of one sequential page fetch |
| `random_page_cost` | 4.0 | Cost of one random page fetch |
| `cpu_tuple_cost` | 0.01 | Per-tuple processing (heap scan, etc.) |
| `cpu_index_tuple_cost` | 0.005 | Per-tuple index entry processing |
| `cpu_operator_cost` | 0.0025 | Per-call WHERE-clause operator / function |
| `parallel_tuple_cost` | 0.1 | Pass one tuple worker→leader through TupleQueue |
| `parallel_setup_cost` | 1000.0 | One-shot cost of launching parallel workers |

All `double`; all overrideable via SET / SIGHUP. Tablespaces can
override `seq_page_cost` / `random_page_cost` via
`ALTER TABLESPACE ... SET ({seq,random}_page_cost = ...)`.

`effective_cache_size` is a related GUC (default 4 GB) that
affects index-scan cost via `compute_correlation` heuristic — it
tells the planner how much of the table the OS might keep
cached.

## Why seq=1.0 is the anchor

[verified-by-code `costsize.c:18-19`]

> seq_page_cost is normally considerably less than random_page_cost.
> (However, if the database is too large to fit in RAM and
> random_page_cost is small...)

Everything is relative to seq_page_cost. Setting `seq_page_cost
= 2.0` while leaving others alone doesn't make queries "slower
on paper" — it just rescales the whole cost space. What matters
is the RATIOS:
- `random_page_cost / seq_page_cost` — drive index vs seq choice.
- `cpu_tuple_cost / seq_page_cost` — drive when to prefer
  predicate filtering vs full scan.
- `parallel_tuple_cost / cpu_tuple_cost` — drive parallel
  worker count selection.

## The "I'm forbidden" sentinel

[verified-by-code `costsize.c:142`]

```c
Cost disable_cost = 1.0e10;
```

When an `enable_*` GUC is `off`, the corresponding path's cost
gets `disable_cost` added — making it astronomically expensive
but not impossible. The planner still considers it as fallback
if every other path is also disabled or infeasible.

This is how `SET enable_seqscan = off` works: SeqScan paths get
cost += 1e10, so any indexable alternative wins.

Recent (PG 17+) refactor: `path->disabled_nodes` counts how many
disabled nodes are in the tree, providing more graceful fallback
than pure cost addition. See `cost_seqscan:335-336`:
```c
path->disabled_nodes =
    (baserel->pgs_mask & enable_mask) == enable_mask ? 0 : 1;
```

## The enable_* family

[verified-by-code `costsize.c:146-167`]

22 booleans gating individual plan-node consideration:

```c
enable_seqscan, enable_indexscan, enable_indexonlyscan,
enable_bitmapscan, enable_tidscan, enable_sort,
enable_incremental_sort, enable_hashagg, enable_nestloop,
enable_material, enable_memoize, enable_mergejoin,
enable_hashjoin, enable_gathermerge, enable_partitionwise_join,
enable_partitionwise_aggregate, enable_parallel_append,
enable_parallel_hash, enable_partition_pruning,
enable_presorted_aggregate, enable_async_append
```

Two patterns:
- **Force-off** (`SET enable_X = off`) — adds disable_cost so the
  planner avoids X.
- **Debugging** — temporarily disable to verify a different plan
  has reasonable cost.

These are NOT runtime safety knobs; production tuning should
adjust the cost ratios instead.

## clamp_row_est — protecting against bad estimates

[verified-by-code `costsize.c:213-230`]

```c
double
clamp_row_est(double nrows)
{
    if (nrows > MAXIMUM_ROWCOUNT || isnan(nrows))
        nrows = MAXIMUM_ROWCOUNT;  /* 1e100 */
    else if (nrows <= 1.0)
        nrows = 1.0;
    else
        nrows = rint(nrows);
    return nrows;
}
```

Every per-relation row estimate runs through this. Three guards:
- **Infinity / NaN** → MAXIMUM_ROWCOUNT (1e100). Garbage in,
  finite out.
- **Below 1** → 1. EXPLAIN shows whole rows; avoids
  divide-by-zero.
- **Round** — make EXPLAIN output integer-looking.

## Cost composition formula

The general pattern in every cost function:

```
total_cost = startup_cost
           + disk_run_cost (pages * spc_page_cost)
           + cpu_run_cost  (tuples * (cpu_tuple_cost + qual_cost))
           + per_output_row_cost (rows * pathtarget->cost.per_tuple)
```

Each cost path:
1. Estimate rows (from stats + selectivity).
2. Estimate pages (from rows + width).
3. Multiply by per-page / per-tuple GUCs.
4. Add startup cost from any sub-paths.
5. Apply parallel divisor if applicable.

## Parallel divisor

[verified-by-code via `get_parallel_divisor` calls]

Cost-side: in a parallel plan, CPU is divided across workers,
but the leader contributes fractionally too. The formula is
`workers + max(0, 1.0 - 0.3 × workers)` — so 1 worker → 1.7,
2 → 2.4, 3 → 3.1, 4+ → workers (leader contribution clamps to
0). See `cost-parallel-adjustments` for the full derivation.

## Per-tablespace overrides

[verified-by-code via `get_tablespace_page_costs`]

```c
void
get_tablespace_page_costs(Oid spcid,
                          double *spc_random_page_cost,
                          double *spc_seq_page_cost);
```

Reads pg_tablespace options. If unset, returns globals. Lets a
mixed-storage cluster have:
- Tablespace `ssd_data` — `random_page_cost = 1.5`.
- Tablespace `archive_disk` — `random_page_cost = 8.0`.

Cost functions call this at the start of every cost computation.

## Append's CPU cost multiplier

[verified-by-code `costsize.c:121`]

```c
#define APPEND_CPU_COST_MULTIPLIER 0.5
```

Append nodes pass tuples through with less per-tuple overhead
than other plan nodes (no projection, no qual eval). Their
per-tuple cost is `0.5 * cpu_tuple_cost`. A magic number, not a
GUC.

## Common review-time concerns

- **Don't tune cost GUCs blindly** — the ratios matter more than
  absolutes. Most tuning advice: lower `random_page_cost` to 1.1
  for SSDs; raise `effective_cache_size` to ~75% of RAM.
- **`enable_*` is a debug knob, not production tuning** —
  production cost adjustment goes through cost GUCs.
- **`disable_cost` is a sentinel, not a hard block** — disabled
  paths can still be chosen if all alternatives are also
  disabled.
- **Per-tablespace overrides override globals** — handy for
  multi-storage clusters.
- **clamp_row_est guards against bad stats** — but doesn't FIX
  bad stats; ANALYZE the table.
- **Cost numbers in EXPLAIN are unitless** — comparing across
  PostgreSQL versions requires checking if GUC defaults changed.

## Invariants

- **[INV-1]** `seq_page_cost = 1.0` is the calibration anchor;
  others are relative.
- **[INV-2]** Disabled nodes add `disable_cost = 1e10` to their
  paths' costs.
- **[INV-3]** `clamp_row_est` enforces row estimates ∈ [1, 1e100]
  and finite.
- **[INV-4]** Tablespace overrides take precedence over globals
  for page costs.
- **[INV-5]** Parallel cost divides CPU by `parallel_workers +
  max(0, 1.0 - 0.3 × workers)` when leader_participation = on.

## Useful greps

- Defaults + globals:
  `grep -n 'DEFAULT_SEQ_PAGE_COST\|DEFAULT_RANDOM_PAGE_COST\|DEFAULT_CPU' source/src/include/optimizer/cost.h | head -10`
- enable_* booleans:
  `grep -n '^bool.*enable_' source/src/backend/optimizer/path/costsize.c | head -25`
- disable_cost users:
  `grep -RIn 'disable_cost\|disabled_nodes' source/src/backend/optimizer | head -10`
- Tablespace cost lookup:
  `grep -RIn 'get_tablespace_page_costs' source/src/backend | head -10`

## Cross-references

- `knowledge/idioms/cost-scan-paths.md` —
  cost_seqscan / cost_index / cost_bitmap_heap_scan callers
  of these GUCs.
- `knowledge/idioms/cost-join-paths.md` —
  initial_cost_* / final_cost_* for nestloop, mergejoin, hashjoin.
- `knowledge/idioms/parallel-gather-merge.md` —
  parallel_setup_cost / parallel_tuple_cost interplay.
- `knowledge/data-structures/plannerinfo.md` —
  RelOptInfo.rows + Path.startup_cost / total_cost.
- `knowledge/idioms/clamp-row-est-stats.md` —
  ANALYZE + stats feeding rows estimates.
- `knowledge/subsystems/optimizer.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/include/optimizer/cost.h` — DEFAULT_* macros.
- `source/src/backend/optimizer/path/costsize.c` — all cost
  functions.
