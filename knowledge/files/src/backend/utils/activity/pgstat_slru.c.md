# `src/backend/utils/activity/pgstat_slru.c`

- **Last verified commit:** `4abf411e2328`
- **Lines:** ~241
- **Source:** `source/src/backend/utils/activity/pgstat_slru.c`

Backs `pg_stat_slru`. Fixed-amount per known SLRU pool (CommitTs,
MultiXactMember, MultiXactOffset, Notify, Serial, Subtrans, Xact,
"other"). Counters: `blks_zeroed`, `blks_hit`, `blks_read`,
`blks_written`, `blks_exists`, `flushes`, `truncates`, `stats_reset`.

Updated inline by `access/transam/slru.c` via
`pgstat_count_slru_page_*` / `pgstat_count_slru_flush` /
`pgstat_count_slru_truncate`. Pending state in `PendingSLRUStats[]`
(one per pool slot) is flushed by `pgstat_slru_flush_cb` (fixed
`flush_static_cb`). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
