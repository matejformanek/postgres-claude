# `src/backend/utils/activity/pgstat_io.c`

- **Last verified commit:** `dde9a87d4d02` (2026-07-20; prior `4abf411e2328`)
- **Lines:** ~591
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

The validity matrix lives in two helpers: `pgstat_tracks_io_object`
(`pgstat_io.c:395`) and `pgstat_tracks_io_op` (`pgstat_io.c:510`).
Commit `4abf411e2328` ("pg_stat_io: Don't flag extends by autovacuum
launcher", Melanie Plageman) refined `pgstat_tracks_io_object`: a
`B_AUTOVAC_LAUNCHER` in `IOCONTEXT_VACUUM` (`:460`) or either autovac
type in `IOCONTEXT_BULKWRITE` (`:463`) now returns false, so the
launcher no longer surfaces (and no longer ERRORs on) spurious
`extend` rows in those contexts. [verified-by-code]

Commit `32e4508db27d` ("Restrict pg_stat_io entries for data checksum
processes") then taught both helpers about the new
`B_DATACHECKSUMSWORKER_LAUNCHER` / `B_DATACHECKSUMSWORKER_WORKER`
backend types: the launcher's catalog scans may use a bulkread
strategy (`pgstat_tracks_io_object` special-case `:471`), the worker
is allowed its own op set (`:486`), and both appear in
`pgstat_tracks_io_op` (`:541-542`). This is what shifted the two
helper cites (`pgstat_tracks_io_object` `:404`→`:395`,
`pgstat_tracks_io_op` `:479`→`:510`) and grew the file from ~558 to
~591 lines at anchor `dde9a87d4d02`. [verified-by-code]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new BufferAccessStrategy ring](../../../../../scenarios/add-new-buffer-strategy.md)
- [Scenario — Add a new BufferAccessStrategy ring](../../../../../scenarios/add-new-buffer-strategy.md)
- [Scenario — Add a new BufferAccessStrategy ring](../../../../../scenarios/add-new-buffer-strategy.md)
- [Scenario — Add a new BufferAccessStrategy ring](../../../../../scenarios/add-new-buffer-strategy.md)

<!-- scenarios:auto:end -->
