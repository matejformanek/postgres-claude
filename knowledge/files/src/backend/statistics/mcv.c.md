# `src/backend/statistics/mcv.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~2300
- **Source:** `source/src/backend/statistics/mcv.c`

## Purpose

Multivariate MCV (Most Common Values) lists (kind `STATS_EXT_MCV`).
For declared statistics columns, stores a list of `MCVItem`s, each
recording a full value-tuple and three numbers:
- `frequency` — fraction of all rows that have this exact tuple.
- `base_frequency` — product of per-column frequencies (what
  independence would predict).
- `nulls[]` — which columns of the tuple are NULL.

The gap between `frequency` and `base_frequency` is the signal
multi-column MCV provides: items where they diverge are the
correlation evidence.

## Build (`statext_mcv_build`, `:178`)

- Group sampled rows on the full column tuple; pick the top items by
  group count until either the target count (`stattarget * STATS_MCV_MAX`)
  is hit or we run out of "interesting" items.
- The cutoff for "interesting" follows the same rule as
  `compute_scalar_stats`: drop items whose frequency is below the noise
  threshold scaled from sample size.
- Computes `base_frequency` from per-column frequencies of each
  component (using per-column stats already built earlier in the same
  ANALYZE pass).

## Selectivity (`mcv_clauselist_selectivity`, `:2046`)

For an MCV list + a clause list, returns three numbers:
- `s` (return value): summed frequency of matching items —
  `mcv_sel`.
- `*basesel`: summed base_frequency of matching items.
- `*totalsel`: summed frequency of **all** items (matching or not) —
  the MCV's total coverage of the data.

Then `mcv_combine_selectivities(simple, mcv, basesel, totalsel)`
(`:2003`-`:2025`) blends with the standard per-column estimate:
```
other_sel = simple_sel - mcv_basesel           # correlation-naive estimate of non-MCV tail
other_sel = min(other_sel, 1 - mcv_totalsel)   # but tail can't exceed actual non-MCV coverage
result    = mcv_sel + other_sel
```
The first line says "the part of the simple estimate attributable to
the MCV portion is already covered exactly by `mcv_sel`, so subtract
it out." The second line clamps. The result combines exact MCV
selectivity with independence-assumption tail selectivity.
[from-comment] (`mcv.c:1990-2025`)

## Match bitmap (`mcv_get_match_bitmap`)

Walks each MCV item, evaluates each compatible clause against the
item's per-column values (using the operator's `fmgr` info), AND/OR/NOT
composes. Inversion (`is_or=true`) lets OR clauses use the same engine.
NULL handling honors PG three-valued logic.

## Serialization (`:619`-`:990`)

`MCVList` header + per-item `(itemoffset, base_frequency, frequency,
nulls bitmap, values)`. Values are stored as `Datum`s via standard
type-input/output. `MAGIC = 0xE3A302D2`. Stored as a bytea in
`pg_statistic_ext_data.stxdmcv`.

## SQL inspection

`pg_mcv_list_items(pg_mcv_list)` SRF (defined in this file) explodes a
stored MCV list into `(index, values[], nulls[], frequency,
base_frequency)` rows — the user-facing way to see what the planner is
working with.

## Tag tally

`[verified-by-code]` 3 / `[from-comment]` 5

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/extended-statistics-statext.md](../../../../idioms/extended-statistics-statext.md)

