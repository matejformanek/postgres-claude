---
source_url: https://www.postgresql.org/docs/current/multivariate-statistics-examples.html
chapter: "69.2 Multivariate Statistics Examples"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# Extended (multivariate) statistics — §69.2

Distilled from §69.2. Sibling of
[[knowledge/docs-distilled/row-estimation-examples.md]] under the parent
"How the Planner Uses Statistics" chapter (whose own page
`planner-stats-details.html` resists WebFetch extraction — see docs
queue note). The three extended-stat kinds each fix a *different*
estimation error; picking the wrong kind silently does nothing.

## Non-obvious claims

- The core failure mode: the planner assumes column independence and
  **multiplies per-column selectivities**, so correlated `WHERE a=1 AND
  b=1` underestimates by orders of magnitude (1% × 1% ⇒ ~1 row when the
  truth is 100). Extended stats are created with `CREATE STATISTICS name
  (kind) ON col, col FROM tbl` and only take effect after `ANALYZE`.
  [from-docs §69.2]
- **`dependencies` (functional dependencies) only help equality.** They
  capture column-level correlation globally, not value-specific combos,
  and do nothing for ranges/inequalities. They fix `a=1 AND b=1` row
  estimates. [from-docs §69.2.1]
- **`ndistinct` only helps `GROUP BY` (and join) cardinality**, not
  `WHERE` filtering. It tracks the number of distinct *combinations* of
  the listed columns, fixing `GROUP BY a, b` overestimates (e.g. 1000 →
  100). Using `ndistinct` expecting it to fix a `WHERE` estimate is a
  no-op. [from-docs §69.2.2]
- **`mcv` (most-common-values lists) is the most powerful and most
  expensive.** It stores actual value combinations, so it (a)
  distinguishes *incompatible* combos — `a=1 AND b=10` correctly drops
  toward 0 when that pair never occurs — and (b) handles **inequalities
  and ranges** (`a<=49 AND b>49`), which `dependencies` cannot.
  [from-docs §69.2.3]
- Inspect an MCV list via
  `pg_statistic_ext JOIN pg_statistic_ext_data ON (oid = stxoid),
  pg_mcv_list_items(stxdmcv)`. Columns: `values` (the combination),
  `nulls` (per-column null flags), `frequency` (observed), and
  **`base_frequency` (the independence-assumption product)** — the gap
  between `frequency` and `base_frequency` is exactly the correlation the
  MCV list exists to correct. [from-docs §69.2.3]
- Cost tradeoff is explicit: `mcv` costs more in ANALYZE time, storage,
  and *planning* time (conditions are evaluated against every list item)
  than `dependencies`. The planner applies clauses to the list via
  `mcv_clauselist_selectivity()` in
  `source/src/backend/statistics/mcv.c`. [from-docs §69.2.3]
- Mental model for choosing: equality-only correlated filters →
  `dependencies`; multi-column `GROUP BY` / join cardinality →
  `ndistinct`; anything needing value-combination awareness or
  range/inequality handling → `mcv`. A single `CREATE STATISTICS` may
  request several kinds at once (`(dependencies, ndistinct)`).
  [from-docs §69.2]

## Links into corpus

- Sibling example chapter: [[knowledge/docs-distilled/row-estimation-examples.md]].
- User-facing planner-stats overview: [[knowledge/docs-distilled/planner-stats.md]].
- Subsystem: [[knowledge/subsystems/optimizer.md]] (selectivity / clause
  estimation).
- Source implementations (one file per kind):
  [[knowledge/files/src/backend/statistics/dependencies.c.md]],
  [[knowledge/files/src/backend/statistics/mvdistinct.c.md]],
  [[knowledge/files/src/backend/statistics/mcv.c.md]],
  [[knowledge/files/src/backend/statistics/extended_stats.c.md]] (the
  `ANALYZE`-time builder), and the catalog header
  [[knowledge/files/src/include/statistics/statistics.h.md]].

## Caveats / verification

- `[from-docs §69.2]`. The `mcv_clauselist_selectivity()` /
  `src/backend/statistics/mcv.c` reference comes verbatim from the docs
  prose; line-precise cites should be taken from the corpus file doc
  above, re-verified at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735`.
