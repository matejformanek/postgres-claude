# `src/backend/utils/activity/pgstat_checkpointer.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~120
- **Source:** `source/src/backend/utils/activity/pgstat_checkpointer.c`

Backs `pg_stat_checkpointer`: fixed-amount, written to file. Split from
`pg_stat_bgwriter` in PG17. Counters: `num_timed`, `num_requested`,
`restartpoints_*`, `write_time`, `sync_time`, `buffers_written`,
`stats_reset`. Updated by the checkpointer process via
`pgstat_report_checkpointer()`. Pending updates live in
`PendingCheckpointerStats` and are accumulated per-checkpoint, flushed
to shmem at end. [from-comment]
