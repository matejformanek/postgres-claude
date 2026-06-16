# `contrib/pg_plan_advice/pgpa_planner.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~82
- **Source:** `source/contrib/pg_plan_advice/pgpa_planner.h`

Exposes the planner-side surface: hook installer, per-PlannerInfo
data struct (`pgpa_planner_info`), the activation counter, and the
PGDLLEXPORT used by `test_plan_advice`. [verified-by-code]

## API / entry points

- `pgpa_planner_install_hooks(void)` (line 17). Called from `_PG_init`.
- `pgpa_planner_info` struct (line 22): per-PlannerInfo bookkeeping.
  Fields: `plan_name`, `alternative_plan_name`, `is_alternative_plan`,
  `rid_array` + `rid_array_size`, `has_rtoffset` + `rtoffset`,
  `sj_unique_rels` (List of Bitmapset). [verified-by-code]
- `pgpa_planner_generate_advice` (line 77): non-atomic counter — modules
  call `pg_plan_advice_request_advice_generation` to bump/decrement.
  [verified-by-code]
- `pgpa_planner_feedback_warning(List *feedback)` (line 80): PGDLLEXPORT —
  for use by `test_plan_advice` regression test harness. [verified-by-code]

## Notable invariants / details

- `has_rtoffset` semantics (lines 47-53): false → this subquery's range
  table wasn't (or only partially was) copied into the final flat range
  table; rtoffset is undefined and `sj_unique_rels` is invalid. Set to true
  ONLY for the top-level proot during planning; other proots are populated
  later in `pgpa_compute_rt_offsets`. [from-comment] [verified-by-code]
- `is_alternative_plan` is set on EVERY proot that shares an
  `alternative_plan_name` with at least one other. Used to drive
  `DO_NOT_SCAN` generation for discarded alternatives. [from-comment]
- `sj_unique_rels` exists so the walker can tell whether SEMIJOIN_NON_UNIQUE
  advice should be emitted: "When the make-unique strategy is not chosen,
  it's not easy to tell from the final plan tree whether it was considered."
  [from-comment]

## Potential issues

- `pgpa_planner.h:77` — single counter, not per-backend or atomic. Implicit
  contract: only main backend bumps it. No comment makes this explicit.
  [ISSUE-undocumented-invariant: pgpa_planner_generate_advice
  threading/process model unspecified (nit)]
- `pgpa_planner.h:79-80` — `PGDLLEXPORT` for test-only function: convention
  in PG is "Must be exported for use by test_plan_advice" comment, used here.
  [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->
