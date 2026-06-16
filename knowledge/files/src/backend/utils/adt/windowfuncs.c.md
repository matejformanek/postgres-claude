# `src/backend/utils/adt/windowfuncs.c`

## Purpose

Built-in SQL window functions: `row_number`, `rank`, `dense_rank`,
`percent_rank`, `cume_dist`, `ntile`, `lag`, `lead`, `first_value`,
`last_value`, `nth_value`. Plus prosupport functions
(`*_support`) that advise the planner about monotonicity and
frame-option simplification. 726 lines.

## Key functions

- `rank_up` — `windowfuncs.c:48`. Shared "should rank advance?"
  helper using `WinRowsArePeers`.
- `window_row_number` — `:84`. Always advances; `WinSetMarkPosition`
  for memory reclaim.
- `window_rank`, `window_dense_rank` — `:139`, `:202`. Use `rank_up`.
- `window_percent_rank`, `window_cume_dist` — `:264`, `:334`. Use
  `WinGetPartitionRowCount` for the denominator.
- `window_ntile` — `:416`. Computes bucket boundaries from total
  row count and bucket count. Rejects `nbuckets <= 0`. NULL input
  → NULL output (spec).
- `leadlag_common` — `:534`. Shared driver for lag/lead. Reads
  `offset` as `int32`. **`forward ? offset : -offset`** — see
  Phase D below.
- `window_lag`, `window_lead`, `window_lag_with_offset`,
  `window_lead_with_offset` (and `_and_default` variants) — `:587`+.
- `window_first_value`, `window_last_value`, `window_nth_value` —
  `:656`, `:678`, `:700`. `nth_value` rejects `nth <= 0`.
- `*_support` prosupport — answer `SupportRequestWFuncMonotonic`
  (most are MONOTONIC_INCREASING) and `SupportRequestOptimizeWindowClause`
  (downgrade to ROWS framing where safe).

## Phase D notes

**lag/lead offset overflow.** `leadlag_common` reads `offset` as a
local `int32` (`:538`) and computes
`(forward ? offset : -offset)` at `:559`. If `offset == INT32_MIN`,
then `-INT32_MIN` overflows to `INT32_MIN` in two's complement, so
`lag(col, INT32_MIN)` would silently treat the offset as still
INT32_MIN rather than rejecting. Whether this matters depends on
the downstream `WinGetFuncArgInPartition` semantics — likely it
just returns isout=true. `[verified-by-code]` for the negation;
downstream behavior `[unverified]`.

There's no explicit `offset < 0` check — by spec, lag/lead with
offset are well-defined for any non-negative offset, but negative
offsets are typically interpreted as the other direction. PG
silently swaps direction at the C level, but I don't see an
explicit reject for negative offsets. `[unverified]` —
double-check against test suite.

`window_ntile` rejects `nbuckets <= 0` properly (`:446`).
`window_nth_value` rejects `nth <= 0` properly (`:714`).

## Potential issues

- [ISSUE-correctness: `leadlag_common` computes `-offset` for `lag`
  without an `INT32_MIN` check. `lag(col, -2147483648)` triggers
  signed-integer overflow (UB in C99). Likely benign in practice
  (downstream treats as out-of-frame) but is a latent UB. (low,
  maybe)] — `windowfuncs.c:559`
- [ISSUE-undocumented-invariant: Negative offsets to lag/lead are
  not explicitly rejected; behaviour reverses direction. SQL spec
  says positive only. (low)]
- [ISSUE-dead-code: None visible.]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
