# `src/backend/utils/adt/rangetypes_selfuncs.c`

- **File:** `source/src/backend/utils/adt/rangetypes_selfuncs.c` (1223 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

Selectivity estimators for range operators. Backs the `oprrest` slots
for `<<`, `>>`, `&<`, `&>`, `-|-`, `@>`, `<@`, `&&`, `=`, `<`, `<=`,
`>`, `>=`. Consumes the bound histograms and empty-fraction produced
by `rangetypes_typanalyze.c`.

The selectivity is computed from the cumulative distribution function
of the **lower** and **upper** bound histograms, depending on the
strategy. The empty fraction is folded in as a separate constant.

## Key functions

- `rangesel(PG_FUNCTION_ARGS)` (`:107+`) — the unified entry point.
  Pulls the constant operand, extracts the var's stats via
  `examine_variable`/`get_attstatsslot`, dispatches by strategy to
  `calc_rangesel` (`:32+ decl, :further down impl`).
  [verified-by-code]
- `default_range_selectivity(operator)` (`:33-34 decl`) — fallback
  constants per strategy. [verified-by-code]
- `calc_hist_selectivity` and `calc_hist_selectivity_scalar`
  (`:34-39 decl`) — the histogram integration. Look up bound's
  position in the histogram (binary search via
  `range_cmp_bounds`), interpolate via `subtype_diff`. The
  scalar form handles e.g. "range << constant_point".
- `length_hist_frac` — uses the length histogram for `@>`-style
  containment estimates where range length matters.

## Phase D notes

- Reads `pg_statistic` slots via `get_attstatsslot` — trust-bounded
  by `statistic_proc_security_check` against the cmp_proc. Garbage
  stats can only mis-estimate, not crash. [verified-by-code]
- Histograms are arrays of canonicalized `RangeType` Datums; their
  varlena structure is the same as user-supplied range values, so
  no separate parsing layer here. [inferred]

## Potential issues

- [ISSUE-correctness: `subtype_diff` may not be defined for
  user-defined range types, in which case histogram interpolation
  degrades to step-function; documented limitation (info)]
- [ISSUE-stale-todo: no join-selectivity counterpart for ranges
  (rangejoinsel doesn't exist as of this commit) — known gap that
  comes up periodically on hackers (info)]

## Cross-references

- `source/src/backend/utils/adt/rangetypes_typanalyze.c` — producer
  of the histograms.
- `source/src/backend/utils/adt/rangetypes.c` — `range_cmp_bounds`,
  `range_deserialize`.
- `source/src/backend/utils/adt/selfuncs.c` — `examine_variable`,
  `statistic_proc_security_check`, `get_attstatsslot`.

## Confidence tag tally
- `[verified-by-code]` × 3
- `[inferred]` × 1
