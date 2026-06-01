# `src/backend/utils/activity/pgstat_relation.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1000
- **Source:** `source/src/backend/utils/activity/pgstat_relation.c`

The largest per-kind file. Backs `pg_stat_user_tables`,
`pg_stat_user_indexes`, and the analyze/vacuum/auto-* trigger counters.
Variable-numbered on (dboid, relid).

## Pending data layout

Per-rel local state `PgStat_TableStatus`:
- `t_counts` (numbers of seq_scan, idx_scan, tuples returned/fetched/
  inserted/updated/deleted/hot_updated, newpage_updated, blocks read/hit,
  ...). Inserted/updated/deleted counters are **transactional** — kept in
  `PgStat_TableXactStatus` per (sub)xact level and merged into
  `t_counts` only on (sub)commit.
- ANALYZE/VACUUM tracking: counters bumped from `vacuum.c` /
  `analyze.c` via `pgstat_report_vacuum` / `pgstat_report_analyze`.

## Transactional integration

- `AtEOXact_PgStat` / `AtEOSubXact_PgStat` (in pgstat_xact.c) walk the
  per-xact stack: on commit, merge into the table-level pending; on
  abort, undo the in-flight tuple counts but keep block counters
  (already paid for). The autovacuum tuple-change estimate
  (`n_live_tup` / `n_dead_tup`) is updated additively from the
  ins/del/upd deltas so the autovacuum launcher's `relation_needs_vacuum`
  check stays current.
- `pgstat_relation_init` allocates a per-rel local entry inside
  `RelationData` (`rd_pgstat_info`); rels never seen until first DML.

## Notable

- `pgstat_count_heap_insert/update/delete/truncate_drop` — DML hooks.
- `pgstat_report_vacuum(tableoid, shared, livetuples, deadtuples)` and
  `pgstat_report_analyze(...)` — set timestamps and tuple estimates;
  also reset `n_dead_tup` / `n_mod_since_analyze` baseline.
- Two-phase commit RMID `TWOPHASE_RM_PGSTAT_ID` so prepared xacts
  carry their tuple-count deltas across COMMIT PREPARED.

`pgstat_relation_flush_cb` merges shared counters under the per-entry
LWLock; `pgstat_relation_delete_pending_cb` handles relation drop while
pending exists. [from-comment]
