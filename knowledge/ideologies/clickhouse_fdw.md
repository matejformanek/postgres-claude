# clickhouse_fdw (ildus/clickhouse_fdw) — a dual-driver FDW (native C++ binary protocol + HTTP/curl) with a deliberately leaky C++ exception firewall

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `ildus/clickhouse_fdw` @ branch `master`, **ARCHIVED**. ~275★,
> language **C/C++**. All `file:line` cites point into that repo (cited as
> `src/binary.cc:NN` etc.), not `source/`. Cites verified against the files
> fetched on 2026-07-07 (see Sources footer). The upstream README opens with
> "The project is currently archived. I recommend to switch to
> [clickhouse/pg_clickhouse], which is basically a continuation of this
> project" (`README.md:4-7` `[from-README]`) — so this is the **older
> community FDW**, the foil to the newer official `[[pg_clickhouse]]`.

This is the corpus's example of an FDW that **speaks two wire protocols
behind one `FdwRoutine`**: a **native binary protocol** driver linking the
C++ `clickhouse-cpp` client library, and an **HTTP** driver over libcurl.
Where `[[tds_fdw]]` is the conformant single-protocol read-only reference and
`[[pgrouting]]` is the two-language extension with a *complete* C++ exception
firewall, clickhouse_fdw sits between them: it is a fully-featured FDW (scan +
aggregate/join pushdown + INSERT DML + IMPORT SCHEMA) whose binary driver
crosses a C↔C++ boundary that it can only *partially* firewall — and it says
so in a source comment.

## Domain & purpose

clickhouse_fdw makes a ClickHouse (column-oriented OLAP database) table appear
as a PostgreSQL foreign table, targeting PostgreSQL 11-17 (`README.md:14`
`[from-README]`). Unlike tds_fdw it is **not** read-only: `SELECT` streams rows
back, `INSERT` ships tuples into ClickHouse column blocks, aggregates and joins
push down, and `IMPORT FOREIGN SCHEMA` auto-generates foreign-table DDL from
ClickHouse's `system.tables`/`system.columns` (`src/pglink.c:859-993`
`[verified-by-code]`). The copyright line "Copyright (c) 2019-2022, Adjust
GmbH" (`src/connection.c:7` `[verified-by-code]`) and the hardcoded
recognition of Adjust-internal extensions (`istore`, `ajtime`, `country`) in
the shippability layer (`src/custom_types.c:189-269` `[verified-by-code]`) mark
it as an analytics-vendor FDW rather than a neutral one. It is archived and
predates the official `[[pg_clickhouse]]`.

## How it hooks into PG

Standard `CREATE FOREIGN DATA WRAPPER ... HANDLER clickhousedb_fdw_handler
VALIDATOR clickhousedb_fdw_validator`. Both are `PG_FUNCTION_INFO_V1`
(`src/clickhouse_fdw.c:183`, `src/option.c:73` `[verified-by-code]`); the
handler `palloc`s a `makeNode(FdwRoutine)` and fills it
(`src/clickhouse_fdw.c:2814-2856` `[verified-by-code]`) — the standard
`[[knowledge/idioms/fmgr]]` handler pattern. `_PG_init` is **empty**
(`src/clickhouse_fdw.c:291` `[verified-by-code]`): no GUCs, no
`shared_preload_libraries` requirement, no hooks. `.control` declares
`relocatable = true`, `default_version = '1.4'`, `module_pathname =
'$libdir/clickhouse_fdw'` (`src/clickhouse_fdw.control:1-4` `[verified-by-code]`).

The callback set it installs (`src/clickhouse_fdw.c:2820-2853`
`[verified-by-code]`) is **much broader than tds_fdw's** — this is a
postgres_fdw-class FDW:

- **Planning + scan:** `GetForeignRelSize`/`GetForeignPaths`/`GetForeignPlan`/
  `BeginForeignScan`/`IterateForeignScan`/`EndForeignScan` (note
  `ReScanForeignScan` is aliased to `clickhouseEndForeignScan`,
  `src/clickhouse_fdw.c:2825`).
- **Write DML:** `PlanForeignModify`, `BeginForeignModify`, `ExecForeignInsert`,
  `BeginForeignInsert`, `EndForeignInsert`/`EndForeignModify`
  (`src/clickhouse_fdw.c:2829-2835`) — INSERT only; no update/delete-exec.
- **Pushdown:** `GetForeignJoinPaths` **and** `GetForeignUpperPaths`
  (aggregate/grouping pushdown) are both registered
  (`src/clickhouse_fdw.c:2847-2850`) — the sharpest contrast with tds_fdw,
  which registers neither.
- **Support:** `RecheckForeignScan`, `ExplainForeignScan`,
  `AnalyzeForeignTable`, `ImportForeignSchema`.

The **options validator** is postgres_fdw's `valid_options`-by-catalog-OID
shape (`src/option.c:50-201` `[verified-by-code]`) but the option surface is
deliberately tiny: server takes `host`/`port`/`dbname`/`driver`, user mapping
takes `user`/`password`, foreign table takes `database`/`table_name`/`engine`,
and a column can carry `aggregatefunction`/`simpleaggregatefunction`/
`column_name`/`arrays` (`src/option.c:50-143` `[verified-by-code]`). Note there
is **no `extensions` server option** — see shippability below.

### The binary-vs-HTTP driver dispatch

This is the structural centerpiece. `clickhouse_connect` reads the `driver`
option (default `"http"`) and branches: `"http"` → `chfdw_http_connect`,
`"binary"` → `chfdw_binary_connect`, else `elog(ERROR, "invalid ClickHouse
connection driver")` (`src/connection.c:42-69` `[verified-by-code]`). The
binary driver also **rewrites the default port from 8123 (HTTP) to 9000
(native)** when the user left it at the HTTP default
(`src/connection.c:62-63` `[verified-by-code]`). Each driver returns a
`ch_connection` carrying a `libclickhouse_methods *` vtable — `http_methods`
or `binary_methods` — plus an `is_binary` flag (`src/pglink.c:37-63,
83-110, 473-496` `[verified-by-code]`). Every downstream operation goes through
the vtable: `conn.methods->simple_query(...)`,
`conn.methods->fetch_row(...)` (`src/clickhouse_fdw.c:867`,
`src/pglink.c:874-878` `[verified-by-code]`). The rest of the FDW is written
against this five-method interface (`disconnect`, `simple_query`, `fetch_row`,
`prepare_insert`, `insert_tuple`, `src/pglink.c:37-43` `[verified-by-code]`),
so the two wire protocols are genuinely interchangeable.

## Where it diverges from core idioms

### 1. Dual-driver vtable — one FDW, two transports

Core FDWs (postgres_fdw, tds_fdw) bind to a single client library. clickhouse_fdw
abstracts the transport behind a runtime-selected function-pointer table
(`libclickhouse_methods`, `src/pglink.c:37-63` `[verified-by-code]`) and picks
the implementation per foreign server from the `driver` option. The HTTP driver
talks ClickHouse's TSV-over-HTTP interface (`ch_http_simple_query` POSTs the SQL
and reads a tab/newline-delimited body, `src/http.c:125-198`,
`src/parser.c:25-78` `[verified-by-code]`); the binary driver drives
`clickhouse-cpp`'s `Client::SelectCancelable` and gets back typed
`clickhouse::ColumnRef` blocks (`src/binary.cc:170-226` `[verified-by-code]`).
The row-fetch contract is unified by having *both* return through
`fetch_tuple`, which switches on `fsstate->conn.is_binary`: HTTP rows arrive as
C strings fed through `InputFunctionCall`, binary rows arrive as pre-built
`Datum`s (`src/clickhouse_fdw.c:867-900`, `src/pglink.c:263-304, 555-655`
`[verified-by-code]`). This transport-abstraction-inside-an-FDW is the design
`[[pg_clickhouse]]` inherits and re-does with the header-only C `clickhouse-c`
client instead of the C++ `clickhouse-cpp`.

### 2. The clickhouse-cpp C++ boundary and its *deliberately leaky* exception firewall

This is the load-bearing divergence, and the sharpest contrast with
`[[pgrouting]]`. `src/binary.cc` is compiled as C++ (`using namespace
clickhouse;`) with the PG headers pulled in under `extern "C" { ... }`
(`src/binary.cc:17-37` `[verified-by-code]`). The `clickhouse-cpp` `Client`,
`Block`, and `ColumnRef` objects are C++ heap objects created with `new`
(`src/binary.cc:132-135` `[verified-by-code]`). The boundary has to bridge
**two** error models — and it bridges them in **both directions**, imperfectly:

- **C++ → PG (outbound), mostly firewalled.** Most `extern "C"` entry points
  wrap their body in `try { ... } catch (const std::exception &e) { ... }` and
  either stash `e.what()` into a `char *error` out-param
  (`ch_binary_connect`/`ch_binary_simple_query`, `src/binary.cc:138-152,
  214-226`) or convert to a PG error with `elog(ERROR, "...%s", e.what())`
  (`ch_binary_prepare_insert`/`ch_binary_column_append_data`/
  `ch_binary_insert_columns`, `src/binary.cc:363-371, 603-607, 624-627`)
  `[verified-by-code]`. On the connection path it even calls
  `client->ResetConnection()` inside the catch before reporting
  (`src/binary.cc:216, 365` `[verified-by-code]`).

- **PG → C++ (inbound), bridged with `PG_TRY`.** Where the C++ code must call
  a PG function that could `ereport`/longjmp — `TupleDescInitEntry` during
  insert preparation — it wraps *that call* in `PG_TRY()/PG_CATCH()` inside the
  C++ lambda, sets an `error` flag on catch, and re-throws as a C++
  `std::runtime_error` so the outer C++ `catch` handles it
  (`src/binary.cc:344-357` `[verified-by-code]`). It also supplies
  `exc_palloc`/`exc_palloc0` — hand-rolled clones of `MemoryContextAlloc` that
  `throw std::bad_alloc()` instead of longjmping — so allocation failures raise
  C++ exceptions rather than jumping out through C++ destructors
  (`src/binary.cc:54-107` `[verified-by-code]`).

- **The acknowledged hole.** `make_datum` — the per-value converter that builds
  Datums from `clickhouse::ColumnRef` cells — calls PG functions
  (`CStringGetTextDatum`, `DirectFunctionCall1(inet_in, ...)`,
  `time_t_to_timestamptz`, `exc_palloc`) that can `palloc` and therefore
  `elog(ERROR)`/longjmp *out of C++ stack frames*, leaking the C++ objects
  those frames own. The source says so verbatim: "This function calls postgres
  functions, which can call `palloc` so we can end up with elog(ERROR) and
  longjmp to upper postgres code with leaking c++ memory. There is no an
  adequate (without huge overheads) solution, we just consider this state
  unfixable." (`src/binary.cc:688-697` `[verified-by-code]`). So unlike
  pgRouting — which guarantees *no* exception and *no* longjmp crosses the
  boundary — clickhouse_fdw's firewall is explicitly partial: it catches C++
  exceptions outbound and catches PG longjmp inbound at the *insert-prepare*
  site, but concedes a longjmp-through-C++ leak on the hot read path. It is
  more careful than `[[pg_jieba]]` (which has no firewall) and less complete
  than `[[pgrouting]]` (catch-all + out-param). Cross-ref
  `[[knowledge/idioms/error-handling]]`, `[[knowledge/idioms/memory-contexts]]`.

### 3. ClickHouse type mapping — two independent mapping layers for two drivers

ClickHouse's type system (nested `Array`, `Nullable`, `LowCardinality`,
`Tuple`, `Enum8/16`, `AggregateFunction`, `Decimal`, `FixedString`,
`DateTime64`, `IPv4/6`, `UUID`) does not line up with PG's, and the FDW maps it
in **two separate places** depending on driver:

- **IMPORT SCHEMA (textual, HTTP-side).** `parse_type` is a recursive
  string parser over ClickHouse type names: `Nullable(T)` sets an out-flag and
  recurses on `T`; `LowCardinality(T)` is transparently unwrapped;
  `Array(T)` → `parse_type(T) || "[]"`; `Decimal(p,s)` → `NUMERIC(p,s)`;
  `FixedString(n)` → `VARCHAR(n)`; `Enum8/16` → `TEXT`; `DateTime[64]` →
  `TIMESTAMP`; `Tuple(...)` degrades to `TEXT` with a `NOTICE` telling the user
  to create a composite type; `AggregateFunction(f, T)` recurses on `T` and
  records `f` as a column option (`src/pglink.c:766-857` `[verified-by-code]`).
  "nested Nullable is not supported" is an explicit error
  (`src/pglink.c:803-806` `[verified-by-code]`).

- **Binary read (typed, C++-side).** `get_corr_postgres_type` switches on
  `clickhouse::Type::Code`, recursing through `LowCardinality`, `Nullable`, and
  `Array` to their nested types and mapping `Tuple` → `RECORDOID`
  (`src/binary.cc:228-280` `[verified-by-code]`). Value construction in
  `make_datum` unwraps `Nullable` by following `->Nested()` with a
  `goto nested_col` (`src/binary.cc:855-866`), materializes `Array` into a
  bespoke `ch_binary_array_t` slot, `Tuple` into a `ch_binary_tuple_t` slot,
  and special-cases ClickHouse's "`Date == 0` means NULL" convention
  (`src/binary.cc:797-809, 868-926` `[verified-by-code]`).

The binary Datums then pass through a **second** conversion stage,
`src/convert.c`, which lazily builds per-column `ch_convert_state` machines
(`convert_record`/`convert_array`/`convert_remote_text`/`convert_bool`/
`convert_date`) to coerce the driver's "natural" PG type into the *declared*
foreign-table column type, using `find_coercion_pathway` and
`convert_tuples_by_position` for composites (`src/convert.c:70-337`
`[verified-by-code]`). Notable asymmetry: ClickHouse `UInt64` maps to signed
`INT8` with an explicit overflow check and a source comment "//overflow risk"
(`src/pglink.c:743`, `src/binary.cc:728-735` `[verified-by-code]`); ClickHouse
`bool`/`UInt8` maps to `INT2` with a user `NOTICE` suggesting a manual change
to `BOOLEAN` (`src/pglink.c:845-849` `[verified-by-code]`).

### 4. Shippability — hardcoded extension recognition + function-name translation, not a user whitelist

`src/shipable.c` reuses postgres_fdw's `chfdw_is_shippable` +
backend-lifespan cache + `pg_foreign_server` invalidation callback structure
verbatim (`src/shipable.c:113-227` `[verified-by-code]`), and builtins below
`FirstUnpinnedObjectId` are presumed shippable (`src/shipable.c:151-155`
`[verified-by-code]`) — same as tds_fdw. But two things diverge:

- **`shippable_extensions` is always `NIL`.** It is initialized to `NIL`
  (`src/clickhouse_fdw.c:364`) and only ever *copied* between fpinfos
  (`src/clickhouse_fdw.c:1910` `[verified-by-code]`); there is no `extensions`
  server option feeding it (contrast postgres_fdw's user-supplied whitelist).
  So the generic extension-membership path (`lookup_shippable`,
  `src/shipable.c:113-132`) can never fire.

- **Instead, shippability of non-builtins is decided by hardcoded name
  matching in `custom_types.c`.** `chfdw_check_for_custom_function` recognizes a
  fixed roster of extensions by string — `istore`, `country`, `ajtime`,
  `ajbool`, `intarray`, `hstore`, and `clickhouse_fdw` itself — and maps
  specific PG function names to ClickHouse function names (`array_position` →
  `indexOf`, `strpos` → `position`, `btrim` → `trimBoth`, `date_trunc`/
  `date_part`/`timezone` to date builtins, `argmax` → `argMax`,
  `uniq_exact` → `uniqExact`, `sum(istore)` → `sumMap`), or flags some as
  `CF_UNSHIPPABLE` (`src/custom_types.c:90-290` `[verified-by-code]`). The
  deparser consults these `CustomObjectDef`s to emit ClickHouse SQL, and
  `foreign_expr_walker` gates each `FuncExpr`/`OpExpr`/`Aggref` on
  `chfdw_is_shippable` (`src/deparse.c:400, 426, 543` `[verified-by-code]`).
  The `foreign_expr_walker` + `FDW_COLLATE` collation state machine itself is
  the postgres_fdw port (`src/deparse.c:54, 106, 299`, cf. `[[tds_fdw]]`'s
  identical port) `[verified-by-code]`, but here it drives full **aggregate
  pushdown** via `deparseAggref` (`src/deparse.c:169` `[verified-by-code]`),
  which tds_fdw lacks entirely.

### 5. Memory — clickhouse-cpp Blocks live in the C++ heap, reclaimed via MemoryContext reset callbacks

The binary driver's result set — a `std::vector<std::vector<ColumnRef>>` — is a
C++ heap object (`new`, `src/binary.cc:180`), owned outside any PG
`MemoryContext`, exactly like `[[pgrouting]]`'s STL working set. clickhouse_fdw
bridges the two lifetimes with **`MemoryContextRegisterResetCallback`**: each
cursor allocates a child of `PortalContext`, and registers a callback
(`binary_cursor_free` / `http_cursor_free`) that calls the C++ `delete`-based
teardown (`ch_binary_response_free`, `ch_binary_read_state_free`) when the
context resets (`src/pglink.c:200-217, 505-553, 657-669` `[verified-by-code]`;
`src/binary.cc:636-649, 1002-1013` `[verified-by-code]`). The source comment is
explicit: "we could not control properly deallocation of libclickhouse memory,
so we use memory context callbacks for that" (`src/pglink.c:200-201`
`[verified-by-code]`). Insert state uses the same reset-callback pattern
(`src/pglink.c:671-704`, `src/binary.cc:282-304` `[verified-by-code]`). This is
the corpus's clean example of **binding a foreign-runtime heap object's
destructor to a PG context lifetime** — the reset-callback dual of pgRouting's
"only marshal the answer across" approach.

### 6. Connection lifecycle — pooled and invalidation-aware (unlike tds_fdw)

Where `[[tds_fdw]]` opens and tears down a db-lib handle per scan,
clickhouse_fdw caches connections in a backend hash keyed by user-mapping OID
and registers `FOREIGNSERVEROID`/`USERMAPPINGOID` syscache invalidation
callbacks to remake them on catalog change — a near-verbatim adoption of
postgres_fdw's connection cache (`src/connection.c:71-205` `[verified-by-code]`).
The cached entry stores the `ch_connection` (vtable + `conn` + `is_binary`), so
pooling works identically for both drivers (`src/connection.c:108-162`
`[verified-by-code]`).

## Notable design decisions (cited)

- **Fake HTTP status codes as control signals.** The HTTP driver reuses
  `curl_easy_perform` return handling to synthesize `418` ("I'm a teapot") for
  a query canceled via the progress callback and `419` for a transport error,
  which `http_simple_query` then turns into retries (up to 3) or a
  `kill query` round-trip + `ereport` (`src/http.c:169-179`,
  `src/pglink.c:152-198` `[verified-by-code]`). Query cancellation is wired
  through `CURLOPT_XFERINFOFUNCTION` checking `ProcDiePending ||
  QueryCancelPending` (`src/pglink.c:65-72`, `src/http.c:156-161`
  `[verified-by-code]`); the binary driver passes an `is_canceled` predicate
  into `SelectCancelable` (`src/pglink.c:74-81, 513`,
  `src/binary.cc:182-189` `[verified-by-code]`).
- **INSERT builds ClickHouse column blocks, not row VALUES (binary path).**
  `binary_insert_tuple` appends each attribute into a
  `clickhouse::ColumnRef` via `ch_binary_column_append_data`, then flushes a
  whole `Block` with `client->Insert(table_name, block, true)` on the
  end-of-input sentinel (`src/pglink.c:706-733`,
  `src/binary.cc:377-628` `[verified-by-code]`) — column-oriented insertion
  matching ClickHouse's storage model. The HTTP path instead accumulates a
  `... FORMAT TSV` text buffer and flushes at 512 MB
  (`src/pglink.c:441-469` `[verified-by-code]`).
- **`malloc`, not `palloc`, for backend-lifetime option tables and libcurl
  buffers.** The option table is `malloc`'d "because it lives as long as the
  backend process does" (`src/option.c:159-166` `[verified-by-code]`), and the
  HTTP response buffers are `malloc`/`realloc`'d inside the curl write callback
  (`src/http.c:36-51` `[verified-by-code]`) — library-owned memory outside PG's
  context discipline, reclaimed by the reset-callback bridge above.
- **`AggregatingMergeTree`/`CollapsingMergeTree` engine awareness.** The
  `engine` foreign-table option is parsed into `ch_table_engine` +
  `ch_table_sign_field`, changing how aggregates and the sign column are
  deparsed (`src/custom_types.c:442-483` `[verified-by-code]`); IMPORT SCHEMA
  emits the engine option automatically (`src/pglink.c:971-985`
  `[verified-by-code]`).
- **`clickhousedb_mock` / `clickhousedb_raw_query`.** Extra SQL-callable
  entry points: `clickhousedb_mock` is a stub that errors unless pushed down
  ("mocked function should be pushed down", `src/clickhouse_fdw.c:2858-2861`
  `[verified-by-code]`), the mechanism by which ClickHouse-only functions
  (`argMax`, `dictGet`, …) are surfaced as PG functions that only ever run
  remotely.
- **Build is CMake with a `clickhouse-cpp` git submodule**, not PGXS/meson:
  `add_subdirectory(clickhouse-cpp)`, C++17, links
  `clickhouse-cpp-lib-static` + `stdc++` + libcurl + libuuid
  (`CMakeLists.txt` (root) `:1-79`; `src/CMakeLists.txt:1-40` `[verified-by-code]`).
  The `.so` is built as a CMake `MODULE` with `-bundle_loader ...postgres` on
  macOS (`src/CMakeLists.txt:35-49` `[verified-by-code]`).

## Links into corpus

- `[[pg_clickhouse]]` — the **newer official sibling** and explicit successor
  ("basically a continuation of this project", `README.md:4-7`
  `[from-README]`). Direct compare/contrast: this FDW's binary driver links the
  **C++ `clickhouse-cpp`** library and pays for it with an `extern "C"`
  boundary, `exc_palloc`-throwing allocators, `PG_TRY`-inside-C++ bridging, and
  an admitted longjmp-through-C++ memory leak (`src/binary.cc:688-697`);
  pg_clickhouse instead builds on the **header-only C `clickhouse-c`** client,
  which keeps the whole FDW in C and sidesteps the two-error-model impedance
  mismatch entirely.
- `[[tds_fdw]]` — the conformant-FDW foil: single protocol, read-only,
  per-scan connections, no join/agg pushdown. clickhouse_fdw shares its
  postgres_fdw-ported `foreign_expr_walker`/`FDW_COLLATE` deparser but adds a
  second transport, INSERT DML, pooled connections, and full pushdown.
- `[[pgrouting]]` / `[[pg_jieba]]` — the C++ exception-firewall spectrum.
  pgRouting is the *complete* firewall (catch-all → out-param, no exception or
  longjmp ever crosses); pg_jieba is the *missing* firewall; clickhouse_fdw is
  the *partial, self-documented* firewall in between.
- `[[pg_duckdb]]` / `[[deltax]]` — other analytics/OLAP-engine integrations
  crossing into a foreign columnar runtime; comparison points for the
  transport-abstraction and type-marshaling story.
- `[[wrappers]]` / `[[steampipe_postgres_fdw]]` — the framework-style FDWs
  (Rust trait + WASM loader; Go plugin FDW) that re-express the C `FdwRoutine`
  surface; clickhouse_fdw is the hand-written-C multi-driver point on that axis.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` handler/validator +
  `makeNode(FdwRoutine)` plumbing.
- `[[knowledge/idioms/memory-contexts]]` — the
  `MemoryContextRegisterResetCallback` bridge tying clickhouse-cpp `delete`
  teardown to `PortalContext` reset.
- `[[knowledge/idioms/error-handling]]` — the bidirectional, partial
  C++↔longjmp firewall (`try/catch` outbound, `PG_TRY` inbound, `exc_palloc`
  throwing `std::bad_alloc`, and the conceded leak).

## Anthropology takeaway

clickhouse_fdw is the doc-set's archetype of a **multi-transport FDW that pays
a language-boundary tax**: one `FdwRoutine`, a runtime-selected
`libclickhouse_methods` vtable, and two wire protocols — a native C++ binary
client and an HTTP/TSV client — behind it. Its single most reusable
observation is the **explicitly-partial exception firewall**: where pgRouting
guarantees no C++ exception and no PG longjmp ever crosses the boundary,
clickhouse_fdw catches C++ exceptions outbound, catches PG longjmp inbound at
the insert-prepare site via `PG_TRY`-inside-C++, throws `std::bad_alloc` from
its own `exc_palloc`, and *still* concedes — in a source comment it calls
"unfixable" — that the hot read-path `make_datum` can longjmp out through C++
frames and leak. That candor makes it the best corpus example of the
real-world middle of the firewall spectrum. Two secondary threads: the
**two-independent-type-mapping-layers** design (textual `parse_type` for
HTTP/IMPORT vs typed `get_corr_postgres_type`+`convert.c` for binary) shows how
much duplicated surface a dual-driver FDW carries; and the
**reset-callback-as-C++-destructor-bridge** is a clean, reusable pattern for any
extension that must free a foreign-runtime heap object on PG context teardown.

## Sources

Fetched 2026-07-07 (branch `master`), all via
`https://raw.githubusercontent.com/ildus/clickhouse_fdw/master/<path>`
(GitHub git/trees API + `get_file_contents` MCP tool are 403 for this
external repo in the cloud sandbox; raw host is open):

- `README.md` → HTTP 200 (157 lines; archived notice, driver usage, PG 11-17).
- `src/clickhouse_fdw.control` → HTTP 200 (4 lines; `default_version = '1.4'`,
  `relocatable = true`).
- `CMakeLists.txt` (root) → HTTP 200 (79 lines; pg_config discovery, regress
  test list).
- `src/CMakeLists.txt` → HTTP 200 (114 lines; `clickhouse-cpp` submodule,
  C++17, source list, curl/uuid link).
- `src/clickhouse_fdw.c` → HTTP 200 (2862 lines; deep-read handler +
  `_PG_init` + callback set; scan/insert lifecycle read in part).
- `src/connection.c` → HTTP 200 (409 lines; deep-read — driver dispatch +
  pooled connection cache + invalidation).
- `src/option.c` → HTTP 200 (285 lines; deep-read — validator, option surface).
- `src/pglink.c` → HTTP 200 (1094 lines; deep-read — the `libclickhouse_methods`
  vtables for both drivers, IMPORT SCHEMA, `parse_type`, escape).
- `src/binary.cc` → HTTP 200 (1014 lines; deep-read — the C++ boundary,
  `exc_palloc`, `make_datum`, `get_corr_postgres_type`, the firewall).
- `src/convert.c` → HTTP 200 (487 lines; deep-read — the second-stage
  `ch_convert_state` coercion machines).
- `src/custom_types.c` → HTTP 200 (565 lines; deep-read — hardcoded
  extension/function-name shippability roster + engine options).
- `src/shipable.c` → HTTP 200 (227 lines; deep-read — postgres_fdw-ported
  shippability cache; `shippable_extensions` always NIL).
- `src/deparse.c` → HTTP 200 (3957 lines; **grep-scanned only**, not
  line-by-line — confirmed `foreign_expr_walker`/`FDW_COLLATE`/`deparseAggref`/
  `chfdw_is_shippable` gating; the postgres_fdw-port claim is
  `[verified-by-code]` at the cited lines, the full deparse logic is
  `[inferred]` from the scan).
- `src/http.c` → HTTP 200 (220 lines; deep-read — libcurl driver, 418/419
  status synthesis).
- `src/parser.c` → HTTP 200 (78 lines; deep-read — TSV response tokenizer).

Unresolved / not fetchable: the **`clickhouse-cpp` submodule internals** are
NOT present under the raw host (they live in a separate git submodule), so all
claims about `clickhouse::Client`, `Block`, `ColumnRef`, `SelectCancelable`,
`PrepareInsert`, and the `Type::Code` enum are **`[inferred]`** from how
`src/binary.cc` calls them, tagged accordingly in-text where load-bearing.
The install SQL (`sql/init.sql`, `sql/functions.sql`, the `--1.x--1.y.sql`
migrations) exists (probe: `src/sql/init.sql` → HTTP 200) but was not fetched;
the extension header `clickhousedb_fdw.h` and `clickhouse_binary.hh`/
`clickhouse_internal.h` were not fetched, so struct field layouts
(`ch_connection`, `ch_cursor`, `CHFdwRelationInfo`, `ch_binary_*`) are
`[inferred]` from their use sites. No requested `.c`/`.cc`/`CMakeLists`/README
path 404'd.
