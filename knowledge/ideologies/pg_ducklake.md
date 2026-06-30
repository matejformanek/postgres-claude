# pg_ducklake — a DuckLake lakehouse layered on pg_duckdb, with the lakehouse catalog living *inside* Postgres tables

> Headline: pg_duckdb's third sibling. It does NOT re-embed DuckDB — it builds
> on `libpgduckdb`/`pg_duckdb` and adds the **DuckLake** table format, whose
> catalog/metadata is stored in ordinary Postgres tables (the `ducklake`
> schema) via SPI — the inverse of pg_lake's Iceberg-JSON-in-object-storage.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `relytcloud/pg_ducklake` @ branch `main` (114★, C++). All `file:line`
> cites below point into that repo (not `source/`), since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against the files fetched on 2026-06-29 (see Sources footer).
> Confidence tags: `[verified-by-code]` / `[from-README]` / `[from-comment]` /
> `[inferred]` / `[unverified]`. Source files were fetched as line-numbered
> renderings via `raw.githubusercontent.com` (the GitHub *API* tree endpoint
> was 403 in this environment); a few cites are line-range approximations from
> those renderings and are tagged where they exceed a verified declaration.

## Domain & purpose

pg_ducklake turns PostgreSQL into a **DuckLake lakehouse**: `CREATE TABLE ...
USING ducklake` makes a columnar/Parquet-backed table with full lakehouse
features — time travel, transactions, partitioning, sort keys, data inlining,
CDC, and a compaction/expiry background worker (`README` overview)
`[from-README]`. Its `.control` comment literally says "DuckLake lakehouse
extension built on libpgddb" (`pg_ducklake/pg_ducklake.control:1`)
`[verified-by-code]` — i.e. it is **layered on `pg_duckdb`/`libpgduckdb`**, not
a fresh embedding of DuckDB. The DuckDB instance and the `CustomScan`/planner
machinery are pg_duckdb's; pg_ducklake adds the DuckLake *table format* on top.

This is the three-way contrast with its siblings. `[[knowledge/ideologies/pg_duckdb]]`
embeds `libduckdb` in-backend and swaps the executor for arbitrary analytic
queries over heap/Parquet. `[[knowledge/ideologies/pg_lake]]` runs DuckDB in a
*separate* `pgduck_server` process and implements the **Iceberg** format, whose
catalog is Iceberg-spec JSON manifests/snapshots in object storage (mirrored
into PG tables). pg_ducklake is closest to pg_duckdb on the *execution* axis
(in-process DuckDB, query routed whole to a DuckDB node) but diverges sharply on
the *table-format* axis: the **DuckLake** format stores its entire catalog —
snapshots, table list, column stats, inlined data — as **SQL tables in the host
Postgres database** (the `ducklake` schema), not as files in a bucket. Built in
C++, supports PG 14–18 `[from-README]`.

## How it hooks into PG

`_PG_init` is a thin C++ shim that delegates to ~13 initializers
(`pg_ducklake/src/pgducklake.cpp:52-69`) `[verified-by-code]`: `InitGUCs`,
`InitMaintenanceWorker`, `InitDirectInsertStatsShmem`, `InitDuckDBManager`,
`pgddb::InitNode("DuckLakeScan")` (the custom scan node — note the `pgddb::`
namespace, i.e. the bundled pg_duckdb library), `RegisterDirectInsertNode`,
`InitTableAmHook`, `InitHooks`, `InitRuleutilsHooks`, `InitTypeHooks`,
`RegisterXactCallback`, `InitFDW`, `InitSecrets`. Module magic uses the modern
`PG_MODULE_MAGIC_EXT(.name=..., .version=...)` with a `PG_MODULE_MAGIC` fallback
(`:41-49`) `[verified-by-code]`.

Before any of that, line 54 does the load-bearing registration: it registers a
**DuckLake metadata-manager factory** into DuckDB's process-global registry —
`duckdb::DuckLakeMetadataManager::Register(PGDUCKLAKE_DUCKDB_CATALOG,
pgducklake::PgDuckLakeMetadataManager::Create)` (`:54`) `[verified-by-code]`.
This is how pg_ducklake teaches the embedded DuckDB's DuckLake implementation to
read/write its metadata through Postgres instead of through DuckLake's default
SQLite/DuckDB metadata store (see §2 below).

`.control` is minimal: `default_version = '1.1.0'`, `relocatable = false`, no
`requires`, no `schema`, no `shared_preload_libraries` line
(`pg_ducklake/pg_ducklake.control:1-4`) `[verified-by-code]`. (Contrast
pg_duckdb, which hard-errors unless preloaded.) `InitHooks` installs **two**
hooks, each chaining the prior value or `standard_*` — explicitly to coexist
with pg_duckdb's own hooks (`pg_ducklake/src/hooks.cpp`, `InitHooks`)
`[verified-by-code]`:

| Hook | Role |
|---|---|
| `planner_hook` (`DucklakePlannerHook`) | Try a direct-insert plan; run pure-PG rewrites (VARIANT `->`/`->>` operators → function calls, regclass → text overloads); attach FDW databases for ducklake foreign tables; route the query to DuckDB via `pgddb::PlanNode()` when it references a ducklake-AM table, a ducklake-only function, or a ducklake foreign table; else fall through to the previous hook (`hooks.cpp`, `DucklakePlannerHook`) `[verified-by-code]`. |
| `ProcessUtility_hook` (`DucklakeUtilityHook`) | DDL/utility interception: force DuckDB commit on explicit `COMMIT`; rewrite `CREATE VIEW` over duckdb_row functions; run `CALL`s of ducklake-only functions in DuckDB; handle `COPY ... FROM STDIN` for ducklake tables; validate `CREATE INDEX` with the `ducklake_sorted` AM; strip ducklake options from `CREATE TABLE`; on `DROP EXTENSION` detach the catalog + invalidate caches (`hooks.cpp`, `DucklakeUtilityHook`) `[verified-by-code]`. |

Plus a **table access method** `ducklake` (`InitTableAmHook`, §3), a **ruleutils
hook** + **type hooks**, an **FDW** for foreign/"frozen" ducklake tables
(`InitFDW`, §5), a **transaction callback** mirroring PG xacts into DuckDB's
DuckLake transaction (`RegisterXactCallback`; comment at `:65-66`)
`[verified-by-code]`, a **secrets** layer (`InitSecrets`, storing cloud creds as
`FOREIGN SERVER` objects) `[from-README]`, and a **maintenance background
worker** (`InitMaintenanceWorker`, §6). Cross-ref
`[[knowledge/subsystems/optimizer]]`, `[[knowledge/subsystems/tcop]]`,
`[[knowledge/idioms/tableam-vtable-lifecycle]]`, `[[knowledge/subsystems/foreign]]`.

## Where it diverges from core idioms

### 1. It reuses pg_duckdb's engine instead of re-embedding DuckDB — the execution divergence is *inherited*

pg_ducklake does not own the planner-rewrite-to-DuckDB trick; it borrows it.
`_PG_init` registers a custom node named `"DuckLakeScan"` through pg_duckdb's
own `pgddb::InitNode` (`pgducklake.cpp:59`) and routes qualifying queries with
pg_duckdb's `pgddb::PlanNode()` (`hooks.cpp`, `DucklakePlannerHook`)
`[verified-by-code]`. The embedded `DuckDBManager` is a process singleton whose
DuckDB runs **in-backend** (`pg_ducklake/src/duckdb_manager.cpp:103-200`)
`[inferred from summary]`, and the comment at `duckdb_manager.cpp:116-118` notes
that pg_duckdb's `PostgresStorageExtension` ("pgduckdb") is registered by the
kernel `DuckDBManager` *before* DuckLake init — establishing a division of
labour: **pg_duckdb handles heap/foreign tables; DuckLake manages its own table
AM** (`:116-118`) `[from-comment]`. So the in-process-vs-out-of-process axis
that separates pg_duckdb from pg_lake is settled here on the pg_duckdb side, by
construction. Cross-ref `[[knowledge/ideologies/pg_duckdb]]` (the engine this
extension stands on), `[[knowledge/subsystems/executor]]`.

### 2. The DuckLake catalog is an ATTACHed DuckDB catalog whose metadata schema is *Postgres tables* — not Iceberg JSON in a bucket

This is pg_ducklake's signature divergence and the heart of the pg_lake
contrast. `OnPostInit` runs `ducklake_attach_catalog()`, whose ATTACH statement
is `attach 'ducklake:pgducklake_duckdb_catalog:'` with `METADATA_SCHEMA` pointed
at the Postgres `pgducklake` schema and `DATA_PATH` set only on first init
(`duckdb_manager.cpp:36-65`, `:114-126`) `[verified-by-code]` (ATTACH string at
`:44`). The factory registered at `pgducklake.cpp:54` makes DuckDB's DuckLake
implementation drive that metadata schema through `PgDuckLakeMetadataManager`,
which **inherits `duckdb::PostgresMetadataManager`** and runs all metadata
SELECT/DDL/DML through **SPI** against Postgres tables — `Query()` /
`Execute()` / `ExecuteCommit()` (`pg_ducklake/src/pgducklake_metadata_manager.cpp:343-373`)
`[verified-by-code]`. The metadata lives in a reserved **`ducklake` schema**
(`PGDUCKLAKE_PG_SCHEMA`) as relations like `ducklake_snapshot`,
`ducklake_table_stats`, `ducklake_table_column_stats`, and
`ducklake_inlined_data_*` (`pgducklake_metadata_manager.cpp`, storage section)
`[verified-by-code]`. `IsInitialized()` literally scans `pg_class` for
`ducklake_*` relations (`:375-410`) `[verified-by-code]`; `AttachMetadata()`
returns empty "because the metadata is already in PG" (`:448-451`)
`[from-comment]`.

Contrast: `[[knowledge/ideologies/pg_lake]]` stores the Iceberg catalog's
*current-snapshot pointer* in PG tables but the snapshots/manifests themselves
are immutable JSON+Parquet in object storage (and it bridges to external
REST/object-store Iceberg catalogs). pg_ducklake keeps the **entire** lakehouse
catalog — every snapshot row, every stats row, inlined data — as MVCC-protected
Postgres rows, with only the Parquet data files in `DATA_PATH` (local or
S3/GCS/R2/Azure) `[from-README]`. DuckLake-the-format is "a lakehouse format
built on a SQL database + Parquet"; pg_ducklake makes that SQL database *be the
host Postgres*. Cross-ref `[[knowledge/architecture/mvcc]]`,
`[[knowledge/idioms/catalog-conventions]]`, `fmgr-and-spi` skill.

### 3. `USING ducklake` is a table AM that is real for catalog purposes and a no-op/error for storage — the same shim pg_duckdb and pg_lake use

`ducklake_am_handler()` returns `ducklake_methods`, a full `TableAmRoutine`
(`pg_ducklake/src/ducklake_table.cpp:236-311`) `[verified-by-code]`, but the
callbacks split three ways `[inferred from summary]`:

- **No-ops / minimal stubs**: `ducklake_scan_getnextslot` returns an empty
  tuple; `tuple_insert` / `multi_insert` are no-ops because data flows through a
  DDL event trigger instead (`:76-110`, `:149-163`); `slot_callbacks` returns
  `TTSOpsMinimalTuple` only so `ANALYZE` does not fail (`:59-62`);
  `relation_set_new_filelocator`/`set_new_filenode` are no-ops since storage
  lives in DuckDB (`:171-193`).
- **`NOT_IMPLEMENTED()` hard errors** (macro at `:40-43`): deletion, update,
  locking, index fetches, cluster, index-build operations (`:111-147`).
- **delegations**: `vacuum` delegates to the background worker;
  `estimate_rel_size` returns zeros (`:181-193`).

Real `CREATE TABLE ... USING ducklake` work happens in an **event trigger**
`ducklake_create_table_trigger` (`:348-432`): it spots ducklake tables by
`pg_am` lookup, extracts the DDL via `Ruleutils().get_tabledef(relid)`, and runs
it against DuckDB with `DuckDBQueryOrThrow(create_table_ddl)` (for CTAS it
appends an INSERT) `[verified-by-code]`. This is the **identical pattern** to
pg_duckdb's stub `USING duckdb` AM and pg_lake's hard-error `USING iceberg`
placeholder: the AM exists to give the table a `pg_class`/`pg_am` identity so
DDL and the catalog are satisfied, while the real read/write path is the
planner-routed DuckDB node. Cross-ref `[[knowledge/idioms/tableam-vtable-lifecycle]]`,
`access-method-apis` skill, `[[knowledge/ideologies/pg_duckdb]]` (same trick),
`[[knowledge/ideologies/pg_lake]]` (same trick).

### 4. External DuckDB clients write the *same* PG metadata tables, and a trigger reverse-syncs DDL into pg_class

Because the DuckLake catalog *is* Postgres tables, an external DuckDB client can
connect to the DuckLake (the tables are "directly queryable from DuckDB
clients", `README`) `[from-README]` and create/drop tables by writing the
`ducklake` metadata relations directly — bypassing PG's DDL. pg_ducklake closes
the loop with `EnsureSnapshotTrigger()`, which installs an AFTER INSERT trigger
on `ducklake.ducklake_snapshot` calling `ducklake._snapshot_trigger()`
(`pgducklake_metadata_manager.cpp:417-440`) `[verified-by-code]`. That trigger
(`pg_ducklake/src/catalog_sync.cpp:38-72`) runs three handlers in sequence —
`SyncNewTables`, `SyncDroppedTables`, `SyncSortKeys` (`:31-36`) — to
"reverse-sync DDL made by external DuckDB clients into the PG catalog"
(`:40-41`) `[from-comment]`, using SPI (`SPI_connect`/`SPI_getbinval`/`SPI_finish`
at `:54`,`:59`,`:74`) `[verified-by-code]`. `SyncNewTables` reads
`ducklake_table`/`ducklake_schema` for tables at the new `begin_snapshot` and
emits `CREATE TABLE` into PG; `SyncDroppedTables` removes pg_class entries for
tables with an `end_snapshot` (`ducklake_table.cpp:641-746`, `:748-818`)
`[verified-by-code]`. A GUC (`enable_metadata_sync`) lets you opt out of the
per-commit overhead (`catalog_sync.cpp:49-50`) `[from-comment]`. This
bidirectional catalog reconciliation — *PG-DDL → DuckDB* (the event trigger in
§3) and *DuckDB-write → PG-catalog* (this snapshot trigger) — has no core
analogue; it exists because two SQL frontends share one physical catalog.
Cross-ref `[[knowledge/idioms/catalog-conventions]]`, `fmgr-and-spi` skill,
`[[knowledge/ideologies/pg_duckdb]]` (whose MotherDuck bgworker syncs an
*external* catalog into PG; here the catalog is co-located and a trigger does
it synchronously).

### 5. The FDW exists but never scans — it's a foreign/"frozen" ducklake registrar, with the planner routing whole queries to DuckDB

`ducklake_fdw_handler` (`pg_ducklake/src/ducklake_fdw.cpp:458-471`) fills a
`FdwRoutine` whose scan callbacks **intentionally error** — the header comment
states "Queries never run through the FDW scan callbacks: the planner routes
them whole to DuckDB" (`:1-...`) `[from-comment]`. The FDW's real job is
registration/detection: `QueryReferencesDucklakeForeignTable()` (`:196`) and
`RegisterForeignTablesInQuery()` (`:213`, attaches the DuckLake database and
blocks non-updatable DML), plus schema import via `DucklakeImportForeignSchema()`
(`:338`) and column inference by querying `LIMIT 0`
(`InferForeignTableColumns()`, `:287`) `[verified-by-code]`. It is **not** a
postgres_fdw derivative (unlike pg_lake_table, whose `postgres*` function names
betray that lineage) — it bypasses the FDW scan contract entirely. It supports a
"frozen" read-only mode over HTTP snapshots in addition to the regular
PG-metadata-backed mode (`:summary`) `[from-comment]`. `InitFDW()` (`:492`)
registers the deparser relation-name hook and the utility hook that intercepts
`CREATE FOREIGN TABLE` for auto column inference `[verified-by-code]`. Cross-ref
`[[knowledge/subsystems/foreign]]`, `[[knowledge/ideologies/pg_lake]]` (which by
contrast leans on the full postgres_fdw `FdwRoutine`).

### 6. C++/longjmp boundary, shared-memory stats, and a launcher→per-DB maintenance worker fleet

Like its siblings, pg_ducklake bridges DuckDB C++ and PG's `ereport`/`longjmp`:
`ExecuteCommit()` runs metadata mutation inside a subtransaction and **converts
PG errors into DuckDB exceptions** (`pgducklake_metadata_manager.cpp:367-373`)
`[verified-by-code]` — the reverse direction from pg_duckdb's `InvokeCPPFunc`
(which turns C++ exceptions into `ereport`), reflecting that here PG-side SPI is
called *from within* DuckDB's metadata manager. The `cpp_wrapper.hpp` from
pg_duckdb is included (`pgducklake.cpp:12`) `[verified-by-code]`. It also
allocates `DirectInsertStats` **shared memory** with `shmem_request_hook` /
`shmem_startup_hook` (`pgducklake.cpp:57`;
`pg_ducklake/src/maintenance_worker.cpp:321-325`) `[verified-by-code]`.

The maintenance worker is a two-tier fleet: `InitMaintenanceWorker` registers a
static **launcher** bgworker (`RegisterBackgroundWorker`, name "ducklake
maintenance launcher", `bgw_restart_time = 60`, starts after recovery)
(`maintenance_worker.cpp:320-340`) `[verified-by-code]`. The launcher polls
`pg_database` and spawns a **dynamic** per-DB worker via
`RegisterDynamicBackgroundWorker()` (`:265-315`, `:313`) `[verified-by-code]`;
each worker connects with `BackgroundWorkerInitializeConnectionByOid()`
(`:138-142`) and runs flush-inlined-data → expire-snapshots →
rewrite-data-files → `merge_adjacent_files` → cleanup-old-files
(`:166-257`) `[verified-by-code]`. This launcher/per-DB-worker shape is the
autovacuum pattern, applied to lakehouse compaction. Cross-ref
`[[knowledge/idioms/bgworker-and-parallel]]`, `[[knowledge/idioms/error-handling]]`,
`bgworker-and-extensions` skill.

## Notable design decisions (cited)

- **`ducklake_initialize()` is a CREATE-EXTENSION-only bootstrap** that forces
  DuckDB init (whose `OnPostInit` attaches the catalog) and, on DROP+CREATE
  within one backend, re-attaches because `OnPostInit` won't re-run
  (`pgducklake.cpp:71-102`) `[verified-by-code]`. It rejects being called
  outside `creating_extension` and errors if the `ducklake` schema is already in
  use (`:79-88`) `[verified-by-code]`.
- **Inlined-data writes route through DuckDB, not SPI**, "to reduce lock
  contention to per-batch rather than whole-operation" — they use
  `transaction.ExecuteRaw()` instead of the SPI metadata path
  (`pgducklake_metadata_manager.cpp:286`) `[from-comment]`. Real-time ingestion
  buffers small writes in the metadata layer before flushing to Parquet
  (`README`, data inlining) `[from-README]`.
- **VARIANT operators and regclass are rewritten in the planner hook before
  DuckDB sees them** — `RewriteVariantOperators` turns `->`/`->>` into function
  calls and `RewriteRegclassFunctions` turns regclass args into text overloads
  (`hooks.cpp`, `DucklakePlannerHook`) `[verified-by-code]` — pure-PG parse-tree
  surgery so the two type systems line up, analogous to pg_lake's shippability
  gate but done as rewrites rather than allow-lists.
- **Cloud credentials are stored as PG `FOREIGN SERVER` objects** via SQL
  helpers like `ducklake.create_s3_secret()` (`README`; `InitSecrets`)
  `[from-README]` — reusing core's foreign-server catalog as a secret store.
- **`relocatable = false`** (`pg_ducklake.control:4`) and the `ducklake` schema
  name is reserved/hardcoded (`PGDUCKLAKE_PG_SCHEMA`) `[verified-by-code]` —
  same schema-pinning posture as pg_duckdb/pg_lake, here because the metadata
  tables and triggers are addressed by that fixed schema.
- **DROP EXTENSION detaches the DuckLake catalog and invalidates caches** in the
  utility hook (`hooks.cpp`, `DucklakeUtilityHook`) `[verified-by-code]` — the
  symmetric teardown for the `ducklake_initialize()` attach.

## Links into corpus

- `[[knowledge/ideologies/pg_duckdb]]` — **the foundation it builds on.** Same
  in-process DuckDB, same `planner_hook`-routes-query-to-a-DuckDB-CustomScan, same
  stub table AM. pg_ducklake reuses pg_duckdb's `pgddb::` node/plan machinery
  (`pgducklake.cpp:12,59`; `hooks.cpp`) and *adds* the DuckLake table format. The
  single most important cross-reference.
- `[[knowledge/ideologies/pg_lake]]` — **the table-format mirror.** Both are
  lakehouse formats over Parquet, but pg_lake implements **Iceberg** (catalog =
  JSON manifests/snapshots in object storage, plus REST/object-store external
  catalogs, DuckDB in a *separate* `pgduck_server`), while pg_ducklake implements
  **DuckLake** (catalog = SQL tables in the host Postgres `ducklake` schema,
  DuckDB *in-process*). The catalog-storage axis is the whole difference.
- `[[knowledge/ideologies/cstore_fdw]]` — the original "bypass smgr/WAL, smuggle
  a columnar store into PG" case; pg_ducklake bypasses the durability stack for
  table *data* (Parquet) but keeps the *catalog* in MVCC PG tables.
- `[[knowledge/subsystems/optimizer]]` — `planner_hook` routing + the inherited
  `pgddb::PlanNode` `CustomScan`.
- `[[knowledge/idioms/tableam-vtable-lifecycle]]` + `access-method-apis` skill — the
  `ducklake` table AM (no-op/NOT_IMPLEMENTED/delegate split) and the
  `ducklake_sorted` index AM for sort keys.
- `[[knowledge/subsystems/foreign]]` — the non-scanning `ducklake_fdw` for
  foreign/frozen ducklake tables.
- `[[knowledge/subsystems/tcop]]` — the `ProcessUtility` hook (COMMIT, COPY,
  CALL, CREATE VIEW/INDEX/FOREIGN TABLE, DROP EXTENSION).
- `[[knowledge/architecture/mvcc]]` — the metadata-in-PG-tables model + the
  transaction callback mirroring PG xacts into DuckLake.
- `[[knowledge/idioms/catalog-conventions]]` + `fmgr-and-spi` skill — heavy SPI
  metadata mutation and the bidirectional PG↔DuckDB catalog sync triggers.
- `[[knowledge/idioms/bgworker-and-parallel]]` + `bgworker-and-extensions` skill
  — the launcher → per-DB dynamic maintenance worker fleet.
- `[[knowledge/idioms/error-handling]]` — the PG-error→DuckDB-exception
  conversion in `ExecuteCommit` (reverse of pg_duckdb's `InvokeCPPFunc`).
- `.claude/skills/extension-development/SKILL.md` — multi-hook chaining (to
  coexist with pg_duckdb), `PG_MODULE_MAGIC_EXT`, event triggers, bgworker
  registration, `CREATE EXTENSION` bootstrap function.

## Sources

Fetched 2026-06-29 (branch `main`). The GitHub *API* tree endpoint
(`api.github.com/.../git/trees/main?recursive=1`) returned **HTTP 403** in this
environment, and the github MCP tool was locked to a different repo; paths were
discovered via the GitHub HTML tree views and files fetched from
`raw.githubusercontent.com`.

- `https://github.com/relytcloud/pg_ducklake/tree/main` → HTTP 200 (root listing;
  code lives under `pg_ducklake/`, bundling `duckdb/`, `libpgduckdb/`,
  `pg_duckdb/` submodules).
- `https://github.com/relytcloud/pg_ducklake/tree/main/pg_ducklake` → HTTP 200.
- `https://github.com/relytcloud/pg_ducklake/tree/main/pg_ducklake/src` → HTTP 200
  (src file listing).
- `https://raw.githubusercontent.com/relytcloud/pg_ducklake/main/README.md`
  → HTTP 200.
- `.../main/pg_ducklake/pg_ducklake.control` → HTTP 200 (4 lines).
- `.../main/pg_ducklake/src/pgducklake.cpp` → HTTP 200 (~104 lines; `_PG_init`,
  metadata-manager factory register, `ducklake_initialize`).
- `.../main/pg_ducklake/src/hooks.cpp` → HTTP 200 (planner + ProcessUtility
  hooks; summarized, line numbers not individually rendered).
- `.../main/pg_ducklake/src/ducklake_table.cpp` → HTTP 200 (table AM +
  create-table event trigger + SyncNewTables/SyncDroppedTables; summarized).
- `.../main/pg_ducklake/src/catalog_sync.cpp` → HTTP 200 (snapshot trigger +
  reverse-sync handlers; summarized).
- `.../main/pg_ducklake/src/pgducklake_metadata_manager.cpp` → HTTP 200
  (`PgDuckLakeMetadataManager` : `PostgresMetadataManager`, SPI Query/Execute/
  ExecuteCommit, EnsureSnapshotTrigger; summarized).
- `.../main/pg_ducklake/src/ducklake_fdw.cpp` → HTTP 200 (non-scanning FDW;
  summarized).
- `.../main/pg_ducklake/src/maintenance_worker.cpp` → HTTP 200 (launcher +
  dynamic per-DB workers; summarized).
- `.../main/pg_ducklake/src/duckdb_manager.cpp` → HTTP 200 (in-process DuckDB
  singleton, `ducklake_attach_catalog`, `OnPostInit`; summarized).

**Gaps / confidence.** `.control`, `_PG_init`, the metadata-manager factory
register, and `ducklake_initialize` are `[verified-by-code]` from the
line-numbered `pgducklake.cpp` rendering. Hook roles, the table-AM
callback split, the FDW handler, the maintenance worker, the metadata manager,
and `duckdb_manager` were fetched as **summarized** line-numbered renderings
(not raw cat-n), so their `file:line` ranges are approximations from those
renderings — load-bearing claims (metadata-in-PG-tables, ATTACH string, snapshot
trigger, in-process DuckDB, no-op AM, non-scanning FDW) are tagged
`[verified-by-code]` where a declaration/string was quoted and `[from-comment]`
where they rest on a quoted source comment. The DuckDB-side DuckLake format
internals (`third_party/`, the bundled `pg_duckdb`/`libpgduckdb`/`duckdb`
submodules), `pg_duckpipe` CDC, `time_travel.cpp`, `freeze.cpp`, and the SQL
install script were NOT deep-read; claims about them are `[from-README]`.
