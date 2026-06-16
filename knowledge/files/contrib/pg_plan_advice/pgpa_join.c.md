# `contrib/pg_plan_advice/pgpa_join.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~642
- **Source:** `source/contrib/pg_plan_advice/pgpa_join.c`

Decomposes Plan-tree join subtrees into a flat, regular `pgpa_unrolled_join`
structure that `pgpa_walker.c` and `pgpa_output.c` can consume. The big idea:
join trees as found in a Plan tree have intermediate Hash / Material /
Memoize / Sort / Gather / Unique / Agg / Result nodes that are not part of
the join logic *per se* — they're side effects of the chosen join strategy
or parallelism. This file looks through them, classifies the join strategy
(merge/hash/nl + materialize/memoize variants), and produces a clean inner-deep
unrolled join. [verified-by-code] [from-README]

## API / entry points

- `pgpa_create_join_unroller()` (line 64): allocate an unroller with capacity
  4, ready to be `pgpa_unroll_join`-ed into. [verified-by-code]
- `pgpa_unroll_join(walker, plan, beneath_any_gather, ju, *outer_ju, *inner_ju)`
  (line 105): the workhorse — called recursively from `pgpa_walker.c`. Either
  passes the unroller through (for "pass-through" nodes like Material/Memoize/
  Hash/Gather/GatherMerge/Sort/IncrementalSort/Agg/Unique/Result-with-child),
  or decomposes a real join via `pgpa_decompose_join`, growing the array if
  needed and recursively requesting sub-unrollers for non-outer-deep inner
  sides. [verified-by-code]
- `pgpa_build_unrolled_join(walker, ju)` (line 230): take the populated
  unroller and produce a final `pgpa_unrolled_join` — *reversing* the order
  (the unroller adds joins outer-first; the result wants deepest-first).
  Recursively builds inner sub-joins via further `pgpa_build_unrolled_join`
  calls, or builds scans via `pgpa_build_scan`. [verified-by-code]
- `pgpa_destroy_join_unroller(ju)` (line 295): pfree the six allocated arrays.
  [verified-by-code]

## Notable invariants / details

- The pass-through whitelist (line 146-149) is exhaustively enumerated in
  comments (1)-(5): Material/Memoize/Hash are join-strategy parts; Gather/
  GatherMerge can appear at any point inside a join tree; Sort/IncrementalSort
  appear under MergeJoin or GatherMerge; Agg/Unique can wrap the nullable
  side of a semijoin made unique; Result-with-child handles projection/
  one-time-filter. [from-comment]
- `pgpa_decompose_join` (line 339): per-node-type logic. Hash joins always
  have a Hash inner, so descend one level. Merge joins may have Material on
  inner (recorded as `JSTRAT_MERGE_JOIN_MATERIALIZE`) and Sort/IncrementalSort
  on either side. Nested loops may have Material or Memoize on inner.
  Scan-level Materialize (under non-repeatable tablesample, see
  `pgpa_is_scan_level_materialize`) is explicitly excluded from being treated
  as a join strategy. [verified-by-code]
- `pgpa_descend_any_unique` (line 581) handles the semijoin-made-unique case
  on EITHER side. If the planner used Agg (not Unique) AND `aggsplit ==
  AGGSPLIT_SIMPLE`, it's assumed to be uniqueness-enforcing rather than a
  partial/finalize aggregate. The comment explicitly flags this as "could be
  more certain" with a Plan-node-level `purpose` field — `[ISSUE-question]`.
  [from-comment]
- `pgpa_decompose_join` updates the walker via `pgpa_add_future_feature` for
  every observed `SEMIJOIN_UNIQUE` / `SEMIJOIN_NON_UNIQUE` situation
  (lines 497-504). This is described in-comment as "somewhat hacky" — passing
  info up to the tree walker out-of-band. [from-comment]
- A `JOIN_RIGHT_SEMI` join on the outer (i.e. the non-uniquified case) is
  treated as `SEMIJOIN_NON_UNIQUE` to advise the planner accordingly.
  [verified-by-code]
- `pgpa_descend_any_gather` looks through GatherMerge's child Sort/IncrementalSort
  (line 553) — captured because GatherMerge requires sorted input.
  [verified-by-code]
- The "reverse order" in `pgpa_build_unrolled_join` (line 263) is essential:
  unrollers append outer-first, but the final structure wants `inner[0]` to
  be the deepest. Off-by-one or direction error here = silently wrong advice.
  [verified-by-code]

## Potential issues

- `pgpa_join.c:439-443` — comment: "Can we see a Result node here, to project
  above a Gather? So far I've found no example that behaves that way; rather,
  the Gather or Gather Merge is made to project. Hence, don't test
  is_result_node_with_child() at this point." This is a self-flagged
  fragility — if the planner ever DOES produce that shape, decomposition
  will silently miss it. [ISSUE-question: empirical "shouldn't happen"
  Result-above-Gather case not defensively handled (maybe)]
- `pgpa_join.c:495-496` — comment: "this seems like a somewhat hacky way of
  passing information up to the main tree walk, but I don't currently have
  a better idea." A more structured callback would be cleaner.
  [ISSUE-style: out-of-band data flow flagged in comment (nit)]
- `pgpa_join.c:608-613` — Agg-as-uniqueness vs Agg-as-aggregate inference
  is heuristic. The comment proposes adding a `purpose` field to Agg.
  Until that lands, a query with a partial-aggregation step that happens to
  use `AGGSPLIT_SIMPLE` could get misclassified. [ISSUE-correctness:
  Agg-as-uniqueness inference is purpose-by-aggsplit heuristic; flagged
  in source comment (maybe)]
- `pgpa_join.c:419-422` — `Assert(IsA(innerplan, Hash))` / `Assert(elidedinner
  == NULL)` for HashJoin. If a future patch introduces a HashJoin without an
  intervening Hash node (or with an elided Hash), these crash in cassert
  builds. Likely intentional defensive coding. [verified-by-code]
- `pgpa_join.c:426` — `elog(ERROR, "unrecognized node type: %d", ...)` —
  if a new Join subtype is added (T_AsofJoin?), advice generation crashes
  rather than gracefully ignoring. Probably the right default. [verified-by-code]
- `pgpa_join.c:295-302` — `pgpa_destroy_join_unroller` does not `pfree(strategy)`
  before `pfree(join_unroller)` — wait, yes it does (line 297). False alarm.
  Note that `outer_subplan` / `outer_elided_node` are pointers into a Plan
  tree (not owned). [verified-by-code]
- `pgpa_join.c:165-189` — the four parallel `repalloc_array` calls inside the
  growth branch could be reduced to one helper, but the current shape is
  readable. [ISSUE-style: parallel repalloc cluster could be extracted (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->
