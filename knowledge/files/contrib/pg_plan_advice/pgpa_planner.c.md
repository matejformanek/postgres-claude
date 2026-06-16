# `contrib/pg_plan_advice/pgpa_planner.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~2229
- **Source:** `source/contrib/pg_plan_advice/pgpa_planner.c`

The biggest file in the module — all interaction with the core planner.
Installs five core-planner hooks and uses them to (a) enforce supplied advice
by clearing bits in `pgs_mask` (the "path generation strategy" mask), and
(b) after planning, walk the resulting plan tree to generate a new advice
string. Heavy lifting for plan-tree walking lives in `pgpa_walker.c`; this
file is the hook surface. [verified-by-code] [from-comment]

## Architecture in one paragraph

Five planner-side hooks are installed (line 180): `planner_setup_hook`,
`planner_shutdown_hook`, `build_simple_rel_hook`, `joinrel_setup_hook`,
`join_path_setup_hook`. `planner_setup` parses any supplied advice into a
`pgpa_trove` and stashes a per-query `pgpa_planner_state` in the
PlannerGlobal's extension state. `build_simple_rel` looks up scan-related
advice for each baserel and applies it by clearing bits in `rel->pgs_mask`.
`joinrel_setup` and `join_path_setup` do the same for join relations —
the former handles advice that applies to a joinrel as a whole (Gather,
Partitionwise), the latter handles advice that depends on which
inner/outer split is being considered (join order, join method, semijoin
uniqueness). `planner_shutdown` walks the final plan to generate advice
output and feedback, stashing both in `PlannedStmt->extension_state` for
the `explain_per_plan_hook` to render. [verified-by-code]

## API / entry points

- `pgpa_planner_install_hooks()` (line 181): chained installation of all
  five planner hooks via the new `*_hook_type` extern slots. [verified-by-code]
- `pgpa_planner_setup` (line 200): per-query init — decides whether to
  generate advice/feedback, parses any supplied advice into a trove, and
  allocates `pgpa_planner_state`. [verified-by-code]
- `pgpa_planner_shutdown` (line 300): per-query teardown — computes
  rt-offsets, validates identifiers (cassert-only), walks the plan via
  `pgpa_plan_walker`, runs `pgpa_output_advice`, generates feedback via
  `pgpa_planner_append_feedback`, and stashes results in
  `pstmt->extension_state`. [verified-by-code]
- `pgpa_build_simple_rel` (line 404): for each baserel, look up SCAN and REL
  advice in the trove, apply via `pgpa_planner_apply_scan_advice`.
  [verified-by-code]
- `pgpa_joinrel_setup` (line 478): joinrel-level advice (PARTITIONWISE, GATHER,
  GATHER_MERGE, NO_GATHER) — applied via `pgpa_planner_apply_joinrel_advice`.
  Also called from joinrel_setup_hook BEFORE any path is built. [verified-by-code]
- `pgpa_join_path_setup` (line 528): join-path-level advice (JOIN_ORDER,
  join methods, semijoin uniqueness). Notes JOIN_UNIQUE_OUTER/INNER attempts
  for `sj_unique_rels` tracking. Applied via
  `pgpa_planner_apply_join_path_advice`. [verified-by-code]
- `pgpa_planner_feedback_warning(feedback)` (line 1908): PGDLLEXPORT —
  used by `test_plan_advice`. Emits a WARNING with one detail line per
  not-fully-matched advice item. [verified-by-code]

## Notable invariants / details

- The trove holds three slices: SCAN, JOIN, REL. `build_simple_rel` queries
  SCAN+REL; `joinrel_setup` queries REL; `join_path_setup` queries JOIN+REL.
  REL is the "either scope" slice for advice that can apply at base-rel or
  joinrel level (PARTITIONWISE, GATHER, GATHER_MERGE, NO_GATHER). [verified-by-code]
- **Only clear bits, never set bits** in `pgs_mask`. Repeated explicitly at
  lines 902, 1137-1140, 1846 — preserves the user's `enable_*` GUCs.
  [from-comment]
- **Don't act on conflicting advice.** Each apply-function tracks
  `*_conflict` booleans; if set, the entry is marked `PGPA_FB_CONFLICTING`
  but `pgs_mask` is not modified. [verified-by-code]
- **`pgpa_join_state` as negative cache** (line 653-661): once
  `pgpa_get_join_state` decides no trove advice applies to a joinrel, the
  empty `pgpa_join_state` sticks around as a negative-cache entry, so
  subsequent calls for the same joinrel return NULL without re-searching.
  [from-comment]
- **GEQO awareness** (line 273-279, 561-567, 667): the file is paranoid about
  short-lived `CurrentMemoryContext` during GEQO. `pps->mcxt` is captured at
  setup time and switched-to before any long-lived allocation. The XXX at
  line 667 admits some uncertainty. [from-comment]
- **PartitionWise re-checking in join_path** (line 956-996): partitionwise
  advice is examined twice — once in `joinrel_setup` (the joinrel as a
  whole) and again in `join_path_setup` (because it can also constrain join
  order, as a side effect). [from-comment]
- **Alternative subplans** (line 2010-2025): `pgpa_planner_get_proot` tracks
  when multiple proots share an `alternative_plan_name` and marks them all
  `is_alternative_plan = true`. The walker later figures out which was
  chosen and emits `DO_NOT_SCAN` for the others. [verified-by-code]
- **5-way set classification drives everything.** `pgpa_join_method_permits_join`,
  `pgpa_opaque_join_permits_join`, `pgpa_semijoin_permits_join`,
  `pgpa_join_order_permits_join` all branch on `pgpa_itm_type` from
  `pgpa_identifiers_match_target`. The semantics docs at the top of each
  function are critical for correctness. [from-comment]
- **Validation under cassert**: `pgpa_validate_rt_identifiers` (line 2138)
  cross-checks planning-time identifiers against post-planning identifiers.
  Only compiled under `USE_ASSERT_CHECKING`. [verified-by-code]
- **`pgs_mask` is the core-planner extension surface.** Bits include
  `PGS_SEQSCAN`, `PGS_INDEXSCAN`, `PGS_BITMAPSCAN`, `PGS_INDEXONLYSCAN`,
  `PGS_TIDSCAN`, `PGS_APPEND`, `PGS_MERGE_APPEND`, `PGS_CONSIDER_INDEXONLY`,
  `PGS_GATHER`, `PGS_GATHER_MERGE`, `PGS_CONSIDER_NONPARTIAL`,
  `PGS_NESTLOOP_*`, `PGS_MERGEJOIN_*`, `PGS_HASHJOIN`, `PGS_FOREIGNJOIN`,
  `PGS_CONSIDER_PARTITIONWISE`, plus `PGS_JOIN_ANY` / `PGS_SCAN_ANY` group
  masks. These live in core PG; this contrib only manipulates them.
  [verified-by-code]

## Potential issues

- `pgpa_planner.c:667` — "XXX. Does this need to do something different under
  GEQO?" — the join-state cache reuse under GEQO is questioned by the
  author. [ISSUE-question: GEQO interaction with join-state cache
  unverified (maybe)]
- `pgpa_planner.c:2229` — final `return "???"` for unknown JoinType: when a
  new JOIN_* enum value gets added, all `trace_mask` log lines lose
  human-readable join type. Silent degradation. [ISSUE-style: ??? sentinel
  vs pg_unreachable() (nit)]
- `pgpa_planner.c:166-167` — `pgpa_compute_rt_identifier` is `inline` but
  declared without `static`. Mismatch with file-static convention.
  [verified-by-code]
- `pgpa_planner.c:96-98` — `planner_extension_id` initialized to -1; the
  documented invariant "`pgpa_planner_install_hooks` runs before any hook
  fires" makes this safe. Not asserted. [ISSUE-undocumented-invariant:
  extension_id initialization assumed (nit)]
- `pgpa_planner.c:1716-1735` — `PARTITIONWISE` applied to >1 rel "has no
  effect at this level"; only single-rel-target PARTITIONWISE biases
  scan_type. Multi-rel PARTITIONWISE is enforced higher up at the joinrel.
  This split is correct but subtle. [from-comment]
- `pgpa_planner.c:1657-1670` — Bitmap heap scan handling preserves
  `PGS_CONSIDER_INDEXONLY` "until that logic is tightened up" — pointer to
  `build_index_scankeys` / `get_index_paths`. Self-flagged tech debt that
  spans modules. [ISSUE-stale-todo: cross-module workaround in
  BITMAP_HEAP_SCAN advice path (maybe)]
- `pgpa_planner.c:1685-1699` — two index specifications considered
  "conflicting unless they match exactly"; e.g. INDEX_SCAN(a c) and
  INDEX_SCAN(a b.c) treated as conflicting even though they could refer
  to the same index. Self-flagged "doesn't seem worth the code" in
  comment. [ISSUE-stale-todo: schema-elided index conflict false-positives
  acknowledged (nit)]
- `pgpa_planner.c:2173` — `pgpa_validate_rt_identifiers` is only compiled
  in cassert builds. Production builds will silently mis-route advice if the
  two identifier-computation paths diverge. [ISSUE-correctness: invariant
  check only present under USE_ASSERT_CHECKING (maybe)]
- `pgpa_planner.c:438-461` — `pg_plan_advice_trace_mask` emits WARNING for
  every changed mask, which can be very noisy. Probably DEBUG would be
  more appropriate, but the GUC name suggests user opt-in. [ISSUE-style:
  WARNING log level may be too noisy for a debug toggle (nit)]
- `pgpa_planner.c:1907-1956` — `pgpa_planner_feedback_warning` emits the
  warning even for `PGPA_FB_MATCH_FULL` entries if any other flag is set
  (e.g. CONFLICTING). Behavior is intentional — but the test for "fully
  matched with no problems" at line 1932 hardcodes
  `MATCH_PARTIAL|MATCH_FULL` as the success set, which means any future
  flag will be treated as a problem. [verified-by-code]
- `pgpa_planner.c:1051-1101` — semijoin uniqueness handling: when neither
  `jt_unique` nor `jt_non_unique` matches, the advice gets
  `PGPA_FB_INAPPLICABLE`, but the join still proceeds. Comment is sparse.
  [from-comment]
- `pgpa_planner.c:782-787` — `Assert(itm != PGPA_ITM_DISJOINT)` relies on
  trove filtering. If the trove ever returns an index for a disjoint
  target, this asserts in cassert and silently wrong-applies in
  production. [verified-by-code]
- `pgpa_planner.c:96-97` — `pgpa_planner_generate_advice` is a non-atomic int
  manipulated via `++`/`--`. Safe in single-backend context only. Comments
  imply expected single-backend use. [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->
