# sqlite_fdw — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgspider/sqlite_fdw` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-23 (see Sources footer).

sqlite_fdw is a SQLite Foreign Data Wrapper: it makes a SQLite database *file*
appear as a set of PostgreSQL foreign tables, with qual / join / aggregate /
ORDER BY / LIMIT push-down, INSERT/UPDATE/DELETE, batch insert, TRUNCATE, ANALYZE,
IMPORT FOREIGN SCHEMA, and (optionally) SpatiaLite↔PostGIS geometry transport
(`README.md:38-92`) `[from-README]`. Structurally it is a **near-verbatim fork of
in-core `postgres_fdw`** — same `SqliteFdwRelationInfo`, same `fdw_private` list
slots, same xact/subxact callback skeleton, same join/upper-rel push-down
machinery, with every function renamed `sqlite*`. **Headline divergence:** the
"remote server" is not a server at all but an *embedded `sqlite3*` library handle
opened on a local file in the backend's own address space, and SQLite's
**dynamic per-value type affinity** collides with PostgreSQL's static per-column
types — so the FDW grows an entire data-normalization layer (`sqlite_data_norm.c`)
of SQLite C functions that it *registers into every connection* and then *wraps
around column references in the deparsed SELECT* to coerce affinity at the source
before the value crosses into PG.

## Domain & purpose

The control comment is just `'SQLite Foreign Data Wrapper'`
(`sqlite_fdw.control:2`), default version `1.1`, `relocatable = true`
(`sqlite_fdw.control:3-5`) `[verified-by-code]`. Where postgres_fdw answers
"talk to another Postgres over libpq", sqlite_fdw answers "talk to a SQLite file
on the same machine via the linked-in SQLite engine". A foreign server carries
`database` (file path), `keep_connections`, `force_readonly`; a foreign table
carries `table`; columns carry `key`, `column_name`, `column_type`
(`option.c:42-62`) `[verified-by-code]`. There is no host, port, user, or
password — postgres_fdw's whole auth/network surface is replaced by a filesystem
path and an open-mode flag.

## How it hooks into PG

- **Handler / validator**: `sqlite_fdw_handler` returns a `makeNode(FdwRoutine)`
  wired with the full callback set (`sqlite_fdw.c:435-493`) `[verified-by-code]`:
  scan, modify (incl. `AddForeignUpdateTargets`/`IsForeignRelUpdatable`), batch
  insert (`ExecForeignBatchInsert`/`GetForeignModifyBatchSize`, PG≥14), direct
  modify (`PlanDirectModify` …), `ExecForeignTruncate` (PG≥14),
  `AnalyzeForeignTable`, `ImportForeignSchema`, and join/upper push-down
  (`GetForeignJoinPaths`/`GetForeignUpperPaths`). `BeginForeignInsert`/
  `EndForeignInsert` exist but both `elog(ERROR, "Not support partition insert")`
  (`sqlite_fdw.c:1930-1942`) `[verified-by-code]`. `sqlite_fdw_validator`
  validates option names with a PG≥16 `initClosestMatch` "did you mean" hint and
  bool/int value checks (`option.c:76-177`) `[verified-by-code]`.
- **`_PG_init` is nearly empty**: it only registers `on_proc_exit(&sqlite_fdw_exit)`
  which calls `sqlite_cleanup_connection()` (`sqlite_fdw.c:418-431`)
  `[verified-by-code]`. No shmem, no GUCs, no background worker, no
  `shared_preload_libraries` requirement — the whole extension lives in
  ordinary backend-local memory plus the SQLite library.
- **Version SRFs**: `sqlite_fdw_version`, `sqlite_fdw_sqlite_version`,
  `sqlite_fdw_sqlite_code_source` expose `CODE_VERSION` (20500,
  `sqlite_fdw.h:58`) and `sqlite3_libversion_number()`/`sqlite3_sourceid()`
  (`sqlite_fdw.c:496-512`) `[verified-by-code]`.
- **Connection-management SRFs**: `sqlite_fdw_get_connections`,
  `sqlite_fdw_disconnect`, `sqlite_fdw_disconnect_all` (`connection.c:59-61`,
  `702-888`) mirror postgres_fdw's same-named functions and `ereport` "not
  supported" below PG 14 (`connection.c:705-709`) `[verified-by-code]`.
- **IMPORT FOREIGN SCHEMA** drives SQLite's own catalog: it queries
  `sqlite_master` for non-`sqlite_%` tables, then runs `PRAGMA table_info(<t>)`
  per table to synthesize `CREATE FOREIGN TABLE` DDL (`sqlite_fdw.c:2887-3024`)
  `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. The "connection" is an in-process `sqlite3*` on a file, not a libpq session

The connection cache keeps postgres_fdw's exact shape — a backend-local `HTAB`
keyed by **foreign-server OID** (`ConnCacheKey = Oid`, `connection.c:32`),
created in `CacheMemoryContext` on first use, with `RegisterXactCallback` +
`RegisterSubXactCallback` + `CacheRegisterSyscacheCallback(FOREIGNSERVEROID, …)`
all registered once (`connection.c:94-128`) `[verified-by-code]`. But the cached
payload is a `sqlite3 *conn` (`connection.c:37`), obtained by
`sqlite3_open_v2(dbpath, &conn, flags, NULL)` (`connection.c:197`) — no
handshake, no auth, no network. Notable consequences of the embedded model:
- **Open-mode is a per-file flag**, not a role: `force_readonly` selects
  `SQLITE_OPEN_READONLY` vs `SQLITE_OPEN_READWRITE` (`connection.c:258`)
  `[verified-by-code]`.
- **Every freshly opened handle is mutated immediately**: `PRAGMA
  case_sensitive_like=1` is executed so SQLite `LIKE` matches PG semantics
  (`connection.c:202-204`), and `sqlite_fdw_data_norm_functs_init(conn)`
  installs the extension's normalization C functions into the handle
  (`connection.c:219`) `[verified-by-code]`. postgres_fdw has nothing analogous —
  there is no "open the remote and register functions into it".
- **The unit of cleanup is `sqlite3_close` + `sqlite3_finalize`**, not
  `PQfinish`. The cache entry holds a `List *stmtList` of live `sqlite3_stmt*`
  prepared statements (`connection.c:47`) that are finalized at xact end /
  disconnect (`connection.c:283`, `464-465`, `1043-1058`) `[verified-by-code]`.

### 2. Transactions are emulated with SQLite `BEGIN` / `SAVEPOINT` text commands

There is no two-phase remote protocol — `sqlite_begin_remote_xact` literally
`sqlite_do_sql_command(conn, "BEGIN", …)` when `xact_depth <= 0`, then stacks
`SAVEPOINT s<n>` strings to match `GetCurrentTransactionNestLevel()`
(`connection.c:357-390`) `[verified-by-code]`. Commit/abort issue `COMMIT` /
`ROLLBACK` / `RELEASE SAVEPOINT s<n>` / `ROLLBACK TO SAVEPOINT s<n>` as SQL text
(`connection.c:463`, `599`, `911`, `917-924`) `[verified-by-code]`. Two
genuinely SQLite-shaped wrinkles:
- **`SQLITE_BUSY` deferral**: `sqlite_do_sql_command` takes a `List
  **busy_connection`; on `SQLITE_BUSY` it stashes a `BusyHandlerArg` and returns
  rather than erroring, and the xact callback re-runs those commands after the
  hash scan completes (`connection.c:303-323`, `502-513`) `[verified-by-code]`.
  This is bespoke retry logic for SQLite's file-lock contention model, absent in
  postgres_fdw.
- **TRUNCATE deliberately runs *outside* a transaction**: because SQLite's
  `PRAGMA foreign_keys = ON` has no effect inside a transaction, `truncatable`
  connections skip `sqlite_begin_remote_xact` entirely (`connection.c:166-181`),
  and subxact handling skips them too (`connection.c:589-590`)
  `[from-comment]`. `XACT_EVENT_PRE_PREPARE` is hard-rejected — "cannot prepare a
  transaction that modified remote tables" (`connection.c:478-480`)
  `[verified-by-code]`.

### 3. SQLite's dynamic affinity vs PG static types → a whole normalization layer

This is the deepest divergence and the reason the codebase is far larger than a
postgres_fdw rename. SQLite stores a *type per value*, not per column
(`sqlite_data_norm.c:4-6` calls it "mixed affinity inputs for PostgreSQL data
column") `[from-comment]`. sqlite_fdw bridges it from both directions:
- **Read path coercion is pushed into the remote SQL.**
  `sqlite_deparse_column_ref` wraps each column reference (in non-DML context)
  with a SQLite function chosen by the PG column's type OID:
  `sqlite_fdw_float(col)` for FLOAT4/8/NUMERIC, `sqlite_fdw_bool(col)` for BOOL,
  `sqlite_fdw_uuid_blob(col)` for UUID, `sqlite_fdw_macaddr_int(col, len)` for
  MACADDR/MACADDR8, `json(col)` for JSON/JSONB (`deparse.c:2359-2457`)
  `[verified-by-code]`. "Popular" exactly-mapping types (INT4, TEXT, BYTEA,
  timestamps, …) are flagged `no_unification` and passed through bare
  (`deparse.c:2364-2382`) `[verified-by-code]`. So the deparser emits SQL that
  *normalizes affinity at the SQLite side* before any byte crosses into PG.
- **Those wrapper functions are SQLite UDFs the FDW defines.**
  `sqlite_fdw_data_norm_functs_init` calls `sqlite3_create_function` for
  `sqlite_fdw_uuid_blob`, `sqlite_fdw_uuid_str`, `sqlite_fdw_bool`,
  `sqlite_fdw_float`, `sqlite_fdw_macaddr_int/str/blob`, each registered
  `SQLITE_UTF8 | SQLITE_INNOCUOUS | SQLITE_DETERMINISTIC`
  (`sqlite_data_norm.c:741-757`) `[verified-by-code]`. The extension literally
  injects C code into the foreign engine — a move postgres_fdw could never make
  against a remote libpq server.
- **Row read uses `sqlite3_value` affinity to drive conversion.**
  `make_tuple_from_result_row` reads `sqlite3_column_value` + `sqlite3_value_type`
  per column and calls `sqlite_convert_to_pg(att, val, …, affinity, …)`
  (`sqlite_fdw.c:1400-1432`); `sqlite_convert_to_pg` switches on the *PG type OID*
  and validates the *SQLite affinity* against it, raising
  `ERRCODE_FDW_INVALID_DATA_TYPE` for disallowed combinations like FLOAT/BLOB
  into a BOOL column (`sqlite_query.c:71-120`) `[verified-by-code]`.

### 4. Result rows are pulled with `sqlite3_step` / `sqlite3_column_*`, not a tuplestore

`sqliteIterateForeignScan` calls `sqlite3_step(stmt)` once per call and builds a
virtual tuple from `SQLITE_ROW`, treating `SQLITE_DONE` as end-of-scan and
anything else as an error (`sqlite_fdw.c:1534-1553`) `[verified-by-code]`.
Parameters are bound just-in-time in `sqlite_create_cursor`
(`sqlite_fdw.c:1457-1458`) `[from-comment]`; the cursor is a single prepared
`sqlite3_stmt`, reset via `sqlite3_reset` on ReScan (`sqlite_fdw.c:1592-1597`)
`[verified-by-code]`. Row-at-a-time pull straight from the SQLite VM, vs
postgres_fdw's libpq cursor-fetch-into-tuplestore.

### 5. UPDATE/DELETE scans buffer the *entire* result first, because SQLite has no read/write isolation on one handle

When a scan is `for_update`, the first `IterateForeignScan` drains the whole
statement into a `festate->rows` array (doubling `repalloc`) before returning any
tuple, switching into `es_query_cxt` so the rows outlive the per-tuple context
(`sqlite_fdw.c:1469-1520`) `[verified-by-code]`. The comment is explicit: "there
is no isolation between update and select on the same database connections"
citing `sqlite.org/isolation.html` (`sqlite_fdw.c:1463-1468`) `[from-comment]`.
postgres_fdw never needs this because the remote PG server isolates its own
cursors; here the SELECT and the UPDATE share one `sqlite3*`.

### 6. Parameter binding maps PG Datums onto SQLite's five storage classes

`sqlite_bind_sql_var` switches on the PG type OID and binds via the SQLite C API:
`sqlite3_bind_int`/`int64`/`double`/`text`/`blob`/`null`
(`sqlite_query.c:747-1058`) `[verified-by-code]`. Text-ish types (TEXT, VARCHAR,
JSON, timestamps, DATE, TIME) go out through `OidOutputFunctionCall` then
`pg_do_encoding_conversion` to UTF-8 before `sqlite3_bind_text` — SQLite stores
UTF-8, so every non-UTF8 PG database encoding is converted at the boundary
(`sqlite_query.c:766-789`, `1080-1091`) `[verified-by-code]`. JSONB is bound as a
SQLite **blob** built by `sqlite_make_JSONb` ("jsonb in SQLite is not the same as
in PostgreSQL, use text transport", `sqlite_query.c:1001-1012`, header note at
`deparse.c:2448`) `[from-comment]`. UUID binds as a 16-byte blob, MAC addresses
as fixed-length blobs (`sqlite_query.c:848-940`) `[verified-by-code]`.

### 7. ANALYZE is a no-op; planning runs on heuristic costs, not remote statistics

`sqliteAnalyzeForeignTable` simply returns `false` with no
`AcquireSampleRowsFunc` set (`sqlite_fdw.c:2844-2851`) `[verified-by-code]` — so
unlike postgres_fdw (which samples the remote table) sqlite_fdw collects no
remote statistics; cost estimation relies on `DEFAULT_FDW_STARTUP_COST` /
`DEFAULT_FDW_TUPLE_COST` and local selectivity
(`sqlite_fdw.c:559-560`, `592-598`) `[verified-by-code]`. The
`use_remote_estimate` knob that anchors postgres_fdw's costing has no analogue
here.

## Notable design decisions (with cites)

- **Prepared statements are cached against the connection entry** so they can be
  finalized at transaction end: `sqlite_prepare_wrapper` optionally calls
  `sqlite_cache_stmt`, which appends to the entry's `stmtList` under
  `TopMemoryContext` (because `CurrentMemoryContext` is gone by cleanup time)
  (`sqlite_fdw.c:514-533`, `connection.c:1022-1075`) `[verified-by-code]`.
- **`column_type` foreign-column option overrides affinity choice**: the deparser
  reads it via `preferred_sqlite_affinity` and, e.g., emits
  `sqlite_fdw_uuid_str(` instead of `_blob(` when the SQLite column prefers TEXT
  (`deparse.c:2333-2337`, `2699-2832`) `[verified-by-code]`. This is a
  user-tunable affinity contract with no postgres_fdw counterpart.
- **TRUNCATE is deparsed to `DELETE` without WHERE**, since SQLite has no
  TRUNCATE (`sqlite_fdw.c:2655-2662`, `README.md:38`) `[verified-by-code]`.
- **UPDATE/DELETE key columns** are identified by the `key 'true'` column option,
  found as resjunk attributes via `ExecFindJunkAttributeInTlist` in
  `BeginForeignModify` and bound by `bindJunkColumnValue`
  (`sqlite_fdw.c:1911-1926`, `2668-2705`) `[verified-by-code]`. IMPORT FOREIGN
  SCHEMA auto-stamps `OPTIONS (key 'true')` on PRAGMA-reported primary keys
  (`sqlite_fdw.c:2985-2986`) `[verified-by-code]`.
- **Type mapping for IMPORT is affinity-rule-based**: `sqlite_to_pg_type` matches
  declared SQLite type-name prefixes/substrings (`int`→`bigint`, `char/clob/text`→
  `text`, `blob`→`bytea`, `real/floa/doub`→`double precision`, empty→`bytea`,
  fallthrough→`decimal`) per SQLite's documented affinity rules, with a
  pass-through list for `datetime/uuid/jsonb/geometry/…` (`sqlite_fdw.c:4832-4930`)
  `[verified-by-code]`.
- **Batch insert respects SQLite limits**: `sqliteGetForeignModifyBatchSize`
  clamps `batch_size` to SQLite's compound-statement limit and disables batching
  for tables with BEFORE/AFTER row triggers or zero columns
  (`sqlite_fdw.c:2035-2069`) `[verified-by-code]`.
- **Optional SpatiaLite↔PostGIS bridge** is a compile-time `SQLITE_FDW_GIS_ENABLE`
  path (`sqlite_query.c:16-18`, `sqlite_fdw.h:416-419`) transporting EWKB
  (`README.md:59`) `[from-README]` — geometry/geography map to SQLite `BLOB`
  otherwise (`sqlite_fdw.c:4886-4909`) `[verified-by-code]`.

## Links into corpus

- [[wrappers]] — the canonical "FDW framework" sibling; sqlite_fdw is the
  hand-written-C cousin to that Rust-macro approach.
- [[tds_fdw]] — closest sibling ideology: another single-source C FDW that maps a
  foreign type system onto PG; contrast its network DB-Library client vs
  sqlite_fdw's embedded file handle.
- [[pglite-fusion]] — the purest "embedded SQLite as a *value*" ideology;
  sqlite_fdw is the "embedded SQLite as a *server*" counterpart (same engine,
  opposite integration seam: FDW callbacks vs a column type).
- [[pg_duckdb]] / [[cstore_fdw]] — other "embedded/columnar engine reached
  through PG planner hooks" ideologies; compare push-down ambitions.
- [[executor-and-planner]] — the FdwRoutine scan/modify callback lifecycle and
  the join/upper-rel push-down path machinery forked from postgres_fdw.
- [[fmgr-and-spi]] — `PG_FUNCTION_INFO_V1` handler/validator and the SRFs;
  `OidOutputFunctionCall` for binding.
- [[memory-contexts]] — `stmtList` parked in `TopMemoryContext` for end-of-xact
  finalize; the `es_query_cxt` switch for the for-update row buffer; per-modify
  `AllocSetContextCreate` temp context (`sqlite_fdw.c:1868-1872`).
- [[error-handling]] — `sqlitefdw_report_error` translating
  `sqlite3_errmsg`/`sqlite3_extended_errcode` into `ereport` with
  `ERRCODE_FDW_*` (`connection.c:396-420`); `PG_TRY`/`PG_CATCH` finalizing
  statements in IMPORT FOREIGN SCHEMA.
- [[catalog-conventions]] — option validation against `ForeignServerRelationId`/
  `ForeignTableRelationId`/`AttributeRelationId` contexts (`option.c:42-62`).

> Corpus gap: there is no idiom doc for the **FDW connection-cache pattern**
> (backend-local `HTAB` keyed by server OID + xact/subxact/syscache-inval
> callbacks) that postgres_fdw established and every C FDW (sqlite_fdw, tds_fdw,
> mysql_fdw…) copies near-verbatim. Worth an `idioms/fdw-connection-cache.md`.
> Corpus gap: no idiom doc for **deparse-side type/affinity coercion** — pushing
> a normalization expression into the *remote* SQL so values arrive in a fixed
> shape (sqlite_fdw's `sqlite_fdw_float(col)` wrapping is the extreme case).

## Sources

All fetched 2026-06-23 via `raw.githubusercontent.com/pgspider/sqlite_fdw/master/`.

- Tree listing: `https://api.github.com/repos/pgspider/sqlite_fdw/git/trees/master?recursive=1` — 200
- `README.md` — 200 (780 lines)
- `sqlite_fdw.control` — 200 (4 lines)
- `sqlite_fdw.h` — 200 (422 lines)
- `sqlite_fdw.c` — 200 (5776 lines)
- `connection.c` — 200 (1075 lines)
- `deparse.c` — 200 (4614 lines; only the column-ref/affinity-coercion + join push-down sections read in depth)
- `option.c` — 200 (247 lines)
- `sqlite_query.c` — 200 (1239 lines)
- `sqlite_data_norm.c` — 200 (768 lines)

No 404s; all target paths resolved at the repo root (no path substitutions
needed). Skimmed-but-not-fetched: `sqlite_gis.c` (GIS/SpatiaLite transport,
behavior inferred from `sqlite_fdw.h:416-419` + README), the `sql/` and
`expected/` per-version test corpora, `Makefile`, `META.json`,
`sqlite_fdw--1.0.sql` / `--1.0--1.1.sql` (SQL install scripts, status not
checked individually).
