# hdfs_fdw — a Hadoop/Hive FDW that embeds a JVM in the backend

- **Repo:** github.com/EnterpriseDB/hdfs_fdw (branch `master`,
  default_version `2.0.5`, `hdfs_fdw.control:16`).
- **Fetched:** `README.md` (521 lines), `hdfs_fdw.control`, `Makefile`,
  `hdfs_fdw.c` (3523 lines), `hdfs_connection.c` (92 lines),
  `hdfs_query.c` (189 lines).

## Domain & purpose

A Foreign Data Wrapper onto **Apache Hive / Spark SQL over HDFS**. It exposes
Hive tables (via HiveServer2, or a Spark Thrift endpoint) as PostgreSQL foreign
tables, translating queries into **HiveQL** and pushing down joins, aggregates,
ORDER BY, and LIMIT (`README.md`, `hdfs_fdw.c:340-388`). It supports two remote
flavours, `hiveserver2` and `spark`, selected by a `client_type` server option
(`hdfs_fdw.c:575,1332-1343`).

## How it hooks into PG

The FDW half is textbook: `hdfs_fdw_handler` fills a full `FdwRoutine`
(`hdfs_fdw.c:434-460`) — not just scan/`Iterate`, but also `ReScanForeignScan`,
`RecheckForeignScan`, `ExplainForeignScan`, `AnalyzeForeignTable`,
`GetForeignJoinPaths`, and `GetForeignUpperPaths` (aggregate/grouping
pushdown). That is the same callback surface as
[[knowledge/subsystems/contrib-postgres_fdw]], documented in
[[knowledge/idioms/fdw-routine-callbacks]].

The **transport** is where it leaves every other FDW in the corpus behind.
Hive's only client is a Java JDBC driver, so `hdfs_fdw` **starts a JVM inside
the PostgreSQL backend process** and drives the JDBC client over JNI through a
C++ bridge library, `libhive`:

- `_PG_init` registers `hdfs_fdw.jvmpath` (path to `libjvm.so`) and
  `hdfs_fdw.classpath` (path to `HiveJdbcClient-X.X.jar`) GUCs, then loads the
  JVM; failure is a hard `ereport(ERROR)` — *"could not load JVM … Add path of
  libjvm.so to hdfs_fdw.jvmpath"* / *"Add path of HiveJdbcClient-X.X.jar to
  hdfs_fdw.classpath"* (`hdfs_fdw.c:318-339, ~393-395`).
- The build links the C++ bridge and the JVM: `SHLIB_LINK := -L libhive
  -lhive -lstdc++ -L$(JDK_INCLUDE)` with `-I$(JDK_INCLUDE)` on the include path
  (`Makefile`). So the loadable `.so` pulls in `libstdc++` and the JDK headers —
  unusual company for a backend module.
- A connection is a `jdbc:hive2://host:port/db` URL assembled in
  `hdfs_get_connection` (`hdfs_connection.c:29-49`), handed to the bridge
  entry `DBOpenConnection` (`:52`), which returns an **integer handle** —
  connections are identified by an `int` index into a pool that lives on the
  **C++/JVM side**, released via `DBCloseConnection` (`hdfs_rel_connection`,
  `:79-92`).

## Where it diverges from core idioms

- **A JVM in the backend, for the data path.** [[knowledge/ideologies/pljava]]
  also embeds a JVM, but for running user PL functions; `hdfs_fdw` embeds one
  as the *only way to reach the remote store*. Every query against an
  hdfs_fdw table runs through JNI into a long-lived JVM co-resident with the
  backend — a heavyweight, GC'd runtime sharing the process with PG's memory
  contexts and signal handlers. Nothing else in the FDW corpus
  ([[knowledge/ideologies/mongo_fdw]] via `libmongoc`,
  [[knowledge/ideologies/duckdb_fdw]] via embedded DuckDB,
  [[knowledge/ideologies/clickhouse_fdw]] via HTTP/native, sqlite/ogr/tds via C
  libs) takes on a managed-runtime dependency of this weight.
- **Connection identity is an opaque `int`, not a PGconn HTAB.** postgres_fdw
  and mongo_fdw both key a `HTAB` connection cache on `(userid, umid)` and store
  a native handle. `hdfs_fdw` delegates pooling to the bridge entirely: the C
  code only ever holds an `int con_index` (`hdfs_connection.c`,
  `hdfs_fdw.c` scan state) — the real connection objects, and their lifetime,
  are inside the JVM/libhive layer, invisible to PG's resource-owner and
  transaction machinery. There is no per-xact callback tearing these down the
  way postgres_fdw's `pgfdw_xact_callback` does.
- **HiveQL, not SQL, and a Thrift/JDBC round trip per fetch.** `hdfs_query.c`
  and the deparse path emit Hive's SQL dialect; result rows arrive as JDBC
  ResultSet columns marshalled back across JNI. The "remote" is a
  batch/warehouse engine, so cardinality estimates and cost are coarse
  (`hdfsGetForeignRelSize`, `hdfs_fdw.c:493`; `AnalyzeForeignTable` support
  exists but Hive stats are approximate).
- **`client_type` heterogeneity is refused mid-join.** Because the HiveServer2
  and Spark dialects differ, `hdfsGetForeignJoinPaths` bails with
  `elog(ERROR, "Multiple client_type server options not supported")` if the two
  join relations come from different client types (`hdfs_fdw.c:1332-1340`) —
  pushdown is only attempted within one remote flavour.

## Notable design decisions

- **Rich auth surface baked into the JDBC URL.** `hdfs_get_connection`
  conditionally appends `;ssl=true`, `;useSystemTrustStore=true`,
  `;sslTrustStore=…`, `;trustStorePassword=…`, and `;auth=<type>` (defaulting to
  `;auth=noSasl` when no username is set) (`hdfs_connection.c:33-48`). Secrets
  like `trustStorePassword` flow through a `StringInfo` connection string and
  into a `DEBUG3` log line (`:50`) — worth noting for a security review.
- **Pushdown is per-shape and GUC-gated**, mirroring mongo_fdw: separate
  `enable_join_pushdown` / `enable_aggregate_pushdown` /
  `enable_order_by_pushdown` / `enable_limit_pushdown` booleans
  (`hdfs_fdw.c:340-388`), each consulted before the corresponding upper-path is
  offered.
- **`relocatable = true`, no bespoke catalog** (`hdfs_fdw.control:18`) — all
  configuration is FDW options + GUCs; the extension ships only the handler and
  validator functions.

## Links into corpus

- [[knowledge/subsystems/contrib-postgres_fdw]] — the reference wrapper and the
  full `FdwRoutine` incl. join/upper-path pushdown that hdfs_fdw mirrors.
- [[knowledge/subsystems/foreign]] — core SQL/MED infrastructure.
- [[knowledge/idioms/fdw-routine-callbacks]], [[knowledge/idioms/fdw-iterate-scan]]
  — the callback set and scan loop.
- [[knowledge/ideologies/pljava]] — the *other* in-backend-JVM extension; the
  sharpest comparison point for "what does hosting a JVM inside a backend cost."
- [[knowledge/ideologies/mongo_fdw]], [[knowledge/ideologies/duckdb_fdw]],
  [[knowledge/ideologies/clickhouse_fdw]], [[knowledge/ideologies/steampipe_postgres_fdw]]
  — sibling FDWs onto non-PostgreSQL engines, for the transport-mechanism
  spectrum (C driver / embedded engine / HTTP / **JVM+JDBC**).

## Sources

- `https://raw.githubusercontent.com/EnterpriseDB/hdfs_fdw/master/README.md`
- `https://raw.githubusercontent.com/EnterpriseDB/hdfs_fdw/master/hdfs_fdw.control`
- `https://raw.githubusercontent.com/EnterpriseDB/hdfs_fdw/master/hdfs_fdw.c`
- `https://raw.githubusercontent.com/EnterpriseDB/hdfs_fdw/master/hdfs_connection.c`
- `https://raw.githubusercontent.com/EnterpriseDB/hdfs_fdw/master/hdfs_query.c`
- `Makefile` fetched for the JVM/libhive linkage.

Confidence: `[verified-by-code]` for the FdwRoutine wiring, the JVM/classpath
GUCs + load-or-error, the int-handle connection model, the JDBC URL/auth
assembly, and the client_type join guard; `[from-README]` for the
Hive/Spark/HiveServer2 background. `hdfs_query.c`/deparse were grepped, not read
in full — the exact HiveQL translation details are `[inferred]`. The C++
`libhive`/JNI bridge itself was not fetched (separate source tree); its internal
JVM management is `[from-comment]`/`[inferred]` from the C-side entry points.
