# TimescaleDB — time-series partitioning + columnstore as an extension

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `timescale/timescaledb` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-02 (see Sources footer).

## Domain & purpose

TimescaleDB is a PostgreSQL extension for high-performance real-time analytics
on time-series and event data `[from-README]` (`README.md:10`). Its central
abstraction is the **hypertable**: a user-facing table that is transparently
partitioned ("chunked") along one or more dimensions (typically a time column)
into many child tables, each an ordinary Postgres relation `[from-README]`
(`README.md:226-233`). On top of that it layers a **columnstore** (per-chunk
columnar compression, ~90%+ typical), **continuous aggregates** (incrementally
refreshed materialized views), and a job/policy system for retention,
compression, and refresh — all driven by background workers. Where Citus
answers "how far can you re-route Postgres *across nodes* from an extension?",
TimescaleDB answers a different question: *how much of a purpose-built
time-series storage + scheduling engine can you bolt onto a single Postgres,
without forking it?*

The structural ideology is **single-node, partition-centric**: a hypertable is
a hypercube in N-dimensional space; a chunk is the sub-cube carved out by one
slice per dimension, materialized as a real table with a `CHECK` constraint per
slice `[verified-by-code]` (`src/chunk.h:55-76`).

## How it hooks into PG

TimescaleDB is `shared_preload_libraries`-loaded, but indirectly — see the
two-stage loader below. The C-level entry point chains the standard core hook
surface from `_PG_init()` `[verified-by-code]` (`src/init.c:91-133`):

| Core mechanism | TimescaleDB use |
|---|---|
| `_PG_init` chained sub-inits | One `_xxx_init()` per subsystem: planner, executor, process-utility, event-trigger, caches, connection layer (`src/init.c:112-125`). Teardown is registered via `on_proc_exit(cleanup_on_pg_proc_exit)` and runs in **strict reverse order** of init (`src/init.c:68-89`, `:130-131`). |
| `planner_hook` | `_planner_init()` installs planner integration that recognizes hypertables and rewrites scans to expand into per-chunk plans (`src/init.c:115`; `src/planner/planner.c`). |
| Custom plan nodes | `ConstraintAwareAppend` and `ChunkAppend` — custom scan nodes for chunk exclusion at execution time (`src/init.c:116-117`, `_constraint_aware_append_init`/`_chunk_append_init`). |
| `ProcessUtility_hook` | `_process_utility_init()` intercepts DDL touching hypertables/chunks (`src/init.c:119`; `src/process_utility.c`). |
| Event triggers | `_event_trigger_init()` for DDL-completion handling (`src/init.c:118`). |
| Background workers | A **launcher** bgworker started at postmaster startup, plus a per-database **scheduler** bgworker (see divergence §2). |
| UDFs | The entire control surface (`create_hypertable`, `add_retention_policy`, `compress_chunk`, `add_continuous_aggregate_policy`, …) is `SELECT`-callable C functions — an extension cannot add DDL grammar, so policy/DDL is expressed as function calls `[verified-by-code]` (`src/chunk.h:24-30` names the drop/compress UDFs; `README.md:277` shows `add_continuous_aggregate_policy`). |

## Where it diverges from core idioms

### 1. Two-stage, per-database **versioned loader**

This is TimescaleDB's most distinctive architectural divergence and has no core
analogue. What `shared_preload_libraries` actually loads is a thin **loader**,
not the feature library. The loader has two jobs `[from-README]`
(`src/loader/README.md:1-21`):

1. **Load the correct *versioned* library per database.** Different databases in
   one Postgres instance may have different TimescaleDB versions installed; the
   loader loads `timescaledb-<version>.so` matching each database's installed
   extension version (`src/loader/README.md:5-11`). Core's extension model
   assumes one `.so` per extension name; TimescaleDB deliberately multiplexes
   many version-stamped libraries behind one preload entry.
2. **Start the launcher** background task at server startup, which in turn
   launches one **scheduler per database** (`src/loader/README.md:12-21`).

The loader also instantiates a **counter** so that TimescaleDB's own workers
never exceed `max_worker_processes` allocation (`src/loader/README.md:20-21`,
`src/loader/bgw_counter.c`) — an extension re-implementing worker-budget
accounting that core does not expose per-extension.

`_PG_init()` itself is written to tolerate being called multiple times (the
"eager load" path) via a static `init_done` guard `[verified-by-code]`
(`src/init.c:94`, `:104-110`). And TSL-module loading is *deferred* out of
`_PG_init` into a separate `ts_post_load_init` SQL-callable, because loading the
TSL during `_PG_init` makes parallel workers try to load the TSL before
TimescaleDB itself, causing link-time errors `[verified-by-code]`
(`src/init.c:135-146`). Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`
and the `extension-development` skill.

### 2. A per-database job **scheduler** with launcher state machines

Core has bgworkers but no scheduling framework. TimescaleDB builds one:

- The **launcher** maintains a per-database state machine
  (`DISABLED → ENABLED → ALLOCATED → STARTED`) driven by a small message queue
  with `start` / `stop` / `restart` messages `[from-README]`
  (`src/loader/README.md:84-141`). The extension's SQL install/upgrade/drop
  scripts *send messages to the launcher*: `CREATE EXTENSION` sends `restart`,
  `ALTER EXTENSION UPDATE` sends `restart` from the pre-update script,
  `DROP EXTENSION` sends `restart` (because the drop can roll back),
  `DROP DATABASE` sends `stop` (`src/loader/README.md:59-82`). The `restart`
  handler *waits on the vxid* of the sending transaction so the scheduler picks
  up the correct post-commit extension version (`src/loader/README.md:42-47`,
  `:111-115`). This is an extension wiring its own control plane into the
  transaction lifecycle.
- The **scheduler** runs jobs from a `bgw_job` catalog table on a
  `schedule_interval`, with exponential backoff on failure via `retry_period`,
  per-job state machine (`SCHEDULED → STARTING → TERMINATING`) `[from-README]`
  (`src/bgw/README.md:9-75`).
- **Crash accounting trick:** because a Postgres crash kills *all* backends and
  forbids any post-crash write, the scheduler deduces crashes retroactively — it
  commits a stats-table change *before* a job starts and undoes it *after*; a job
  left in the intermediate state must have crashed `[from-README]`
  (`src/bgw/README.md:36-47`). The crash count is deliberately an over-estimate
  to never under-apply backoff. This is a genuinely non-core idiom: using
  transaction commit boundaries as a crash-detection oracle.

### 3. The catalog: core *conventions*, but ordinary tables in private schemas

TimescaleDB keeps a substantial metadata catalog (`hypertable`, `dimension`,
`dimension_slice`, `chunk`, `bgw_job`, `bgw_job_stat`, `continuous_agg`,
`compression_settings`, … — 23 tables) `[verified-by-code]`
(`src/ts_catalog/catalog.h:33-60`). The ideology is explicit and split-minded:
*"definitions and naming should roughly follow how things are done in Postgres
internally"* — yet the storage is **regular tables**, not BKI bootstrap
catalogs `[from-comment]` (`src/ts_catalog/catalog.h:18-32`). Concretely:

- Tables live in private schemas: `_timescaledb_catalog`,
  `_timescaledb_internal`, `_timescaledb_functions`, `_timescaledb_cache`
  `[verified-by-code]` (`src/extension_constants.h:39-44`). Contrast core's
  `pg_catalog` BKI catalogs with bootstrap OIDs — see
  `[[knowledge/idioms/catalog-conventions]]`.
- Each table has hand-declared `Anum_*` attribute-number enums mirroring the
  core `Anum_pg_xxx` style (`src/ts_catalog/catalog.h:106-153` for hypertable),
  and a cached `Catalog` object holds the runtime relation OIDs
  (`catalog.h:26-29`, `:79-88`). Because OIDs are assigned at runtime (not
  bootstrap), all access goes through the cached `ts_catalog_get()` indirection
  rather than compile-time `RelationId` constants.
- **On-disk bit-flag discipline:** chunk status is a persisted power-of-2
  bitmask (`CHUNK_STATUS_COMPRESSED=1`, `_UNORDERED=2`, `_FROZEN=4`,
  `_COMPRESSED_PARTIAL=8`) with an explicit comment that the values *must never
  change* and that new flags need downgrade-script handling because older
  extension versions won't understand them `[verified-by-code]`
  (`src/chunk.h:276-305`). This is the extension-versioning analogue of core's
  `catversion`/`pg_upgrade` on-disk-format discipline.

### 4. Partitioning re-implemented, not built on declarative partitions

A hypertable is *not* a Postgres declarative-partitioned table. It is a plain
relation whose `Hypertable` struct carries a `Hyperspace *space` (the dimension
set) and a `SubspaceStore *chunk_cache` `[verified-by-code]`
(`src/hypertable.h:41-48`). A `Chunk` is a real table (`relkind` is
`RELKIND_RELATION` or `RELKIND_FOREIGN_TABLE`) positioned by a `Hypercube` of
dimension slices, each slice enforced by a `CHECK` constraint
(`src/chunk.h:55-76`, `:263-273`). Chunk routing for an inserted row is a
geometric point-in-hyperspace lookup (`ts_hypertable_find_chunk_for_point`,
`ts_chunk_find_for_point`) (`src/hypertable.h:117-123`, `src/chunk.h:155`).

This predates and diverges from PG native partitioning: TimescaleDB owns chunk
creation/exclusion entirely (custom `ChunkAppend`/`ConstraintAwareAppend` plan
nodes, §How-it-hooks), rather than relying on the core partition planner. It
buys runtime/dynamic chunk creation (chunks are created on demand at insert
time — `ts_chunk_create_for_point`, `src/chunk.h:156`) and per-chunk DDL
(compress/freeze/reorder a single chunk), at the cost of carrying a parallel
partitioning engine.

### 5. License-gated runtime module loading (Apache core + TSL)

The source is split: Apache-2.0 **core** under `src/`, and **TSL**
(Timescale License) features under `tsl/` — continuous aggregates, compression,
query optimizations `[from-README]` (`tsl/README.md:1-9`). `_PG_init` calls
`ts_license_enable_module_loading()` (deferred into `ts_post_load_init`) and a
`license_guc` gates whether the TSL `.so` may load at all `[verified-by-code]`
(`src/init.c:18-19`, `:143`, `src/license_guc.c`). Core Postgres has no notion
of license-conditional symbol loading inside one running backend; this is a
bespoke dynamic-loading layer the extension adds on top of `fmgr`/dynloader.
Cross-ref `[[knowledge/idioms/fmgr]]`.

### 6. Compression as a shadow hypertable

A compressed chunk is not an in-place format change: compression creates a
*separate* internal compressed table and links it via `compressed_chunk_id`,
with the hypertable carrying a `compression_state`
(`HypertableCompressionEnabled` / `…InternalCompressionTable`)
`[verified-by-code]` (`src/hypertable.h:27-40`, `:135-143`; `src/chunk.h:206-226`).
A chunk can be simultaneously compressed *and* hold uncompressed tuples
(`CHUNK_STATUS_COMPRESSED_PARTIAL`), and `ts_chunk_validate_chunk_status_for_operation`
guards which operations a given status permits (`src/chunk.h:221-223`). The
locking primitive `ts_chunk_lock_for_creating_compressed_chunk` returns a core
`TM_Result` (`src/chunk.h:239-240`), reusing the heap tuple-lock outcome
vocabulary — see `[[knowledge/idioms/locking-overview]]`.

## Notable design decisions (cited)

- **Loader indirection over direct preload** — one preload entry multiplexes
  many version-stamped libraries so heterogeneous-version databases coexist in
  one cluster (`src/loader/README.md:5-11`). The deepest non-core idea here.
- **Reverse-order teardown contract** — `cleanup_on_pg_proc_exit` documents that
  fini order must be the strict reverse of `_PG_init` (`src/init.c:71-73`),
  the disciplined version of the hook-chaining idiom.
- **Idempotent `_PG_init` guard** for eager loads (`src/init.c:94`,`:104-110`).
- **TSL load deferred to avoid parallel-worker link races** (`src/init.c:135-146`)
  — a concrete parallel-query footgun the extension hit and worked around.
- **Catalog stored in regular tables but named like core** — deliberately
  Postgres-flavored conventions over a non-bootstrap storage model
  (`src/ts_catalog/catalog.h:18-32`).
- **Persisted bit-flags are forever** — chunk status values are an on-disk ABI;
  changing them requires downgrade-script handling (`src/chunk.h:276-281`).
- **Dynamic chunk creation at insert time** — point-in-hyperspace routing rather
  than pre-declared partitions (`src/chunk.h:155-157`).

## Links into corpus

- `[[knowledge/idioms/catalog-conventions]]` — core BKI/bootstrap-OID catalogs
  vs TimescaleDB's runtime-OID regular-table catalog in private schemas.
- `[[knowledge/idioms/bgworker-and-parallel]]` — the launcher + per-DB
  scheduler, worker-budget counter, and the parallel-worker TSL load race.
- `[[knowledge/idioms/locking-overview]]` — `LOCKMODE`/`TM_Result` reuse around
  chunk creation and compression.
- `[[knowledge/idioms/fmgr]]` — UDF-as-control-surface; license-gated module
  loading layered on fmgr/dynloader.
- `[[knowledge/architecture/planner]]` + `[[knowledge/subsystems/optimizer]]` —
  `planner_hook` entry and custom chunk-exclusion plan nodes.
- `[[knowledge/architecture/executor]]` — `ChunkAppend`/`ConstraintAwareAppend`
  custom scan nodes.
- `.claude/skills/extension-development/SKILL.md` — `_PG_init` hook chaining,
  `shared_preload_libraries`, teardown discipline — TimescaleDB exemplifies the
  versioned-loader extreme of this idiom.

## Sources

Fetched 2026-06-02 (branch `main`):

- `https://raw.githubusercontent.com/timescale/timescaledb/main/README.md`
  @ 2026-06-02T23:04Z → HTTP 200 (458 lines; mostly a getting-started guide —
  used only for domain/purpose framing).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/docs/SECURITY.md`
  @ 2026-06-02T23:04Z → **HTTP 404** (manifest gap; file does not exist at this
  path on `main` — no security-model claims are made in this doc as a result).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/chunk.h`
  @ 2026-06-02T23:04Z → HTTP 200 (308 lines).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/hypertable.h`
  @ 2026-06-02T23:04Z → HTTP 200 (153 lines).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/init.c`
  @ 2026-06-02T23:04Z → HTTP 200 (146 lines).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/loader/README.md`
  @ 2026-06-02T23:04Z → HTTP 200 (140 lines).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/bgw/README.md`
  @ 2026-06-02T23:04Z → HTTP 200 (85 lines).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/ts_catalog/catalog.h`
  @ 2026-06-02T23:04Z → HTTP 200 (1410 lines; read top + table-name index only).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/extension_constants.h`
  @ 2026-06-02T23:04Z → HTTP 200 (schema-name constants).
- Tree listing
  `https://api.github.com/repos/timescale/timescaledb/git/trees/main?recursive=1`
  @ 2026-06-02T23:04Z → HTTP 200 (2838 blobs; used to discover the loader/bgw
  READMEs and `init.c` beyond the sparse manifest).

Manifest gap: `docs/SECURITY.md` 404'd. To compensate (and because the manifest
omitted any architecture file), this run additionally fetched the `src/loader`
and `src/bgw` READMEs, `src/init.c`, `catalog.h`, and `extension_constants.h` —
the load-bearing sources for the divergence analysis. README-sourced narrative
is tagged `[from-README]`/`[from-comment]`; struct/enum/constant cites against
the fetched headers are `[verified-by-code]`. The C subsystem `.c` bodies
(`planner.c`, `process_utility.c`, the launcher/scheduler implementations) were
not fetched; behavioral claims about them rest on the project's own READMEs and
are tagged accordingly.
</content>
