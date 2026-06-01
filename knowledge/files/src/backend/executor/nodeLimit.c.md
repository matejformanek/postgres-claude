# nodeLimit.c

- **Source:** `source/src/backend/executor/nodeLimit.c` (≈480 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Implements LIMIT/OFFSET (including `FETCH FIRST n {ROWS | PERCENT}` and the
`WITH TIES` variants). [from-comment] `:15-19`

## Per-state machine

`lstate ∈ { LIMIT_INITIAL, LIMIT_RESCAN, LIMIT_EMPTY, LIMIT_INWINDOW,
LIMIT_WINDOWEND, LIMIT_WINDOWSTART, LIMIT_SUBPLANEOF }`. Per call:

- INITIAL → recompute_limits (evaluate `limitOffset` and `limitCount`
  expressions; these may be Params), skip OFFSET tuples by pulling and
  discarding, transition to INWINDOW.
- INWINDOW → return next tuple while position < OFFSET + COUNT; else go
  WINDOWEND.
- Backward scan: walk back to OFFSET position; WINDOWSTART when at start.

## WITH TIES

When the request is `FETCH FIRST n ROWS WITH TIES`, the node remembers the
sort-key value of the n-th row, then continues to read additional rows from
the outer (which the planner has ensured is a Sort with matching key) and
emits them as long as they tie. Uses an `eqfunctions`-based comparator.

## PERCENT

`FETCH FIRST n PERCENT`: the count is computed from total input row count.
nodeLimit eagerly drains the entire outer into the buffering child (it
requires Sort or Material below) and then emits the computed prefix.

## `tuples_needed` propagation

`compute_tuples_needed` returns an upper bound that's communicated downward
via `ExecSetTupleBound` — Sort uses this to switch to bounded sort, parallel
workers use it to stop fetching early.

## Tags

- [verified-by-code] state machine constants + WITH TIES handling.
- [from-comment] interface comment.
