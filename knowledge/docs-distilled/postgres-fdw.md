---
source_url: https://www.postgresql.org/docs/current/postgres-fdw.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — postgres_fdw (the FDW reference implementation)

`contrib/postgres_fdw` is *the* worked example of the `FdwRoutine` callback set
— the one to read when implementing pushdown, remote cost estimation, async
execution, or join/aggregate shipping in a custom FDW. This note captures the
non-obvious mechanics, not the usage surface. `[from-docs]`

## Pushdown — what crosses the wire

- **WHERE clauses** are shipped only when they use **built-in operators/functions
  marked `IMMUTABLE`**; anything else is evaluated locally after fetch. `[from-docs]`
- **Joins** between two foreign tables on the **same** foreign server are pushed
  whole — *unless* the two table references use different user mappings (then
  each is fetched separately). Aggregates, `ORDER BY`, and `LIMIT` push under
  similar safety rules. `[from-docs]`
- Full `UPDATE`/`DELETE` push only when there are no unpushable WHERE clauses, no
  local joins, no row triggers, no stored generated columns, no view CHECK
  OPTIONs. The actual remote SQL is visible via `EXPLAIN VERBOSE`. `[from-docs]`
- `extensions` option (server-level): names extensions installed *identically*
  on both ends, so their IMMUTABLE functions/operators become shippable. The
  user owns the "behaves identically" guarantee. `[from-docs]`

## Cost estimation

- `use_remote_estimate` — default **false**: cost from local `ANALYZE` stats plus
  `fdw_startup_cost` (default **100**) and `fdw_tuple_cost` (default **0.2**).
  Set **true** to run remote `EXPLAIN` for real estimates (table-level overrides
  server-level). `[from-docs]`
- `analyze_sampling` (default **auto**): remote-side sampling for `ANALYZE` —
  `off`/`random`/`system`/`bernoulli`/`auto`. `[from-docs]`

## Connection & transaction management

- One cached connection per **(user mapping, foreign server)** pair, reused
  across the session. `keep_connections` default **on** (set off to drop at end
  of each xact). Inspect/close via `postgres_fdw_get_connections([check_conn])`,
  `postgres_fdw_disconnect(server)`, `postgres_fdw_disconnect_all()`. `[from-docs]`
- Remote isolation: local `SERIALIZABLE` → remote `SERIALIZABLE`; **all other
  local levels → remote `REPEATABLE READ`**, so multiple remote scans in one
  local xact see a single consistent snapshot. `[from-docs]`
- **No two-phase commit**: postgres_fdw does not PREPARE remote transactions.
  `parallel_commit`/`parallel_abort` (both default **false**) commit/abort
  multiple servers' remote xacts concurrently at local commit/abort. `[from-docs]`

## Throughput knobs & async

- `batch_size` (INSERT, default **1**) — multi-row insert; auto-capped so
  `columns × batch_size ≤ 65535` (libpq parameter limit); `COPY` into a foreign
  table caps at 1000 rows/batch. `fetch_size` (default **100**) — cursor fetch
  size. `[from-docs]`
- `async_capable` (default **false**): lets an `Append` over multiple foreign
  servers scan them concurrently (one connection per server still). `[from-docs]`
- Forced remote session settings (non-overridable): `search_path='pg_catalog'`,
  `TimeZone='UTC'`, `DateStyle='ISO'`, `IntervalStyle='postgres'`,
  `extra_float_digits=3` — so schema-qualify names in remote views/triggers.
  `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/fdwhandler.md]]` — the `FdwRoutine` callback
  contract postgres_fdw implements.
- `[[knowledge/docs-distilled/fdw-planning.md]]` / `[[knowledge/docs-distilled/fdw-callbacks.md]]`
  — scan/modify planning hooks where pushdown decisions live.
- `[[knowledge/docs-distilled/fdw-row-locking.md]]` — remote row-locking the
  UPDATE/DELETE pushdown rules interact with.
- `[[knowledge/docs-distilled/explicit-joins.md]]` — local join planning that
  join-pushdown shortcuts.
- Skills: `executor-and-planner` (Append/async, pushdown costing), `fmgr-and-spi`.
