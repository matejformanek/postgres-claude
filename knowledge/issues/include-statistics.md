# Issues — `src/include/statistics/`

Per-subdirectory issue register for the extended-statistics and
per-column-statistics headers. Companion to
`knowledge/issues/statistics.md` (which covers
`src/backend/statistics/`).

**Parent docs:** `knowledge/files/src/include/statistics/*.h.md`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/statistics/extended_stats_internal.h:119-142 | undocumented-invariant | likely | `mcv_combine_selectivities` and `mcv_clause_selectivity_or` encode the MCV-vs-non-MCV combine formula via parameter list; any formula change must update both signatures | open | files/.../extended_stats_internal.h.md |
| 2026-06-11 | src/include/statistics/extended_stats_internal.h:75-83 | doc-drift | nit | `_validate` functions take `int elevel` but expected levels (WARNING vs ERROR) not stated in header | open | files/.../extended_stats_internal.h.md |
| 2026-06-11 | src/include/statistics/extended_stats_internal.h:116-117 | doc-drift | nit | `examine_opclause_args` false-return path not documented in header | open | files/.../extended_stats_internal.h.md |
| 2026-06-11 | src/include/statistics/statistics.h:19 | undocumented-invariant | likely | `STATS_MAX_DIMENSIONS = 8` is hard-coded in multiple representations (`MCVList.types`, `int2vector stxkeys` signatures); raising it requires coherent edits | open | files/.../statistics.h.md |
| 2026-06-11 | src/include/statistics/statistics.h:22-23,43-44,66-67 | style | nit | Three independent magic numbers per stat kind — no central registry | open | files/.../statistics.h.md |
| 2026-06-11 | src/include/statistics/statistics.h:124-128 | doc-drift | nit | `choose_best_statistics` tie-break rule (first-found) not in header | open | files/.../statistics.h.md |
| 2026-06-11 | src/include/statistics/statistics.h:115-122 | undocumented-invariant | maybe | `statext_clauselist_selectivity`'s `is_or` boolean was added later; pre-`is_or` callers would silently miss the parameter | open | files/.../statistics.h.md |
| 2026-06-11 | src/include/statistics/stat_utils.h:1-12 | doc-drift | likely | File-header comment says "Extended statistics" but file is for per-column attribute stats (companion to `pg_restore_attribute_stats`) | open | files/.../stat_utils.h.md |
| 2026-06-11 | src/include/statistics/stat_utils.h:51-54 | style | nit | `statatt_set_slot` has 11 arguments — candidate for small-struct refactor | open | files/.../stat_utils.h.md |
| 2026-06-11 | src/include/statistics/stat_utils.h:40-42 | doc-drift | nit | `stats_fill_fcinfo_from_arg_pairs` bool-return semantics (skip vs error) not in header | open | files/.../stat_utils.h.md |
| 2026-06-11 | src/include/statistics/statistics_format.h:18-46 | undocumented-invariant | nit | No version field in the JSON; forward-compat depends on parser tolerance | open | files/.../statistics_format.h.md |
| 2026-06-11 | src/include/statistics/statistics_format.h | question | nit | MCV equivalent (`pg_mcv_list_items`) doesn't get parallel keys file here (it's a SRF instead) — asymmetry worth noting | open | files/.../statistics_format.h.md |

## Wontfix / Submitted / Landed

(empty)

## Notes

- The `stat_utils.h` file-header comment mismatch is the clearest
  doc-drift in this sweep — easy `hf(corpus)` candidate.
- `STATS_MAX_DIMENSIONS = 8` is structurally hard-coded; raising it
  is a known multi-site change.
- The header chain has clean separation: `statistics.h` is the
  public-ish surface (planner consumes), `extended_stats_internal.h`
  is backend-only, `stat_utils.h` is for per-column-stats import,
  `statistics_format.h` is shared frontend+backend JSON keys.
