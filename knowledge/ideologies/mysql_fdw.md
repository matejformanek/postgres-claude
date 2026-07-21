# mysql_fdw — an FDW onto a foreign RDBMS over a native binary client

- **Repo:** github.com/EnterpriseDB/mysql_fdw (branch `master`,
  `default_version = '1.2'`, `mysql_fdw.control:15`). Portions ex-PGDG
  2012-2014, maintained by EnterpriseDB.
- **Fetched:** `README.md` (525 lines), `mysql_fdw.control`, `Makefile`,
  `mysql_fdw.h` (345 lines), `mysql_fdw.c` (5066 lines), `connection.c`
  (302 lines), `mysql_query.c` (493 lines), `deparse.c` (2596 lines). The
  two large `.c` files were grepped and read in targeted windows, not whole.

## Domain & purpose

A Foreign Data Wrapper mapping **MySQL / MariaDB tables** to PostgreSQL
foreign tables. Where the reference wrapper
[[knowledge/subsystems/contrib-postgres_fdw]] bridges SQL→SQL over libpq to
another PostgreSQL, `mysql_fdw` bridges SQL→**MySQL SQL** over
`libmysqlclient` — but it does not deparse-and-send a SQL *string* the way
postgres_fdw does for scans. It speaks the MySQL **binary prepared-statement
client protocol** (`mysql_stmt_prepare` / `mysql_stmt_bind_*` /
`mysql_stmt_execute` / `mysql_stmt_fetch`, `README.md:47-52`). It is
read/write (INSERT/UPDATE/DELETE + TRUNCATE), maintains a per-session
connection cache, and pushes down WHERE, JOIN, ORDER BY, LIMIT/OFFSET, and a
capped set of aggregates (`README.md:53-102`). This is the "foreign RDBMS
reachable only through a vendor C client library" point on the FDW map:
close to postgres_fdw in *shape* (it reuses its deparser near-verbatim) but
divergent in *transport* (a dlopen'd binary protocol, not libpq).

## How it hooks into PG

Standard FDW plumbing: `mysql_fdw_handler` fills an `FdwRoutine`
(`mysql_fdw.c:518-566`) with the read set `GetForeignRelSize` /
`GetForeignPaths` / `GetForeignPlan` / `BeginForeignScan` /
`IterateForeignScan` / `ReScanForeignScan` / `EndForeignScan`
(`:523-529`) and a **full writable** set `AddForeignUpdateTargets` /
`PlanForeignModify` / `BeginForeignModify` / `ExecForeignInsert` /
`ExecForeignUpdate` / `ExecForeignDelete` / `EndForeignModify`
(`:532-538`) — the callback set of [[knowledge/idioms/fdw-routine-callbacks]].
It goes further than most siblings, wiring `RecheckForeignScan` (EvalPlanQual,
`:541`), `AnalyzeForeignTable` (`:547`), `ImportForeignSchema` (`:550`),
`BeginForeignInsert` / `EndForeignInsert` (COPY / partition routing,
`:553-554`), `GetForeignJoinPaths` (`:557`), `GetForeignUpperPaths`
(aggregate/grouping pushdown, `:560`), and `ExecForeignTruncate` (`:563`).
The scan loop is the classic [[knowledge/idioms/fdw-iterate-scan]] shape:
`mysqlIterateForeignScan` (`:779`) calls `mysql_stmt_fetch` (`:813`) for the
next row and converts each bound column with `mysql_convert_to_pg`
(`:824`, defined `mysql_query.c:56`).

**The external client library is dlopen'd, not linked-and-called directly.**
This is the sharpest bootstrap divergence from postgres_fdw (which links
libpq at build time and has no runtime symbol dance). `_PG_init`
(`mysql_fdw.c:464-501`) calls `mysql_load_library` (`:378`), which
`dlopen`s `libmysqlclient.so` with **`RTLD_LAZY | RTLD_DEEPBIND`**
(`:388`; plain `RTLD_LAZY` on macOS/BSD, `:386`) and then `dlsym`s ~30
`mysql_*` entry points into function pointers (`:393-422`). The header
`#define`s each public name to the loaded pointer, e.g.
`#define mysql_stmt_prepare (*_mysql_stmt_prepare)` (`mysql_fdw.h:44-73`).
`RTLD_DEEPBIND` exists specifically to stop libmysqlclient's internal
`list_delete` from binding to PostgreSQL's `list_delete` and crashing
`mysql_stmt_close` — documented in a long comment (`:352-376`). There is no
`_PG_fini`; process-exit cleanup is an `on_proc_exit` callback
(`mysql_fdw_exit` → `mysql_cleanup_connection`, `:500-511`) rather than a
library teardown call. Two planner-ish GUCs are registered in `_PG_init`:
`mysql_fdw.wait_timeout` and `mysql_fdw.interactive_timeout`
(`:472-498`), both `PGC_USERSET` session-timeout knobs pushed to the remote,
not pushdown toggles.

## Where it diverges from core idioms

- **Binary prepared-statement protocol, not SQL text over libpq.** For
  scans, `mysqlBeginForeignScan` (`mysql_fdw.c:574`) runs
  `mysql_stmt_init` → `mysql_stmt_prepare` (`:695-704`), sets the cursor and
  prefetch attrs via `mysql_stmt_attr_set` (`:722-726`), fetches result
  metadata with `mysql_stmt_result_metadata` (`:732`), and binds each output
  column with `mysql_bind_result` (`:755`, defined `mysql_query.c:412`).
  Rows arrive as bound C buffers, not a libpq `PGresult`. postgres_fdw sends
  a SQL cursor string and reads text/binary tuples through libpq; here the
  transport *is* the MySQL client protocol. `[verified-by-code]`
- **Two type-mapping directions, both hand-rolled.** Because MySQL's type
  system is not PostgreSQL's, mysql_fdw carries an explicit type-mapping
  table in each direction. `mysql_from_pgtyp` (`mysql_query.c:133-177`)
  maps PG OIDs to `MYSQL_TYPE_*` for parameter binding
  (INT4→`MYSQL_TYPE_LONG`, NUMERIC→`MYSQL_TYPE_DOUBLE`, TEXT/JSON/enum→
  `MYSQL_TYPE_STRING`, BYTEA→`MYSQL_TYPE_BLOB`, …), erroring on any
  unmapped type (`:170-175`). `mysql_convert_to_pg` (`:56-127`) goes the
  other way, feeding the datum string through the PG type's `typinput`
  proc. postgres_fdw needs none of this — the remote already speaks SQL
  types. `[verified-by-code]`
- **MySQL type quirks are special-cased in C.** `BIT(n)` comes back from
  MySQL as a decimal integer, so the wrapper converts decimal↔binary-string
  with `dec_bin` / `bin_dec` before handing PG a bit string
  (`mysql_query.c:97-106,357-372,459-493`, with a long explanatory comment
  at `:77-96`). Dates/timestamps are marshalled into `MYSQL_TIME` structs
  via a `DATE_MYSQL_PG` macro and `timestamp2tm` fixed to UTC
  (`:315-355,37-45`). These are impedance shims with no postgres_fdw
  analogue. `[verified-by-code]`
- **`deparse.c` is a near-verbatim port of postgres_fdw's `deparse.c`.**
  The file carries postgres_fdw's exact internal scaffolding —
  `foreign_glob_cxt`, `foreign_loc_cxt`, the `FDWCollateState` enum
  (`FDW_COLLATE_NONE/SAFE/UNSAFE`), `foreign_expr_walker`, `deparse_expr_cxt`
  (`deparse.c:45-79`, `:1974`) — the same structures postgres_fdw uses to
  decide pushdown safety and emit remote SQL. The divergences are MySQL
  dialect edits layered onto that port: identifiers quoted with **backticks**
  via `mysql_quote_identifier(str, '`')` (`:214-219,600`) instead of
  double-quotes; PG's `~~`/`!~~`/`~`/`!~` operators rendered as
  MySQL `LIKE BINARY` / `NOT LIKE BINARY` / `REGEXP BINARY` /
  `NOT REGEXP BINARY` (`:1196-1208`); and an ORDER-BY `IS NULL` prefix
  injected to emulate PG's NULL-ordering because MySQL sorts NULLs the
  opposite way (`:1412,2512-2526`; rationale `README.md:86-94`). Pushdown
  eligibility is additionally gated by a `mysql_pushability.c` /
  `mysql_fdw_pushdown.config` allow-list (`deparse.c:29`,
  `Makefile:8,11`) and a `mysql_is_builtin` check (`:1463,1918`) — a
  config-file mechanism postgres_fdw does not have. `[verified-by-code]`
- **Connection cache keyed by (serverid, userid), holding a `MYSQL*`.**
  `connection.c` keeps a `ConnectionHash` HTAB of `ConnCacheEntry`
  (`connection.c:40-52`) keyed by `ConnCacheKey{serverid, userid}`
  (`:34-38,95-97`), each caching a live `MYSQL *conn` (`:43`).
  `mysql_get_connection` (`:62`) finds-or-connects and reuses across a
  session; `mysql_fdw_connect` (`:195`) does the `mysql_init` /
  `mysql_ssl_set` / `mysql_real_connect` dance (`:208-257`). This mirrors
  postgres_fdw's per-user-mapping cache *shape* and even reuses its
  invalidation idiom — `mysql_inval_callback` (`:278`) is explicitly noted
  as "similar as pgfdw_inval_callback" (`:274-276`) and hooks the same
  `FOREIGNSERVEROID` / `USERMAPPINGOID` syscache callbacks (`:89-92`) — but
  it stores an opaque MySQL handle instead of a `PGconn`. It is also a
  deliberate fix for the old "new connection per query" behaviour
  (`README.md:41-45`). `[verified-by-code]` / `[from-README]`

## Notable design decisions

- **`use_remote_estimate` runs MySQL `EXPLAIN`, not `EXPLAIN` over a
  cursor.** When the server/table option is set, `mysqlGetForeignRelSize`
  (`mysql_fdw.c:984`) deparses the remote SELECT, prefixes `EXPLAIN`
  (`:1052-1057`), runs it with the *simple* `mysql_query` API, and scrapes
  the `rows` and `filtered` columns out of the result set to derive a row
  estimate (`:1059-1088`). Default is `false` (`mysql_fdw.h:95`,
  `README.md:185-188`), so the common path is local heuristic costing in
  `mysqlEstimateCosts` (`:1179`). `[verified-by-code]`
- **`fetch_size` drives server-side prefetch.** The `fetch_size` option
  (default 100, server- or table-level, `README.md:222-228`,
  `mysql_fdw.h:96`) is pushed into the statement as
  `STMT_ATTR_PREFETCH_ROWS` (`mysql_fdw.c:725-726`) — batching rows off the
  MySQL wire rather than the FETCH-N cursor loop postgres_fdw uses. `mysql_fdw.h`
  also carries a compile-time `MYSQL_PREFETCH_ROWS 100` default (`:34`).
  `[verified-by-code]`
- **Pushdown is conservative and allow-list-driven.** JOIN pushdown is
  restricted to INNER and LEFT/RIGHT OUTER between two same-server foreign
  tables with only relational/arithmetic join operators, explicitly to
  "avoid any potential join failure" (`README.md:67-75`); aggregate pushdown
  is capped at `min/max/sum/avg/count` to avoid emitting functions MySQL
  lacks (`README.md:77-84`); OFFSET-without-LIMIT and ALL/NULL LIMIT are not
  pushed (`README.md:96-102`). The wrapper prefers fetch-and-compute-locally
  over mistranslation. `[from-README]`
- **Rich secondary surface.** `IMPORT FOREIGN SCHEMA`
  (`mysqlImportForeignSchema`, `mysql_fdw.c:2104`) with
  `import_default` / `import_not_null` / `import_enum_as_text` /
  `import_generated` options (`README.md:289-318`); a broad SSL option set
  (`ssl_key/cert/ca/capath/cipher`, threaded into `mysql_ssl_set`,
  `connection.c:247`, `README.md:199-220`); `sql_mode` defaulting to
  `ANSI_QUOTES` and pushed via `SET sql_mode` on each connection setup
  (`mysql_fdw.c:689-691,1020-1022`); `mysql_default_file`, `init_command`,
  `reconnect`, `secure_auth`, `character_set`, and per-table `truncatable`
  (`README.md:176-247`); plus utility SQL functions `mysql_fdw_version()`
  and `mysql_fdw_display_pushdown_list()` (`README.md:338-344`,
  `mysql_fdw.c:185-186`). `[verified-by-code]` / `[from-README]`
- **`relocatable = true`** (`mysql_fdw.control:17`) — no schema-pinned
  objects. Supports PG 14-18 only, enforced in the Makefile
  (`Makefile:43-45`), and links whichever of `mariadbclient` /
  `mysqlclient` `mysql_config` reports (`Makefile:19-24`). `[verified-by-code]`

## Links into corpus

- [[knowledge/subsystems/contrib-postgres_fdw]] — the reference SQL→SQL
  wrapper; every divergence above is measured against it, and mysql_fdw's
  `deparse.c` / connection-invalidation code is a direct descendant of it.
- [[knowledge/subsystems/foreign]] — the core SQL/MED / `FdwRoutine`
  infrastructure and foreign-table / user-mapping catalogs.
- [[knowledge/idioms/fdw-routine-callbacks]] — the callback set
  `mysql_fdw_handler` populates (`mysql_fdw.c:518-566`).
- [[knowledge/idioms/fdw-iterate-scan]] — the per-tuple `mysql_stmt_fetch`
  scan loop shape.
- [[knowledge/subsystems/contrib-file_fdw]] — the other core FDW, for the
  "read-only, no pushdown" end of the spectrum mysql_fdw sits far from.
- Sibling foreign-RDBMS FDWs in this corpus:
  [[knowledge/ideologies/oracle_fdw]] and [[knowledge/ideologies/tds_fdw]]
  (SQL Server) — the other "vendor C client library" wrappers;
  [[knowledge/ideologies/sqlite_fdw]] (embedded SQL engine, no network);
  [[knowledge/ideologies/mongo_fdw]] (document store, BSON not SQL);
  [[knowledge/ideologies/clickhouse_fdw]] (columnar OLAP). mysql_fdw is the
  "foreign RDBMS reached over a dlopen'd native binary client protocol"
  point on that map — SQL-dialect-close to postgres_fdw, transport-distant.

## Sources

- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/README.md`
- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/mysql_fdw.control`
- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/Makefile`
- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/mysql_fdw.h`
- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/mysql_fdw.c`
- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/connection.c`
- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/mysql_query.c`
- `https://raw.githubusercontent.com/EnterpriseDB/mysql_fdw/master/deparse.c`
- All 8 URLs returned HTTP 200; no 404s. `mysql_pushability.c`,
  `option.c`, and the install SQL scripts were referenced (via Makefile /
  includes) but not fetched.

Confidence: `[verified-by-code]` for the FdwRoutine wiring, the dlopen /
`RTLD_DEEPBIND` bootstrap, the binary prepared-statement scan path, the
two-way type mapping, the BIT/date shims, the connection cache, and the
backtick/`LIKE BINARY`/`IS NULL` deparse edits — all cited to `file:line`.
`[from-README]` for the pushdown scope limits, the connection-pooling
rationale, and the option catalog. The claim that `deparse.c` is a
near-verbatim postgres_fdw port is `[verified-by-code]` at the level of
shared struct/enum names and function scaffolding (`foreign_glob_cxt`,
`FDWCollateState`, `foreign_expr_walker`); a line-by-line diff against
upstream `contrib/postgres_fdw/deparse.c` was not performed, so the exact
divergence percentage is `[inferred]`. `mysql_fdw.c` and `deparse.c` were
grepped and read in windows, not end-to-end.
