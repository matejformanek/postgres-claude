# `contrib/pg_plan_advice/pgpa_walker.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1174
- **Source:** `source/contrib/pg_plan_advice/pgpa_walker.c`

Walks a finished `PlannedStmt` to produce the inputs needed by
`pgpa_output.c` to render an advice string. Recursively descends Plan trees
(main + subplans), constructing `pgpa_scan` and `pgpa_unrolled_join` objects
along the way. Maintains "active query features" — Gather/GatherMerge and
semijoin-unique decisions that must enumerate the RTIs beneath them.
Crosses no subquery boundaries except via explicit SubqueryScan recursion;
crosses no partitionwise boundaries except via the elided-node mechanism.
Also provides `pgpa_walker_would_advise` — the "would this plan generate
exactly this advice?" oracle that drives `PGPA_FB_FAILED` feedback.
[verified-by-code]

## API / entry points

- `pgpa_plan_walker(walker, pstmt, proots)` (line 77): top-level entry.
  Walks `pstmt->planTree` then each non-NULL `pstmt->subplans` entry. Adjusts
  semijoin-unique relid sets to the flattened RT layout via per-proot
  rtoffset. Reconciles observed vs planning-time `SEMIJOIN_UNIQUE/NON_UNIQUE`
  to filter spurious NON_UNIQUE advice for cases where the planner never
  considered uniquification. Classifies alternative subplans into chosen
  vs discarded and emits `DO_NOT_SCAN` for the latter. [verified-by-code]
- `pgpa_walk_recursively` (line 246): the main workhorse. Handles
  "future query features" (set up by `pgpa_join.c:decompose` via
  `pgpa_add_future_feature`), elided nodes (with the rule "elided nodes
  act as barriers to query features"), Gather/GatherMerge detection, build_scan
  invocation when *not* within a join problem, the kick-off of a new join
  unroller when we hit a Join with no active unroller, the
  `pgpa_unroll_join` per-step, descent into lefttree/righttree (skipped for
  ForeignScan), build_unrolled_join at the top of the join tree, and
  recursion through extraplans (Append/MergeAppend/Bitmap/CustomScan
  children, SubqueryScan subplans). [verified-by-code]
- `pgpa_process_unrolled_join` (line 497): once a top-level unrolled-join
  is built, recurse and append inner-relid bitmapsets to
  `walker->join_strategies[strategy]`. Used to drive
  `HASH_JOIN(...)`/`NESTED_LOOP_*(...)` advice. [verified-by-code]
- `pgpa_add_future_feature(walker, type, plan)` (line 534): public — called
  by `pgpa_decompose_join` from `pgpa_join.c` to flag a Plan node that
  should be treated as a query feature when the walker reaches it.
  [verified-by-code]
- `pgpa_last_elided_node`, `pgpa_relids`, `pgpa_scanrelid`,
  `pgpa_is_scan_level_materialize`, `pgpa_filter_out_join_relids` (lines
  549-659): small public helpers used by `pgpa_join.c` and `pgpa_scan.c`.
  [verified-by-code]
- `pgpa_walker_would_advise(walker, rt_identifiers, tag, target)` (line 731):
  the post-planning oracle used by `pgpa_planner_append_feedback` to set
  `PGPA_FB_FAILED` on fully-matched-but-not-realized advice. Big switch over
  tag types; each branch consults a small helper:
  `pgpa_walker_find_scan` (by strategy + relids),
  `pgpa_walker_contains_feature` (by qf_type + relids),
  `pgpa_walker_contains_join` (by join_strategy + relids),
  `pgpa_walker_contains_no_gather`, `pgpa_walker_join_order_matches`,
  `pgpa_walker_index_target_matches_plan`. [verified-by-code]

## Notable invariants / details

- **Query features have "no admixture of parent and child RTIs"** rule
  (`pgpa_walker.h:35-42`): if the entire inheritance hierarchy is below a
  feature, only the parent RTI is named; if only some partitions are below,
  child RTIs are named directly. [from-comment]
- **Elided nodes act as barriers** (line 297-310): RTIs from the
  uppermost elided node are added to active features, then the active list
  is reset to NIL. Lower elided nodes have their RTIs ignored for feature
  purposes. [from-comment]
- **`within_join_problem` semantics** (line 222-229): the recursion variable
  that says "we entered a join subtree higher up". Reset to false when
  crossing a partitionwise boundary or subquery boundary. The unroller is
  responsible for `pgpa_build_scan` calls when within a join problem; the
  walker is responsible outside. [from-comment]
- **`single_copy` Gather exception** (line 350): Gather nodes with
  `single_copy = true` (from `debug_parallel_query`) are intentionally
  ignored — emitting GATHER advice for them would be counterproductive.
  [from-comment]
- **ForeignScan recursion skipped** (line 406-416): postgres_fdw can put EPQ
  recheck plans in lefttree; this module has no way to advise on that
  duality, so it punts. [from-comment]
- **Plan-Tree-feature vs Planner-state-feature reconciliation** (line 127-157):
  the `SEMIJOIN_UNIQUE` plan-tree finding must correspond to a planning-time
  attempt observed in `pgpa_planner_info->sj_unique_rels`. If a plan-tree
  unique was observed but no planning-time attempt was recorded,
  `elog(ERROR)` — that's a bug in this module. The reverse (planning attempt
  without plan realization) just emits no advice. [from-comment]
- **`classify_alternative_subplans`** (line 1123-1174): a subplan is "chosen"
  iff any of its scan RTIs appear in the final flat scan-RTI set. Multiple
  alternatives can be chosen (siblings), but those whose RTIs disappeared
  get `DO_NOT_SCAN`. The rationale: `AlternativeSubPlan` and `MinMaxAggPath`
  resolve to one of several considered subplans; we need to advise the
  discarded ones be skipped. [from-comment] [from-README]
- **`pgpa_walker_would_advise` is a forward-vs-backward check**: it asks
  "would generating advice from the final plan produce this trove entry?"
  If not, set FAILED. This means the planning-time match (`MATCH_FULL`)
  said yes but the post-planning observation says no — usually because of
  later setrefs processing or cost-based rejection. [from-comment]
- The cross between `pgpa_walker_would_advise` and `pgpa_walker_*_matches`
  on RTI matching: it uses `pgpa_compute_rti_from_identifier` to map
  user-supplied identifiers to RTIs in the flat range table, then compares
  by `bms_equal` to the recorded relids. [verified-by-code]

## Potential issues

- `pgpa_walker.c:160-184` — the "Partial Aggregates in such a case" comment
  proposes a planner refactor that would simplify this module. Until then,
  Gather/GatherMerge query features with NULL relids are silently dropped.
  Could lead to no NO_GATHER advice when one would be appropriate.
  [ISSUE-stale-todo: cross-module Partial-Aggregates relid-set workaround (maybe)]
- `pgpa_walker.c:146-156` — "found unique semijoin but not observed during
  planning" elog(ERROR) is internal-bug-detection. If a future planner
  change creates the situation, every advice-generating query against the
  affected shape errors out. [ISSUE-correctness: elog(ERROR) on
  internal-bug condition crashes user queries (maybe)]
- `pgpa_walker.c:399-405` — comment "Maybe some better handling is needed
  here, but for now, we just punt." for FDW EPQ rechecks. Self-flagged
  limitation. [ISSUE-stale-todo: FDW EPQ recheck-plan handling
  acknowledged as incomplete (maybe)]
- `pgpa_walker.c:467` — `pgpa_walk_recursively(walker, ..., 0, NULL, NIL, ...)`
  uses literal `0` for the bool `within_join_problem` parameter. Should be
  `false`. Style nit. [ISSUE-style: bool param passed as 0 literal (nit)]
- `pgpa_walker.c:1148-1166` — alternative-subplan classification requires
  `has_rtoffset`. Subplans where rt_offset couldn't be computed never become
  "chosen", which means they always become "discarded" — and may incorrectly
  receive `DO_NOT_SCAN` advice. The "`some_alternative_chosen`" check at
  `pgpa_walker.c:194-209` mitigates by requiring a *sibling* to be chosen,
  but if both siblings have no rtoffset, neither gets advice. [verified-by-code]
- `pgpa_walker.c:269-279` — `future_query_features` lookup is O(N×N) — list
  scan inside a walker that runs once per Plan node. For small lists, this
  is fine. For pathologically large plans, would matter. [ISSUE-style:
  O(N²) future-feature lookup; N typically small (nit)]
- `pgpa_walker.c:556-561` — `pgpa_last_elided_node` is a linear scan of
  `pstmt->elidedNodes` for every Plan node visited. Called twice per
  node (once here, once in `pgpa_join.c`). [ISSUE-style: linear scan of
  elided nodes per visit could be index-cached (nit)]
- `pgpa_walker.c:899-900` — `/* should not get here */ return false;` after
  an exhaustive switch. Missing `pg_unreachable()`. [ISSUE-style:
  unreachable fallthrough lacks pg_unreachable hint (nit)]
- `pgpa_walker.c:736-738` — early-out for JOIN_ORDER short-circuits the
  switch below, which uses `relids` that wasn't built for JOIN_ORDER.
  Correct, but the layout could be cleaner. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
