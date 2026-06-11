# `src/backend/statistics/stat_utils.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~755
- **Source:** `source/src/backend/statistics/stat_utils.c`

Shared utilities for the `pg_restore_*_stats` / `pg_clear_*_stats`
family. Three buckets: (1) argument validation helpers used by
attribute/extended/relation entry points, (2)
`RangeVarCallbackForStats` privilege + relkind callback shared by
all three, (3) `statatt_*` helpers that distill an attribute's type
information out of `pg_attribute`+`pg_type` and onto a per-slot
`pg_statistic` row. [verified-by-code]

## API / entry points (header-exported)

- `stats_check_required_arg(fcinfo, arginfo, argnum)` — ERROR if
  arg is null. Uses `arginfo[argnum].argname` for the message.
  [verified-by-code]
- `stats_check_arg_array(fcinfo, arginfo, argnum)` — WARNING +
  return false if non-null but not a 1-D non-null array.
- `stats_check_arg_pair(fcinfo, arginfo, argnum1, argnum2)` —
  WARNING + return false if only one of the two args is null.
  Used for stakind pairs (MCV vals/freqs, etc.). [from-comment]
- `RangeVarCallbackForStats(relation, relId, oldRelId, arg)` —
  privilege + relkind check used by all three statistics-update
  entry points via `RangeVarGetRelidExtended`. arg is the caller's
  `Oid *locked_table` so the callback can manage cross-call
  bookkeeping when an index resolves to its parent. [verified-by-code]
- `stats_fill_fcinfo_from_arg_pairs(pairs_fcinfo, positional_fcinfo,
  arginfo)` — translate variadic (name, value, name, value, ...)
  pairs into a positional `FunctionCallInfo`. Recognized special
  arg `"version"` is accepted but ignored. Returns false if any
  pair was malformed (with the bad arg left NULL in positional).
  [from-comment]
- `statatt_get_type(reloid, attnum, *atttypid, *atttypmod,
  *atttyptype, *atttypcoll, *eq_opr, *lt_opr)` — derive
  pg_statistic's per-attribute type metadata. Handles index
  expressions (uses exprType/exprTypmod/exprCollation), domain →
  base type for operator resolution, tsvector → text, multirange
  → contained range. [from-comment]
- `statatt_get_elem_type(atttypid, atttyptype, *elemtypid,
  *elem_eq_opr)` — derive element type for array-shaped stat
  kinds (mcelem, dechist). [verified-by-code]
- `statatt_build_stavalues(staname, array_in, d, typid, typmod,
  *ok)` — convert a text-encoded array Datum into an `anyarray`
  via `array_in`, with soft-error capture; sets `*ok=false` on
  conversion failure (WARNING raised, returns Datum 0). Also
  rejects multi-D or NULL-containing arrays. [from-comment]
- `statatt_set_slot(values, nulls, replaces, stakind, staop,
  stacoll, stanumbers, stanumbers_isnull, stavalues,
  stavalues_isnull)` — write into the first free or matching
  `stakind*` slot of the `pg_statistic` tuple. [from-comment]
- `statatt_init_empty_tuple(reloid, attnum, inherited, values,
  nulls, replaces)` — initialize a Datum/null/replaces triple
  with `pg_statistic` defaults: starelid/staattnum/stainherit
  populated; stanullfrac/stawidth/stadistinct zeroed; stakind*,
  staop*, stacoll* slots zeroed but non-null.
  [verified-by-code]

## Static helpers

- `get_arg_by_name(argname, arginfo)` — linear lookup by name in
  arginfo; WARNING + return -1 if missing. [verified-by-code]
- `stats_check_arg_type(argname, argtype, expectedtype)` —
  WARNING + return false on mismatch.
- `statatt_get_index_expr(rel, attnum)` — walk the
  `rd_indexprs` list for the nth index expression attribute
  (attnum that maps to 0 in `rd_index->indkey.values`).
  [verified-by-code]

## Notable invariants / details

- Defaults (lines 39-44):
  - `DEFAULT_STATATT_NULL_FRAC = 0.0`
  - `DEFAULT_STATATT_AVG_WIDTH = 0` (also the "unknown" sentinel)
  - `DEFAULT_STATATT_N_DISTINCT = 0.0` (also "unknown")
- `RangeVarCallbackForStats` callback design (lines 143-253):
  - Lock is `ShareUpdateExclusiveLock` (matches ANALYZE).
  - If the resolved OID changes between retries, releases the
    stale lock first.
  - Index case: resolve to parent rel via `IndexGetRelation`.
  - Two concurrent-DDL races handled with explicit ERRORs:
    "index was concurrently dropped" and "index was concurrently
    created". [from-comment]
  - relkind whitelist: `RELATION`, `MATVIEW`, `FOREIGN_TABLE`,
    `PARTITIONED_TABLE`. Anything else → `ERRCODE_WRONG_OBJECT_TYPE`.
  - Shared relations rejected (`relisshared`).
  - Privilege: db-owner-of-non-shared OR `ACL_MAINTAIN` on
    relation. [from-comment]
  - **Lock heap before index** to avoid deadlock (line 249-253).
    Important invariant. [from-comment]
- Variadic name/value parser: rejects odd argument count, rejects
  non-TEXT names, skips NULL value (so `pg_restore_…_stats('mcv',
  NULL, ...)` is a no-op for that kind). Reserves `"version"` for
  future use.
- `statatt_get_type` handles the tsvector special case: collation
  forced to `DEFAULT_COLLATION_OID`, mirroring
  `compute_tsvector_stats`. [from-comment]
- `statatt_get_type` mimics `examine_attribute` but does NOT skip
  attrs with `attstattarget=0`. [from-comment]
- `statatt_build_stavalues` uses the soft-error idiom: build an
  `ErrorSaveContext`, pass via `LOCAL_FCINFO`, on
  `error_occurred` re-throw as WARNING. [verified-by-code]

## Potential issues

- Lines 280-296. `get_arg_by_name` raises WARNING but also returns
  -1; callers must check. Mixing soft-error WARN + sentinel
  return is mildly fragile vs an outright ERROR. Tradeoff: keep
  one bad-name from aborting an entire bulk restore.
  [ISSUE-style: WARN-plus-sentinel return (nit)]
- "version" handling is a single-arg case but with no formal
  registry; future versions may need real handling. Comment notes
  "For now, 'version' is accepted but ignored". [unverified]
- Hidden cross-file coupling: callers of
  `stats_fill_fcinfo_from_arg_pairs` must pre-init their
  positional fcinfo with a size matching `arginfo`; nothing
  prevents passing a smaller size and writing past
  `args[NUM_*_ARGS]`. The caller is responsible. [unverified]
- `RangeVarCallbackForStats` carries no opaque table-OID context
  past the index-parent-rel resolution; this is correct but
  subtle, depends on the caller passing `Oid *locked_table` for
  state retention across retries.

## Synthesized by
<!-- backlinks:auto -->
