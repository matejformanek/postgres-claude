# `src/include/statistics/stat_utils.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~61
- **Source:** `source/src/include/statistics/stat_utils.h`

Shared helpers for the SQL-callable statistics-import / inspection
functions (`pg_restore_attribute_stats`,
`pg_clear_attribute_stats`, etc.). These functions accept a
variadic-pair `(name, value)` API; the helpers here validate the
arg pairs and translate them into a positional FunctionCallInfo
suitable for the inner implementation. [verified-by-code] [inferred]

## API / declarations

- `StatsArgInfo { const char *argname; Oid argtype }` — single
  entry in a per-function arg-spec table. [verified-by-code]
- `stats_check_required_arg(fcinfo, arginfo, argnum)` — ereport on
  missing required arg.
- `stats_check_arg_array(fcinfo, arginfo, argnum)` → bool.
- `stats_check_arg_pair(fcinfo, arginfo, argnum1, argnum2)` → bool
  — verifies two args appear together or not at all (e.g. stavalues
  + stanumbers).
- `RangeVarCallbackForStats(relation, relId, oldRelId, *arg)` —
  RangeVarGetRelidExtended callback that enforces statistic-write
  privilege.
- `stats_fill_fcinfo_from_arg_pairs(pairs_fcinfo, positional_fcinfo,
  arginfo)` → bool — name/value pair → positional translator.
- Attribute-stat helpers used by the inner implementation:
  - `statatt_get_type(reloid, attnum, *atttypid, *atttypmod,
    *atttyptype, *atttypcoll, *eq_opr, *lt_opr)`,
  - `statatt_init_empty_tuple(reloid, attnum, inherited, *values,
    *nulls, *replaces)`,
  - `statatt_set_slot(*values, *nulls, *replaces, stakind, staop,
    stacoll, stanumbers, stanumbers_isnull, stavalues,
    stavalues_isnull)`,
  - `statatt_build_stavalues(staname, array_in, d, typid, typmod,
    *ok)` → Datum,
  - `statatt_get_elem_type(atttypid, atttyptype, *elemtypid,
    *elem_eq_opr)`.

## Notable invariants / details

- The `arginfo` table is per-function; entries are positional, so
  `argnum` arguments to the helpers index into BOTH the fcinfo
  positional array AND the StatsArgInfo table. Misalignment
  silently mislabels errors. [inferred]
- `RangeVarCallbackForStats` is the privilege gate — using it for
  `pg_restore_*_stats` ensures the same relkind/ownership rules as
  ANALYZE. [inferred]
- "Extended statistics and selectivity estimation functions." — the
  file header comment is misleading; this file is about **per-column
  attribute** statistics (`pg_statistic`), not extended ones.
  [ISSUE-doc-drift: comment claims extended stats but file is for
  attribute stats (likely)]

## Potential issues

- File-header comment mismatch (see above). [ISSUE-doc-drift:
  stat_utils.h comment vs content (nit)]
- `statatt_set_slot` takes 11 arguments — likely candidate for a
  small struct refactor. Not a correctness issue.
  [ISSUE-style: long arg list on statatt_set_slot (nit)]
- `stats_fill_fcinfo_from_arg_pairs` returns bool — semantics of
  false (skip vs error) is not in the header.
  [ISSUE-doc-drift: false return contract (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-statistics`](../../../../issues/include-statistics.md)
<!-- issues:auto:end -->
