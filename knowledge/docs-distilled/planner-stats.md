---
source_url: https://www.postgresql.org/docs/current/planner-stats.html
fetched_at: 2026-06-05T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 14.2: Statistics Used by the Planner

What the optimizer reads to turn a query into row-count estimates: per-relation
counts in `pg_class`, per-column distribution stats in `pg_statistic`, and the
opt-in multivariate `CREATE STATISTICS` objects. The recurring theme: every
number here is *approximate by design*, and the planner rescales rather than
trusts.

## Single-column statistics (14.2.1)

- **`pg_class.reltuples` / `relpages` are cached, not live.** They are refreshed
  only by `VACUUM`, `ANALYZE`, and a few DDL commands (`CREATE INDEX`), never
  on-the-fly per query. [from-docs]
- **A partial scan updates them approximately, and the planner rescales.** When
  `VACUUM`/`ANALYZE` doesn't read the whole table, `reltuples` is extrapolated
  from the scanned fraction; the planner then scales the stored `reltuples` by
  the *current* physical relation size to get its working estimate — so even a
  stale `reltuples` self-corrects somewhat as the table grows/shrinks.
  [from-docs]
- **`pg_statistic` is superuser-only; `pg_stats` is the public, readable view.**
  `pg_stats` exposes only rows for tables the current user can read, and presents
  the arrays in human-readable form for manual inspection. [from-docs]
- **`pg_statistic` entries are "always approximate even when freshly updated."**
  ANALYZE samples; it does not census. [from-docs]
- **`default_statistics_target` (default 100) caps the array sizes.** It bounds
  the entry count in `most_common_vals` and `histogram_bounds`; override
  per-column with `ALTER TABLE ... ALTER COLUMN ... SET STATISTICS n`. [from-docs]
- **Raising the target trades planning cost for estimate accuracy.** More MCVs +
  histogram buckets help irregular/skewed distributions but enlarge
  `pg_statistic` and lengthen every plan's estimation step; lower it for simple
  uniform columns. The target also drives the ANALYZE *sample size*. [from-docs]

## Extended (multivariate) statistics (14.2.2)

- **Multivariate stats are never automatic — you must `CREATE STATISTICS`.**
  Single-column stats assume column independence; cross-column correlation is
  only captured for explicitly declared column groups. The object just declares
  *what* to compute; `ANALYZE` does the actual collection. [from-docs]
- **Extended stats reuse the same row sample as single-column stats.** Bumping
  the table's or any member column's statistics target enlarges the shared
  sample, improving extended-stat accuracy at higher ANALYZE cost. [from-docs]
- **Functional dependencies (`dependencies`) model "column A determines column
  B".** The dependency *degree* is a coefficient in [0,1]: 1.0 = full
  determination (zip → city), and e.g. 0.42 = partial (city → zip is only ~42%
  deterministic because a city spans many zips). [from-docs]
- **Dependencies only fix *equality* and `IN`-with-constants estimates** — not
  column-to-column comparisons, ranges, `LIKE`, etc. Outside that shape they
  don't apply. [from-docs]
- **Dependencies assume compatible predicates and won't detect contradictions.**
  For `city='San Francisco' AND zip='90210'` (mismatched) the planner still
  won't estimate zero rows — the dependency stat lacks the value-level detail to
  notice the impossibility. (MCV stats can, because they store actual values.)
  [from-docs]
- **N-distinct stats (`ndistinct`) fix `GROUP BY a,b` cardinality.** Per-column
  `n_distinct` multiplied together overestimates distinct combinations when the
  columns correlate; `ndistinct` stores the true distinct counts for all 2+
  column subsets of the group. [from-docs]
- **MCV lists (`mcv`) store actual common *combinations* of values.** They
  capture cases a per-column MCV misses — e.g. `{Washington, DC}` at 0.35%
  frequency vs a 0.0027% independence-assumption "base frequency", two orders of
  magnitude off. Inspect via the `pg_mcv_list_items()` SRF (`index`, `values`,
  `nulls`, `frequency`, `base_frequency`). [from-docs]
- **Create extended stats only where they pay off:** strongly-correlated columns
  (dependencies), columns actually grouped together (ndistinct), or columns used
  together in WHERE (mcv). Otherwise you burn ANALYZE and planning cycles for
  nothing. [from-docs]

## Links into corpus

- [[knowledge/subsystems/optimizer.md]] — where these estimates feed cost-based
  path selection.
- [[knowledge/architecture/planner.md]] — the planner pipeline that consumes
  selectivity.
- [[knowledge/files/src/backend/commands/analyze.c.md]] — how the sample is taken
  and `pg_statistic`/`reltuples` written.
- [[knowledge/files/src/backend/utils/adt/selfuncs.c.md]] — the selectivity
  estimators that read MCV/histogram/n_distinct.
- [[knowledge/files/src/backend/statistics/extended_stats.c.md]] — driver for
  multivariate stat collection.
- [[knowledge/files/src/backend/statistics/dependencies.c.md]] — functional
  dependency stats.
- [[knowledge/files/src/backend/statistics/mvdistinct.c.md]] — n-distinct stats.
- [[knowledge/files/src/backend/statistics/mcv.c.md]] — multivariate MCV lists +
  `pg_mcv_list_items()`.

## Confidence note

All claims `[from-docs]` (Chapter 14.2, fetched 2026-06-05). The corpus
cross-links point at per-file docs whose own `source/...:line` cites carry the
code-level verification; not re-verified line-by-line this run.
