# pg_lake — ideology / divergence-from-core notes

> Headline: an Iceberg/data-lake engine split across a Postgres FDW and an
> external `pgduck_server` process (the inverse of pg_duckdb's embed-in-backend).

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `Snowflake-Labs/pg_lake` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-15 (see Sources footer). Confidence tags:
> `[verified-by-code]` / `[from-README]` / `[from-comment]` / `[inferred]` /
> `[unverified]`.

## Domain & purpose

pg_lake turns PostgreSQL into a **stand-alone Iceberg lakehouse**: it lets you
`CREATE TABLE ... USING iceberg`, `COPY` Parquet/CSV/JSON to and from object
storage (S3/GCS/R2), and create foreign tables over raw lake files — all with
"full transactional guarantees and no SQL limitations," combining heap, Iceberg,
and external Parquet in one query (`README.md:5-14`) `[from-README]`. It is the
open-sourced descendant of Crunchy Data Warehouse / Crunchy Bridge for
Analytics; Crunchy Data was acquired by Snowflake in June 2025, and the project
was open-sourced as pg_lake in November 2025 at version 3.0 "because of the two
prior generations" (`README.md:223-228`) `[from-README]`.

The architectural thesis is the same one pg_duckdb answers, but pg_lake answers
it the **opposite** way. pg_duckdb embeds `libduckdb` *inside* the backend and
swaps the executor via `planner_hook`. pg_lake **refuses to embed DuckDB in the
backend at all** — it runs DuckDB in a separate `pgduck_server` process that
speaks the PostgreSQL wire protocol over a Unix socket, "to avoid the threading
and memory-safety limitations that would arise from embedding DuckDB directly
inside the Postgres process, which is designed around process isolation rather
than multi-threaded execution" (`README.md:197`) `[from-README]`. So pg_lake is
*two cooperating servers*: PostgreSQL-with-extensions for catalog/transaction/
planning, and a multi-threaded DuckDB daemon for scan + compute. Built in C
(the PG side; the DuckDB side is the `duckdb_pglake` C++ extension).

## How it hooks into PG

pg_lake is a **monorepo of ~8 cooperating extensions**, not one extension. The
README enumerates them (`README.md:210-221`) `[from-README]`; the load-bearing
ones for this doc are:

| Component | Role |
|---|---|
| `pg_lake` | umbrella; `requires = 'pg_lake_table,pg_lake_copy'` (`pg_lake/pg_lake.control:7`) |
| `pg_lake_table` | the **FDW** + the **whole-query pushdown planner hook** (`pg_lake_table/src/fdw/pg_lake_table.c`, `.../planner/query_pushdown.c`) |
| `pg_lake_iceberg` | the Iceberg v2 spec implementation: manifests, snapshots, table-metadata, REST + object-store catalogs |
| `pg_lake_engine` | shared library; owns the **pgduck_server client** (`.../pgduck/client.c`) |
| `pg_extension_base` | a framework other pg_lake extensions build on (worker launching, extension deps) |
| `pgduck_server` | the **external** DuckDB daemon speaking PG wire protocol on `host=/tmp port=5332` |
| `duckdb_pglake` | a DuckDB C++ extension adding PG-compatible functions to DuckDB |

`pg_lake.control` is `relocatable = false`, `schema = pg_catalog`
(`pg_lake/pg_lake.control:5-6`) `[verified-by-code]`. `pg_lake_table.control`
additionally `requires = 'pg_lake_engine,pg_lake_iceberg,btree_gist'`
(`pg_lake_table/pg_lake_table.control:7`) — the `btree_gist` dependency is for
range/exclusion logic over Iceberg metadata `[inferred]`. Both control files
carry a commented-out `#!shared_preload_libraries` hint
(`pg_lake/pg_lake.control:8`, `pg_lake_table/pg_lake_table.control:8`).

**Two integration surfaces, one extension.** `pg_lake_table` registers *both* a
classic FDW handler and a planner hook:

1. **FDW handler** `pg_lake_table_handler` fills a `FdwRoutine` with the full
   `postgres_fdw`-style callback set — `GetForeignRelSize`/`GetForeignPaths`/
   `GetForeignPlan`, `BeginForeignScan`/`IterateForeignScan`, the modify path
   `AddForeignUpdateTargets`/`PlanForeignModify`/`ExecForeignInsert`/
   `ExecForeignUpdate`/`ExecForeignDelete`, plus `GetForeignJoinPaths` and
   `GetForeignUpperPaths` (`pg_lake_table/src/fdw/pg_lake_table.c:537-599`)
   `[verified-by-code]`. The retained `postgres*` static-function names betray
   the lineage: this is `contrib/postgres_fdw` whose "remote server" has been
   redirected from another Postgres to `pgduck_server`.
2. **planner_hook** `LakeTablePlanner` is installed in `query_pushdown.c`
   (`pg_lake_table/src/planner/query_pushdown.c:193-197`) `[verified-by-code]`,
   chaining the prior `planner_hook` (or `standard_planner`) and also taking
   `set_rel_pathlist_hook` (→ `PgLakeRecordPlannerRestrictions`) and
   `ExplainOneQuery_hook` (`:200`). When a query touches only lake tables and is
   fully shippable, the hook discards the local plan and substitutes a single
   `CustomScan` that *is the whole query, deparsed for DuckDB* (see §2 below).

`pg_lake_iceberg` registers an `RegisterXactCallback(IcebergXactCallback)`
transaction callback (`pg_lake_table/src/transaction/transaction_hooks.c:33`)
`[verified-by-code]`. Cross-ref `[[knowledge/subsystems/foreign]]`,
`[[knowledge/subsystems/optimizer]]`, `[[knowledge/idioms/extension-development]]`.

There is also a **placeholder table access method**: `USING iceberg` maps to a
`pg_am` row whose handler `pg_lake_iceberg_am_handler` immediately
`ereport(ERROR, ... "access method is a placeholder and should not be used")`
(`pg_lake_table/src/access_method/access_method.c:28-35`) `[verified-by-code]`.
The AM exists purely so `CREATE TABLE ... USING iceberg` parses and gets a
catalog identity; `GetPgLakeTableTypeViaAccessMethod` reads the AM name to route
the table to the Iceberg code path (`:45-68`). This is the **same trick
pg_duckdb plays** with its stub `USING duckdb` AM. Cross-ref
`[[knowledge/subsystems/access-methods]]`, `access-method-apis` skill.

## Where it diverges from core idioms

### 1. Storage is Parquet/Iceberg on object storage — smgr, bufmgr, and WAL see none of the table data

Lake-table rows never live in `$PGDATA` heap pages. The data is Parquet files in
S3/GCS, written and read by DuckDB inside pgduck_server; the Iceberg *metadata*
(manifests, manifest-lists, snapshots, table-metadata JSON) is produced by
`pg_lake_iceberg` and also lands in object storage
(`README.md:132-141` shows `metadata_location` as an `s3://.../metadata/...metadata.json`)
`[from-README]`. So the entire core durability stack — `SMgrRelation`, the
buffer manager, WAL, full-page writes, checkpoints, physical replication — does
**not** cover lake-table contents. What core *does* still cover is the catalog
side: which is the crux of pg_lake's transaction model (§4). Cross-ref
`[[knowledge/subsystems/storage-buffer]]`, `[[knowledge/architecture/wal]]`,
`[[knowledge/ideologies/cstore_fdw]]` (the older "bypass smgr/WAL" example —
cstore_fdw wrote raw `$PGDATA` files; pg_lake writes Parquet to S3 instead).

### 2. Execution is offloaded to a separate process over libpq — two whole-query pushdown paths

This is pg_lake's signature divergence. Compute does not happen in the backend
at all when it can be shipped:

- **Per-table FDW path.** `postgresBeginForeignScan` opens a `PGDuckConnection`
  and `postgresIterateForeignScan` pulls rows from pgduck_server, materializing
  each into a `HeapTuple` via `ExecStoreHeapTuple`
  (`pg_lake_table/src/fdw/pg_lake_table.c:1848-1882`) `[verified-by-code]`.
  `postgresEndForeignScan` calls `ReleasePGDuckConnection` (`:1916-1928`).
- **Whole-query path.** When `pg_lake_table.enable_full_query_pushdown` is on
  (default true) and the query references only lake tables with no
  scroll-cursor, `LakeTablePlanner` first runs the normal planner, then — if
  `FullQueryIsPushdownable(originalQuery)` — calls `GeneratePushdownPlan`, whose
  `GeneratePushdownScan` builds a lone `CustomScan` with
  `methods = &QueryPushdownScanMethods` and the deparsed-for-DuckDB query in
  `custom_private` (`pg_lake_table/src/planner/query_pushdown.c:280-319`,
  `GeneratePushdownScan` makes the `CustomScan` + an `RTE_RESULT` range-table
  entry) `[verified-by-code]`. At exec time `QueryPushdownScanNextInternal`
  drives the pgduck connection in **single-row mode**, reading `PGRES_SINGLE_TUPLE`
  results and converting `PQgetvalue` text into datums `[verified-by-code]`.

The `CustomScan` here is a near-twin of pg_duckdb's, but where pg_duckdb hands
the query to an *in-process* `duckdb::Connection`, pg_lake hands it to a *remote*
`PGconn`. The executor's `ExecProcNode` contract is satisfied by adapting
libpq result rows back into `TupleTableSlot`s. Cross-ref
`[[knowledge/subsystems/executor]]`, `[[knowledge/ideologies/pg_duckdb]]`
(in-process vs out-of-process is the entire difference), `[[knowledge/subsystems/optimizer]]`.

### 3. The "remote server" is DuckDB wearing the Postgres wire protocol

pg_lake reuses libpq as its IPC. `GetPGDuckConnection` does
`PQconnectdb(PgduckServerConninfo)` where `PgduckServerConninfo` defaults to
`"host=/tmp port=5332"` — a Unix-domain socket, not TCP
(`pg_lake_engine/src/pgduck/client.c:133-168`,
`pg_lake_engine/include/pg_lake/pgduck/client.h:25`) `[verified-by-code]`.
Connections are cached in an `HTAB` keyed by a monotonically-incrementing
`ConnectionId`, tagged with `GetCurrentSubTransactionId()` so subtransaction
abort can reap them (`client.c:154-167`, the `PgDuckConnectionHash`). Errors
from DuckDB are surfaced as `ereport(ERROR, ... "could not start query engine")`
/ `"lost connection to query engine"` (`client.c:147-150`, `:222`), and in
non-assert builds the raw DuckDB error is deliberately hidden ("hide internals
from users", `:149`) `[from-comment]`. The client implements its own
cancel-query handshake (`StartCancelQuery`/`FinishCancelQuery`,
`client.c:51-52`) so a Postgres statement-cancel propagates to the DuckDB side.
This makes `pgduck_server` look, from libpq's vantage, exactly like a remote
Postgres — which is precisely why the FDW could be derived from `postgres_fdw`.
Cross-ref `[[knowledge/idioms/error-handling]]`,
`[[knowledge/architecture/process-model]]`.

### 4. MVCC over an immutable Iceberg snapshot model — catalog is real PG state, data is append-only snapshots

pg_lake gets crash-safety/transactions for the *catalog* because the Iceberg
catalog is stored in **ordinary Postgres tables** mutated via SPI:
`InsertInternalIcebergCatalogTable` / `InsertExternalIcebergCatalogTable` /
`DeleteInternalIcebergCatalogTable` all `SPI_EXECUTE` INSERT/DELETE against
catalog relations (`pg_lake_iceberg/src/iceberg/catalog.c:49-72`, `:162-186`,
`:194-214`) wrapped in `SPI_START_EXTENSION_OWNER(PgLakeIceberg)` …`SPI_END()`
`[verified-by-code]`. The user-visible `iceberg_tables` view
(`README.md:135`) is one such relation. So a table's *current snapshot pointer*
(its `metadata_location`) lives in MVCC-protected PG rows, while the snapshot's
*data* is immutable Parquet referenced by Iceberg manifests.

The transaction callback reconciles the two worlds at commit:
`IcebergXactCallback` (`transaction_hooks.c:37-88`) `[verified-by-code]`:

- On `XACT_EVENT_PRE_COMMIT`, it `PushActiveSnapshot(GetTransactionSnapshot())`,
  calls `ConsumeTrackedIcebergMetadataChanges(false)` — flushing buffered
  Iceberg manifest/metadata writes to object storage — then pops the snapshot.
  A comment notes core "does not expect a snapshot to be left active at this
  point," so it pushes one transiently (`:46-58`) `[from-comment]`.
- On `XACT_EVENT_COMMIT`, it `PostAllRestCatalogRequests()` — the REST-catalog
  commit is fired *after* the PG commit (`:80-86`).
- On `XACT_EVENT_ABORT`, it resets tracked metadata + REST requests (`:63-69`).
- On `XACT_EVENT_PREPARE`, it **refuses two-phase commit** if any Iceberg
  metadata changed: `ereport(ERROR, ... "cannot prepare a transaction that has
  Iceberg metadata changes")` (`:70-78`) `[verified-by-code]` — because the
  object-store/REST commit cannot participate in PG's 2PC. This is a candid
  admission of the seam: PG's transaction manager and the Iceberg/REST commit
  are *coordinated*, not *atomic*. Cross-ref `[[knowledge/architecture/mvcc]]`,
  `[[knowledge/architecture/wal]]` (no 2PC across the object store).

### 5. Catalog integration is dual: Iceberg catalog in PG tables, plus REST + object-store external catalogs

Unlike pg_duckdb (which fights *two* `pg_catalog`s), pg_lake keeps the Iceberg
catalog authoritative inside Postgres but also bridges to **external** Iceberg
catalogs. `catalog.c` distinguishes *internal* vs *external* catalog tables
(`InsertInternalIcebergCatalogTable` vs `InsertExternalIcebergCatalogTable`,
`catalog.c:49`, `:162`) and `ErrorIfSameTableExistsInExternalCatalog` checks
`(catalog_name, table_namespace, table_name)` uniqueness against the external
catalog before creating a table (`catalog.c:119-155`) `[verified-by-code]`. The
external side is split across `object_store_catalog/object_store_catalog.c` and
`rest_catalog/rest_catalog.c` (Iceberg REST catalog over HTTP, fired at commit
via `PostAllRestCatalogRequests`). Cross-ref
`[[knowledge/idioms/catalog-conventions]]`, `fmgr-and-spi` skill (the heavy SPI
usage for catalog mutation).

### 6. Pushdown is gated by an explicit shippability model, not by trusting the planner

Because compute is shipped to DuckDB, pg_lake must decide *per-expression*
whether DuckDB can evaluate it. `query_pushdown.c` carries an `IsShippableContext`
walker (`query_pushdown.c:79-94`) and helpers `ExpressionHasNonShippableObject`,
`ExpressionReturnsNonShippableType`, `ExpressionHasCollation` (`:104-106`)
`[verified-by-code]`, backed by curated allow-lists in the engine:
`shippable_builtin_functions.c`, `shippable_builtin_operators.c`,
`shippable_spatial_functions.c`. The GUC `pg_lake_table.enable_strict_pushdown`
(default true) restricts pushdown "only safe operators, functions and types"
(`pg_lake_table/src/init.c`) `[verified-by-code]`. Collations especially must be
stopped — DuckDB does not share PG's collation semantics. This per-symbol
shippability gate has no core analogue; it is the price of a heterogeneous
execution engine. Cross-ref `[[knowledge/subsystems/optimizer]]`,
`[[knowledge/idioms/node-types-and-lists]]`.

## Notable design decisions (cited)

- **Permission checks re-grafted onto the pushdown plan.** Since
  `GeneratePushdownScan` builds a fresh plan with no `permInfos`, `AppendPermInfos`
  concatenates the *local* plan's `permInfos`/`rtable` onto the pushdown plan and
  rebases `perminfoindex`, "to ensure that the permission checks are enforced
  correctly" — they could not easily re-derive column-level usage on the pushed
  query (`query_pushdown.c:204-248`) `[verified-by-code]` `[from-comment]`. Same
  class of problem pg_duckdb solved with hand-rolled `check_view_perms_recursive`.
- **Full-query pushdown is refused for scrollable cursors.** The hook checks
  `(cursorOptions & CURSOR_OPT_SCROLL) == 0` before substituting the pushdown
  plan (`query_pushdown.c:297-299`) `[verified-by-code]` — the single remote
  cursor cannot scan backward, the same limitation pg_duckdb wraps in a
  `Material` node.
- **INSERT…SELECT has its own pushdown path.** When the query is not a plain
  pushdownable SELECT, `IsPushdownableInsertSelectQuery` →
  `GenerateInsertSelectPushdownPlan` lets DuckDB write the Iceberg data files
  directly (`query_pushdown.c:301-318`) `[verified-by-code]`, gated by
  `pg_lake_table.enable_insert_select_pushdown`.
- **Data-file & partition pruning happen on the PG side from Iceberg stats.**
  GUCs `enable_data_file_pruning` / `enable_partition_pruning` (both `PGC_SUSET`,
  default true) prune Parquet files using Iceberg manifest min/max statistics
  *before* shipping to DuckDB (`pg_lake_table/src/init.c`) `[verified-by-code]` —
  a BRIN-like skip done at the metadata layer, outside any index AM.
- **Commit-time ANALYZE threshold.** `commit_time_analyze_threshold` counts
  data-file ADD/REMOVE ops in a transaction and triggers `ANALYZE` on the
  pg_lake catalog relations (`pg_lake_table/src/init.c`) `[verified-by-code]` —
  the planner's row estimates depend on catalog stats, not heap stats.
- **`USING iceberg` AM handler is a hard-error placeholder**
  (`access_method.c:31-35`) — the AM is a routing shim, never a storage engine.
- **DuckDB error text hidden in production builds** (`client.c:146-151`) —
  internals leak only under `USE_ASSERT_CHECKING`.

## Links into corpus

- `[[knowledge/ideologies/pg_duckdb]]` — the mirror-image sibling: same DuckDB
  engine, same `CustomScan`-wraps-the-query trick, same stub table AM, but
  pg_duckdb embeds `libduckdb` **in-process** while pg_lake isolates it in
  `pgduck_server` and talks libpq. The single most important cross-reference.
- `[[knowledge/ideologies/cstore_fdw]]` — the prior "FDW-as-storage / bypass
  smgr+WAL" case; pg_lake also bypasses the durability stack but stores Parquet
  in S3 and keeps the catalog in MVCC PG tables.
- `[[knowledge/ideologies/hydra-columnar]]` — fellow columnar/analytics lineage.
- `[[knowledge/subsystems/foreign]]` — the `FdwRoutine`/`postgres_fdw` machinery
  pg_lake_table repurposes (its `postgres*` function names are the tell).
- `[[knowledge/subsystems/optimizer]]` — `planner_hook` + `set_rel_pathlist_hook`
  + `GetForeignUpperPaths` are where whole-query pushdown is decided; the
  shippability model lives here.
- `[[knowledge/subsystems/executor]]` — `CustomScan`/`CustomScanState` adapting
  remote libpq single-row results into `TupleTableSlot`s.
- `[[knowledge/subsystems/access-methods]]` + `access-method-apis` skill — the
  placeholder `USING iceberg` table AM.
- `[[knowledge/architecture/mvcc]]` + `[[knowledge/architecture/wal]]` — the
  catalog-in-PG / data-in-Iceberg split and the `XACT_EVENT_PREPARE` 2PC refusal.
- `[[knowledge/idioms/catalog-conventions]]` + `fmgr-and-spi` skill — Iceberg
  catalog mutation via SPI.
- `[[knowledge/idioms/error-handling]]` — the "lost connection to query engine"
  ereport bridge over libpq.
- `.claude/skills/extension-development/SKILL.md` — multi-extension monorepo,
  `requires` dependency chains, `planner_hook`/`set_rel_pathlist_hook` chaining,
  `RegisterXactCallback`.

## Sources

Fetched 2026-06-15 (branch `main`):

- `https://api.github.com/repos/Snowflake-Labs/pg_lake/git/trees/main?recursive=1`
  @ 2026-06-15 → HTTP 200 (tree listing; ~8-extension monorepo).
- `https://raw.githubusercontent.com/Snowflake-Labs/pg_lake/main/README.md`
  @ 2026-06-15 → HTTP 200 (240 lines).
- `.../main/pg_lake/pg_lake.control` → HTTP 200 (8 lines).
- `.../main/pg_lake_table/pg_lake_table.control` → HTTP 200 (8 lines).
- `.../main/pg_lake_table/src/fdw/pg_lake_table.c` → HTTP 200 (5893 lines; read
  the `FdwRoutine` fill + Iterate/End scan; skimmed the modify path).
- `.../main/pg_lake_table/src/access_method/access_method.c` → HTTP 200 (80 lines).
- `.../main/pg_lake_table/src/planner/query_pushdown.c` → HTTP 200 (1932 lines;
  read `LakeTablePlanner`, `AppendPermInfos`, `GeneratePushdownScan`, exec-scan).
- `.../main/pg_lake_table/src/transaction/transaction_hooks.c` → HTTP 200 (88 lines).
- `.../main/pg_lake_table/src/init.c` → HTTP 200 (GUC definitions; grepped).
- `.../main/pg_lake_engine/src/pgduck/client.c` → HTTP 200 (975 lines; the
  pgduck_server libpq bridge).
- `.../main/pg_lake_engine/include/pg_lake/pgduck/client.h` → HTTP 200
  (`DEFAULT_PGDUCK_SERVER_CONNINFO "host=/tmp port=5332"`).
- `.../main/pg_lake_iceberg/src/iceberg/catalog.c` → HTTP 200 (699 lines;
  internal/external Iceberg catalog SPI mutation).

**File choices & gaps.** The manifest hint was just `README.md`; from the tree I
picked the FDW handler, the planner pushdown, the access-method placeholder, the
transaction hooks, the pgduck client, and the Iceberg catalog — the spine of
"how Iceberg tables are represented, where execution happens, and how the catalog
integrates." All cites are `[verified-by-code]` against the fetched files except
the end-user feature narrative, the pgduck_server/duckdb_pglake split, and the
project history, which are `[from-README]`. NOT deep-read (so claims about them
are `[inferred]`/`[from-README]`): the DuckDB side (`duckdb_pglake/*`, C++), the
Iceberg manifest/snapshot serializers (`pg_lake_iceberg/src/iceberg/api/*`,
`write_manifest.c`, `read_table_metadata.c`), `pg_lake_copy` (the COPY-to-S3
path), the REST/object-store catalog internals (`rest_catalog.c`,
`object_store_catalog.c`), and `pg_extension_base` (the worker framework). The
`btree_gist` dependency rationale is `[inferred]`.
