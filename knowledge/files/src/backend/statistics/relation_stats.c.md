# `src/backend/statistics/relation_stats.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~243
- **Source:** `source/src/backend/statistics/relation_stats.c`

SQL-callable family for direct manipulation of *relation-level*
statistics: the four `pg_class` columns `relpages`, `reltuples`,
`relallvisible`, `relallfrozen`. Used by pg_dump --statistics-only
and pg_upgrade to seed the new cluster without re-running ANALYZE.
[verified-by-code]

## API / entry points

- `pg_restore_relation_stats(PG_FUNCTION_ARGS)` — variadic
  (name, value) pairs. Builds a positional `FunctionCallInfo` of
  `NUM_RELATION_STATS_ARGS=6`, then dispatches to
  `relation_statistics_update`. Returns bool. [verified-by-code]
- `pg_clear_relation_stats(PG_FUNCTION_ARGS)` — takes
  (schemaname, relname). Hand-builds a 6-arg positional
  `FunctionCallInfo` with the four numeric args set to
  empty-table defaults (`relpages=0`, `reltuples=-1.0`,
  `relallvisible=0`, `relallfrozen=0`) and dispatches to the same
  update function. Returns void. [verified-by-code]

## Static helpers

- `relation_statistics_update(fcinfo)` — the worker.
  `ShareUpdateExclusiveLock` on the relation via
  `RangeVarCallbackForStats`; `RowExclusiveLock` on `pg_class`
  (matches `vac_update_relstats` discipline); update only the
  columns whose argument is non-NULL AND whose current value
  differs from the target. Returns false (via `result`) only if
  `reltuples < -1.0`. [verified-by-code]

## Notable invariants / details

- Lock discipline parallels `vac_update_relstats` per the
  in-source comment (line 137-138). Release after the catalog
  update; CCI before return.
- Skip-if-same optimization (lines 148-174): each of the four
  columns is only added to the replace set if `update_X && X !=
  pgcform->X`. No-op if nothing changed.
- `reltuples < -1.0` is the only validation: `-1.0` is the
  sentinel for "never analyzed", values below are invalid;
  WARNING + skip. [verified-by-code]
- Recovery guard (line 94-98): ERROR if `RecoveryInProgress`.
- `NUM_RELATION_STATS_ARGS = 6` (RELSCHEMA, RELNAME, RELPAGES,
  RELTUPLES, RELALLVISIBLE, RELALLFROZEN); `pg_clear` hard-codes
  the same count and the empty-table sentinel values.
- `relarginfo[]` is shared between restore and clear (and
  `stats_fill_fcinfo_from_arg_pairs` uses it for name→position
  lookup). [verified-by-code]

## Potential issues

- Lines 201-223. `pg_clear_relation_stats` re-derives the number
  6 and the sentinel values inline; if `NUM_RELATION_STATS_ARGS`
  ever grows, this caller breaks silently (out-of-bounds args[]
  access OR fewer-than-expected positional args). Should use
  `NUM_RELATION_STATS_ARGS` symbolically. [ISSUE-undocumented
  -invariant: magic-number 6 (nit)]
- Sentinel `Float4GetDatum(-1.0)` for `reltuples` in clear means
  "never analyzed"; not commented inline.
- `Datum values[4]` / `bool nulls[4]` / `int replaces[4]` are
  sized to the four updatable columns. If a fifth ever gets
  added, all three arrays must grow together. [unverified]

## Synthesized by
<!-- backlinks:auto -->
