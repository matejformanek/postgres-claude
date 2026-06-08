---
source_url: https://www.postgresql.org/docs/current/monitoring-stats.html
fetched_at: 2026-06-08T20:53:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — The Cumulative Statistics System

Not the per-view column lists (those are reference) — the *internals* of how
PG accumulates and exposes activity counters. The non-obvious parts are the
PG15 shared-memory transition, the in-transaction snapshot semantics, and the
clean-vs-crash persistence rule.

## Collection architecture

- **Shared-memory collection since PG15.** Each process accumulates stats
  locally and flushes them into shared memory at intervals. This **replaced the
  dedicated stats-collector process + UDP-to-temp-file model** of PG≤14 (which
  is why `pg_stat_tmp` and `stats_temp_directory` are gone in PG15+). [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/utils/activity/pgstat.c.md]]]
- **Collection GUCs** (superuser-only `SET`, so a user can't hide their own
  activity): `track_activities` (current command), `track_counts`
  (table/index access counts — required for autovacuum to work),
  `track_functions` (UDF call counts/time), `track_io_timing` (block
  read/write/extend/fsync timing), `track_wal_io_timing`, `track_cost_delay_timing`.
  [from-docs]

## In-transaction snapshot semantics

- Cumulative views show **static data for the duration of a transaction** by
  default — the snapshot is cached on first access and held to transaction end,
  so totals **lag actual activity** and an in-flight query doesn't move them.
  Only `track_activities` data (`pg_stat_activity`) is always live. [from-docs]
- **`stats_fetch_consistency`** tunes this: `snapshot` (default-ish — consistent
  snapshot per access, more memory), `cache` (cache each object on first read),
  `none` (no caching — cheapest when each counter is read once, but values can
  shift between two reads in the same xact). [from-docs]
- **`pg_stat_clear_snapshot()`** discards the transaction's cached snapshot so
  the next access rebuilds it. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/utils/activity/pgstat.c.md]]]
- **`pg_stat_xact_*`** views (`pg_stat_xact_user_tables`,
  `pg_stat_xact_user_functions`, …) show the **un-flushed, transaction-local**
  counters that *do* update continuously — distinct from the shared snapshot.
  [from-docs] [verified-by-code, via [[knowledge/files/src/backend/utils/activity/pgstat_xact.c.md]]]

## Reporting lag

- A process flushes its pending stats to shared memory no more often than
  **`PGSTAT_MIN_INTERVAL`** (≈1 s); this is the source of the visible lag
  between activity and counters. [from-docs]

## Persistence & reset

- **Clean shutdown writes a permanent copy under the `pg_stat/` subdirectory**,
  reloaded on the next clean start. [from-docs]
- **Any unclean exit resets all counters to zero** — crash, immediate
  shutdown, recovery from a base backup, or point-in-time recovery. Don't rely
  on cumulative counters surviving a crash. [from-docs]
- **`pg_stat_reset*()`** family clears counters (cluster-wide, per-table,
  per-function, per-shared-object, SLRU, etc.). [from-docs]

## pg_stat_io (block-level I/O accounting)

- Rows keyed by **backend type × object (relation / temp relation / WAL) ×
  context (normal, init, vacuum, bulkread, bulkwrite)**. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/utils/activity/pgstat_io.c.md]]]
- Timing columns (`read_time`, `write_time`, …) are **zero unless
  `track_io_timing`/`track_wal_io_timing` was on for the whole interval** — the
  docs explicitly warn against trusting them after a partial-coverage window.
  `bulkread`/`bulkwrite` cover large operations done **outside shared buffers**.
  [from-docs]
- I/O stats **don't distinguish a real disk fetch from a kernel page-cache
  hit** — combine with OS tools. [from-docs]

## Security / consistency notes

- Ordinary users see only their own session rows; **superusers and
  `pg_read_all_stats`** see all sessions. [from-docs]
- The system **does not synchronize different facets** of a backend's activity
  data (`state` vs `wait_event` can be momentarily inconsistent) — a deliberate
  trade for low reporting overhead. [from-docs]

## Links into corpus
- [[knowledge/files/src/backend/utils/activity/pgstat.c.md]] — the shared-memory stats core + snapshot logic.
- [[knowledge/files/src/backend/utils/activity/pgstat_io.c.md]] — pg_stat_io accounting.
- [[knowledge/files/src/backend/utils/activity/pgstat_relation.c.md]] — table/index access counters (track_counts).
- [[knowledge/files/src/backend/utils/activity/pgstat_xact.c.md]] — transaction-local pending stats + xact callbacks.
- [[knowledge/files/src/backend/utils/activity/backend_status.c.md]] — pg_stat_activity (track_activities).

## Gaps / follow-ups
- The exact PG15 on-disk format id (`PGSTAT_FILE_FORMAT_ID`) and the per-kind
  flush intervals (`PGSTAT_*_INTERVAL` constants) live in `pgstat.c` /
  `pgstat_internal.h`; the docs page names them only functionally. Cross-check
  the per-file doc when quoting constant values.
