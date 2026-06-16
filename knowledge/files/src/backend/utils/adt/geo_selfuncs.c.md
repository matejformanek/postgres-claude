# geo_selfuncs.c — selectivity estimators for geometric operators

## Purpose

Selectivity functions for geometric operators (`<<`, `>>`, `&<`, `<@`, `@>`, etc.). Returns fixed constants — there is **no statistics-driven estimation** for geometry types; the planner gets a generic guess. This is a known long-standing limitation.

Source: `source/src/backend/utils/adt/geo_selfuncs.c` (95 lines).

## Key functions

- `areasel` (line 47) — selectivity for "overlap area" operators (`&&`, etc.). Returns `DEFAULT_INEQ_SEL` (0.3333). [verified-by-code]
- `areajoinsel` (line 53) — join selectivity for the same family. Returns `DEFAULT_INEQ_SEL`. [verified-by-code]
- `positionsel` (line 66) — selectivity for positional operators (`<<`, `>>`, `&<`, `&>`, ...). Returns `DEFAULT_INEQ_SEL`. [verified-by-code]
- `positionjoinsel` (line 72) — `DEFAULT_INEQ_SEL`. [verified-by-code]
- `contsel` (line 85) — selectivity for containment (`@>`, `<@`). Returns `DEFAULT_INEQ_SEL` / 10 (0.0333). [verified-by-code]
- `contjoinsel` (line 91) — same. [verified-by-code]

## Phase D notes

- **No actual estimation logic.** The whole file is constant returns. A common cause of bad plans on geometric columns.
- **Constants chosen empirically long ago** — `DEFAULT_INEQ_SEL = 0.3333` for overlap/position (assume 1/3 of rows match), `DEFAULT_INEQ_SEL/10` for containment (much rarer).
- This is the place a future enhancement would hook MCV-based or histogram-based geometry stats.

## Potential issues

- `[ISSUE-stale-todo: geo selectivity is hardcoded; for tables with selective geometry filters, the planner picks bad plans. Known limitation but no in-file TODO marker. (medium; long-standing)]`.
- `[ISSUE-undocumented-invariant: the 0.3333 constant is shared with many non-geo "I don't know" estimators; if a workload depends on this value to coax a particular plan, future changes could regress silently (low)]`.

Confidence: `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
