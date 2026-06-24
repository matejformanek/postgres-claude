---
source_url: https://www.postgresql.org/docs/current/progress-reporting.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — Progress Reporting (the pg_stat_progress_* views)

The progress-reporting chapter is where a backend hacker learns the **phase
state machines** of the long-running maintenance commands and the
`PgBackendStatus` progress-param mechanism that feeds them. Six commands report:
`ANALYZE`, `CLUSTER`, `CREATE INDEX`, `VACUUM`, `COPY`, `BASE_BACKUP`. (Chapter
number drifts by version — §27.4 / §28.4 — the slug `progress-reporting` is the
stable handle.) `[from-docs]`

## CREATE INDEX — the phase sequence encodes the CONCURRENTLY protocol

`pg_stat_progress_create_index` phases, in order — the concurrent-only phases
*are* the CIC/RIC multi-pass protocol made observable `[from-docs]`:

1. `initializing`
2. `waiting for writers before build` *(concurrent only)*
3. `building index`
4. `waiting for writers before validation` *(concurrent only)*
5. `index validation: scanning index` *(concurrent only)*
6. `index validation: sorting tuples` *(concurrent only)*
7. `index validation: scanning table` *(concurrent only)*
8. `waiting for old snapshots` *(concurrent only)*
9. `waiting for readers before marking dead` *(REINDEX CONCURRENTLY only)*
10. `waiting for readers before dropping` *(REINDEX CONCURRENTLY only)*

Columns: `pid, datid, relid, index_relid, command, phase, blocks_total,
blocks_done, tuples_total, tuples_done, lockers_total, lockers_done,
current_locker_pid, partitions_total, partitions_done`. The `lockers_*` +
`current_locker_pid` trio is exactly the "wait for everyone holding a
conflicting snapshot/lock" barrier the CONCURRENTLY phases sit on. `[from-docs]`

## VACUUM — phases + the dead-tuple memory accounting

`pg_stat_progress_vacuum` phases `[from-docs]`:

1. `initializing`
2. `scanning heap`
3. `vacuuming indexes`
4. `vacuuming heap`
5. `cleaning up indexes`
6. `truncating heap`
7. `performing final cleanup`

Columns: `pid, datid, relid, phase, heap_blks_total, heap_blks_scanned,
heap_blks_vacuumed, index_vacuum_count, max_dead_tuple_bytes, dead_tuple_bytes,
num_dead_item_ids, indexes_total, indexes_processed, delay_time`. Non-obvious:
`max_dead_tuple_bytes` / `dead_tuple_bytes` are the **PG17+ TID-store memory
accounting** (replacing the old fixed `maintenance_work_mem` dead-tuple array) —
when `dead_tuple_bytes` approaches `max_dead_tuple_bytes`, VACUUM does an index
pass and `index_vacuum_count` ticks up. `delay_time` only populates when
`track_cost_delay_timing` is on. `[from-docs]` `[inferred for the TID-store
framing]`

## The backend mechanism (names from docs; signatures live in source)

- A command calls `pgstat_progress_start_command()` to begin reporting, then
  `pgstat_progress_update_param()` (and the multi-param variant) to push
  counters into the **`st_progress_param` array of `PgBackendStatus`**; the
  views read that shared array. Each command has a `progress.h`-style header
  defining its phase + param index constants. `[from-docs]` (The docs name the
  mechanism but not the C signatures — treat the exact prototypes as
  `[unverified]` until checked against `source/src/backend/utils/activity/`.)

## The other three (briefer)

- `pg_stat_progress_analyze`: `initializing` → `acquiring sample rows` →
  `acquiring inherited sample rows` → `computing statistics` → `computing
  extended statistics` → `finalizing analyze`. `[from-docs]`
- `pg_stat_progress_cluster`: shares the `VACUUM FULL` rewrite phases.
  `[from-docs]`
- `pg_stat_progress_copy`: `bytes_processed, tuples_processed, tuples_excluded,
  tuples_skipped`. `[from-docs]`
- `pg_stat_progress_basebackup`: `initializing` → `waiting for checkpoint to
  finish` → `estimating backup size` → `streaming database files` → `waiting for
  wal archiving to finish` → `transferring wal files`. `[from-docs]`

## Links into corpus

- Cumulative stats machinery (sibling subsystem): [docs-distilled/monitoring-stats.md](./monitoring-stats.md)
- VACUUM heap mechanics behind the phases: [docs-distilled/storage-hot.md](./storage-hot.md), [docs-distilled/storage-vm.md](./storage-vm.md)
- CREATE INDEX CONCURRENTLY locking the phases observe: [docs-distilled/index-locking.md](./index-locking.md)
- Relevant skills: `debugging` (watch a stuck VACUUM/CIC via these views),
  `access-method-apis` (ambuild drives the create-index phases).
