# `src/backend/utils/activity/pgstat_database.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~500
- **Source:** `source/src/backend/utils/activity/pgstat_database.c`

Backs `pg_stat_database` + `pg_stat_database_conflicts`. Variable-numbered
(keyed on dboid). `accessed_across_databases=true` so a connection in
db A can see counters for db B.

## Counters

- Connection counters: `numbackends`, `xact_commit`, `xact_rollback`,
  total session_time.
- Block/tuple counters: `blks_read`, `blks_hit`, `tup_returned`,
  `tup_fetched`, `tup_inserted`, `tup_updated`, `tup_deleted`,
  `conflicts`, `temp_files`, `temp_bytes`, `deadlocks`,
  `checksum_failures`, `checksum_last_failure`.
- Conflict counters from `standby.h`: `confl_tablespace`, `confl_lock`,
  `confl_snapshot`, `confl_bufferpin`, `confl_deadlock`,
  `confl_active_logicalslot` — incremented by
  `pgstat_report_recovery_conflict()`.
- Parallel-worker / I/O timing aggregates.

## Notable entry points

- `pgstat_report_recovery_conflict(reason)` — recovery-conflict bumper
  used by `storage/ipc/standby.c`.
- `pgstat_report_deadlock`, `pgstat_report_checksum_failure*`,
  `pgstat_report_connect`, `pgstat_report_disconnect`,
  `pgstat_report_tempfile`, `pgstat_report_query_id`.
- `pgstat_update_dbstats` (called from `pgstat.c:pgstat_report_stat`)
  drains the per-database pending counters into shmem; merges in
  connection-time deltas via `GetCurrentTimestamp()`.

## Flush callback

`pgstat_database_flush_cb` merges `PgStat_StatDBEntry` pending → shared
under the shared entry's LWLock, additively. [from-comment]
