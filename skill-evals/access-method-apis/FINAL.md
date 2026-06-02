# access-method-apis — final eval summary

| Iter | Baseline | With-skill | Uplift |
|------|----------|------------|--------|
| 1    | 11.5/23  | 23/23      | +50 pp |
| 2    | 15.5/23  | 23/23      | +33 pp |

with_skill saturates the iter-1 assertion rubric in both iterations. Baseline
fluctuates by ±4 points between independent attempts — a single-judge,
single-prompter methodology cannot resolve finer differences once the skill
is already saturating.

## What changed between iter-1 and iter-2

Six "minor polish" edits from `iteration-1/proposed-edits.md` were applied:

1. `IndexBulkDeleteResult *` return type made explicit on `ambulkdelete` and
   `amvacuumcleanup` rows.
2. `ambeginscan` / `RelationGetIndexScan` return-identity rule lifted from
   inline paragraph to a fenced **GOTCHA** block.
3. `amparallelvacuumoptions` documented with the three bit names and the
   `VACUUM_OPTION_NO_PARALLEL = 0` opt-out for new AMs.
4. Table-AM mandatory count reconciled — was "~45 callbacks / ~30 Asserts",
   now "~45-callback struct; tableamapi.c asserts 37 of them" (verified
   `grep -c 'Assert(routine'` = 37 in source).
5. Autovacuum-stats leakage made explicit — `pg_stat_all_tables` counters,
   `pgstat_count_heap_*` and `pgstat_report_vacuum` named as the entry points
   a non-heap AM must call from inside its own tuple ops.
6. Lifecycle diagram order fixed — `aminsertcleanup` no longer reads as
   per-row; now `(per row) aminsert → (once at end of statement) aminsertcleanup`.

All six edits were applied without touching the skill's two-table top framing,
the ~240-line length, or the heap-leakage list (which scored 8/8 in eval #3 of
iter-1).

## Quality vs score

iter-2 with_skill answers are qualitatively better than iter-1's — more
specific type names, exact Assert count, named GUC/stats entry points — but
the iter-1 assertion rubric doesn't reward those refinements, so headline
score stays at 23/23. Future iterations should probe narrower corners
(opclass `amvalidate` vs `amadjustmembers`, `index_fetch_tuple` lifetime,
`tuple_lock` `TM_Result` semantics under SSI) per the "Suggested next
iteration" note in `iteration-1/proposed-edits.md` to actually move the
ceiling.

## Verdict

The skill is **stable and production-ready** for the prompts it was designed
for. No further edits planned without harder prompts.
