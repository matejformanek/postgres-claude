# `src/backend/utils/adt/multirangetypes_selfuncs.c`

- **File:** `source/src/backend/utils/adt/multirangetypes_selfuncs.c` (1336 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

Selectivity estimators for multirange operators. Largely parallels
`rangetypes_selfuncs.c` because `multirange_typanalyze` collapses each
multirange to its **bounding range** before computing histograms — so
the same bound-histogram-driven CDF machinery is reused.

## Key functions

- `multirangesel(PG_FUNCTION_ARGS)` (`:136-137+`) — the unified
  entry point for `oprrest`. Dispatches by strategy.
  [verified-by-code]
- Internal helpers mirror `rangetypes_selfuncs.c`:
  `calc_multirangesel`, `default_multirange_selectivity`,
  `calc_hist_selectivity` for bound-position interpolation. The
  empty-multirange fraction adjusts the result for operators that
  treat empties specially.

## Phase D notes

- The collapse-to-bounding-range approach makes `@>` against a
  multirange constant under-conservative (since gaps inside the
  bounding range are ignored). Documented design trade-off.
  [from-comment in rangetypes_typanalyze.c]
- Reads pg_statistic; trust-bounded by
  `statistic_proc_security_check`. [verified-by-code]

## Potential issues

- [ISSUE-correctness: gap-blind selectivity for multiranges
  produces optimistic estimates for `@>`-style queries against
  bounding-range histograms; affects plan choice on multirange-heavy
  workloads (info)]
- [ISSUE-stale-todo: no `multirangejoinsel` (mirrors the range case)
  (info)]

## Cross-references

- `source/src/backend/utils/adt/multirangetypes.c` — operators and
  serialization this estimates for.
- `source/src/backend/utils/adt/rangetypes_typanalyze.c` —
  `compute_range_stats` produces the bounding-range histograms.
- `source/src/backend/utils/adt/rangetypes_selfuncs.c` — sibling with
  near-identical structure.

## Confidence tag tally
- `[verified-by-code]` × 2
- `[from-comment]` × 1
