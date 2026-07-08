# duckdb_fdw (alitrack/duckdb_fdw) — a sqlite_fdw-lineage FdwRoutine retargeted at the DuckDB C API, plus a dynamic-linker coexistence firewall against pg_duckdb

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `alitrack/duckdb_fdw` @ branch `main`. ~407★, language **C** (with a
> `-lstdc++` link for the C++ runtime libduckdb pulls in). All `file:line` cites
> below point into that repo (cited as `deparse.c:NN` etc.), not `source/`,
> since this doc characterizes an *external* extension. Cites verified against
> the files fetched on 2026-07-07 (see Sources footer). It is the **FDW corner**
> of the DuckDB-integration cluster — the deliberate structural opposite of
> `[[pg_duckdb]]` (whole-plan replacement via `planner_hook`).

This is a **medium-divergence FDW**: the callback skeleton and deparser are the
Toshiba/postgres_fdw FDW family, near-verbatim, so on the FdwRoutine axis it sits
next to `[[tds_fdw]]` (the conformant foil). What makes it interesting is
everything *below* the callbacks: the SQLite C API of its ancestor is swapped for
the **DuckDB C API** (`duckdb.h`, `libduckdb`), and it ships a bespoke
`runtime_guard.c` that walks the backend's loaded shared objects with
`dl_iterate_phdr` to refuse to run when `pg_duckdb` is co-loaded.

## Domain & purpose

duckdb_fdw makes DuckDB (and everything DuckDB can read — Parquet, Iceberg,
S3/S3-Tables, MotherDuck, Quack) queryable as PostgreSQL **foreign tables**. A
`SELECT` over a foreign table deparses to DuckDB SQL, runs on an embedded
in-process DuckDB via the C API, and streams the result back as PG tuples. The
README frames the contrast with `pg_duckdb` explicitly: duckdb_fdw is "PG →
DuckDB data lake" (lets PG query DuckDB's world) whereas pg_duckdb is "DuckDB
engine → PG tables" (embeds the engine to accelerate PG-native queries), and the
two "cannot coexist in the same backend (both link `libduckdb.so`)"
(`README.md:308-320` `[from-README]`). Deploys with plain `CREATE EXTENSION` — no
`shared_preload_libraries`, no restart (`README.md:311` `[from-README]`),
`relocatable = true`, `default_version = '2.0.1'` (`duckdb_fdw.control:3-5`
`[verified-by-code]`).

**Lineage.** `deparse.c` carries `Portions Copyright (c) 2021, TOSHIBA
CORPORATION` (`deparse.c:5` `[verified-by-code]`) — the signature of Toshiba's
FDW family (sqlite_fdw / mysql_fdw / griddb_fdw share it). The README's own
feature table records the switch: the v1.x "Kernel Interface" was **"SQLite
Compatibility"** and v2.0+ is **"Native DuckDB C API"** with "Chunk-based result
scan" replacing "Row-by-row" (`README.md:296-303` `[from-README]`). So the
codebase is a **sqlite_fdw fork**: the FdwRoutine + `deparse.c` deparser started
as alitrack's sqlite_fdw (which talked to DuckDB through DuckDB's sqlite3
compatibility shim), and v2.0 swapped the SQLite C API for the DuckDB C API +
chunk scanning while keeping the deparse machinery. See `[[sqlite_fdw]]`.

## How it hooks into PG

Standard `CREATE FOREIGN DATA WRAPPER ... HANDLER duckdb_fdw_handler VALIDATOR
duckdb_fdw_validator` wiring; both are `PG_FUNCTION_INFO_V1`
(`option.c:95`, `duckdb_fdw.c:1080` `[verified-by-code]`). The handler
`makeNode(FdwRoutine)`s and fills the callback set (`duckdb_fdw.c:1083-1108`
`[verified-by-code]`):

- **Scan:** `GetForeignRelSize` / `GetForeignPaths` / `GetForeignPlan` /
  `BeginForeignScan` / `IterateForeignScan` / `ReScanForeignScan` /
  `EndForeignScan` / `ExplainForeignScan` (`:1084-1094`).
- **Pushdown:** `GetForeignJoinPaths` → `duckdbGetForeignJoinPaths` and
  `GetForeignUpperPaths` → `duckdbGetForeignUpperPaths` (`:1087`, `:1092`) — so
  it registers **JOIN and aggregate pushdown**, unlike `[[tds_fdw]]`.
- **DDL:** `ImportForeignSchema` → `duckdb_import_foreign_schema` (`:1093`).
- **Write (INSERT only):** the full `PlanForeignModify` / `BeginForeignModify` /
  `ExecForeignInsert` / `ExecForeignBatchInsert` / `EndForeignModify` set is
  assigned (`:1097-1106`), but `IsForeignRelUpdatable` returns only
  `(1 << CMD_INSERT)` and `PlanForeignModify` returns `NIL`
  (`duckdb_fdw.c:911-935` `[verified-by-code]`) — UPDATE/DELETE are structurally
  refused.

**`_PG_init` exists but installs no query hooks** — it only defines one GUC,
`duckdb_fdw.allow_unsupported_pg_duckdb_coexistence` (`PGC_SUSET`), and
immediately forces it off (`duckdb_fdw.c:1424-1447` `[verified-by-code]`). This
is the anti-pg_duckdb: no `planner_hook`, no `shared_preload_libraries`
requirement. The **options validator** is the textbook `valid_options[]` table
keyed by catalog OID — `database`/`s3_*`/`motherduck_token`/`attach_catalogs`/
`extensions`/`quack_host` on `ForeignServerRelationId`, `table`/`read_parquet` on
`ForeignTableRelationId`, and secrets duplicated onto `UserMappingRelationId` as
the preferred secure path (`option.c:33-75` `[verified-by-code]`;
`pg_foreign_server` is public-readable, so S3 keys belong in a user mapping,
`option.c:46-48` `[from-comment]`).

## Where it diverges from core idioms

### 1. The libduckdb boundary is crossed via the C API, so there is NO C++ exception firewall — the ABI itself is the firewall

This is the sharpest contrast with the sibling `[[pg_duckdb]]`. pg_duckdb links
DuckDB's **C++** API and must wrap every hook in `InvokeCPPFunc` to translate C++
exceptions into `ereport` (see `[[pg_duckdb]]` §6); pgrx solves the analogous
Rust↔C problem with a `siglongjmp` trampoline. duckdb_fdw sidesteps the entire
problem by linking the **DuckDB C API** (`duckdb.h`): its functions are `noexcept`
and return `DuckDBError`/`DuckDBSuccess` status codes, catching C++ exceptions
*inside libduckdb*. So the divergence is that there is no per-call PG_TRY firewall
at all — `duckdb_do_sql_command` just checks the status code and turns
`DuckDBError` into `ereport(level, ERRCODE_FDW_ERROR, ...)` (`connection.c:504-527`
`[verified-by-code]`). The residual C++ concern is purely at *link* time:
`SHLIB_LINK = -L. -lduckdb -lstdc++` plus, on Linux, `-D_GLIBCXX_USE_CXX11_ABI=0`
(`Makefile:28`, `:39` `[verified-by-code]`) to match the libstdc++ ABI libduckdb
was built against `[inferred]`. This is the correct, boring answer to the
C++-boundary problem that `[[pgrouting]]` (C++ throwing across the C boundary) and
the `[[pg_jieba]]` negative example (no firewall at all) get wrong — duckdb_fdw
never lets a C++ exception reach PG because it never calls C++ directly.

### 2. `runtime_guard.c` — a dynamic-linker coexistence firewall against pg_duckdb, NOT an error firewall

The name misleads: it does not guard C++ exceptions or re-entrancy. It guards
against **two DuckDB runtimes in one backend**. On Linux it calls `dladdr` on
`duckdb_library_version` to find which `libduckdb` provided *its* symbols, then
`dl_iterate_phdr` to walk every loaded shared object, counting modules whose
basename starts with `pg_duckdb` and noting any second `libduckdb*` image
(`runtime_guard.c:57-109` `[verified-by-code]`). It returns a status enum
(`no_peer_loaded` / `peer_loaded_need_validation` / `compatible_unproven` /
`incompatible`, `:223-241`). `duckdb_runtime_guard_check` is called at the top of
`duckdb_get_connection` (`connection.c:410` `[verified-by-code]`) and in
`duckdb_fdw_version`; if pg_duckdb is co-loaded it `ereport(ERROR,
ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE, "strict coexistence policy rejected the
current DuckDB runtime combination")` unless the session GUC override is armed
(`runtime_guard.c:184-221` `[verified-by-code]`). The override GUC is
deliberately hard to set: a check hook rejects anything but `PGC_S_SESSION` and
forbids enabling it inside a transaction block (`duckdb_fdw.c:1397-1422`
`[verified-by-code]`), and there's a `duckdb_fdw_preflight()` SPI probe that
warns if `pg_duckdb` is merely installed (`duckdb_fdw.c:1204-1287`). No core FDW
introspects the process's loaded-object list to decide whether it is safe to run;
this is a bespoke defense against the ABI clash the README names
(`README.md:319` `[from-README]`). Cross-ref `[[pg_duckdb]]`, `error-handling`
skill.

### 3. DuckDB result/chunk memory lives outside PG's MemoryContext, freed by hand

The exec state holds raw libduckdb handles — `duckdb_database`,
`duckdb_connection`, `duckdb_result`, `duckdb_data_chunk`,
`duckdb_prepared_statement`, `duckdb_appender` (`duckdb_fdw.h:65-94`
`[verified-by-code]`). These are DuckDB-heap-owned, invisible to PG's
`MemoryContext`, and released by explicit calls in `duckdbEndForeignScan`
(`duckdb_destroy_data_chunk`, `duckdb_destroy_result`, `duckdb_destroy_prepare`,
`duckdb_fdw.c:843-855` `[verified-by-code]`); per-cell `duckdb_value_varchar`
strings are individually `duckdb_free`'d after conversion
(`duckdb_fdw.c:704`, `:729` `[verified-by-code]`). This is the same
"third-party handles freed by hand, outside MemoryContext discipline" pattern
`[[tds_fdw]]` shows with FreeTDS db-lib, and the same divergence from core's
palloc-everything idiom. Cross-ref `[[knowledge/idioms/memory-contexts]]`.

### 4. Two tuple-marshalling paths — a fast direct-vector chunk scan, and nanoarrow vendored but not wired in

`duckdbIterateForeignScan` has two modes. For a "simple" tuple (all columns in
`{bool,int2/4/8,float4/8,date,timestamp(tz)}`, decided by
`duckdb_can_use_chunk_scan`, `duckdb_fdw.c:222-257`) it pulls a
`duckdb_data_chunk`, and for each column reads the DuckDB **vector's raw column
buffer + validity bitmap directly** — `duckdb_data_chunk_get_vector` →
`duckdb_vector_get_data` / `duckdb_vector_get_validity`, indexing the typed C
array by row (`duckdb_fdw.c:771-813` `[verified-by-code]`), then
`ExecStoreVirtualTuple` (`:830`). For anything else it falls back to per-value
extraction that routes non-native types through `duckdb_value_varchar` +
`OidInputFunctionCall`/`cstring_to_text`, including a hack that rewrites DuckDB
`[1,2]` list syntax to PG `{1,2}` array text (`duckdb_fdw.c:678-733`
`[verified-by-code]`). Notably: although `nanoarrow.c` (the full ~4,100-line
vendored Apache Arrow nanoarrow library) ships and `duckdb_fdw.h:6` includes
`nanoarrow/nanoarrow.h`, **no `ArrowArray`/`ArrowSchema` symbol is referenced
anywhere in the FDW C sources** (`duckdb_fdw.c`/`deparse.c`/`connection.c`/
`import.c` — grep-clean `[verified-by-code]`). The Arrow C-Data-Interface bridge
is staged/vendored but the live tuple path is DuckDB-vector-direct, not
Arrow-marshalled. Cross-ref `[[knowledge/subsystems/executor]]`.

### 5. Connection cache is per-transaction, not per-session — torn down at every commit/abort

`connection.c` caches one `{duckdb_database, duckdb_connection}` per foreign
server OID in an HTAB in `CacheMemoryContext` (`connection.c:412-429`
`[verified-by-code]`) — pooling in the postgres_fdw spirit. But it registers a
`XactCallback` that **closes and clears the whole cache** on `XACT_EVENT_COMMIT`
/ `ABORT` / parallel variants (`connection.c:49-65`, `:24-47`
`[verified-by-code]`), and a `SubXactCallback` that clears everything on
subtransaction abort (`:67-84`). So a DuckDB connection lives only for the
duration of a transaction, discarding DuckDB's in-memory catalog/attachments
each commit — conservative but different from postgres_fdw's session-persistent
libpq pool and from `[[tds_fdw]]`'s per-scan open/close. On (re)connect it
replays extension installs, `CREATE SECRET`, MotherDuck token, and `ATTACH`
statements from server/user-mapping options (`connection.c:125-401`).

### 6. IMPORT FOREIGN SCHEMA executes its own DDL via SPI and returns NIL

The core contract for `ImportForeignSchema` is to *return* a `List` of
`CREATE FOREIGN TABLE` command strings that the backend then executes.
duckdb_fdw instead `SPI_connect`s, `DESCRIBE`s the DuckDB table (or
`DESCRIBE SELECT * FROM read_parquet(...)` for a file path), builds the DDL
string, runs it itself with `SPI_execute`, and returns `NIL`
(`import.c:64-223` `[verified-by-code]`). Type mapping is a hand-rolled
DuckDB→PG name table (`DECIMAL(p,s)`→`numeric(p,s)`, `HUGEINT`→`numeric`,
`JSON`→`jsonb`, `INTEGER[]`→`int4[]`, default `text`, `import.c:12-62`). Running
DDL through SPI from inside the callback rather than handing strings back to core
is a divergence from the documented FDW import protocol. Cross-ref
`[[knowledge/idioms/fmgr-and-spi]]`.

## Notable design decisions (cited)

- **INSERT via the DuckDB Appender API, with a SQL fallback.**
  `duckdbBeginForeignModify` opens a `duckdb_appender_create`; if it succeeds,
  each `ExecForeignInsert` binds the slot's columns through typed
  `duckdb_append_*` calls (`duckdb_append_slot_row`,
  `duckdb_fdw.c:259-329`, `:956-968` `[verified-by-code]`). Batch insert is
  wired to `ExecForeignBatchInsert` (`:1102-1103`). UPDATE/DELETE deliberately
  omitted via `IsForeignRelUpdatable` (`:911-921`).
- **Prepared-statement param pushdown.** When the plan has `fdw_exprs`, the scan
  `duckdb_prepare`s the deparsed SQL and binds evaluated Datums with typed
  `duckdb_bind_*` (falling back to `duckdb_bind_varchar` +
  `OidOutputFunctionCall` for unknown types) (`duckdb_fdw.c:156-202`, bind
  switch `:110-153` `[verified-by-code]`).
- **Full postgres_fdw-shape pushdown in `deparse.c`.** The `FDWCollateState`
  (`NONE/SAFE/UNSAFE`) collation state machine, `duckdb_is_foreign_expr` /
  `duckdb_foreign_expr_walker`, and `duckdb_classify_conditions`
  (`deparse.c:285`, `:3997` `[verified-by-code]`) are the postgres_fdw deparser.
  WHERE, aggregate (`duckdb_deparse_aggref`, `deparse.c:3400`), and LIMIT/OFFSET
  pushdown are present — with a DuckDB quirk: a bare OFFSET is emitted as
  `LIMIT -1 OFFSET n` because DuckDB rejects OFFSET without LIMIT
  (`deparse.c:3664-3674` `[from-comment]`).
- **Defense-in-depth SQL-injection guards.** Because option values (catalog
  names, extension names, S3 URIs) are interpolated into DuckDB SQL,
  `sql_utils.c` provides `duckdb_fdw_quote_literal` / `_quote_identifier`,
  `_is_valid_identifier`, and `_is_safe_sql_fragment` (rejects `;`, `--`,
  `/* */`, control chars), applied throughout `connection.c`'s ATTACH/secret
  builders (`sql_utils.c:24-99`, e.g. `connection.c:293-312`
  `[verified-by-code]`).
- **Secret redaction in error text.** `duckdb_fdw_redact_secret_text` scrubs
  DuckDB error strings that mention `SECRET`/`KEY_ID`/`ACCESS_KEY`/`TOKEN`/
  `motherduck` before they reach `ereport` (`sql_utils.c:101-118`, called from
  `connection.c:512` `[verified-by-code]`).
- **`relocatable = true`** (`duckdb_fdw.control:5`) — unlike `[[pg_duckdb]]`'s
  pinned schema; an FDW has no schema-coupled UDFs to anchor. The Makefile also
  bundles and installs `libduckdb` alongside the module and sets
  `-Wl,-rpath,'$ORIGIN'` so the runtime finds it (`Makefile:66-73`).

## Links into corpus

- `[[pg_duckdb]]` — the sibling and primary contrast: same embedded DuckDB, but
  pg_duckdb replaces the whole plan (`planner_hook` + one `CustomScan`) and links
  the C++ API (needing an exception firewall), whereas duckdb_fdw is a
  per-foreign-table SQL round-trip through the C API (no firewall needed). The
  two cannot share a backend — hence `runtime_guard.c`.
- `[[sqlite_fdw]]` — the direct ancestor; duckdb_fdw is sqlite_fdw with the
  SQLite C API swapped for the DuckDB C API + chunk scanning (Toshiba copyright,
  README v1.x "SQLite Compatibility" kernel).
- `[[tds_fdw]]` — the conformant-FDW foil; same postgres_fdw `deparse.c`
  heritage and same "third-party handles freed outside MemoryContext" pattern,
  but tds_fdw does no JOIN/agg pushdown and no connection pooling.
- `[[pg_ducklake]]`, `[[pg_duckpipe]]`, `[[parquet_s3_fdw]]`, `[[cstore_fdw]]` —
  the rest of the columnar / data-lake cluster; duckdb_fdw is the FDW-shaped
  DuckDB data-lake gateway (Parquet/Iceberg/S3/MotherDuck via `IMPORT FOREIGN
  SCHEMA` + `read_parquet`).
- `[[pgrouting]]` / `[[pg_jieba]]` — the C++-across-the-C-boundary problem;
  duckdb_fdw is the clean case (C API, ABI-level error codes) against pg_jieba's
  no-firewall negative example and pgrx's `siglongjmp` boundary.
- `[[knowledge/idioms/memory-contexts]]` — DuckDB handles freed by hand in
  `EndForeignScan`, outside MemoryContext.
- `[[knowledge/idioms/fmgr-and-spi]]` — `ImportForeignSchema` running its own
  `SPI_execute` DDL; the several `PG_FUNCTION_INFO_V1` SQL helpers
  (`duckdb_execute`, `duckdb_create_s3_secret`, `duckdb_fdw_preflight`).
- `[[knowledge/subsystems/foreign]]` + `fdw-development` skill — the FdwRoutine
  dispatch and pushdown callbacks this extension plugs into.
- `[[knowledge/idioms/error-handling]]` — `DuckDBError`→`ereport(ERRCODE_FDW_*)`
  translation with secret redaction.

## Sources

Fetched 2026-07-07 (branch `main`), all via
`https://raw.githubusercontent.com/alitrack/duckdb_fdw/main/<path>`:

- `Makefile` → HTTP 200 (76 lines; OBJS, `-lduckdb -lstdc++`,
  `_GLIBCXX_USE_CXX11_ABI=0`, rpath, libduckdb install hook).
- `README.md` → HTTP 200 (≈340 lines; feature/comparison tables, pg_duckdb
  contrast, usage — `[from-README]` for the narrative).
- `duckdb_fdw.control` → HTTP 200 (5 lines).
- `duckdb_fdw.h` → HTTP 200 (147 lines; `DuckDBFdwExecState`/`...RelationInfo`,
  exported decls, nanoarrow include).
- `connection.c` → HTTP 200 (527 lines; per-txn cache + xact/subxact teardown,
  secret/extension/ATTACH setup, `duckdb_do_sql_command`).
- `option.c` → HTTP 200 (164 lines; `valid_options[]` by catalog OID, validator).
- `deparse.c` → HTTP 200 (4017 lines; Toshiba copyright, postgres_fdw deparser,
  aggref/LIMIT/OFFSET pushdown — skimmed beyond the cited functions).
- `duckdb_fdw.c` → HTTP 200 (1477 lines; FdwRoutine handler, scan/iterate,
  chunk vs value marshalling, appender insert, `_PG_init` GUC, runtime SQL
  functions).
- `nanoarrow.c` → HTTP 200 (4117 lines; the vendored Apache Arrow nanoarrow
  library — confirmed **not referenced** by the FDW hot path; header include
  only).
- `import.c` → HTTP 200 (223 lines; SPI-driven `IMPORT FOREIGN SCHEMA`,
  DuckDB→PG type map).
- `sql_utils.c` → HTTP 200 (151 lines; quoting/validation/redaction helpers).
- `runtime_guard.c` → HTTP 200 (242 lines; `dl_iterate_phdr` pg_duckdb
  coexistence guard).

No 404 gaps — all 12 requested paths returned HTTP 200 (`duckdb_fdw--*.sql` was
not fetched; the `.control` `default_version = '2.0.1'` implies
`duckdb_fdw--2.0.1.sql`, `[inferred]`, not read). All cites are
`[verified-by-code]` against the fetched sources except the end-user feature
narrative and the pg_duckdb comparison (`[from-README]`), the `LIMIT -1` and
security-path rationales (`[from-comment]`), and the `_GLIBCXX_USE_CXX11_ABI=0`
motivation (`[inferred]`). `deparse.c` and `nanoarrow.c` were skimmed, not
deep-read line-by-line; pushdown-shape claims rest on the cited function
signatures + the postgres_fdw heritage.
