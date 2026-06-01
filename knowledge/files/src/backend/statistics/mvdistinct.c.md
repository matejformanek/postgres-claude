# `src/backend/statistics/mvdistinct.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~670
- **Source:** `source/src/backend/statistics/mvdistinct.c`

## Purpose

Multivariate ndistinct coefficients (kind `STATS_EXT_NDISTINCT`). For a
declared statistics object on columns `(a,b,c)`, this stores
`n_distinct((a,b))`, `n_distinct((a,c))`, `n_distinct((b,c))`,
`n_distinct((a,b,c))`. Used to estimate `GROUP BY` cardinality and
distinct-grouping selectivity when columns are correlated and the
per-column estimates would either over- or under-shoot. [from-comment]
(`mvdistinct.c:5-13`)

## Build (`statext_ndistinct_build`, `:84`)

- For each non-trivial subset of the declared columns (size 2 up to
  `STATS_MAX_DIMENSIONS = 8`), compute `n_distinct` using the standard
  per-column estimator generalized to multiple columns —
  `estimate_num_groups`-style HyperLogLog-ish via the sampled rows.
- Stored in `MVNDistinct` containing an array of `MVNDistinctItem`
  `{attrs (bitmapset), ndistinct, nattributes}` records.

## Consumption

Planner: `estimate_num_groups` (`utils/adt/selfuncs.c`) checks for
`STATS_EXT_NDISTINCT` stats covering the GROUP BY clause. If a stats
object covers a subset of the grouping keys, the multi-column estimate
is combined with per-column estimates of the remaining keys via:
```
ndistinct(group_keys) = ndistinct(covered_subset) * product(ndistinct(remaining))
```
(taking a slight pessimism factor to avoid over-estimating when
correlations are strong on the covered subset and weak on the rest).

## Serialization (`:176`-`:325`)

`MAGIC = 0xA352BFA4`, `TYPE = 1`. Header + per-item:
`{nattributes:uint32, ndistinct:double, attrs:[]int16}`. Stored in
`pg_statistic_ext_data.stxdndistinct`.

## Load (`statext_ndistinct_load`, `:144`)

Reads `STATEXTDATASTXOID` syscache; one row per (statoid, inh flag).
Returns a palloc'd `MVNDistinct` in `CurrentMemoryContext`.

## Tag tally

`[verified-by-code]` 2 / `[from-comment]` 3
