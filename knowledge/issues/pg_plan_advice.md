# Issues — `pg_plan_advice`

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent subsystem doc:** (none yet — first-time coverage at sweep A21)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/pg_plan_advice/pg_plan_advice.c:36 | style | nit | always_explain_supplied_advice GUC declared static; asymmetric vs other four GUCs which are non-static / externally visible | open | knowledge/files/contrib/pg_plan_advice/pg_plan_advice.c.md §Potential issues |
| 2026-06-11 | contrib/pg_plan_advice/pg_plan_advice.c:248 | correctness | maybe | pg_plan_advice_request_advice_generation(false) Assert-on-counter-underflow; in release, would silently underflow | open | knowledge/files/contrib/pg_plan_advice/pg_plan_advice.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pg_plan_advice.c:402 | undocumented-invariant | nit | strVal(advice_string_item->arg) assumes String Node by construction; no Assert | open | knowledge/files/contrib/pg_plan_advice/pg_plan_advice.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pg_plan_advice.h:41-45 | style | nit | flag macros public but flag-printer pgpa_trove_append_flags is in pgpa_trove.h, not exposed here | open | knowledge/files/contrib/pg_plan_advice/pg_plan_advice.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_ast.c:163 | correctness | maybe | pgpa_parse_advice_tag on failure returns arbitrary PGPA_TAG_SEQ_SCAN; caller forgetting *fail check silently mis-interprets | open | knowledge/files/contrib/pg_plan_advice/pgpa_ast.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_ast.c:289 | leak | nit | rids_used bool array palloc0_array'd per call, relies on caller's short-lived context | open | knowledge/files/contrib/pg_plan_advice/pgpa_ast.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_ast.c:73-77 | style | nit | pg_unreachable() outside switch instead of default-case idiom | open | knowledge/files/contrib/pg_plan_advice/pgpa_ast.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_ast.h:76-78 | undocumented-invariant | maybe | no compile-time enforcement that pgpa_advice_tag_type enum and pgpa_parse_advice_tag / pgpa_cstring_advice_tag stay in sync | open | knowledge/files/contrib/pg_plan_advice/pgpa_ast.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_ast.h:60-64 | undocumented-invariant | nit | itarget field conditionally meaningful (only INDEX_SCAN/INDEX_ONLY_SCAN identifier targets); not flagged in struct | open | knowledge/files/contrib/pg_plan_advice/pgpa_ast.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_identifier.c:289 | question | nit | "shouldn't ever iterate more than once" while-loop defensive Assert absent | open | knowledge/files/contrib/pg_plan_advice/pgpa_identifier.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_identifier.c:415-430 | undocumented-invariant | maybe | parent-before-child appinfo list ordering assumed without runtime check; would produce wrong identifiers if violated | open | knowledge/files/contrib/pg_plan_advice/pgpa_identifier.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_identifier.c:235 | undocumented-invariant | nit | caller contract "must contain at least one non-RTE_JOIN" not in header | open | knowledge/files/contrib/pg_plan_advice/pgpa_identifier.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_identifier.c:378-388 | question | nit | return-0 ambiguity between no-match and multi-match in pgpa_compute_rti_from_identifier | open | knowledge/files/contrib/pg_plan_advice/pgpa_identifier.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_identifier.h:30-38 | style | nit | strings_equal_or_both_null static inline in header; pure helper, not idiomatic PG | open | knowledge/files/contrib/pg_plan_advice/pgpa_identifier.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_join.c:439-443 | question | maybe | self-flagged "haven't found a Result-above-Gather case" — defensive handling absent | open | knowledge/files/contrib/pg_plan_advice/pgpa_join.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_join.c:495-496 | style | nit | "somewhat hacky way of passing info up to tree walk" — pgpa_add_future_feature flagged in source | open | knowledge/files/contrib/pg_plan_advice/pgpa_join.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_join.c:608-613 | correctness | maybe | Agg-as-uniqueness inferred via aggsplit==AGGSPLIT_SIMPLE; future partial-Agg in same shape would misclassify; proposed "purpose" field on Agg | open | knowledge/files/contrib/pg_plan_advice/pgpa_join.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_join.h:54 | undocumented-invariant | nit | "exactly one of scan and unrolled_join non-NULL" not compile-time enforced | open | knowledge/files/contrib/pg_plan_advice/pgpa_join.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_join.h:35 | style | nit | comment-only NUM_PGPA_JOIN_STRATEGY sync; pattern repeated throughout module | open | knowledge/files/contrib/pg_plan_advice/pgpa_join.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_output.c:114 | style | nit | hardcoded wrap_column = 76 magic constant | open | knowledge/files/contrib/pg_plan_advice/pgpa_output.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_output.c:280-284 | correctness | maybe | get_rel_name(relid) NULL not handled; dropped relation between planning and EXPLAIN would crash | open | knowledge/files/contrib/pg_plan_advice/pgpa_output.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_output.c:596-606 | style | nit | pgpa_maybe_linebreak directly manipulates StringInfo internals bypassing standard API | open | knowledge/files/contrib/pg_plan_advice/pgpa_output.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.c:667 | question | maybe | "Does this need to do something different under GEQO?" — join-state cache reuse unverified | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.c:1657-1670 | stale-todo | maybe | BITMAP_HEAP_SCAN advice forced to keep PGS_CONSIDER_INDEXONLY due to build_index_scankeys/get_index_paths quirk; "perhaps that logic should be tightened up" | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.c:1685-1699 | stale-todo | nit | schema-elided index advice (e.g. INDEX_SCAN(a c) vs INDEX_SCAN(a b.c)) treated as conflicting; "doesn't seem worth the code" | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.c:2173 | correctness | maybe | pgpa_validate_rt_identifiers only compiled under USE_ASSERT_CHECKING; production builds silently mis-route on divergence | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.c:438-461 | style | nit | trace_mask emits WARNING for every changed mask; could be very noisy at high planner load | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.c:782-787 | correctness | maybe | Assert(itm != PGPA_ITM_DISJOINT) relies on trove pre-filtering; bug in trove silently wrong-applies | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.c:2229 | style | nit | "???" sentinel for unknown JoinType in trace string; should be pg_unreachable() | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_planner.h:77 | undocumented-invariant | nit | pgpa_planner_generate_advice non-atomic int; threading/process model unspecified | open | knowledge/files/contrib/pg_plan_advice/pgpa_planner.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_scan.c:280-283 | correctness | maybe | elog(ERROR) on rtekind mismatch in Append; pluggable executor / custom RTEs may trip this | open | knowledge/files/contrib/pg_plan_advice/pgpa_scan.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_scan.h:62-66 | style | nit | comment-only NUM_PGPA_SCAN_STRATEGY sync | open | knowledge/files/contrib/pg_plan_advice/pgpa_scan.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_trove.c:472-477 | question | nit | hash-tweak (total-of-lengths) acknowledged as "not clear what to do" | open | knowledge/files/contrib/pg_plan_advice/pgpa_trove.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_trove.c:257-264 | undocumented-invariant | maybe | Assert all rids share plan_name; caller bug silently misbehaves in production | open | knowledge/files/contrib/pg_plan_advice/pgpa_trove.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_trove.c:135 | undocumented-invariant | nit | palloc_object(pgpa_trove) uninitialized; relies on per-slice init for every field | open | knowledge/files/contrib/pg_plan_advice/pgpa_trove.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_trove.c:447-448 | leak | maybe | pgpa_trove_entry_create uses CurrentMemoryContext; GEQO short-context interaction noted in pgpa_planner.c could leak partial state | open | knowledge/files/contrib/pg_plan_advice/pgpa_trove.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_trove.h:26-31 | style | nit | flags field is plain int, not bitfield typedef | open | knowledge/files/contrib/pg_plan_advice/pgpa_trove.h.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.c:160-184 | stale-todo | maybe | NULL-relids Gather features silently dropped (partitionwise aggregation case); proposes upstream UPPERREL_GROUP_AGG with non-empty relid set | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.c:146-156 | correctness | maybe | elog(ERROR) on "unique semijoin found but not observed during planning" crashes user query for internal bug condition | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.c:399-405 | stale-todo | maybe | FDW EPQ recheck-plan handling acknowledged as incomplete: "we just punt" | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.c:467 | style | nit | bool param passed as literal 0 instead of false | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.c:269-279 | style | nit | future_query_features lookup is O(N*M); N typically small | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.c:556-561 | style | nit | linear scan of pstmt->elidedNodes per Plan-node visit could be indexed | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.c:899-900 | style | nit | exhaustive-switch fallthrough lacks pg_unreachable() | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md |
| 2026-06-11 | contrib/pg_plan_advice/pgpa_walker.h:88-89 | leak | nit | future_query_features postcondition (empty after walk) not asserted | open | knowledge/files/contrib/pg_plan_advice/pgpa_walker.h.md |

## Wontfix / Submitted / Landed

(none yet)

## Notes

First-time coverage of `contrib/pg_plan_advice` at sweep A21
(2026-06-11), pin `e18b0cb7344`. This is a new PG18+ contrib module
implementing plan hints / advice. Architecture summary:

- **Hooks installed** (line `pgpa_planner.c:181`): `planner_setup_hook`,
  `planner_shutdown_hook`, `build_simple_rel_hook`, `joinrel_setup_hook`,
  `join_path_setup_hook`, plus `explain_per_plan_hook` chained from
  `pg_plan_advice.c`.
- **GUCs**: `pg_plan_advice.advice` (string, parsed by GUC check hook),
  `always_explain_supplied_advice`, `always_store_advice_details`,
  `feedback_warnings`, `trace_mask`.
- **EXPLAIN option**: `EXPLAIN (PLAN_ADVICE)` — registered via
  `RegisterExtensionExplainOption`.
- **Public C-extension API**: `pg_plan_advice_add_advisor` /
  `pg_plan_advice_remove_advisor` (function-pointer hook for other modules
  to supply per-query advice strings), `pg_plan_advice_request_advice_generation`.
- **Mechanism**: advice is enforced by clearing bits in `RelOptInfo->pgs_mask`
  (path generation strategy mask, exposed by core PG as `PGS_*` constants).
  The contrib only ever CLEARS bits, never sets — preserving the user's
  `enable_*` GUCs.
- **Round-trip property**: identifiers are stable
  (`alias_name#occurrence/partnsp.partrel@plan_name`), generated advice
  re-applied to the same query should re-produce the same plan.
- **Feedback bits**: `PGPA_FB_MATCH_PARTIAL`, `MATCH_FULL`, `INAPPLICABLE`,
  `CONFLICTING`, `FAILED` — surfaced via `Supplied Plan Advice` in EXPLAIN.

The top three issues by severity (all "maybe"):

1. **`pgpa_planner.c:1657-1670`** — BITMAP_HEAP_SCAN advice has to leave
   `PGS_CONSIDER_INDEXONLY` set due to a quirk in
   `build_index_scankeys`/`get_index_paths`. Cross-module tech debt that
   could be tightened in core. (stale-todo)
2. **`pgpa_walker.c:146-156`** — `elog(ERROR)` on the internal-bug
   condition "unique semijoin found but not observed during planning"
   crashes user queries if this contrib has any latent bug. Either downgrade
   to LOG and silently emit no advice, or add a tighter test net. (correctness)
3. **`pgpa_join.c:608-613`** — Agg-vs-Unique inference relies on
   `aggsplit == AGGSPLIT_SIMPLE` as "this is semijoin uniqueness, not
   eager aggregation". Self-flagged: proposed `purpose` field on Agg.
   Future planner changes could silently misclassify. (correctness)
