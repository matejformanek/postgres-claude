# documentdb — a MongoDB-compatible document store shipped as a native BSON type + a C-implemented CRUD API, not a parser hook

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `microsoft/documentdb` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> blobs fetched on 2026-07-11 (see Sources footer). Line numbers are for the
> `main` blobs as fetched. This is a large multi-directory C repo; only ~7
> high-signal files were read, so structural/architectural claims spanning
> unread files are tagged `[inferred]`.

documentdb is the PostgreSQL backend that FerretDB (and the bundled
`pg_documentdb_gw` gateway) targets to serve the MongoDB wire protocol: it
introduces a **native binary BSON datatype** and a **MongoDB-compatible
operator/function library** so that CRUD, aggregation, geospatial, full-text,
and vector workloads run inside a normal PostgreSQL backend (`README.md:3`)
`[from-README]`. **Headline divergence:** where `apache-age` rewrites the
query tree and `pg_graphql` resolves a foreign schema, documentdb hooks
*nothing* in the parser/planner grammar. It ships an entire alternate
data-access API as **`LANGUAGE C` SQL-callable functions** (`command_insert`,
`command_update`, `command_delete`, `command_create_indexes`, the aggregation
pipeline) over a **custom `bson` base type** with its own I/O functions
(`bson_in`/`bson_out`/`bson_recv`/`bson_send`, `bson_io.c:60-63`)
`[verified-by-code]` and its own **GIN/RUM operator classes** whose strategy
numbers encode Mongo query operators (`$gt`, `$in`, `$elemMatch`, `$regex`,
`bson_gin_core.c:499-937`) `[verified-by-code]`. The Mongo semantics live in C
functions and index opclasses, reached by SQL the gateway generates — not in
new SQL grammar.

## Domain & purpose

"`DocumentDB` is a MongoDB compatible open source document database built on
PostgreSQL … enabling seamless CRUD … operations on BSON (Binary JSON) data
types within a PostgreSQL framework" (`README.md:3`) `[from-README]`. The
project is **three components** (`README.md:11-13`) `[from-README]`:

- **`pg_documentdb_core`** — "PostgreSQL extension introducing BSON datatype
  support and operations for native Postgres" (`README.md:11`). This is the
  type layer: the `bson` base type + libbson wiring.
- **`pg_documentdb`** — "The public API surface for DocumentDB providing CRUD
  functionality on documents in the store" (`README.md:12`). This is the
  `documentdb_api` C function library.
- **`pg_documentdb_gw`** — "The gateway protocol translation layer that
  converts the user's MongoDB APIs into PostgreSQL queries" (`README.md:13`).
  This is the wire-protocol server; FerretDB plays the same role externally.

The two-extension split is enforced by the control files: `documentdb_core`
requires nothing (`documentdb_core.control:6`), while `documentdb` requires
`documentdb_core, pg_cron, tsm_system_rows, vector, postgis`
(`documentdb.control:6`) `[verified-by-code]` — i.e. the API layer composes a
whole *stack* of extensions (pg_cron for background jobs, pgvector for vector
search, PostGIS for geospatial, tsm_system_rows for sampling) rather than
reimplementing them.

## How it hooks into PG

**Two shared libraries, both `shared_preload_libraries`-only.** Each extension
has its own `_PG_init` that hard-errors unless loaded at preload time
(`pg_documentdb_core.c:49-55`, `pg_documentdb.c:57-64`) `[verified-by-code]`.

- **Core init** installs a libbson memory vtable so libbson allocations route
  through `palloc`, then defines its GUCs and reserves the `documentdb_core`
  prefix (`pg_documentdb_core.c:57-62`) `[verified-by-code]`. Note the comment
  that a `service.so` may be the *real* `_PG_init` and the extension's own is
  skipped via `SkipDocumentDBCoreLoad` (`pg_documentdb_core.c:21-35,44-47`)
  `[verified-by-code]` — a hosted-service embedding hook.
- **API init** wires the full runtime: `InitApiConfigurations`,
  `InitializeSharedMemoryHooks`, a background worker
  (`InitializeDocumentDBBackgroundWorker` + `RegisterDocumentDBBackgroundWorkerJobs`),
  and `InstallDocumentDBApiPostgresHooks` (`pg_documentdb.c:66-84`)
  `[verified-by-code]`. `_PG_fini` calls `UninstallDocumentDBApiPostgresHooks`
  (`pg_documentdb.c:115-124`) `[verified-by-code]`.

**The `bson` base type.** `bson_io.c` declares the type I/O surface with
`PG_FUNCTION_INFO_V1`: `bson_out` (binary→canonical-extended-JSON *or* hex,
GUC-gated, `bson_io.c:81-97`), `bson_in` (JSON *or* hex → binary,
`bson_io.c:103-124`), plus `bson_recv`/`bson_send` for the binary protocol —
the latter two carry an honest `TODO … still relatively untested … used only
in the CREATE TYPE` comment (`bson_io.c:177-203`) `[from-comment]`. The type is
varlena/TOASTable: `bson_send` copies via `PG_DETOAST_DATUM_COPY`
(`bson_io.c:198-203`) `[verified-by-code]`. Alongside I/O it ships a broad
value-extraction surface (`bson_get_value`, `bson_object_keys` as an SRF,
`row_get_bson`, `bson_repath_and_build`, `bson_build_document`,
`bson_to_json_string`, hex/bytea casts — `bson_io.c:64-75`)
`[verified-by-code]`.

**The `documentdb_api` C CRUD surface.** Each Mongo verb is a SQL-callable C
function. `insert.c` alone exports `command_insert`, `command_insert_one`,
`command_insert_worker`, `command_insert_bulk`, and `command_insert_txn_proc`
(`insert.c:96-100`) `[verified-by-code]`; the function-vs-procedure split
exists because the bulk procedure commits per batch and refuses to run inside a
transaction block (`insert.c:182-211`) `[verified-by-code]`. Sibling files
(`update.c`, `delete.c`, `create_indexes.c`, `aggregation/…`) follow the same
pattern `[inferred]`.

**Opclasses.** `bson_gin_core.c` implements the GIN extract/consistent
callbacks over BSON (`bson_gin_core.c:5-8` cites the PG GIN-extensibility docs)
`[from-comment]`; the consistent core dispatches on a **BSON-specific strategy
enum** (`GinBsonConsistentCore` switch, `bson_gin_core.c:499-937`)
`[verified-by-code]`.

## Where it diverges from core idioms

### 1. BSON as a first-class base type, not core jsonb

Core's document type is `jsonb` (binary, but a fixed encoding with core-owned
operators). documentdb ships its **own** `bson` varlena type with libbson as
the encoder, its own extended-JSON and hexadecimal text representations
(switchable by the `BsonTextUseJsonRepresentation` GUC, `bson_io.c:87-94`)
`[verified-by-code]`, and a whole SQL→BSON value marshaller
(`PgbsonElementWriterWriteSQLValue`) that maps PG scalar types into BSON value
types — `int8`→int32/int64 by range, `numeric`→decimal128-then-narrowed,
`uuid`→BSON binary subtype UUID, arrays recursively
(`bson_io.c:629-834`) `[verified-by-code]`. This is the jsonb road not taken:
rather than lean on core jsonb / the `.claude/skills/jsonpath-and-jsonb` road,
it re-owns the binary format so it can be byte-compatible with MongoDB's BSON.

### 2. An alternate CRUD API as C functions, not SQL grammar

Every Mongo operation is a `Datum command_*(PG_FUNCTION_ARGS)` entry point that
takes a BSON command document and returns a BSON response
(`insert.c:170-234`) `[verified-by-code]`. There is no `INSERT … MONGO`
grammar; the gateway/FerretDB emits ordinary `SELECT
documentdb_api.insert(...)` calls. This is the axis that separates documentdb
from `[[knowledge/ideologies/apache-age.md]]` (query-tree substitution) and
`[[knowledge/ideologies/pg_graphql.md]]` (schema reflection): documentdb keeps
the SQL grammar untouched and puts *all* Mongo semantics behind `fmgr` — see
`.claude/skills/fmgr-and-spi`. Internally the functions build and run plans
directly (`CreateLocalShardInsertPlan` / `ExecuteLocalShardInsertPlan`,
`insert.c:142-145`) `[verified-by-code]`, blending fmgr entry with hand-built
executor plans.

### 3. RUM (not stock GIN) is the default index AM, with Mongo-operator strategy numbers

`GetIndexAmHandlerByName` defaults every index to the **`rum`** access method
and only honours an alternate AM if it advertises the needed capability, else
falls back to `rum` (`create_indexes.c:463-492`) `[verified-by-code]`. RUM is a
third-party GIN-derivative extension; documentdb even hardcodes RUM's term-size
limit (`_RUM_TERM_SIZE_LIMIT 2712`, `create_indexes.c:192-201`)
`[verified-by-code]`. Indexes are created by **generating a `CREATE INDEX …
USING rum(…)` SQL string at runtime** against the physical shard table
(`create_indexes.c:5230-5250`) `[verified-by-code]` — DDL-as-string rather than
a catalog-time opclass declaration. The opclass consistent/extract functions
switch on a custom `BsonIndexStrategy` enum whose members are Mongo query
operators — `BSON_INDEX_STRATEGY_DOLLAR_GREATER`, `…_DOLLAR_IN`,
`…_DOLLAR_ELEMMATCH`, `…_DOLLAR_REGEX`, `…_DOLLAR_BITS_ALL_SET`, etc.
(`bson_gin_core.c:511-937`) `[verified-by-code]`. Geospatial indexes instead
generate `USING GIST(bson_validate_geometry(...))` (`create_indexes.c:5389-5413`)
`[verified-by-code]`, delegating to PostGIS. Cross-ref
`[[knowledge/idioms/gin-scan-and-consistent.md]]`,
`[[knowledge/idioms/gin-tree-structure.md]]`,
`.claude/skills/access-method-apis`.

### 4. Its own background/sharding/distribution machinery

The API `_PG_init` registers a background worker and cron-scheduled jobs
(`pg_documentdb.c:72-74`, and the `pg_cron` requires clause,
`documentdb.control:6`) `[verified-by-code]`. `api_hooks.c` defines a large
table of **extension-internal hook function pointers** for cluster
distribution — `run_command_on_metadata_coordinator_hook`,
`distribute_postgres_table_hook`, `is_shard_table_for_documentdb_table_hook`,
`handle_colocation_hook`, index-build scheduling hooks, external-identity-provider
user hooks (`api_hooks.c:29-83`) `[verified-by-code]`. These are set NULL by
default and filled in by a distribution layer (Citus-style), so the same code
runs single-node or sharded. This is a private plugin seam *inside* the
extension, distinct from PG's own `_hook` globals. Cross-ref
`[[knowledge/ideologies/citus.md]]`, `.claude/skills/bgworker-and-extensions`.

### 5. Its own schema/catalog conventions

documentdb owns a family of schemas rather than living in the user's schema:
physical documents land in `documentdb_data.documents_<collectionId>`
(`create_indexes.c:5232`) `[verified-by-code]`; index metadata is recorded in
`ApiCatalogSchemaName.collection_indexes` (`create_indexes.c:553`)
`[verified-by-code]`; the public API is `documentdb_api` (optionally
`documentdb_api_v2` under an RBAC GUC, `pg_documentdb.c:91-96`)
`[verified-by-code]`; the type/operators live in `documentdb_core`. Collections
are looked up through a `MongoCollection` cache
(`GetMongoCollectionByNameDatum`, `insert.c:268-270`) `[verified-by-code]`.
This is a self-contained metadata catalog rather than reuse of user tables —
cross-ref `[[knowledge/idioms/catalog-conventions.md]]`,
`.claude/skills/catalog-conventions`.

## Notable design decisions (cited)

- **Errors carry Mongo-style SQLSTATEs.** Validation failures use
  `ERRCODE_DOCUMENTDB_BADVALUE` and named location codes like
  `ERRCODE_DOCUMENTDB_LOCATION40236` (`bson_io.c:420-502`) `[verified-by-code]`
  — a private errcode namespace mirroring MongoDB error numbers.
- **SQL NULL is written as BSON null before any detoast**, with an explicit
  comment that a by-ref 0 Datum would otherwise crash the backend
  (`bson_io.c:633-646`) `[verified-by-code]` — a hard-won marshalling
  invariant.
- **`numeric` is routed through decimal128 then narrowed** to int32/int64/double
  when the value is a fixed integer or fits a double (`bson_io.c:772-819`)
  `[verified-by-code]`, preserving Mongo's numeric-type fidelity.
- **libbson memory routed through `palloc`** via a per-`.so` vtable installed at
  init, because each shared object statically links its own libbson copy
  (`pg_documentdb_core.c:31-35,57`, `pg_documentdb.c:39-43,66`)
  `[verified-by-code]`.
- **Bulk insert is a procedure that commits per batch** and is forbidden inside
  a transaction block, unlike the transactional `command_insert` function
  (`insert.c:181-211`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/apache-age.md]]` — the contrast case: AGE bends the
  query tree; documentdb leaves grammar untouched, putting semantics in C
  functions + opclasses.
- `[[knowledge/ideologies/pg_graphql.md]]` — another "alternate API over PG";
  resolves a schema rather than shipping a base type.
- `[[knowledge/ideologies/citus.md]]` — the distribution layer documentdb's
  `api_hooks.c` seam is designed to plug into.
- `[[knowledge/idioms/gin-scan-and-consistent.md]]` /
  `[[knowledge/idioms/gin-tree-structure.md]]` — the GIN extract/consistent
  machinery documentdb specializes over BSON (via RUM).
- `[[knowledge/idioms/catalog-conventions.md]]`,
  `[[knowledge/idioms/fmgr.md]]`, `[[knowledge/idioms/spi.md]]` — schema family +
  fmgr CRUD entry points that build/run plans internally.
- `.claude/skills/access-method-apis` (opclass/strategy-number surface),
  `.claude/skills/jsonpath-and-jsonb` (the core jsonb road not taken),
  `.claude/skills/fmgr-and-spi`, `.claude/skills/extension-development`,
  `.claude/skills/bgworker-and-extensions`, `.claude/skills/catalog-conventions`
  — the C-extension mechanics used.

## Anthropology takeaway

documentdb is the corpus's clearest example of "build a whole database on top
of PG without touching PG's front door." It adds no grammar, no planner hook,
no rewrite pass — instead it (a) mints a native `bson` base type byte-compatible
with MongoDB, (b) exposes every Mongo verb as a SQL-callable C function that the
wire gateway calls, (c) teaches GIN/RUM opclasses a Mongo-operator strategy
vocabulary, and (d) composes an ecosystem of existing extensions (RUM, pgvector,
PostGIS, pg_cron, Citus-style hooks) rather than reimplementing them. The
reusable pattern for the corpus: a MongoDB *compatibility surface* is
achievable purely through the type system + fmgr + custom opclasses + generated
DDL, with the parser left entirely stock — the inverse of the `apache-age`
query-tree-substitution strategy. Worth a dedicated idiom note is the
"strategy-number-as-domain-operator" trick (`bson_gin_core.c`), where GIN
strategy integers are repurposed to carry `$gt`/`$in`/`$elemMatch` semantics.

## Sources

All fetched 2026-07-11, branch `main`, via
`https://raw.githubusercontent.com/microsoft/documentdb/main/<path>`:

- `README.md` — 200 (169 lines; components split, BSON purpose — `[from-README]`).
- `pg_documentdb/documentdb.control` — 200 (6 lines; requires
  documentdb_core/pg_cron/tsm_system_rows/vector/postgis).
- `pg_documentdb_core/documentdb_core.control` — 200 (6 lines; requires none).
- `pg_documentdb_core/src/io/bson_io.c` — 200 (839 lines; BSON type I/O,
  SQL→BSON marshaller — deep-read).
- `pg_documentdb_core/src/pg_documentdb_core.c` — 200 (71 lines; core
  `_PG_init`, libbson vtable — deep-read).
- `pg_documentdb/src/pg_documentdb.c` — 200 (124 lines; API `_PG_init`, bgworker,
  hooks, RBAC schema — deep-read).
- `pg_documentdb/src/api_hooks.c` — 200 (779 lines; distribution hook-pointer
  table — grepped, header + hook list read).
- `pg_documentdb/src/commands/insert.c` — 200 (1895 lines; `command_insert*`
  CRUD entry points — top ~280 lines read + grepped).
- `pg_documentdb/src/commands/create_indexes.c` — 200 (7181 lines; RUM default
  AM, generated `CREATE INDEX … USING rum`, GIST geospatial — grepped +
  targeted reads).
- `pg_documentdb/src/opclass/bson_gin_core.c` — 200 (4179 lines; GIN
  consistent/extract, `BSON_INDEX_STRATEGY_*` — grepped + targeted reads).
- `pg_documentdb_core/include/io/bson_core.h` — 200 (probe/header only).

**Coverage limits.** This is a very large repo (`create_indexes.c` and
`bson_gin_core.c` alone are >11k lines) and only ~7 files were read in depth;
`update.c`, `delete.c`, the `aggregation/` pipeline, `metadata/collection.c`,
the RUM-integration/index-AM glue, and all SQL install scripts were **not**
fetched. 404s during probing (expected — wrong path guesses): `*.control.in`,
`pg_documentdb_core/src/types/pgbson.c`, `.../src/bson/*.c`,
`pg_documentdb/src/documentdb.c`, `.../opclass/bson_rum.c`,
`.../index_am/documentdb_rum.c` — the real layout is
`pg_documentdb_core/src/io/` and `pg_documentdb/src/{commands,opclass}/`. Claims
about sibling CRUD files, the RUM linkage internals, the aggregation pipeline,
and the sharding/distribution runtime are tagged `[inferred]` because the
backing files were not read. The GitHub tree/API was blocked this run, so paths
were probed directly with `curl` HEAD checks rather than enumerated.
