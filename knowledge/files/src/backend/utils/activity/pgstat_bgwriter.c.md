# `src/backend/utils/activity/pgstat_bgwriter.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~100
- **Source:** `source/src/backend/utils/activity/pgstat_bgwriter.c`

Backs `pg_stat_bgwriter` (now slimmer since checkpointer split out):
fixed-amount stats. The bgwriter process flushes locally-accumulated
`PendingBgWriterStats` into the shared `PgStatShared_BgWriter` slot via
`pgstat_report_bgwriter()`. Counters tracked: `buffers_clean`,
`maxwritten_clean`, `buffers_alloc` (since PG17 some moved to
`pg_stat_io`). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
