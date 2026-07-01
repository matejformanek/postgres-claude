---
source_url: https://www.postgresql.org/docs/current/runtime-config-statistics.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Run-time Statistics configuration

The stats/monitoring GUC reference. Serves the standing `gap:pgstat` cluster
(heaviest recurring harvester gap). Companion:
`knowledge/docs-distilled/monitoring-stats.md` for the cumulative-stats views.

## Cumulative Query and Index Statistics

- **`track_counts` (default on) is REQUIRED for autovacuum** — without it the
  daemon has no dead-tuple counts to threshold against. Also gates the
  `pg_stat_*`/`pg_statio_*` views. [from-docs]
- **`stats_fetch_consistency` (default `cache`) changes read semantics inside a
  transaction** [from-docs]:
  - `none` — re-fetch from shared memory each access (cheapest; best for a
    monitoring tool doing single reads).
  - `cache` — first access caches *that object's* stats until end of xact, so a
    self-join over `pg_stat_*` sees consistent values.
  - `snapshot` — first access caches **all** stats in the current DB (highest
    overhead; for interactive poking). Changing the GUC mid-xact discards the
    snapshot; `pg_stat_clear_snapshot()` resets manually.
- **`track_io_timing`, `track_wal_io_timing`, `track_cost_delay_timing` all
  default OFF because they hammer the clock** — potentially significant overhead
  on platforms with slow `gettimeofday`; measure with `pg_test_timing` first.
  They light up `pg_stat_io`, `EXPLAIN (BUFFERS)`, `VACUUM VERBOSE`,
  `pg_stat_statements`, and autovacuum logging respectively. [from-docs]
- **`track_functions` (default `none`)**: `pl` = PL functions only, `all` adds
  SQL+C. **SQL functions simple enough to be inlined are never tracked**,
  regardless of the setting. [from-docs]
- **`track_activity_query_size` (default 1024, restart-only)** reserves that
  many bytes *per session* for `pg_stat_activity.query`; **`track_activities`
  data is visible only to superusers, `pg_read_all_stats`, and the session
  owner.** [from-docs]

## Statistics Monitoring / query-id

- **`compute_query_id` (default `auto`)**: `auto` lets an extension
  (`pg_stat_statements`) turn it on; `on`/`off` force it; **`regress` behaves
  like `auto` but hides the id from `EXPLAIN`** so regression output stays
  stable. An external module computing its own id should set `off` (double-compute
  is an error). Feeds `pg_stat_activity`, `EXPLAIN`, and `log_line_prefix`.
  [from-docs]
- **`log_statement_stats` is mutually exclusive with the per-module
  `log_parser_stats` / `log_planner_stats` / `log_executor_stats`** — you get
  the whole-statement getrusage-style dump OR the per-phase ones, not both.
  Crude profiling to the server log. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/monitoring-stats.md]] — the views these GUCs feed.
- [[knowledge/docs-distilled/runtime-config-vacuum.md]] — why `track_counts`
  gates autovacuum.
- [[knowledge/docs-distilled/dynamic-trace.md]] — DTrace probes, the other
  instrumentation surface.
- [[knowledge/idioms/guc-variables.md]] — GUC context/flags model.
- Skill: `gucs-config` — adding a tracking GUC; `debugging` — `pg_test_timing`.

## Confidence note

All claims `[from-docs]` (Run-time Statistics chapter, fetched 2026-07-01).
The cumulative-stats shared-memory mechanism (pgstat_* backend C) is
doc-referenced only here; the C signatures live in
`src/backend/utils/activity/pgstat*.c` and are `[unverified]` this run.
