# `src/backend/utils/adt/array_selfuncs.c`

- **File:** `source/src/backend/utils/adt/array_selfuncs.c` (1201 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

Selectivity estimators for array operators `@>` (contains), `<@`
(contained-by), and `&&` (overlap), driven by the MCELEM
(most-common-elements) statistics gathered by `array_typanalyze.c`.

Entry points exposed as `oprrest`/`oprjoin` in `pg_operator.dat`:
- `arraycontsel(PlannerInfo*, oid, args, varRelid)` — restriction sel
  (`:241-315`).
- `arraycontjoinsel` (`:321-327`) — join sel. **Currently a stub**
  returning `DEFAULT_SEL(operator)`. [verified-by-code]

## Key functions

- `DEFAULT_CONTAIN_SEL` = 0.005, `DEFAULT_OVERLAP_SEL` = 0.01 (`:30`,
  also default-sel constants). [verified-by-code]
- `arraycontsel` (`:241-315`) — sanity-checks the
  `(var op const)`/`(const op var)` shape, handles NULL const, commutes
  operator if var is on right, then dispatches to
  `calc_arraycontsel` if const is same array element type as column.
  Returns `DEFAULT_SEL` if no usable stats. [verified-by-code]
- `calc_arraycontsel(vardata, constval, elemtype, operator)` (`:337+`)
  — extracts MCELEM slot via `get_attstatsslot` with
  `STATISTIC_KIND_MCELEM`, plus the length-histogram slot
  (`STATISTIC_KIND_DECHIST`), passes to `mcelem_array_selec`.
  Includes a `statistic_proc_security_check` gate against
  leakproof-violating comparison functions (`:357-358`). [verified-by-code]
- `mcelem_array_selec` (further down) does the heavy lifting: for `@>`
  multiplies per-element probabilities (independence assumption),
  for `&&` does inclusion-exclusion, for `<@` integrates over the
  length histogram. (Not deep-read in this pass — see `selfuncs.c.md`
  for the broader sel-estimator framework.) [unverified]

## Phase D notes

- Reads pg_statistic via `get_attstatsslot` — these slots are populated
  by `array_typanalyze.c` and trusted. A malicious extension that
  writes garbage MCELEM stats could mis-estimate but cannot crash
  (the comparison function used is the element's own cmp_proc,
  protected by `statistic_proc_security_check`). [verified-by-code]
- `arraycontjoinsel` being a stub means array-join planning relies on
  the default constant — known limitation, not a bug. [from-comment]

## Potential issues

- [ISSUE-stale-todo: `arraycontjoinsel` is "just a stub" (`:323`
  comment); long-standing TODO (info)]
- [ISSUE-correctness: independence assumption in `@>` element-prob
  product can severely under-estimate when elements are correlated;
  documented PG limitation (info)]

## Cross-references

- `source/src/backend/utils/adt/array_typanalyze.c` — produces the
  MCELEM/DECHIST stats this consumes.
- `source/src/backend/utils/adt/selfuncs.c` — `get_restriction_variable`,
  `statistic_proc_security_check`, `get_attstatsslot`.
- `source/src/include/catalog/pg_statistic.h` —
  `STATISTIC_KIND_MCELEM`, `STATISTIC_KIND_DECHIST`.

## Confidence tag tally
- `[verified-by-code]` × 4
- `[from-comment]` × 2
- `[unverified]` × 1
