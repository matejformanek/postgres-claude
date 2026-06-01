# `src/backend/utils/activity/pgstat_wal.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~150
- **Source:** `source/src/backend/utils/activity/pgstat_wal.c`

Backs `pg_stat_wal`. Fixed-amount. Counters: `wal_records`, `wal_fpi`,
`wal_bytes`, `wal_buffers_full`, `wal_write`, `wal_sync`, `wal_write_time`,
`wal_sync_time`, `stats_reset`.

Most counters are fed from `instrument.h` `WalUsage` accumulators that
every backend maintains in `pgWalUsage`; `pgstat_report_wal()` flushes
the delta via `pgstat_wal_flush_cb` (a `flush_static_cb` since this is
fixed). The `wal_write_time` / `wal_sync_time` are accumulated in
`xlog.c` around `pg_pwrite_zeros`/`fsync` calls when
`track_wal_io_timing` is on. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
