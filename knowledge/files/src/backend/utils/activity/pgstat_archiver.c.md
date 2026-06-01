# `src/backend/utils/activity/pgstat_archiver.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~100
- **Source:** `source/src/backend/utils/activity/pgstat_archiver.c`

Backs `pg_stat_archiver`: fixed-amount stats, written to disk at shutdown.

Counters incremented by the archiver process (`postmaster/pgarch.c`):
- `pgstat_report_archiver(xlog, failed)` — `archived_count`,
  `last_archived_wal`, `last_archived_time` on success;
  `failed_count`, `last_failed_wal`, `last_failed_time` otherwise.

Kind callbacks: `init_shmem_cb`, `reset_all_cb`, `snapshot_cb`. The
shared entry sits at `PgStat_ShmemControl.archiver`. [from-comment]
