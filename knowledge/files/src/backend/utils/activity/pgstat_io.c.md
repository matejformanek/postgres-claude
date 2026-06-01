# `src/backend/utils/activity/pgstat_io.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~540
- **Source:** `source/src/backend/utils/activity/pgstat_io.c`

Backs `pg_stat_io` (PG16+): a 3-D matrix of counters keyed by
`(BackendType, IOObject, IOContext, IOOp)`:
- `BackendType` ∈ {client backend, autovacuum worker, bgwriter,
  checkpointer, standalone, walsender, walreceiver, archiver,
  startup, ...}.
- `IOObject` ∈ {relation, temp_relation}.
- `IOContext` ∈ {normal, vacuum, bulkread, bulkwrite}.
- `IOOp` ∈ {read, write, extend, fsync, hit, evict, reuse, writeback}.

For each cell: count + accumulated time (when `track_io_timing` on).

- `pgstat_count_io_op(*counters, op, cnt, bytes)` — fast inline path.
- `pgstat_count_io_op_time(io_object, io_context, io_op, start_time,
  cnt, bytes)` — variant with timing.
- `pgstat_prepare_io_time` / `pgstat_get_io_time_now` — start/stop
  timer wrapper.
- Validation table `pgstat_tracks_io_op[bktype][io_object][io_context][io_op]`
  decides which cells are valid; cells that never make sense (e.g.
  bgwriter writing temp_relation in bulkread context) ERROR if updated.

Flushed via `pgstat_io_flush_cb` (fixed-amount). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
