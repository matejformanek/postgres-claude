# `src/backend/utils/adt/rangetypes_typanalyze.c`

- **File:** `source/src/backend/utils/adt/rangetypes_typanalyze.c` (427 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **typanalyze** functions for range and multirange columns. Tells
ANALYZE how to collect statistics by setting `compute_stats` and
`minrows` on the `VacAttrStats` block. Produces three artifacts:

1. **Histograms of lower and upper bounds** (combined into a single
   array of valid ranges with the same shape `std_typanalyze` would
   produce — described at `:7-14` [from-comment]).
2. **Length histogram** of `subdiff(upper, lower)` values (only when
   the type has a `subdiff` function defined).
3. **Empty fraction** + **NULL fraction**.

## Key functions

- `range_typanalyze(PG_FUNCTION_ARGS)` (`:45-63`) — sets
  `stats->compute_stats = compute_range_stats`,
  `stats->extra_data = typcache`, `minrows = 300 * attstattarget`
  (matches `std_typanalyze` heuristic). Looks up type cache via
  `range_get_typcache(fcinfo, getBaseType(stats->attrtypid))` so
  domains-over-range are handled. [verified-by-code]
- `multirange_typanalyze(PG_FUNCTION_ARGS)` (`:71-89`) — analogous;
  uses `multirange_get_typcache`. Stats are computed against the
  **smallest enclosing range** of each multirange (`:68-69`
  [from-comment]), so the same `compute_range_stats` works.
  [verified-by-code]
- `float8_qsort_cmp` (`:95-106`) — qsort comparator for lengths.
- `range_bound_qsort_cmp` (`:112-119`) — qsort comparator using
  `range_cmp_bounds` from `rangetypes.c`. [verified-by-code]
- `compute_range_stats(stats, fetchfunc, samplerows, totalrows)`
  (`:125+`) — the actual sample-walking routine. Allocates three
  arrays of length `samplerows`, deserializes each fetched value,
  collects bounds and lengths, qsorts them, and emits the histogram
  arrays into the `pg_statistic` slots
  (`STATISTIC_KIND_BOUNDS_HISTOGRAM`,
  `STATISTIC_KIND_RANGE_LENGTH_HISTOGRAM`). [verified-by-code]

## Phase D notes

- `palloc_array` sizes (`:154-156`) are bounded by `samplerows`, which
  is set by ANALYZE based on `attstattarget`. No attacker control.
  [verified-by-code]
- Multirange path: collapses to bounding range; consequence is
  multirange selectivity for `<<`/`>>` is conservative — known and
  documented. [from-comment]

## Potential issues

- [ISSUE-correctness: collapsing multirange to bounding range loses
  the "gaps" structure; selectivity for operators that care about
  gaps will be biased pessimistic — known design trade-off (info)]
- [ISSUE-stale-todo: the length histogram is only useful when
  `subdiff` is defined; without it, length-based selectivity falls
  back to a constant. Not flagged as a gap but worth noting (info)]

## Cross-references

- `source/src/include/commands/vacuum.h` — `VacAttrStats`,
  `AnalyzeAttrFetchFunc`, `compute_stats` callback shape.
- `source/src/backend/utils/adt/rangetypes_selfuncs.c` — consumes
  the histograms produced here.
- `source/src/backend/commands/analyze.c` — driver.

## Confidence tag tally
- `[verified-by-code]` × 4
- `[from-comment]` × 3
