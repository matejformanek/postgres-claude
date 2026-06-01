# `src/backend/utils/activity/pgstat_subscription.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~120
- **Source:** `source/src/backend/utils/activity/pgstat_subscription.c`

Backs `pg_stat_subscription_stats`. Variable-numbered keyed on
subscription oid. Counters track logical-replication apply errors:
`apply_error_count`, `sync_error_count`, `confl_*` (various conflict
reasons added in PG18). Updated by subscription apply workers
(`replication/logical/worker.c`) via
`pgstat_report_subscription_error` and `pgstat_report_subscription_conflict`.

`accessed_across_databases=true`. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
