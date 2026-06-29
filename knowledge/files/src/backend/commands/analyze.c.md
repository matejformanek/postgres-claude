# analyze.c

- **Source path:** `source/src/backend/commands/analyze.c`
- **Lines:** 3149
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `vacuum.c` (driver), `utils/misc/sampling.c` (BlockSampler + Vitter reservoir), `statistics/extended_stats.c` (multi-column stats), `commands/statscmds.c` (extended-stats DDL), `catalog/pg_statistic.h`.

## Purpose

"The Postgres statistics generator." [from-comment, analyze.c:3] Owns the ANALYZE command body: per-relation orchestration, sample row acquisition (two-stage block sampling + Vitter reservoir), per-attribute statistics computation (trivial / distinct / scalar slots), index-expression stats, inheritance-tree stats, and writing the results into `pg_statistic` / `pg_statistic_ext_data` and `pg_class.reltuples`.

## Public surface

- `analyze_rel` (110) — per-relation entry, called from `vacuum.c:vacuum`. Opens with `ShareUpdateExclusiveLock`, validates the user can analyse it, picks the `AcquireSampleRowsFunc` (heap → `acquire_sample_rows`; FDW → `GetForeignRowAnalyzeFunc` callback), then calls `do_analyze_rel`.
- `do_analyze_rel` (306) — **the orchestrator**, ~570 lines. Computes `targrows = max(100, 300 * attstattarget)` per column, allocates the reservoir, calls the sampler, then for each `VacAttrStats` runs its `compute_stats` callback. If the relation has inheritance children, calls `acquire_inherited_sample_rows` and re-runs stats with `stainherit=true`. Writes results via `update_attstats` and calls into `statistics/extended_stats.c` for any extended stats.
- `compute_index_stats` (877) — for each expression index, fetch the index expression and gather stats on the *computed* values (so e.g. `(lower(x))` gets its own histogram).
- `examine_attribute` (1082) — decide what stats kind to compute for one attribute. Calls the attribute's type-specific `typanalyze` function (or `std_typanalyze` 1950, the default). The typanalyze sets `stats->compute_stats` and `stats->minrows`.
- `attribute_is_analyzable` (1176) — honour `ALTER COLUMN SET STATISTICS 0` (skip) and certain unanalysable types.
- `block_sampling_read_stream_next` (1219) — `ReadStream` callback that returns the next block chosen by `BlockSampler` (in utils/misc/sampling.c).
- `acquire_sample_rows` (1262) — the **two-stage sampler** described in §"Sampling algorithm" below.
- `acquire_inherited_sample_rows` (1450) — sample across a partition/inheritance tree, weighting each child's contribution to `targrows` proportional to its block count: `childtargrows = round(targrows * childblocks / totalblocks)`. [verified-by-code, analyze.c:1632]
- `update_attstats` (1714) — write one or more `pg_statistic` tuples per attribute. Each slot carries (`stakind`, `staop`, `stacoll`, `stanumbersN`, `stavaluesN`) for histogram/MCV/correlation/distinct/etc.
- `std_fetch_func` / `ind_fetch_func` (1856, 1872) — the indirection used by per-attribute computations to retrieve a datum from the reservoir row (`std_*` for table columns; `ind_*` for index-expression rows whose datum has already been computed).
- `std_typanalyze` (1950) — **default typanalyze**: chooses among `compute_trivial_stats` (no `eqfn`), `compute_distinct_stats` (`eqfn` only, no `<`), `compute_scalar_stats` (full `eqfn` + `ltfn`).
- `compute_trivial_stats` (2028) — only computes width and null-fraction.
- `compute_distinct_stats` (2118) — MCV list + ndistinct via the Haas-Stokes estimator (over the sample), no histogram.
- `compute_scalar_stats` (2461) — **the canonical path**: sort sample by `<`, derive MCVs (with the Lyberg-style threshold), then a `default_statistics_target`-bucket histogram of the remaining values, plus physical-order correlation. Several hundred lines, with the bulk going into MCV-selection heuristics. `analyze_mcv_list` (3039) implements the dynamic threshold (a value is "common" if its sample frequency is statistically distinguishable from average).

## Sampling algorithm [load-bearing]

Two-stage sampling, in use since 2004 (comment at analyze.c:1289-1259): [verified-by-code, from-comment, analyze.c:1289-1259]

1. **Stage 1 — Block sampling.** `BlockSampler_Init` picks **up to `targrows` random blocks** (uniform without replacement via reservoir sampling on the block list).
2. **Stage 2 — Vitter row sampling.** For each chosen block, walk every live tuple and either insert it into the reservoir (first `targrows` tuples) or run Vitter's Algorithm Z to maybe replace a random reservoir slot (after that). Both stages execute simultaneously: each block is processed as soon as stage 1 emits its number, and stage 2 decides per-row inclusion as the heap is scanned.

**Property:** every row has equal inclusion probability, BUT not every possible sample is equally likely — the set of blocks-represented is constrained. The doc note in the source (lines 1247-1258) acknowledges this gives slightly biased per-block-density estimates for large tables. Live and dead row counts are tracked separately so `pg_class.reltuples` / `relpages` / `n_dead_tup` can be set.

**`targrows` = `300 * default_statistics_target`** (or per-column `attstattarget`). With the default target of 100, that's 30 000 sample rows. [verified-by-code, analyze.c:1999, 2006, 2013] The factor 300 is empirical; the comment in `compute_scalar_stats` justifies it via the Chaudhuri/Motwani/Narasayya error bound: 300 rows per bucket gives ≥ 90% confidence that the histogram boundaries are within reasonable error.

## Inheritance sampling [HIGH-RISK]

When a partitioned/inherited table is analysed, the parent's `pg_statistic` rows have `stainherit=true` and are computed by **scanning ALL leaf children** (proportional row count) — separate from each child's own `stainherit=false` row produced by its individual ANALYZE. The planner uses the inherit row when planning queries against the partitioned root. This is why a parent ANALYZE on a 1000-partition table is very expensive even though each child has its own stats. [verified-by-code, analyze.c:1450-1713]

## Tests

- `src/test/regress/sql/stats_ext.sql` (extended stats — touches statscmds.c too)
- `src/test/regress/sql/vacuum.sql`, `vacuum_parallel.sql`, `inherit.sql`
- `src/test/regress/sql/sanity_check.sql` indirectly verifies pg_statistic layout

## Open questions

- The Vitter Algorithm Z reservoir behaviour in the presence of HOT-updated chains and visibility-map-skipped pages — exact interaction with `table_scan_analyze_next_tuple` was not traced. [unverified]
- Whether `acquire_inherited_sample_rows` correctly excludes foreign children when `default_statistics_target` < 100 — edge case. [unverified]

## Confidence tag tally

`[verified-by-code]=10 [from-comment]=3 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/analyze-block-and-reservoir-sampling.md](../../../../idioms/analyze-block-and-reservoir-sampling.md)
- [idioms/analyze-mcv-histogram-correlation.md](../../../../idioms/analyze-mcv-histogram-correlation.md)
- [idioms/extended-statistics-statext.md](../../../../idioms/extended-statistics-statext.md)

