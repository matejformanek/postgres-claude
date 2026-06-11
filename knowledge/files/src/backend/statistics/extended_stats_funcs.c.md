# `src/backend/statistics/extended_stats_funcs.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1836
- **Source:** `source/src/backend/statistics/extended_stats_funcs.c`

SQL-callable family for direct manipulation of *extended* statistics
(`pg_statistic_ext_data`): `pg_restore_extended_stats` and
`pg_clear_extended_stats`. Mirrors `attribute_stats.c` in spirit but
deals with the multi-column world: ndistinct, dependencies, MCV lists,
expressions stats. Heavy use of Jsonb for the MCV/expressions
import because those are stored as Jsonb in `pg_statistic_ext_data`
(line ~140 ff). [verified-by-code]

## API / entry points

- `pg_restore_extended_stats(PG_FUNCTION_ARGS)` — variadic
  (name, value) pairs. Calls `stats_fill_fcinfo_from_arg_pairs` to
  rewrite into a positional fcinfo, then `extended_statistics_update`.
  Returns bool. [verified-by-code]
- `pg_clear_extended_stats(PG_FUNCTION_ARGS)` — required args:
  relation schema, relation name, statistics schema, statistics
  name, inherited. Deletes the matching `pg_statistic_ext_data` row
  via `delete_pg_statistic_ext_data`. [verified-by-code]

## Static helpers

- `extended_statistics_update(fcinfo)` — looks up the rel
  (`ShareUpdateExclusiveLock`), then looks up `pg_statistic_ext` by
  (statsschema, statsname), reads `stxkind` to learn which kinds the
  stats object is allowed to have. For each provided value
  (ndistinct, deps, MCV, expressions), validate the input shape and
  pack into the `pg_statistic_ext_data` row. [verified-by-code]
- `expand_stxkind(tup, enabled)` — decode the `stxkind` text array
  from a `pg_statistic_ext` tuple into a `StakindFlags` bitmask.
  [verified-by-code]
- `upsert_pg_statistic_ext_data(...)` / `delete_pg_statistic_ext_data
  (stxoid, inherited)` — catalog-row writers (mirrors of attribute
  helpers but for the *_ext_data catalog). [verified-by-code]
- `check_mcvlist_array(arr, argindex, ...)` — validate that an
  array meets MCV-list shape constraints (1-D, no NULLs). Warning
  on failure. [verified-by-code]
- `import_mcv(mcv_arr, ...)` — parse a Jsonb-encoded MCV list,
  resolve types, build the on-disk `MCVList` struct.
- `import_expressions(pgsd, numexprs, ...)` — parse and
  re-typecheck expression stats. [from-comment]
- `import_pg_statistic(pgsd, cont, ...)` — for "expressions"
  extended stats, reach inside the JSON document and build per-expr
  pg_statistic-shaped rows.
- `jbv_string_get_cstr` / `jbv_to_infunc_datum` /
  `key_in_expr_argnames` / `check_all_expr_argnames_valid` /
  `array_in_safe` — small Jsonb / input-function plumbing used by
  the import paths.

## Notable invariants / details

- Recovery guard at top of update path. Lock via
  `RangeVarCallbackForStats` (same MAINTAIN/dbo rules as attribute_stats).
- The stats kinds allowed on a `pg_statistic_ext` object are
  determined at CREATE STATISTICS time and recorded in `stxkind`;
  passing values for other kinds at restore is silently ignored
  (per `expand_stxkind` mask). [verified-by-code]
- `argnum` enum (lines 45-58): `RELSCHEMA`, `RELNAME`,
  `STATSCHEMA`, `STATNAME`, `INHERITED`, `NDISTINCT`,
  `DEPENDENCIES`, `MOST_COMMON_VALS`, `MOST_COMMON_FREQS`,
  `MOST_COMMON_BASE_FREQS`, `EXPRESSIONS`. [verified-by-code]
- MCV pairs are checked together (vals + freqs + base_freqs each
  required if MCV kind enabled). [from-comment]
- Errors are split: not-found ERROR, type mismatch / bad array
  shape WARNING + skip-this-kind. Same doctrine as attribute_stats.
- `delete_pg_statistic_ext_data` is the only mutation in the clear
  path; the `pg_statistic_ext` row itself stays (it's the
  definition; only the data is wiped). [from-comment]
- Jsonb is the wire format for MCV and expressions stats so
  pg_dump can emit `pg_restore_extended_stats(...)` calls with
  Jsonb literals. Inside the catalog, MCV is the binary `MCVList`
  representation. [from-comment]
- `array_in_safe` (line ~966) wraps `array_in` with a soft-error
  context so a bad array element raises WARNING rather than ERROR.
  This is the soft-error idiom (escontext). [verified-by-code]

## Potential issues

- Lines 142-143. `expand_stxkind` is declared static and uses
  `StakindFlags` from `extended_stats_internal.h`; no cross-ref
  in the comment makes it hard to find the flag definitions.
  [ISSUE-doc-drift: missing struct cross-ref (nit)]
- Variadic-pair → positional translation in
  `stats_fill_fcinfo_from_arg_pairs` (stat_utils.c) and the
  subsequent positional call duplicate the validation steps. If a
  name is unknown, the warning comes from `get_arg_by_name`; if a
  type mismatches, from `stats_check_arg_type`. Both still let the
  outer call proceed (with that arg missing). Worth a top-level
  comment summarizing what "false return" means.
- `import_mcv` / `import_expressions` are large (~150-300 lines
  each) and do not appear in idioms documentation; future patches
  that touch MCV serialization will need to keep these in sync
  with `statistics/mcv.c`. [unverified]

## Synthesized by
<!-- backlinks:auto -->
