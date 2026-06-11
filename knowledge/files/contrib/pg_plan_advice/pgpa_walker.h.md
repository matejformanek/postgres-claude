# `contrib/pg_plan_advice/pgpa_walker.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~125
- **Source:** `source/contrib/pg_plan_advice/pgpa_walker.h`

Defines `pgpa_qf_type` (the 4 query-feature kinds), `pgpa_query_feature`,
and `pgpa_plan_walker_context` — the post-planning accumulator that drives
output. [verified-by-code]

## API / entry points

- `pgpa_qf_type` enum (line 43): `PGPAQF_GATHER`, `PGPAQF_GATHER_MERGE`,
  `PGPAQF_SEMIJOIN_NON_UNIQUE`, `PGPAQF_SEMIJOIN_UNIQUE`.
  `NUM_PGPA_QF_TYPES` macro. [verified-by-code]
- `pgpa_query_feature` struct (line 59): `type`, `plan`, `relids`.
  [verified-by-code]
- `pgpa_plan_walker_context` struct (line 94): per-walker accumulator —
  `pstmt`, `scans[NUM_PGPA_SCAN_STRATEGY]`, `no_gather_scans`,
  `toplevel_unrolled_joins`, `join_strategies[NUM_PGPA_JOIN_STRATEGY]`,
  `query_features[NUM_PGPA_QF_TYPES]`, `future_query_features` (scratch),
  `do_not_scan_identifiers`. [verified-by-code]
- Public function declarations: `pgpa_plan_walker`,
  `pgpa_add_future_feature`, `pgpa_last_elided_node`, `pgpa_relids`,
  `pgpa_scanrelid`, `pgpa_is_scan_level_materialize`,
  `pgpa_filter_out_join_relids`, `pgpa_walker_would_advise`.

## Notable invariants / details

- **Query-feature concept** (line 20-42): "plan nodes that are interesting
  in the following way: to generate advice, we'll need to know the set of
  same-subquery, non-join RTIs occurring at or below that plan node,
  without admixture of parent and child RTIs." The walker propagates a
  per-recursion `active_query_features` list to which observed RTIs are
  added. [from-comment]
- **`future_query_features` is scratch**: must be empty after the walk
  completes (line 87-89). The walker drains it as it encounters the
  registered plan nodes. [from-comment]
- **NULL relids on a Gather** can happen with partitionwise aggregation
  (per `pgpa_walker.c:160-168`). Those entries are filtered out at
  end-of-walk. [from-comment]

## Potential issues

- `pgpa_walker.h:88-89` — "future_query_features ... should be empty when
  the tree walk concludes." Not asserted at the top of `pgpa_plan_walker`.
  A walker leak across walks would be silently observable. [ISSUE-leak:
  future_query_features postcondition not asserted (nit)]
- `pgpa_walker.h:48-50` — same "update NUM_PGPA_QF_TYPES" comment pattern.
  [ISSUE-style: comment-only sentinel update (nit)]
