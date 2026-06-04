# `src/backend/utils/adt/orderedsetaggs.c`

## Purpose

Implementation of SQL ordered-set aggregates (`WITHIN GROUP`):
`percentile_cont`, `percentile_disc`, `mode` plus the hypothetical
ranks (`rank`, `dense_rank`, `percent_rank`, `cume_dist`). All share
a generic transition/final pattern: per-group `OSAPerGroupState`
holding a `Tuplesortstate` that accumulates input rows; finalfn
sorts and pulls the right percentile or mode.

`OSAPerQueryState` (`:49`) is shared across groups when nodeAgg
merges aggregates with identical inputs. 1431 lines.

## Key functions

- `ordered_set_startup`, `ordered_set_transition` — `:359`.
  One-row-at-a-time accumulation into `Tuplesortstate`.
- `ordered_set_transition_multi` — `:384`. For hypothetical-rank
  aggregates (multi-column).
- `percentile_disc_final` — `:428`. Single percentile, discrete.
- `percentile_cont_final_common` — `:527`. Linear interpolation
  between adjacent rows.
- `percentile_cont_float8_final`, `percentile_cont_interval_final`
  — `:614`, `:623`. Type-specific dispatchers.
- `percentile_disc_multi_final` — `:732`. Array-of-percentiles.
- `percentile_cont_multi_final_common` — `:849`. Array-of-percentiles
  with interpolation.
- `mode_final` — `:1034`. Scan sorted rows, count peers, return
  most-frequent value.
- `hypothetical_rank_common` — `:1172`. For `rank() WITHIN GROUP
  (ORDER BY ...)` — insert hypothetical row, sort, find its rank.

## Phase D notes

**Memory growth.** Each ordered-set aggregate buffers ALL input
rows in a Tuplesortstate before final-func. For huge groups this
spills to disk via `tuplesort_performsort` — but on-memory bound is
`work_mem`. A `percentile_cont(0.5) WITHIN GROUP (ORDER BY x)` over
a billion rows will spill, but won't OOM if `work_mem` is sane.

**Hypothetical aggregates** insert a synthetic row matching the
direct arguments and sort — same memory model. The
`hypothetical_check_argtypes` (`:1143`) validates types match the
WITHIN GROUP columns.

Percentile fraction is validated `0 ≤ p ≤ 1`; NaN rejected.
`[unverified]` — needs a closer read.

The shared `OSAPerQueryState` optimisation (`:42-46`) lets one sort
serve multiple percentile calls (e.g. computing 0.25, 0.5, 0.75 in
the same query) — `rescan_needed` flag drives whether to keep the
sort alive across finals.

## Potential issues

- [ISSUE-dos: Each ordered-set aggregate buffers entire group into
  a Tuplesortstate. For very large groups this spills to disk —
  fine — but the user has no way to skip non-zero rows during
  transition; the entire input is required. (informational)]
- [ISSUE-correctness: Percentile fraction validation must reject
  NaN and out-of-range. Worth verifying explicitly in the percentile
  finalfns (skim suggests the check is present but file is large).
  `[unverified]` (low)]
- [ISSUE-undocumented-invariant: The `rescan_needed` flag in
  `OSAPerQueryState` (`:58`) drives multi-final-call behaviour but
  the contract is subtle — nodeAgg decides; comments in nodeAgg.c
  would help. (low)]
