# pg_duckpipe — logical-replication CDC that streams Postgres row-tables into a co-located DuckLake, making one database do both T and A

> Headline: the CDC/streaming-ingestion third member of the relytcloud lakehouse
> trio. Where `[[pg_ducklake]]` and `[[pg_lake]]` give Postgres a *columnar
> table format*, pg_duckpipe gives it a *pipe*: a pgrx extension whose
> per-sync-group background worker runs a `START_REPLICATION` logical-decoding
> client (via the `pgwire-replication` crate), decodes pgoutput, and applies the
> changes into DuckLake columnar tables through an **in-process embedded
> DuckDB** — so heap tables stay the transactional source and their DuckLake
> mirrors become the analytical sink (HTAP), inside one server.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `relytcloud/pg_duckpipe` @ branch `main` (62★, Rust), fetched
> 2026-07-02. All `file:line` cites point into that repo, not `source/`.
> Caveat: fetched via `raw.githubusercontent.com` (the GitHub API tree endpoint
> was 403). Files read: `README.md`, `Cargo.toml`, the three member
> `Cargo.toml`s, `duckpipe-pg/src/{lib,worker,planner_hook,api}.rs`,
> `duckpipe-core/src/{lib,slot_consumer,service,duckdb_flush}.rs`. The `daemon`
> crate, `decoder.rs`, `flush_coordinator.rs`, `snapshot_manager.rs`, and the
> `doc/*.md` set were listed/probed but not deep-read; claims resting on them
> are tagged `[from-README]` / `[inferred]`.

## Domain & purpose

pg_duckpipe brings **real-time change data capture (CDC)** to Postgres,
"enabling HTAP by continuously syncing your row tables to DuckLake columnar
tables" (`README.md:15`) `[from-README]`. The whole UX is one call:
`SELECT duckpipe.add_table('public.orders')` snapshots existing rows then
streams new changes to an auto-created `orders_ducklake` target
(`README.md:27,46-53`) `[from-README]`. It is a Rust workspace of three crates
(`Cargo.toml:2`) `[verified-by-code]`: `duckpipe-core` (the engine — logical
replication client + DuckDB writer), `duckpipe-pg` (the **pgrx 0.16** extension
that hosts the engine in a bgworker and exposes the SQL API), and
`duckpipe-daemon` (a standalone `axum` REST service running the same core out of
process). It requires **PG 17/18**, `wal_level = logical`, source tables with a
**PRIMARY KEY**, and `shared_preload_libraries = 'pg_duckdb, pg_duckpipe'`
(`README.md:63-67`) `[from-README]` — i.e. it presupposes `[[pg_ducklake]]`
(which bundles `[[pg_duckdb]]` + libduckdb) is already installed.

Position in the trio: pg_duckpipe does **not** define a table AM or a table
format. It is the *ingestion* layer that fills the DuckLake tables that
pg_ducklake defines. Contrast the format-CDC that pg_ducklake ships internally
(its maintenance worker compacting its own lakehouse) — pg_duckpipe's CDC is the
**other direction**: it reads Postgres's own WAL and pushes heap changes *into*
DuckLake.

## How it hooks into PG

- **`_PG_init`** (pgrx `#[pg_guard] extern "C-unwind"`) does three things:
  `pg_shmem_init!(METRICS_SHM)` to register a shared-memory metrics region;
  defines seven GUCs; and installs a planner hook
  (`duckpipe-pg/src/lib.rs:406-486`) `[verified-by-code]`. It detects preload
  via `pg_sys::process_shared_preload_libraries_in_progress` and, if not
  preloaded, warns that SHM metrics are unavailable and degrades gracefully
  rather than panicking (`lib.rs:96-106,420-433`) `[verified-by-code]`.
- **GUCs** (all `duckpipe.*`): `poll_interval`, `batch_size_per_group`,
  `enabled`, `debug_log` (SIGHUP), plus `data_inlining_row_limit`,
  `query_routing` (an `off/on/auto` enum), and `query_routing_log` (USERSET)
  (`lib.rs:379-393,436-485`) `[verified-by-code]`.
- **The CDC capture path is logical decoding, not triggers or a WAL reader.**
  `duckpipe.add_table` / `create_sync_group` create a slot with
  `pg_create_logical_replication_slot($1, 'pgoutput')` and a `CREATE
  PUBLICATION` (`duckpipe-pg/src/api.rs:330,337,358,372`) `[verified-by-code]`.
  The consumer opens a **`START_REPLICATION` streaming connection** through the
  `pgwire-replication` crate's `ReplicationClient`
  (`duckpipe-core/src/slot_consumer.rs:1-45`) `[verified-by-code]` and decodes
  the pgoutput binary stream (Begin/Commit synthesized to keep one decoder path,
  `slot_consumer.rs:83-129`) `[verified-by-code]`.
- **One bgworker per sync group.** `launch_worker` fills a `BackgroundWorker`
  and calls `RegisterDynamicBackgroundWorker`, with `bgw_function_name =
  "duckpipe_worker_main"`, the group name in `bgw_extra`, `MyDatabaseId` in
  `bgw_main_arg`, and `bgw_restart_time = -1` (BGW_NEVER_RESTART — re-launched
  on demand by `add_table`/`start_worker`) (`api.rs:242-273`)
  `[verified-by-code]`. The worker connects with
  `BackgroundWorkerInitializeConnectionByOid`, builds a **single-threaded tokio
  runtime**, reads config from `duckpipe.*` catalog tables via SPI, and runs a
  poll loop wrapped in `catch_unwind` for panic recovery
  (`duckpipe-pg/src/worker.rs:107-289`) `[verified-by-code]`.
- **DuckDB is reached in-process, embedded in the worker** via the `duckdb`
  crate: each target table's flush worker holds a long-lived
  `duckdb::Connection` that `INSTALL`/`LOAD`s the DuckLake extension and
  `ATTACH`es Postgres (`duckdb_flush.rs:1-9,57-70`) `[verified-by-code]`. Cloud
  credentials are lifted from pg_duckdb's FDW catalogs as `CREATE SECRET`
  statements via SPI (`worker.rs:82-101`) `[verified-by-code]`.

## Where it diverges from core idioms

**1. Core has no CDC-into-an-analytics-engine primitive — pg_duckpipe assembles
one from replication plumbing.** Postgres ships logical decoding (slots,
publications, pgoutput) as building blocks for *replication to another
Postgres*. pg_duckpipe reuses those exact primitives but terminates the stream
in an **embedded columnar engine in the same process**, not a peer PG. It is a
logical-replication *subscriber* written in Rust that happens to live inside a
bgworker of the publisher cluster (`slot_consumer.rs:1-10`, `api.rs:330-372`)
`[verified-by-code]`. This is the same pgoutput/slot machinery that
`[[wal2json]]`, `[[decoderbufs]]`, and `[[synchdb]]` tap — but where synchdb
embeds Debezium/JVM to reach *external* sinks, pg_duckpipe's sink is
co-resident. Cross-ref `[[pglogical]]`, `[[pgactive]]`.

**2. Postgres-as-T, DuckDB-as-A, one server.** Core's storage model is a single
heap+WAL substrate for both reads and writes. pg_duckpipe deliberately runs
**two storage engines side by side**: the heap keeps serving OLTP while a
continuously-maintained DuckLake mirror serves OLAP. The `README` benchmark
table frames it as "Snapshot rows/s" + "OLTP TPS" + "Avg Lag" + "Consistency:
PASS" columns (`README.md:73-78`) `[from-README]` — the divergence is the
explicit acceptance of a *replication lag window* (~5 s default flush) between
the transactional truth and the analytical copy, in exchange for not paying
columnar-write cost on the OLTP path (`README.md:28`) `[from-README]`.

**3. The consistency model is at-least-once streaming + idempotent PK-keyed
apply → effectively exactly-once row state.** The crash-safe restart point is
`confirmed_lsn` from the slot; on any consumer error the connection is dropped
and the next cycle reconnects from that LSN (`slot_consumer.rs:6-10`)
`[verified-by-code]`. The checkpoint reported back via `StandbyStatusUpdate` is
`min(applied_lsn)` across all active tables of the group
(`service.rs:7,56-58`) `[verified-by-code]`. Re-delivered changes are made
idempotent by the flush path: buffer changes in DuckDB, **compact/dedup by
primary key**, then apply **DELETE+INSERT** into DuckLake and drop the buffer
(`duckdb_flush.rs:6-9`) `[verified-by-code]`. This is why the PRIMARY KEY
requirement is load-bearing, not incidental (`README.md:67`) `[from-README]`.

**4. A decoupled producer-consumer pipeline with backpressure — an in-process
Kafka-lite.** Each sync group is an isolated bgworker with its own slot ("a slow
table in one group cannot affect another"); each target table gets a **dedicated
OS flush thread** draining a change queue to DuckLake; when queued changes exceed
a threshold the WAL consumer **pauses** to bound memory (`README.md:91-95`)
`[from-README]`; the design comment enumerates slot-consumer → flush-coordinator
→ checkpoint → backpressure as four stages (`service.rs:1-9`)
`[verified-by-code]`. Group/table metrics (queued bytes, backpressure flag,
pending LSN, flush durations) live in a fixed-slot shared-memory struct guarded
by a pgrx `PgLwLock` (`lib.rs:37-94,111-157`) `[verified-by-code]` — core has no
comparable "streaming ingestion telemetry" surface.

**5. A `planner_hook` that transparently reroutes SELECTs to the columnar
mirror.** When `duckpipe.query_routing` is `on`/`auto`, the hook rewrites
`RangeTblEntry` OIDs so a SELECT on a synced source table is redirected to its
DuckLake target, after which pg_ducklake/pg_duckdb execute it in DuckDB
(`planner_hook.rs:1-6,84-127`) `[verified-by-code]`. It carries an RAII
re-entrancy guard because the hook's own SPI cache-refresh queries re-enter the
planner, and reads the GUC via `*QUERY_ROUTING.as_ptr()` to bypass pgrx's
main-thread check since the hook can fire on bgworker flush threads
(`planner_hook.rs:16-73`) `[verified-by-code]`. This makes the T/A split
*invisible* to the client — the HTAP payoff.

## Notable design decisions

- **pgrx, but the engine is framework-agnostic core.** `duckpipe-core` depends
  only on `tokio`, `tokio-postgres`, `duckdb`, and `pgwire-replication` — no
  pgrx (`duckpipe-core/Cargo.toml:7-20`) `[verified-by-code]` — so the identical
  CDC engine runs either inside a pgrx bgworker or as the standalone `duckpipe`
  daemon (`duckpipe-daemon/Cargo.toml:7-9`) `[verified-by-code]`. Cross-ref
  `[[pgrx]]`.
- **Single-threaded tokio in the bgworker** ("bgworker safety") with a
  `catch_unwind` panic boundary around each `block_on` cycle
  (`worker.rs:198-202,285-289`) `[verified-by-code]` — the discipline for
  bridging an async Rust runtime into PG's single-threaded, longjmp-based
  backend.
- **BGW_NEVER_RESTART + on-demand relaunch.** Workers are not auto-restarted by
  the postmaster; `add_table`/`start_worker` re-launch them, keeping idle groups
  from holding a worker slot (`api.rs:259,273`) `[verified-by-code]`.
- **DuckDB extension loaded from local pkglibdir with
  `allow_extensions_metadata_mismatch`** to tolerate the git-metadata skew
  between pg_ducklake's bundled DuckLake build and its shipped libduckdb
  (`duckdb_flush.rs:31-45`) `[verified-by-code]`.
- **Secrets reuse pg_duckdb's FDW catalogs**, not a new secret store — the
  worker reads `CREATE SECRET` SQL from the `duckdb` FDW via SPI and injects it
  into each DuckDB connection (`worker.rs:78-101`) `[verified-by-code]`, the
  same "reuse core foreign-server objects as a credential store" posture
  `[[pg_ducklake]]` uses.
- **Per-group `LISTEN` wakeup** so `add_table`/`resync_table`/`enable_group`
  `NOTIFY` the worker to act immediately instead of waiting a poll interval
  (`worker.rs:281-326`) `[verified-by-code]`.
- **Sync groups share one publication + slot** across multiple tables to bound
  slot/WAL-sender consumption (`README.md:29`) `[from-README]`.

## Links into corpus

- `[[pg_ducklake]]` — **the sink.** pg_duckpipe writes into the DuckLake tables
  pg_ducklake defines; it presupposes pg_ducklake (which bundles pg_duckdb +
  libduckdb) is installed (`README.md:64`). The single most important
  cross-reference.
- `[[pg_duckdb]]` — the embedded-DuckDB engine reused for execution and for the
  FDW secret catalogs; pg_duckpipe's flush path opens its own `duckdb::Connection`
  and its planner hook hands routed SELECTs to pg_duckdb.
- `[[pg_lake]]` — the trio's Iceberg-format sibling; contrast on both the format
  axis (Iceberg vs DuckLake) and process axis (separate `pgduck_server` vs
  in-process). pg_duckpipe is format-agnostic ingestion aimed at DuckLake.
- `[[synchdb]]` — the closest CDC cousin: also embeds a change-capture engine in
  a bgworker, but consumes *external* sources (Debezium/MySQL/Oracle) into PG,
  the mirror image of pg_duckpipe (PG → columnar).
- `[[wal2json]]`, `[[decoderbufs]]` — logical-decoding output plugins tapping the
  same slot/pgoutput machinery pg_duckpipe consumes; pg_duckpipe uses core
  `pgoutput` directly rather than a custom plugin.
- `[[pglogical]]`, `[[pgactive]]` — logical-replication subscriber/BDR
  frameworks; pg_duckpipe is a subscriber whose "downstream" is a columnar
  engine in the same process instead of a peer Postgres.
- `[[pgrx]]` — the Rust extension framework hosting the pg side (bgworker, GUCs,
  SHM, planner hook, SPI).

## Sources

- `https://api.github.com/repos/relytcloud/pg_duckpipe/git/trees/main?recursive=1`
  — HTTP 403 (session lacks repo access). Tree not obtained; files fetched
  directly by path.
- `https://github.com/relytcloud/pg_duckpipe/tree/main` (+ `/src`) — HTTP 403
  (HTML tree view blocked).
- `https://raw.githubusercontent.com/relytcloud/pg_duckpipe/main/README.md` — 200.
- `.../main/Cargo.toml` — 200 (workspace: duckpipe-core/-pg/-daemon).
- `.../main/duckpipe-pg/Cargo.toml` — 200 (pgrx 0.16.1, pg14–pg18).
- `.../main/duckpipe-core/Cargo.toml` — 200 (tokio, tokio-postgres, duckdb,
  pgwire-replication; no pgrx).
- `.../main/duckpipe-daemon/Cargo.toml` — 200 (axum REST daemon).
- `.../main/duckpipe-pg/src/lib.rs` — 200 (_PG_init, GUCs, SHM metrics, planner
  hook install).
- `.../main/duckpipe-pg/src/worker.rs` — 200 (bgworker main, tokio runtime, SPI
  config, flush coordinator wiring).
- `.../main/duckpipe-pg/src/planner_hook.rs` — 200 (query-routing planner hook).
- `.../main/duckpipe-pg/src/api.rs` — 200 (add_table/create_sync_group,
  slot+publication creation, launch_worker/RegisterDynamicBackgroundWorker).
- `.../main/duckpipe-core/src/lib.rs` — 200 (core module map).
- `.../main/duckpipe-core/src/slot_consumer.rs` — 200 (START_REPLICATION via
  pgwire-replication; pgoutput event decoding).
- `.../main/duckpipe-core/src/service.rs` — 200 (sync-cycle orchestration,
  confirmed_lsn checkpoint, backpressure design comment).
- `.../main/duckpipe-core/src/duckdb_flush.rs` — 200 (embedded DuckDB flush:
  buffer → dedup-by-PK → DELETE+INSERT into DuckLake).
- `.../main/{duckpipe-core/src/{decoder,snapshot,flush_coordinator}.rs, doc/*.md}`
  — probed (200) but not deep-read; used only for `[from-README]`/`[inferred]`
  context.
- `.../main/pg_duckpipe.control`, `.../duckpipe.control`, `Makefile` at repo root
  — HTTP 404 (pgrx-managed control/build; not at those paths).
