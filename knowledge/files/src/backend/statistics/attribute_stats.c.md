# `src/backend/statistics/attribute_stats.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~690
- **Source:** `source/src/backend/statistics/attribute_stats.c`

Implements the SQL-callable family for direct manipulation of
per-column statistics (`pg_statistic`): `pg_restore_attribute_stats`
and `pg_clear_attribute_stats`. Introduced for the pg_dump
`--statistics-only` and pg_upgrade fast-stats-restore workflow.
Operations validate just enough to keep the catalog internally
consistent — for individual statistic-kind shapes, conversion
failures are reported as `WARNING` and the function returns false
without aborting the larger restore. [verified-by-code]

## API / entry points

- `pg_restore_attribute_stats(PG_FUNCTION_ARGS)` — variadic
  text-keyed (name, value) pairs. Wraps `attribute_statistics_update`
  via `stats_fill_fcinfo_from_arg_pairs`. Returns bool: true if all
  stat kinds applied. [verified-by-code]
- `pg_clear_attribute_stats(PG_FUNCTION_ARGS)` — required args:
  schemaname, relname, attname, inherited. Deletes the matching
  `pg_statistic` row. [verified-by-code]

## Static helpers

- `attribute_statistics_update(fcinfo)` — main mutation routine.
  Looks up relation under `ShareUpdateExclusiveLock` (via
  `RangeVarCallbackForStats`), resolves attname/attnum (caller
  picks one but not both), derives the attribute's type / collation
  / eq operator via `statatt_get_type` (stat_utils.c). For each
  optional stat kind passed, validates and packs into the
  `Datum values[Natts_pg_statistic]` slot array. Conversion errors
  emit `WARNING` and skip that slot. [verified-by-code]
- `upsert_pg_statistic(starel, oldtup, values, nulls, replaces)` —
  `heap_modify_tuple` + `CatalogTupleUpdate` on hit,
  `heap_form_tuple` + `CatalogTupleInsert` on miss.
  `CommandCounterIncrement` after. [verified-by-code]
- `delete_pg_statistic(reloid, attnum, stainherit)` — syscache
  lookup `STATRELATTINH`, `CatalogTupleDelete`. [verified-by-code]

## Notable invariants / details

- Two parallel arginfo arrays: `attarginfo[]` (18 fields for
  restore) and `cleararginfo[]` (4 fields for clear). Indexed via
  the matching enum so position-by-name introspection works.
  [from-comment]
- Recovery guard: both restore and clear ereport ERROR if
  `RecoveryInProgress()` (lines 177-181, 616-620). [verified-by-code]
- Lock: relation taken with `ShareUpdateExclusiveLock` — same as
  ANALYZE — via `RangeVarCallbackForStats` (privilege check: db
  owner of non-shared rel OR MAINTAIN privilege). [from-comment]
- System columns can't be cleared: `attnum < 0` → `ERRCODE_
  FEATURE_NOT_SUPPORTED` (line 629). [verified-by-code]
- "Major errors at ERROR, minor at WARNING" doctrine: missing
  table / missing attribute / privilege failure → ERROR; bad
  histogram array → WARNING + skip kind. [from-comment]
- Per-stat-kind flags (lines 154-163) gate which slots get
  populated: `do_mcv`, `do_histogram`, `do_correlation`,
  `do_mcelem`, `do_dechist`, `do_bounds_histogram`,
  `do_range_length_histogram`. Pair-membership (e.g. MCV needs
  both vals and freqs) enforced via `stats_check_arg_pair` from
  stat_utils.c. [verified-by-code]
- `statatt_get_type` is the single source of truth for the type
  fields used to interpret incoming text-encoded arrays.
- Custom (extension) stat kinds explicitly unsupported (line 116
  comment). [from-comment]

## Potential issues

- Lines 100-101. In `cleararginfo[]`, the names for
  `C_ATTRELSCHEMA_ARG` and `C_ATTRELNAME_ARG` are both `"relation"`,
  yet the equivalent in `attarginfo[]` (line 63-64) correctly uses
  `"schemaname"` and `"relname"`. Only manifests in `errmsg` from
  `stats_check_required_arg` (which uses `arginfo[argnum].argname`).
  Confusing user-facing message: "argument \"relation\" must not be
  null" twice in a row. [ISSUE-correctness: arg-name typo (likely)]
- Lines 177-181 and 616-620. Same `RecoveryInProgress()` check
  duplicated; a shared helper would be cleaner. [ISSUE-style: copy
  -paste (nit)]
- `attribute_statistics_update` returns bool, but is also called
  from inside `pg_restore_attribute_stats` whose final
  `PG_RETURN_BOOL(result)` ANDs together two `result` values. If
  `stats_fill_fcinfo_from_arg_pairs` returns false (bad pair), we
  still call `attribute_statistics_update` with whatever was
  populated, then return false. Risk: partial application reported
  as success-but-bool-false is hard to tell apart from per-kind
  warnings. Probably acceptable. [unverified]

## Synthesized by
<!-- backlinks:auto -->
