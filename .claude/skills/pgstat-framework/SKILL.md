---
name: pgstat-framework
description: The PostgreSQL cumulative-statistics framework — `src/backend/utils/activity/pgstat*.c` (post-PG-15 shared-memory design). Loads when the user asks about `pg_stat_*` views, cumulative stats, stat kinds (variable vs fixed), pending-vs-shared flush timing, adding a new stat counter, extending stats with a custom kind, wait events, backend status, IO/SLRU/WAL/replslot/subscription stats, or debugging "I ran a query but pg_stat shows 0" surprises. Also use for pgstat_progress_* (in-progress command reporting via a separate shmem slot per backend), backend_status.c (the process-level status the ps output + pg_stat_activity read from), and wait_event.c (the taxonomy behind `wait_event_type` / `wait_event`). Skip when the ask is about extended-column statistics (`pg_statistic` / `pg_statistic_ext` — different subsystem: `src/backend/statistics/`, use `extended-statistics-statext` idiom), or about `pg_stat_statements` contrib module (different, though it hooks in).
when_to_load: Adding a new stat / new stat kind; debugging "why is pg_stat_X zero" (pending-flush-timing questions); extending wait events; touching backend_status / pgstat_progress; understanding the PG-15 shmem-dshash rewrite that replaced the stats-collector process.
companion_skills:
  - locking
  - memory-contexts
  - bgworker-and-extensions
---

# pgstat-framework — cumulative statistics + progress reporting + wait events

The `src/backend/utils/activity/` tree implements three related-but-distinct observability surfaces:

1. **Cumulative statistics** — the `pg_stat_*` views. Per-kind counters accumulate in shared memory since PG15 (no more stats-collector process).
2. **Backend progress reporting** — `pgstat_progress_*` — per-backend transient state for commands like VACUUM, CREATE INDEX, COPY, that a monitoring session can read via `pg_stat_progress_*` views.
3. **Wait events + backend status** — what a backend is doing RIGHT NOW (`pg_stat_activity.wait_event_type` / `wait_event` / `state`). This is separate from cumulative counters.

Getting the right file among the ~20 in the tree matters — patches often land in the wrong one because the file names are similar.

## The file map

### Cumulative-stats core

| File | Lines | Role |
|---|---:|---|
| `pgstat.c` | 2,155 | Framework core. Registration, flush cadence (`PGSTAT_MIN_INTERVAL` / `MAX_INTERVAL`), pending→shared machinery, kind table. |
| `pgstat_shmem.c` | ~1,191 | Shared-memory storage layer. DSA + dshash keyed by `(kind, dboid, objid)`; per-backend refcount + generation protocol for safe drop-when-last-referrer-releases. |
| `pgstat_xact.c` | ~330 | Transaction-boundary flush hooks — `AtEOXact_PgStat` etc. |

### Per-kind stat modules (one file each)

Each per-kind file owns its counters, its shmem serialization, and its "flush pending → shared" routine. Adding a new stat kind = new file here + kind registration in `pgstat.c` + view in `system_views.sql`.

| File | Kind | Notable |
|---|---|---|
| `pgstat_database.c` | database | `pg_stat_database` |
| `pgstat_relation.c` | relation (and index) | `pg_stat_user_tables` / `pg_statio_*` — the biggest per-kind file at 30 KB, hot path |
| `pgstat_function.c` | function | `pg_stat_user_functions` — off by default (`track_functions` GUC) |
| `pgstat_replslot.c` | replication slot | `pg_stat_replication_slots` |
| `pgstat_subscription.c` | subscription | `pg_stat_subscription_stats` (logical rep only) |
| `pgstat_backend.c` | backend (variable) | Per-backend IO + wait-event stats — variable because backends come and go |
| `pgstat_archiver.c` | archiver (fixed) | `pg_stat_archiver` |
| `pgstat_bgwriter.c` | bgwriter (fixed) | `pg_stat_bgwriter` |
| `pgstat_checkpointer.c` | checkpointer (fixed) | `pg_stat_checkpointer` |
| `pgstat_io.c` | I/O (fixed) | `pg_stat_io` — per-object-type × per-context × per-operation matrix |
| `pgstat_slru.c` | SLRU (fixed) | `pg_stat_slru` — one row per SLRU pool |
| `pgstat_wal.c` | WAL (fixed) | `pg_stat_wal` |
| `pgstat_lock.c` | lock (mostly infrastructure) | Helper for the fixed-kind flush lock discipline. |

### Backend progress reporting

| File | Role |
|---|---|
| `backend_progress.c` | Per-backend progress-slot API — `pgstat_progress_start_command`, `pgstat_progress_update_param`, `pgstat_progress_end_command`. Used by VACUUM, CREATE INDEX, COPY, CLUSTER, ANALYZE, base backup. |
| `backend_status.c` | The `PgBackendStatus` struct + `pg_stat_activity` machinery — application name, client address, query text, wait event slot, state. This is what `ps` output and `pg_stat_activity` read. |

### Wait events

| File | Role |
|---|---|
| `wait_event.c` | The runtime API — `pgstat_report_wait_start` / `pgstat_report_wait_end` (both inline for hot-path efficiency, defined in `wait_event.h`). |
| `wait_event_funcs.c` | SQL-callable helpers backing `pg_wait_events` view. |
| `wait_event_names.txt` | The taxonomy source. Perl codegen (`generate-wait_event_types.pl`) produces `pgstat_wait_event.c` + `wait_event_types.h` from this — adding a wait event is editing this txt file + running the codegen. |

## The PG-15 rewrite (why this is complicated)

Before PG15: separate `pgstat` background process, backends sent counter updates via a UDP socket, stats materialized to `pg_stat_tmp/` files.

After PG15 (commit `5891c7a8ed8`): **no more stats-collector process.** Counters live in shared memory (DSA + dshash) directly. Backends buffer pending counter increments locally (no shmem contention on the hot path), then flush periodically or at transaction end.

Consequences you'll trip over:

1. **Pending vs shared** — a query that touched a table increments a *pending* counter in the backend. `pg_stat_user_tables` reads the *shared* counter. If pending hasn't flushed yet, the view shows 0. This is the #1 support question the harvester keeps flagging.
2. **Flush cadence** — `PGSTAT_MIN_INTERVAL = 1000ms`, `PGSTAT_MAX_INTERVAL = 60000ms`. Flushes happen at transaction commit boundaries too. Between `MIN` and `MAX`, `pgstat_report_stat()` will try to flush if the previous flush was more than MIN ago; MAX is the hard "flush now regardless" upper bound.
3. **Generation counter + refcount** — dropped entries (dropped table's `pg_stat_user_tables` row) can't be freed until the last backend holding a reference releases. `pgstat_shmem.c` implements a generation protocol so a backend can detect that its ref-to-slot is stale.
4. **Checkpointer writes stats file at shutdown** — on clean shutdown, checkpointer writes `pg_stat/pgstat.stat` so the counters survive restart. Crash → file is discarded on next startup.
5. **Fixed vs variable kinds** — fixed kinds (archiver / bgwriter / IO / etc.) have a single global slot; variable kinds (database / relation / etc.) have one slot per object. The distinction changes shmem layout and flush semantics.

## Common patch shapes

### Add a new counter to an existing stat kind

- Edit the counter struct in `src/include/pgstat.h` (e.g. `PgStat_StatTabEntry`).
- Bump `PGSTAT_FILE_FORMAT_ID` in `pgstat_internal.h` (the on-disk file format changed).
- Update the view definition in `src/backend/catalog/system_views.sql` (bump `CATALOG_VERSION_NO` — see `catalog-conventions`).
- Add the SQL-callable function in the corresponding `pgstat_<kind>.c` (via `pg_proc.dat` if new).
- Wire the increment site (usually in the hot code path that would count the event).
- Regress test in `src/test/regress/sql/stats.sql`.

### Add a new stat kind (rare)

Full worked example: see `pgstat.c` docblock at line ~110 for the "adding a new kind" checklist.

- New `pgstat_<kind>.c` file + entries in `pgstat_internal.h` + `pgstat.h`.
- New `PgStat_KindInfo` row in the `pgstat_kind_builtin_infos` table (`pgstat.c`).
- New view + supporting functions.
- Consider whether it's fixed or variable — fixed is cheaper but less flexible.
- Note: as of PG 18, extensions can register **custom** kinds via `pgstat_register_kind` — see the pg-stat-kind-info work upstream (07-01 batch).

### Add a progress-reporting phase

- Register a new command type in `src/include/commands/progress.h`.
- Call `pgstat_progress_start_command(cmdtype, relid)` at the start; `pgstat_progress_update_param(paramnum, value)` for each phase change; `pgstat_progress_end_command()` at the end.
- Add the view in `system_views.sql`.
- Existing example: `pg_stat_progress_vacuum` — grep for `PROGRESS_VACUUM_*` in `commands/vacuumlazy.c` for a canonical pattern.

### Add a wait event

- Edit `wait_event_names.txt` — add a row with (category, name, description).
- Run `generate-wait_event_types.pl` to regenerate `pgstat_wait_event.c` + `wait_event_types.h`.
- Use `pgstat_report_wait_start(WAIT_EVENT_<CATEGORY>_<NAME>)` at the wait site + `pgstat_report_wait_end()` after.

## Pitfalls

- **`pgstat.c` vs `pgstat_shmem.c`** — cadence + registration logic vs storage layer. Adding a new stat kind touches both; understanding the split saves review pushback.
- **The "pending flush" surprise** — `SELECT COUNT(*) FROM t; SELECT * FROM pg_stat_user_tables WHERE relname='t';` may show `seq_scan = 0` because pending hasn't flushed. Wait 1s+ (past `PGSTAT_MIN_INTERVAL`), or commit the transaction, then re-check.
- **Refcount + generation** — never grab a raw pointer to a shared stat entry; go through `pgstat_get_entry_ref` so the refcount is honored. Otherwise you may read freed memory when an entry is dropped by another backend.
- **`ExecutorStart` hooks don't get post-flush** — extensions that hook the executor and try to read `pg_stat_*` from inside their hook see PRE-flush values. This trips up query-analysis extensions.
- **Backend-kind stats are per-process** — `pgstat_backend.c` counters die with the backend. Long-term aggregation lives in the DB-level counters. Don't build monitoring that assumes backend-kind is durable.
- **Wait event names are compile-time** — you can't add a wait event dynamically. Extensions get a small pool of `WAIT_EVENT_EXTENSION` slots via `WaitEventExtensionNew` (in `wait_event.c`).
- **`backend_status.c` writes are visible IMMEDIATELY** — unlike cumulative counters, `PgBackendStatus` updates aren't buffered. `pg_stat_activity` shows the current query text as soon as `pgstat_report_activity` is called. This is why `pg_stat_activity` has different consistency semantics than `pg_stat_user_tables`.

## Related corpus

- **Idioms**: `pgstat-flush-timing` (the pending→shared cadence).
- **Data structures**: `pgstat-counter` (the `PgStat_Counter` typedef + counter-family struct pattern).
- **Scenarios**: `add-new-pg-stat-view`.
- **Past planning**: `planning/pgstat_progress_leak/` (calibration-run memory-leak fix that touched `backend_progress.c` — see `notes.md` + `comparison.md`).
- **File docs**: `knowledge/files/src/backend/utils/activity/*.md` — 20 docs, one per source file in the tree.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/utils/activity/pgstat.c
python3 scripts/corpus-chain.py --idiom pgstat-flush-timing
```

Both surface the tight neighborhood — the 20 files + the flush-cadence idiom + the `add-new-pg-stat-view` scenario + the past `pgstat_progress_leak` planning artifact.

## Boundary

**Use this skill** for `src/backend/utils/activity/` and the `pg_stat_*` view surface.

**Don't use** for:
- **`pg_statistic` / `pg_statistic_ext`** — planner column statistics (histograms, MCVs, correlations). Different subsystem (`src/backend/statistics/`), use `extended-statistics-statext` idiom.
- **`pg_stat_statements` contrib** — the per-query-shape stats module. It hooks into pgstat_framework but lives in `contrib/pg_stat_statements/`.
- **`auto_explain` contrib** — similar; separate contrib module.
- **EXPLAIN / EXPLAIN ANALYZE output** — those numbers come from the executor's instrumentation, not from the cumulative-stats framework.
