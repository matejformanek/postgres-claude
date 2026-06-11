# Issues — `statistics`

Per-subsystem issue register for files under `src/backend/statistics/`.
See `knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent subsystem doc:** none yet (extended/attribute stats is
half-documented through `knowledge/files/src/backend/statistics/extended_stats.c.md`
and friends).

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | statistics/attribute_stats.c:100-101 | correctness | likely | In `cleararginfo[]`, both `C_ATTRELSCHEMA_ARG` and `C_ATTRELNAME_ARG` are named `"relation"`; the first should clearly be `"schemaname"` (cf. `attarginfo[]` at line 63-64). Affects only error messages emitted by `stats_check_required_arg()`, but they will be confusing. | open | knowledge/files/src/backend/statistics/attribute_stats.c.md §Potential issues |
| 2026-06-11 | statistics/relation_stats.c:55,201 | undocumented-invariant | nit | `pg_clear_relation_stats` hand-constructs a 6-arg `FunctionCallInfo` to call `relation_statistics_update`; magic constants 6/-1.0/0 mirror the `relarginfo` schema implicitly. If the schema grows, this caller breaks silently. | open | knowledge/files/src/backend/statistics/relation_stats.c.md §Potential issues |
| 2026-06-11 | statistics/stat_utils.c:280-296 | style | nit | `get_arg_by_name` issues `WARNING` on unknown name and returns -1; callers must check. Mixing WARN + sentinel return is mildly fragile vs ereport(ERROR). | open | knowledge/files/src/backend/statistics/stat_utils.c.md §Potential issues |
| 2026-06-11 | statistics/extended_stats_funcs.c:142-143 | doc-drift | nit | `expand_stxkind()` declared `static` but the in-source comment block above says nothing about the StakindFlags struct it populates; struct definition is in `extended_stats_internal.h`. Worth a one-liner cross-reference. | open | knowledge/files/src/backend/statistics/extended_stats_funcs.c.md §Potential issues |
| 2026-06-11 | statistics/attribute_stats.c:177-181 | undocumented-invariant | nit | `RecoveryInProgress()` check throws before lock acquisition is reasonable; but the parallel `pg_clear_attribute_stats()` (line ~643) has the same check after seeing both spelling drift, the duplication is a pattern that could be factored. | open | knowledge/files/src/backend/statistics/attribute_stats.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- `attribute_stats.c` / `extended_stats_funcs.c` / `relation_stats.c`
  implement the `pg_restore_*_stats` / `pg_clear_*_stats` functions
  introduced in PG17 (in support of pg_dump --statistics-only and
  upgrade-time stats import). All three rely on `stat_utils.c` for
  argument-pair translation and lock callbacks.
- The "named-attribute pseudo style" — pairs of (text name, value) —
  was chosen over real named parameters so that the function signature
  can evolve without breaking calls. `stats_fill_fcinfo_from_arg_pairs`
  is the translator.
- The ATTRELSCHEMA/ATTRELNAME swap in `cleararginfo[]` is the only
  bug-looking thing in this sweep that's worth chasing upstream.
