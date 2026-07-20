# mongo_fdw — an FDW onto a schemaless document store

- **Repo:** github.com/EnterpriseDB/mongo_fdw (branch `master`,
  default_version `1.1`, `mongo_fdw.control:6`). Portions ex-Citus Data.
- **Fetched:** `README.md` (501 lines), `mongo_fdw.control`, `Makefile`,
  `mongo_fdw.c` (4735 lines), `mongo_query.c` (1834 lines), `connection.c`
  (227 lines).

## Domain & purpose

A Foreign Data Wrapper mapping **MongoDB collections** to PostgreSQL foreign
tables. Where the reference wrapper
[[knowledge/subsystems/contrib-postgres_fdw]] bridges SQL→SQL over libpq,
`mongo_fdw` bridges SQL→**BSON documents** over the MongoDB C driver
(`libmongoc` / `libbson`). It is read/write (INSERT/UPDATE/DELETE), maintains a
session connection pool, and pushes down WHERE, JOIN, ORDER BY, and a limited
set of aggregates (`min/max/sum/avg/count`) into MongoDB's aggregation pipeline
(`README.md:28-70`).

## How it hooks into PG

Standard FDW plumbing: `mongo_fdw_handler` fills an `FdwRoutine`
(`mongo_fdw.c:336-355`) with `GetForeignRelSize` / `GetForeignPaths` /
`GetForeignPlan` / `BeginForeignScan` / `IterateForeignScan` for reads and
`ExecForeignInsert` / `ExecForeignUpdate` / `ExecForeignDelete` for writes —
the callback set documented in [[knowledge/idioms/fdw-routine-callbacks]]. The
scan loop is the classic pattern of [[knowledge/idioms/fdw-iterate-scan]]:
`mongoIterateForeignScan` pulls the next BSON document from the driver cursor
and materialises a slot.

The driver library is initialised process-globally in `_PG_init` via
`mongoc_init()` (`mongo_fdw.c:325`) and torn down in `_PG_fini` with
`mongoc_cleanup()` (`:387`) — a departure point from postgres_fdw, which has no
external library state to bootstrap. Three planner GUCs toggle pushdown:
`mongo_fdw.enable_join_pushdown`, `enable_order_by_pushdown`,
`enable_aggregate_pushdown` (`mongo_fdw.c:276-301`).

## Where it diverges from core idioms

- **The document/relation impedance mismatch is the whole game.** A MongoDB
  document is schemaless and nested; a PG tuple is a fixed, typed rowtype.
  `column_mapping_hash` (`mongo_fdw.c:1968`) builds a hash keyed by BSON field
  name → `(attnum, atttypid)`, and `fill_tuple_slot` (`:2104`) walks the BSON
  document, looks each key up in that hash, checks `column_types_compatible`
  (`:192`) between the BSON type tag and the PG column type, and converts. This
  runtime BSON-type-vs-declared-type reconciliation has no analogue in
  postgres_fdw, where the remote already speaks the SQL type system.
- **Nested fields via dotted column names.** The mapping supports
  `_id.<field>` style keys — `column_mapping_hash` synthesises hash keys like
  `psprintf("_id.%s", columnName)` (`mongo_fdw.c:2052`) so a PG column can
  target a sub-field of the Mongo document. Flattening a nested store into flat
  columns is done in the mapping layer, not by the remote.
- **`_id` is a mandatory, special first column.** The row identity is Mongo's
  12-byte ObjectId. The wrapper hard-requires the foreign table's first column
  to be named `_id` (`mongo_fdw.c:1687-1688,1788,1872`) and, on INSERT, refuses
  a user-supplied `_id`, telling MongoDB to generate it
  (`:1697-1705`). Row identity is registered with `add_row_identity_var`
  (`:1760`) rather than the ctid/system-column machinery a heap-backed table
  would use.
- **Query translation targets BSON, not a SQL string.** `mongo_query.c` builds
  a BSON query/pipeline document from the pushed-down quals rather than
  deparsing SQL text; aggregate pushdown emits pipeline stages whose results
  come back under a synthetic `AGG_RESULT_KEY` that `fill_tuple_slot`
  special-cases (`mongo_fdw.c:2205`). Contrast postgres_fdw's `deparse.c`,
  which emits remote SQL.
- **Connection pool keyed by user mapping, holding a driver handle.**
  `connection.c` keeps a `ConnectionHash` HTAB of `ConnCacheEntry`
  (`connection.c:39-51`) keyed by `(userid, umid)` (`:96-101`), each caching a
  live `mongoc_client_t`. This mirrors postgres_fdw's per-user-mapping cache
  shape but stores an opaque driver object instead of a `PGconn`, and it is a
  deliberate fix for the older "new connection per query" behaviour
  (`README.md:37-42`).

## Notable design decisions

- **Pushdown is conservative by construction.** JOIN pushdown is limited to
  INNER and one-sided OUTER joins between exactly two base foreign tables with
  only relational/arithmetic join operators, explicitly to *"avoid any
  potential join failure"* (`README.md:44-53`); aggregate pushdown is capped at
  five functions. `pushdown_safe` / `is_agg_scanrel_pushable` /
  `is_order_by_pushable` flags on the `fpinfo` gate each
  (`mongo_fdw.c:430,490,493`). The wrapper prefers to fetch-and-compute-locally
  rather than mistranslate.
- **Relation names are quoted into the remote namespace.**
  `mongoGetForeignRelSize` composes the remote target with `quote_identifier`
  on database and collection (`mongo_fdw.c:476-480`) — the collection plays the
  role of a table.
- **`relocatable = true`** (`mongo_fdw.control:8`) — no schema-pinned objects,
  unlike `anon`'s `relocatable = false`.

## Links into corpus

- [[knowledge/subsystems/contrib-postgres_fdw]] — the reference SQL→SQL
  wrapper; the baseline every divergence above is measured against.
- [[knowledge/subsystems/foreign]] — the core SQL/MED / `FdwRoutine`
  infrastructure.
- [[knowledge/idioms/fdw-routine-callbacks]] — the callback set `mongo_fdw_handler`
  populates.
- [[knowledge/idioms/fdw-iterate-scan]] — the per-tuple scan loop shape.
- [[knowledge/subsystems/contrib-file_fdw]] — the other core FDW, for the
  "read-only, no pushdown" end of the spectrum.
- Sibling non-SQL-source FDWs in this corpus: [[knowledge/ideologies/duckdb_fdw]],
  [[knowledge/ideologies/clickhouse_fdw]], [[knowledge/ideologies/ogr_fdw]],
  [[knowledge/ideologies/parquet_s3_fdw]], [[knowledge/ideologies/sqlite_fdw]],
  [[knowledge/ideologies/tds_fdw]] — mongo_fdw is the document-store point on
  that map.

## Sources

- `https://raw.githubusercontent.com/EnterpriseDB/mongo_fdw/master/README.md`
- `https://raw.githubusercontent.com/EnterpriseDB/mongo_fdw/master/mongo_fdw.control`
- `https://raw.githubusercontent.com/EnterpriseDB/mongo_fdw/master/mongo_fdw.c`
- `https://raw.githubusercontent.com/EnterpriseDB/mongo_fdw/master/mongo_query.c`
- `https://raw.githubusercontent.com/EnterpriseDB/mongo_fdw/master/connection.c`
- `Makefile` fetched for build shape (libmongoc/libbson linkage).

Confidence: `[verified-by-code]` for the FdwRoutine wiring, `_id` handling,
column-mapping/BSON conversion, and connection cache; `[from-README]` for the
pushdown scope limits and the connection-pooling rationale. `mongo_query.c`'s
BSON pipeline builder was grepped, not read line-by-line — the aggregate/JOIN
translation details beyond the cited flags are `[inferred]`.
