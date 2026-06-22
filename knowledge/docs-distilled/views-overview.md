---
source_url: https://www.postgresql.org/docs/current/views-overview.html
fetched_at: 2026-06-21T00:00:00Z
anchor_sha: f25a07b2d94c
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §53.1: System Views — Overview

Companion to [catalogs-overview.md](./catalogs-overview.md). The per-view
reference pages are excluded from this corpus, but the overview's *taxonomy* of
what each view category is *for* is a useful map when you need to introspect a
running backend from SQL instead of attaching a debugger.

## What system views are

- System views provide a **friendlier, read-only interface over raw catalogs and
  runtime state**. They live in **`pg_catalog`** and are queried like any other
  view. `[from-docs]`
- The page states flatly: **all the views described here are read-only.** `[from-docs]`
  (Unlike catalogs, which are technically writable tables — see
  catalogs-overview — views can't be the target of DML at all.)

## The four functional categories (the useful map)

1. **Structural / informational** — friendlier projections of catalog data:
   `pg_tables`, `pg_views`, `pg_indexes`, `pg_matviews`, `pg_sequences`
   (schema objects); `pg_roles`, `pg_user`, `pg_group` (roles); `pg_config`
   (compile-time configuration). `[from-docs]`
2. **Live runtime state** — windows onto in-memory backend/cluster state:
   `pg_locks` (held/awaited locks), `pg_cursors` (open cursors),
   `pg_prepared_statements`, `pg_prepared_xacts` (2PC),
   `pg_replication_slots`, `pg_replication_origin_status` (replication). `[from-docs]`
3. **Planner statistics** — the optimizer's view of the data:
   `pg_stats`, `pg_stats_ext`, `pg_stats_ext_exprs`. `[from-docs]`
4. **Configuration files** — parsed views of on-disk config:
   `pg_file_settings`, `pg_hba_file_rules`, `pg_ident_file_mappings`,
   `pg_settings`. `[from-docs]`

## Hacker-relevant runtime-introspection views

- **`pg_backend_memory_contexts`** — the live MemoryContext tree of a backend;
  the SQL-level analogue of dumping contexts in a debugger (pairs with the
  `memory-contexts` skill). `[from-docs]`
- **`pg_shmem_allocations`** / **`pg_shmem_allocations_numa`** — what's carved
  out of the main shared-memory segment; useful when sizing or debugging a new
  `*Shmem*` allocation. `[from-docs]`
- **`pg_aios`** — in-flight asynchronous I/O operations (the PG18 AIO subsystem
  surface). `[from-docs]`
- **`pg_wait_events`** — the catalog of wait-event names; the lookup table behind
  `pg_stat_activity.wait_event` (recurring gap flagged by the user-question
  harvester). `[from-docs]`

## Note on the `pg_stat_*` family

- The runtime *statistics* views (`pg_stat_activity`, `pg_stat_*`) are documented
  under **Monitoring** (§28), not here — this overview covers the structural and
  config views. For the stats collector / cumulative-stats system see
  [docs-distilled/monitoring-stats.md](./monitoring-stats.md). `[inferred]`

## Links into corpus

- Catalog side (the writable tables these views project):
  [docs-distilled/catalogs-overview.md](./catalogs-overview.md)
- Cumulative statistics views (the `pg_stat_*` family):
  [docs-distilled/monitoring-stats.md](./monitoring-stats.md)
- Relevant skills: `memory-contexts` (pg_backend_memory_contexts),
  `locking` (pg_locks), `debugging` (SQL-level runtime introspection).
