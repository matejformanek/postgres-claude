# `src/backend/utils/activity/pgstat.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 2155
- **Source:** `source/src/backend/utils/activity/pgstat.c`

## Purpose

Cumulative-statistics infrastructure. Tracks per-kind counters
(database/relation/function/replslot/subscription/backend variable; archiver/
bgwriter/checkpointer/io/slru/wal fixed) entirely in shared memory, with
per-backend pending buffers flushed to shmem after each transaction.
Replaces the old separate `pgstats` collector process — since PG15 there is
no statistics-collector process, just shmem and a checkpointer-driven file
write at shutdown. [from-comment] (`pgstat.c:3-94`)

## Mental model

- **Per-kind dispatch via `PgStat_KindInfo`** table (`pgstat.c:283-...`):
  each kind declares whether it's fixed_amount, whether it persists to file,
  its shmem layout, pending entry size, and a vtable of callbacks
  (`flush_pending_cb`, `flush_static_cb`, `init_shmem_cb`, `reset_*_cb`,
  `snapshot_cb`, `serialize_*`, ...). Custom extension stats kinds register
  into `pgstat_kind_custom_infos` at startup. [from-comment] (`pgstat.c:53-62`,
  `:270-282`)
- **Variable-numbered stats live in a `dshash`** keyed by `PgStat_HashKey`
  `{kind, dboid, objid}`. Hash entry header is `PgStatShared_HashEntry`;
  the actual counters live in a separately-allocated body so the dshash
  can be schema-uniform across kinds. Each shared entry has a dedicated
  LWLock. [from-comment] (`pgstat.c:20-43`)
- **Two-level cache.** Backend-local `pgStatEntryRefHash` (a simplehash) maps
  HashKey → `PgStat_EntryRef`, which caches the dshash entry pointer + a
  process-local pointer to the stats body, so steady-state operations
  bypass dshash entirely. [from-comment] (`pgstat.c:32-39`)
- **Pending-then-flush.** Most updates first accumulate in process-local
  pending counters (`PgStat_EntryRef->pending`), linked into `pgStatPending`
  dlist. `pgstat_report_stat()` (called by tcop after each xact, by SPI,
  by logical apply, …) flushes them to shmem; this practically eliminates
  contention on individual counters. [from-comment] (`pgstat.c:45-51`)
- **Fixed-numbered stats** (archiver, bgwriter, checkpointer, slru, io, wal)
  sit in plain (non-dynamic) shmem at known offsets recorded in `KindInfo`.
  (`pgstat.c:18`)
- **Consistency modes.** `stats_fetch_consistency` GUC = `NONE | CACHE |
  SNAPSHOT`. CACHE (default) memoizes individual fetched entries for the
  xact in `pgStatLocal.snapshot`. SNAPSHOT builds a one-shot whole-stats
  snapshot at first fetch. NONE re-reads shmem every time. [from-comment]
  (`pgstat.c:64-68`)

## Spine

- `pgstat_initialize` (`pgstat.c:670`) — backend startup; calls kind-specific
  init hooks; registers `pgstat_shutdown_hook` as before-shmem-exit.
- `pgstat_shutdown_hook` (`pgstat.c:632`) — final forced
  `pgstat_report_stat(true)` plus per-kind shutdown.
- `pgstat_report_stat` (`pgstat.c:723`) — the workhorse. Throttled by
  `PGSTAT_MIN_INTERVAL = 1s`; force-flushes if pending exceeds
  `PGSTAT_MAX_INTERVAL = 60s`; returns `PGSTAT_IDLE_INTERVAL = 10s` so
  callers can arm a timeout. Walks `pgStatPending` list with `nowait`
  unless `force`; partial flush is allowed and reported back.
  (`pgstat.c:703-836`)
- `pgstat_flush_pending_entries` — iterates `pgStatPending`, calls each
  kind's `flush_pending_cb` under the per-entry LWLock; on `nowait`
  conflict, leaves entry on list for next round.
- `pgstat_fetch_entry` (`pgstat.c:963`) — variable-numbered fetch honoring
  consistency mode; populates `pgStatLocal.snapshot` for CACHE/SNAPSHOT.
- `pgstat_snapshot_fixed` (`pgstat.c:1105`) — fixed-stat fetch path
  (caches into `pgStatLocal.snapshot.<kind>`).
- `pgstat_prep_pending_entry` (`pgstat.c:1310`) — get-or-create the local
  pending struct for a kind/db/obj, fetches the shared entry ref into the
  local cache as a side effect.
- `pgstat_restore_stats` / `pgstat_discard_stats` (`pgstat.c:526`, `:538`) —
  startup paths. Restore reads `pg_stat/<file>` written at last clean
  shutdown; if any kind tag mismatches (e.g. custom kind not loaded), or
  after a crash, the whole stats file is discarded.
- `pgstat_register_kind` (`pgstat.c:1508`) — extension entry point;
  validates the assigned custom ID against the wiki-tracked registry
  (range check), no overlap with built-ins.
- `pgstat_get_kind_info` (`pgstat.c:1480`) — kind → `PgStat_KindInfo*`,
  spanning built-in and custom arrays.

## Per-kind callback table contract

Each `PgStat_KindInfo`:
- `fixed_amount`: true → fixed shmem; false → dshash.
- `write_to_file`: persistence across clean shutdown.
- `accessed_across_databases`: a connection in db A may see B's entries
  (used for database/replslot/subscription/backend).
- `shared_size`, `shared_data_off`, `shared_data_len`, `pending_size`:
  layout used by the generic infrastructure to allocate / memcpy bodies.
- `flush_pending_cb(EntryRef *, nowait)`: merge pending into shared under
  LWLock; return true if "needs retry" (couldn't lock in nowait mode).
- `flush_static_cb(nowait)`: for fixed-numbered kinds with their own pending
  state (currently `backend`).
- `reset_*_cb`, `snapshot_cb`, `to/from_serialized_name`: optional vtable
  slots used in `pgstat_reset_*`, snapshot construction, file write/read.

## File-format anchors

- Entry types in `pg_stat/<file>`: `'F'` fixed, `'N'` name-keyed (used for
  replslot via `to_serialized_name`), `'S'` HashKey-keyed, `'E'` end marker.
  (`pgstat.c:144-148`)

## Notable invariants

- `pgstat_report_stat` requires "not in transaction" — uses
  `GetCurrentTransactionStopTimestamp()` as a wall-clock proxy.
  (`pgstat.c:719-720`, `:732`)
- Variable-numbered objects must be addressable by `{kind,dboid,objid}` at
  runtime; only file serialization may use a wider name. (`pgstat.c:27-30`)
- Crash-on-startup → all stats discarded (no fsync of the running shmem
  state; only at clean shutdown). (`pgstat.c:12-16`)
- After `pgstat_before_server_shutdown`, `pgStatLocal.shmem->is_shutdown =
  true`; subsequent reports must be no-ops. (`pgstat.c:749-754`)

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 14

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [data-structures/pgstat-counter.md](../../../../../data-structures/pgstat-counter.md)
- [idioms/pgstat-flush-timing.md](../../../../../idioms/pgstat-flush-timing.md)

