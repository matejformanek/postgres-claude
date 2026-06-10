---
source_url: https://www.postgresql.org/docs/current/row-estimation-examples.html
fetched_at: 2026-06-10T20:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Row Estimation Examples (internals ch. 69.1)

Worked numeric examples of the planner's cardinality estimation — the concrete
arithmetic behind `planner-stats.md`. Chosen this run as the dense leaf that
dodges the `planner-stats-details` parent (ToC-only extraction failure, logged
in the docs queue). The formulas here are the live ones in `selfuncs.c`.

## Non-obvious claims (formulas)

- **Base cardinality from `pg_class`:** `reltuples` and `relpages`, set by the
  last `VACUUM`/`ANALYZE`. The planner reads the *current* physical page count and
  **scales `reltuples` proportionally** when `relpages` has drifted — so estimates
  self-correct between ANALYZEs as a table grows. [from-docs]
- **Range condition → histogram.** For `unique1 < 1000` with
  `histogram_bounds` from `pg_stats`, selectivity interpolates *within the
  containing bucket*:
  `sel = (1 + (value − bucket.min)/(bucket.max − bucket.min)) / num_buckets`.
  Example → 0.100697 → ~1007 rows of 10000. [from-docs]
- **Equality, value in MCV:** selectivity is read **directly** out of
  `most_common_freqs` at the matching `most_common_vals` index (e.g. 0.003 → 30
  rows). No computation. [from-docs]
- **Equality, value NOT in MCV:** the non-MCV mass is spread over the non-MCV
  distinct values:
  `sel = (1 − sum(most_common_freqs)) / (n_distinct − num_mcv)`.
  Example → 0.0014559 → ~15 rows. [from-docs]
- **🔑 Histograms exclude MCV mass.** For a range on a non-unique column, the
  histogram represents only the non-MCV portion. Total selectivity is
  `sel_mcv + sel_histogram × (1 − sum(all_mcv_freqs))`, where `sel_mcv` sums the
  frequencies of MCVs that satisfy the predicate. Forgetting the `(1 − Σmcv)`
  scaling double-counts. Example → 0.307669 → ~3077 rows. [from-docs]
- **Multiple conditions multiply (independence assumption).** `unique1 < 1000 AND
  stringu1 = 'xxx'` → 0.100697 × 0.0014559 → ~1 row. This independence assumption
  is exactly what extended (multivariate) statistics exist to correct. [from-docs]
- **Join selectivity for unique keys (`n_distinct = −1`):**
  `sel = (1 − null_frac1)(1 − null_frac2) / max(num_rows1, num_rows2)`; join rows
  `= outer_card × inner_card × sel`. Example → 0.0001 →
  (50 × 10000) × 0.0001 = 50 rows. This is `eqjoinsel`. [from-docs]
- **`pg_stats` columns that drive all of the above:** `null_frac`, `n_distinct`,
  `most_common_vals`, `most_common_freqs`, `histogram_bounds`. [from-docs]

## Links into corpus

- Conceptual parent: `knowledge/docs-distilled/planner-stats.md`; cost model
  consumer: `knowledge/docs-distilled/planner-optimizer.md` (this run).
- Multivariate correction (the independence-assumption escape hatch):
  `multivariate-statistics-examples` leaf — candidate for a future run; the
  `planner-stats-details` parent remains an extraction-failure (ToC-only).
- Code (per the docs page's own "Further reading" pointers, [from-docs]):
  `source/src/backend/optimizer/util/plancat.c` (table size estimation),
  `source/src/backend/optimizer/path/clausesel.c` (generic clause selectivity),
  `source/src/backend/utils/adt/selfuncs.c` (operator-specific selectivity incl.
  `eqsel`/`eqjoinsel`/`scalarltsel`). [unverified — not line-pinned this run]
