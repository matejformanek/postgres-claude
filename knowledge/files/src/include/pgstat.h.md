# `src/include/pgstat.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~881
- **Source:** `source/src/include/pgstat.h`

The cumulative-statistics subsystem master header. Defines every
counter struct visible across the pgstat machinery (table, function,
database, WAL, IO, lock, archiver, bgwriter, checkpointer, replslot,
SLRU, subscription, backend), the counter / IO-op / IO-context
enumerations, and the public reporting API. Backend-status and
backend-progress live in separate sibling headers
(`utils/backend_status.h`, `utils/backend_progress.h`) that this file
re-includes for backward compatibility (`pgstat.h:19-20`).
[verified-by-code]

## API / declarations

### File-level constants (`pgstat.h:14-40`)

- `PGSTAT_STAT_PERMANENT_DIRECTORY = "pg_stat"`,
  `PGSTAT_STAT_PERMANENT_FILENAME = "pg_stat/pgstat.stat"`,
  `PGSTAT_STAT_PERMANENT_TMPFILE = "pg_stat/pgstat.tmp"`.
- `PG_STAT_TMP_DIR = "pg_stat_tmp"` — runtime temp dir.

### Enums (`pgstat.h:42-65`)

- `TrackFunctionsLevel { TRACK_FUNC_OFF, TRACK_FUNC_PL, TRACK_FUNC_ALL }`
  — order is significant.
- `PgStat_FetchConsistency { NONE, CACHE, SNAPSHOT }` — controls
  `pgstat_fetch_consistency` GUC behavior.
- `SessionEndType { DISCONNECT_NOT_YET, DISCONNECT_NORMAL,
  DISCONNECT_CLIENT_EOF, DISCONNECT_FATAL, DISCONNECT_KILLED }`.

### Counter type

- `typedef int64 PgStat_Counter` (`pgstat.h:71`) — the universal
  counter unit.

### Backend-local accumulation structs (`pgstat.h:74-210`)

- `PgStat_FunctionCounts { numcalls, total_time, self_time }`
  (instr_time format until flush).
- `PgStat_FunctionCallUsage { fs, save_f_total_time, save_total,
  start }` — per-call timer state.
- `PgStat_BackendSubEntry { apply_error_count, sync_seq_error_count,
  sync_table_error_count, conflict_count[CONFLICT_NUM_TYPES] }`.
- `PgStat_TableCounts { numscans, tuples_returned, tuples_fetched,
  tuples_inserted/updated/deleted/hot_updated/newpage_updated,
  truncdropped, delta_live_tuples (can be negative),
  delta_dead_tuples (can be negative), changed_tuples,
  blocks_fetched, blocks_hit }` — comment notes
  `pg_memory_is_all_zeros` is used to detect "nothing changed", so
  this struct should be PURE counters with no derived fields.
- `PgStat_TableStatus { id, shared, trans, counts, relation }` —
  per-table backend state.
- `PgStat_TableXactStatus { tuples_inserted/updated/deleted,
  truncdropped, inserted/updated/deleted_pre_truncdrop, nest_level,
  upper, parent, next }` — a per-subxact stack for transactional
  fields.

### On-disk / shmem structs (`pgstat.h:213-538`)

- `PGSTAT_FILE_FORMAT_ID = 0x01A5BCBC` (`pgstat.h:221`) — bump when
  any of these structs change. The single coarse-grained
  on-disk-format gate.
- `PgStat_ArchiverStats { archived_count, last_archived_wal[MAX_XFN_CHARS+1],
  last_archived_timestamp, failed_count, last_failed_wal,
  last_failed_timestamp, stat_reset_timestamp }`.
- `PgStat_BgWriterStats { buf_written_clean, maxwritten_clean,
  buf_alloc, stat_reset_timestamp }`.
- `PgStat_CheckpointerStats { num_timed, num_requested, num_performed,
  restartpoints_timed/requested/performed, write_time, sync_time,
  buffers_written, slru_written, stat_reset_timestamp }`.
- `IOObject { IOOBJECT_RELATION, IOOBJECT_TEMP_RELATION, IOOBJECT_WAL }`
  — `IOOBJECT_NUM_TYPES = IOOBJECT_WAL + 1`.
- `IOContext { IOCONTEXT_BULKREAD, IOCONTEXT_BULKWRITE, IOCONTEXT_INIT,
  IOCONTEXT_NORMAL, IOCONTEXT_VACUUM }` —
  `IOCONTEXT_NUM_TYPES = IOCONTEXT_VACUUM + 1`.
- `IOOp { IOOP_EVICT, IOOP_FSYNC, IOOP_HIT, IOOP_REUSE, IOOP_WRITEBACK,
  IOOP_EXTEND, IOOP_READ, IOOP_WRITE }` — split into "not tracked in
  bytes" (first 5) and "tracked in bytes" (last 3). The
  `pgstat_is_ioop_tracked_in_bytes(io_op)` macro relies on this
  ordering (`pgstat.h:325-327`).
- `PgStat_BktypeIO { bytes[O][C][P], counts[O][C][P], times[O][C][P] }`
  — 3-D matrix per backend type.
- `PgStat_PendingIO` — same dims with instr_time for pending times.
- `PgStat_IO { stat_reset_timestamp, stats[BACKEND_NUM_TYPES] }` —
  one BktypeIO per BackendType.
- `PgStat_LockEntry { waits, wait_time, fastpath_exceeded }`.
- `PgStat_PendingLock { stats[LOCKTAG_LAST_TYPE+1] }`,
  `PgStat_Lock { stat_reset_timestamp, stats[LOCKTAG_LAST_TYPE+1] }`.
- `PgStat_StatDBEntry` — the big per-database row visible via
  `pg_stat_database`. 27 counters + 3 timestamps. Includes
  `parallel_workers_to_launch` / `parallel_workers_launched`.
- `PgStat_StatFuncEntry`, `PgStat_StatReplSlotEntry` (with
  spill/stream/slotsync counters), `PgStat_SLRUStats`,
  `PgStat_StatSubEntry`, `PgStat_StatTabEntry` (the big per-table
  row, 23 counters + 9 timestamps).
- `PgStat_WalCounters { wal_records, wal_fpi, wal_bytes, wal_fpi_bytes,
  wal_buffers_full }`.
- `PgStat_WalStats { wal_counters, stat_reset_timestamp }`.
- `PgStat_Backend { stat_reset_timestamp, io_stats, wal_counters }` /
  `PgStat_BackendPending { pending_io }`.

### Function families (`pgstat.h:541-832`)

Organized per source file (pgstat_archiver.c, pgstat_backend.c,
pgstat_bgwriter.c, pgstat_checkpointer.c, pgstat_io.c, pgstat_lock.c,
pgstat_database.c, pgstat_function.c, pgstat_relation.c,
pgstat_replslot.c, pgstat_slru.c, pgstat_subscription.c,
pgstat_xact.c, pgstat_wal.c). Highlights:

- Lifecycle: `pgstat_restore_stats`, `pgstat_discard_stats`,
  `pgstat_before_server_shutdown`, `pgstat_initialize`.
- Reporting: `pgstat_report_stat(force)` returns long (ms until next
  flush deadline), `pgstat_force_next_flush`.
- Reset: `pgstat_reset_counters`, `pgstat_reset(kind, dboid, objid)`,
  `pgstat_reset_of_kind(kind)`.
- Snapshots: `pgstat_clear_snapshot`,
  `pgstat_get_stat_snapshot_timestamp(&have_snapshot)`.
- Helpers: `pgstat_get_kind_from_str(kind_str)`, `pgstat_have_entry(...)`.
- IO timing macros (`pgstat.h:658-665`):
  `pgstat_count_buffer_read_time(n)` += pgStatBlockReadTime;
  `pgstat_count_buffer_write_time(n)`; `pgstat_count_conn_active_time(n)`;
  `pgstat_count_conn_txn_idle_time(n)`.
- Per-relation counter macros (`pgstat.h:711-751`) — inlined to skip
  the function-call when stats not enabled.
- `pgstat_should_count_relation(rel)` — the gateway predicate.

### Globals (`pgstat.h:835-879`)

- GUCs: `pgstat_track_counts` (bool), `pgstat_track_functions` (int),
  `pgstat_fetch_consistency` (int).
- Pending counters: `PendingBgWriterStats`, `PendingCheckpointerStats`,
  `pgStatBlockReadTime`, `pgStatBlockWriteTime`, `pgStatActiveTime`,
  `pgStatTransactionIdleTime`, `pgStatSessionEndCause`.

## Notable invariants / details

- `PGSTAT_FILE_FORMAT_ID` MUST be bumped when any persisted struct
  changes (`pgstat.h:216-219`). Forgetting this corrupts the post-crash
  recovered stats file. [from-comment]
  [ISSUE-undocumented-invariant: PGSTAT_FILE_FORMAT_ID bump is
  comment-only; no static-assert on struct sizes (likely)]
- The `pg_memory_is_all_zeros` "nothing changed" pattern requires
  PgStat_TableCounts and PgStat_BgWriterStats to contain ONLY raw
  counter fields — no derived fields, no timestamps. Comment is
  explicit (`pgstat.h:126-129, 240-242`). [from-comment]
  [ISSUE-undocumented-invariant: pg_memory_is_all_zeros pattern
  constrains struct layout; new field additions silently break it
  if non-zero by default (likely)]
- `IOOp` ordering is load-bearing — `pgstat_is_ioop_tracked_in_bytes`
  relies on `IOOP_EXTEND` being the first bytes-tracked entry
  (`pgstat.h:303-307`). New IOOp values MUST be inserted in the
  appropriate sub-group, not at the end. [from-comment]
- `IOOBJECT_NUM_TYPES`, `IOCONTEXT_NUM_TYPES`, `IOOP_NUM_TYPES`,
  `BACKEND_NUM_TYPES` (from miscadmin.h) form a 4-dimensional
  matrix size. Even modest growth blows up shmem footprint —
  see `PgStat_BktypeIO` = 3 arrays of [3][5][8] = 360 uint64 per
  backend type × `BACKEND_NUM_TYPES` (~20) = ~58 KB per stats
  snapshot. [verified-by-code]
- `instr_time` (from `portability/instr_time.h`) is platform-specific;
  PgStat_FunctionCounts uses it to avoid converting until flush.
  PgStat_Counter is int64 microseconds. [from-comment]
- `PgStat_TableXactStatus` is a linked stack of per-subxact deltas;
  on subxact commit they merge to parent, on abort they drop.
  Operations on this stack are NOT protected by locks (they live
  in CurrentMemoryContext).
- `delta_live_tuples` and `delta_dead_tuples` can be **negative**
  (`pgstat.h:139-140`). Code that consumes them must not assume
  monotonically growing.
- The macros `pgstat_count_heap_scan(rel)` etc. (`pgstat.h:717-751`)
  use `unlikely` via `pgstat_should_count_relation` so the
  stats-disabled path is single-load + branch-predicted-skip. New
  rel-counter macros should follow the same shape.
- `pgstat_track_counts` defaults to true; `pgstat_track_functions`
  defaults to TRACK_FUNC_NONE. The GUC type for the latter is `int`
  (`pgstat.h:840`) — same as the enum, but exposed without enum
  type-safety. [ISSUE-style: pgstat_track_functions GUC declared as
  `int` not enum (nit)]
- Custom stats kinds (extension hookpoint) are NOT declared here —
  they live in `utils/pgstat_internal.h` / `utils/pgstat_kind.h`.
  Only the kind helpers (`pgstat_get_kind_from_str`) leak out.

## Potential issues

- `pgstat.h:14-19` — the file pulls in 6 cross-subsystem headers
  (timestamp, instr_time, pgarch, conflict, locktag, backend_progress,
  backend_status, pgstat_kind). Touching pgstat.h invalidates every
  build artifact downstream. [ISSUE-style: pgstat.h fan-in too broad
  (nit)]
- `pgstat.h:221` — `PGSTAT_FILE_FORMAT_ID = 0x01A5BCBC` is the only
  on-disk-format gate. A struct change without the bump silently
  loads corrupt stats. [ISSUE-correctness: PGSTAT_FILE_FORMAT_ID
  discipline is comment-only (confirmed echo of A15 ISSUE pattern)]
- `pgstat.h:368-403` — `PgStat_StatDBEntry` is huge and growing;
  adding new fields requires PGSTAT_FILE_FORMAT_ID bump + careful
  ordering (writers and readers must agree). [ISSUE-api-shape:
  PgStat_StatDBEntry has no version field (nit)]
- `pgstat.h:439-441` — `replslot_skip_count` / `slotsync_last_skip`
  are aggregate counters; a fork that distinguishes skip reasons
  loses information. [ISSUE-doc-drift: slotsync_skip_count is
  single bucket (nit)]
- `pgstat.h:868-870` — `pgStatBlockReadTime` / `pgStatBlockWriteTime`
  are mutable PGDLLIMPORT counters. Extensions can scribble.
  [ISSUE-defense-in-depth: timing counters mutable via PGDLLIMPORT
  (nit)]
- `pgstat.h:835-841` — GUC globals are exported as bare ints; check
  hooks could enforce range but enums would be better.
  [ISSUE-style: pgstat GUCs declared as int (nit)]
- `pgstat.h:711-713` — `pgstat_should_count_relation(rel)` macro has
  the side effect of `pgstat_assoc_relation(rel)` on the
  pgstat-enabled but not-yet-associated branch. Embedding side
  effects in a Bool-named macro is mildly hazardous if used in a
  short-circuit expression. [ISSUE-style: side-effect in
  pgstat_should_count_relation (nit)]
- `pgstat.h:777-782` — `pgstat_acquire_replslot(slot)` /
  `pgstat_drop_replslot` form an acquire/release pair. Failure to
  drop leaks the stat entry until process exit. [ISSUE-leak:
  pgstat_acquire/drop_replslot pairing not enforced (maybe)]
- `pgstat.h:822-823` — `pgstat_get_transactional_drops(isCommit,
  &items)` returns int but xl_xact_stats_item layout is opaque to
  callers via forward struct decl. New caller types must consult
  the .c file. [ISSUE-doc-drift: xl_xact_stats_item layout opaque
  at header (nit)]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new BufferAccessStrategy ring](../../../scenarios/add-new-buffer-strategy.md)
- [Scenario — Add a new `pg_stat_*` view](../../../scenarios/add-new-pg-stat-view.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->
