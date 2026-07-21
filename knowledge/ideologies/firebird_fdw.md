# firebird_fdw — an FDW onto a legacy RDBMS through a libpq-shaped shim

- **Repo:** github.com/ibarwick/firebird_fdw (branch `master`,
  `default_version = '1.5.0'`, `firebird_fdw.control:3`). Author Ian Barwick;
  actively maintained, PostgreSQL Licence.
- **Fetched:** `README.md` (731 lines), `firebird_fdw.control` (5 lines),
  `Makefile` (85 lines), `src/firebird_fdw.c` (4403 lines), `src/firebird_fdw.h`
  (374 lines), `src/convert.c` (2719 lines), `src/connection.c` (711 lines).
  `libfq` itself is a **separate repo** (github.com/ibarwick/libfq) and was NOT
  fetched — claims about its internals are tagged accordingly.

## Domain & purpose

A Foreign Data Wrapper mapping tables in a **Firebird** database (the
open-source descendant of Borland InterBase) to PostgreSQL foreign tables.
Where the reference wrapper [[knowledge/subsystems/contrib-postgres_fdw]]
bridges SQL→SQL over libpq, `firebird_fdw` bridges SQL→SQL over **libfq** — a
thin `libpq`-lookalike wrapper the *same author* wrote over Firebird's native
`isc_*` C client API (`ibase.h` / `fbclient`). It is read/write
(`INSERT`/`UPDATE`/`DELETE`), supports `IMPORT FOREIGN SCHEMA`, `ANALYZE`,
`TRUNCATE` (PG 14+), `COPY` / partition routing (PG 11+), batch insert (PG 14+),
connection caching, and pushdown of some `WHERE` conditions including
translation of a handful of built-in functions (`README.md:52-64`). The
divergence-of-record is that Firebird's client library is the old InterBase
`isc` call-and-transaction API, not a modern SQL wire protocol — so the whole
FDW is written against a purpose-built PGconn/PQexec-shaped facade rather than
against Firebird directly.

## How it hooks into PG

Standard FDW plumbing: `firebird_fdw_handler` fills an `FdwRoutine`
(`src/firebird_fdw.c:794-838`) with the full callback set of
[[knowledge/idioms/fdw-routine-callbacks]]:

- **Scan** — `GetForeignRelSize` / `GetForeignPaths` / `GetForeignPlan` /
  `BeginForeignScan` / `IterateForeignScan` / `ReScanForeignScan` /
  `EndForeignScan` (`:801-808`), plus `ExplainForeignScan` (`:804`).
- **Write** — `AddForeignUpdateTargets` / `PlanForeignModify` /
  `BeginForeignModify` / `ExecForeignInsert` / `ExecForeignUpdate` /
  `ExecForeignDelete` / `EndForeignModify` (`:815-825`), plus
  `IsForeignRelUpdatable` (`:814`), `GetForeignModifyBatchSize` /
  `ExecForeignBatchInsert` (`:820-821`), `ExecForeignTruncate` (`:829`), and
  `BeginForeignInsert` / `EndForeignInsert` for COPY/partition routing
  (`:836-837`).
- **DDL / stats** — `ImportForeignSchema` (`:833`) and `AnalyzeForeignTable`
  (`:811`).

The scan loop is the classic pattern of [[knowledge/idioms/fdw-iterate-scan]]:
`firebirdIterateForeignScan` runs the remote SELECT on first call via
`FQexec` (`:1635`), checks `FQresultStatus(...) == FBRES_TUPLES_OK` (`:1639`),
then walks the result set row-by-row with `FQntuples` / `FQnfields` /
`FQgetisnull` / `FQgetvalue` (`:1648-1707`) and builds each tuple with
`BuildTupleFromCStrings` through an `AttInMetadata` (`:1663,1726`). Note the
libfq call names are a **deliberate `PQ*`→`FQ*` transliteration**: `FQexec`,
`FQntuples`, `FQgetvalue`, `FQclear`, `FQstatus`, `CONNECTION_OK`,
`FBRES_TUPLES_OK` — so the scan body reads almost identically to postgres_fdw's
`PQexec` loop `[verified-by-code]`.

`_PG_init` is unusually **empty**: it only registers `exitHook` via
`on_proc_exit` (`:850-854`); there is no client-library global init call
(contrast mongo_fdw's `mongoc_init()`), because the Firebird/`isc` client needs
no process-global bootstrap `[verified-by-code]`. Remote SELECT text is built
by `buildSelectSql` (`:1356`) and the WHERE deparser lives in
`src/convert.c` (`convertExpr` and the `convert*` recursor family,
`convert.c:952-1830`).

## Where it diverges from core idioms

- **libfq is a libpq-lookalike shim over the isc API — the headline design
  choice.** The FDW never touches Firebird's `isc_*` calls directly; it links
  `-lfq -lfbclient` (`Makefile:30`) and includes a single `"libfq.h"`
  (`src/firebird_fdw.h:47`). Connection handles are typed `FBconn *` and result
  sets `FBresult *` (`src/firebird_fdw.h:213,239`) — the structural analogues of
  `PGconn *` / `PGresult *`. The author reshaped InterBase's stateful
  call-level interface into a PQ-style request/response API precisely so the
  FDW code could be modelled line-for-line on postgres_fdw. That libfq wraps the
  `isc_*` client and is co-developed with the FDW ("the two are usually
  developed in tandem") is `[from-README]` (`README.md:91-96`); the internals of
  that wrapping were not inspected here (`[inferred]`).

- **Row identity is Firebird's `RDB$DB_KEY`, smuggled through the PG tuple
  header's CTID + XMAX system columns.** Firebird exposes a per-row
  `RDB$DB_KEY` pseudo-column (an 8-byte physical row locator) as its
  ctid-equivalent; the README lists "UPDATE and DELETE statements use Firebird's
  row identifier RDB$DB_KEY" as a headline feature (`README.md:55-56`).
  `firebirdAddForeignUpdateTargets` adds **two** resjunk targets,
  `db_key_ctidpart` and `db_key_xmaxpart`, built as `Var`s over the
  `SelfItemPointerAttributeNumber` (CTID, `TIDOID`) and
  `MaxTransactionIdAttributeNumber` (XMAX, `INT4OID`) system attributes
  (`src/firebird_fdw.c:1908-1964`), registered via `add_row_identity_var` on
  PG ≥ 14 (`:1939,1964`). `convertDbKeyValue` splits the 8-byte key into two
  uint32 halves (`:1763-1779`) and the scan loop packs them into
  `tuple->t_self.ip_blkid` (`:1735-1736`). The header comment calls this "a bit
  of a hack, as it seems it's currently impossible to add an arbitrary column as
  a resjunk column" (`:1885-1887`), and a code comment notes the pre-PG-12 path
  used the tuple-header OID + CTID instead (`:1894-1895`). This is a genuinely
  different mechanism from mongo_fdw's `_id` column or postgres_fdw's remote
  `ctid`: the row identifier is *disassembled to fit the two 32-bit system-column
  slots PG will actually carry through the plan* `[verified-by-code]`.

- **Type conversion is SQL-text based, in `convert.c`.** Values come back from
  libfq as C strings (`FQgetvalue`) and go straight into
  `BuildTupleFromCStrings` (`src/firebird_fdw.c:1707,1726`), so inbound
  conversion leans on PG's own input functions via `AttInMetadata`. Outbound and
  literal conversion is `convert.c`'s job: `convertDatum` (`convert.c:649`)
  renders a Datum to Firebird SQL text, `convertConst` / `convertStringLiteral`
  (`convert.c:1126,927`) emit literals, and `convertFirebirdObject`
  (`convert.c:461`) maps Firebird column metadata to a PG `CREATE TABLE` during
  import. Firebird-specific type gaps are documented rather than silently
  mishandled: `DECFLOAT` is "not currently supported by libfq"
  (`README.md:558-563`), `INT128` imports as `NUMERIC(39,0)`
  (`README.md:565-569`) `[from-README]`.

- **Connection cache keyed by server+user, holding an `FBconn`.**
  `connection.c` keeps a `ConnectionHash` HTAB of `ConnCacheEntry` each holding
  an `FBconn *conn` and an `xact_depth` (`src/connection.c:32-44`);
  `firebirdInstantiateConnection` does the `HASH_ENTER` lookup
  (`:185-220`) and `firebirdGetConnection` opens via `FQconnectdbParams` with a
  `kw[]`/`val[]` array (`:64-160`) — the exact shape of libpq's
  `PQconnectdbParams`. On a dead handle it calls `FQreconnect`
  (`:288-290`). This mirrors postgres_fdw's per-user-mapping cache but stores an
  `FBconn` rather than a `PGconn` `[verified-by-code]`.

- **Character-set bridging is hand-maintained.** `firebirdGetConnection`
  translates PG's database encoding into Firebird's `client_encoding` names via
  an explicit `switch` (e.g. `PG_SQL_ASCII`→`NONE`, `PG_ISO_8859_5`→`ISO8859_5`,
  `PG_WIN866`→`DOS866`), falling through to `GetDatabaseEncodingName()`
  (`src/connection.c:121-152`). Where PG and Firebird disagree on encoding
  names the FDW rewrites transparently rather than relying on a shared
  catalog `[verified-by-code]`.

- **Transaction semantics are mapped, not identical.** Firebird has no
  READ-COMMITTED-by-default posture matching PG; `fb_begin_remote_xact` opens
  the remote transaction with `SET TRANSACTION SNAPSHOT` — "roughly equivalent
  to SERIALIZABLE" per its own comment (`src/connection.c:325-360`) — and
  stacks Firebird `SAVEPOINT s<n>` statements to mirror PG subtransaction
  depth (`:377-388`). A `fb_xact_callback` registered on `XactEvent` drives
  `FQcommitTransaction` at `XACT_EVENT_PRE_COMMIT` and `FQexec(conn,
  "ROLLBACK")` at abort (`:395-476`); the abort path carries an explicit
  caveat that Firebird may already have done an implicit rollback
  (`:463-465`) `[from-comment]`.

## Notable design decisions

- **Pushdown is opt-outable and function-aware but conservative.** WHERE
  deparse runs through `convert.c`'s recursor, which handles `OpExpr`,
  `BoolExpr`, `NullTest`, `BooleanTest`, `ScalarArrayOpExpr`, `RelabelType` and
  a small allow-list of functions — `convertFunctionConcat` /
  `Position` / `Substring` / `Trim` (`convert.c:1830,110-113`) — gated by
  `canConvertOp(..., firebird_version)` so it won't emit SQL a given Firebird
  version can't parse (`convert.c:118`). A `disable_pushdowns` server/table
  option turns the whole thing off for old/untested Firebird versions
  (`README.md:137-141`, `src/firebird_fdw.c:919,1076`). There is no JOIN or
  aggregate pushdown — narrower than postgres_fdw, comparable to the
  conservative end of the sibling FDWs.

- **`implicit_bool_type` bridges Firebird's late BOOLEAN.** Firebird only gained
  a native `BOOLEAN` in 3.0; the `implicit_bool_type` option turns on implicit
  conversion of Firebird integer columns to PG boolean, and the README spells
  out the resulting pushdown asymmetry (`WHERE boolcol IN (TRUE, NULL)` won't
  push down but `WHERE boolcol IS NOT FALSE` will) (`README.md:154,241-246`)
  `[from-README]`.

- **`TRUNCATE` is emulated.** Firebird has no `TRUNCATE`; the FDW's
  `ExecForeignTruncate` simulates it with `DELETE FROM`, and `CASCADE` /
  `RESTART IDENTITY` are unsupported (`README.md:303-314`) `[from-README]`.

- **`estimated_row_count` / primitive cost model.** `firebirdEstimateCosts`
  just picks startup cost 10 vs 25 based on whether the server address is
  `127.0.0.1`/`localhost` (`src/firebird_fdw.c:971-1001`) — self-described as
  "a very primitive implementation" (`:967-969`); a table option lets the user
  supply an `estimated_row_count` instead (`:949`).

- **`relocatable = true`** (`firebird_fdw.control:5`) — no schema-pinned
  objects, same as mongo_fdw.

- **A SIGINT workaround.** `fbSigInt` re-implements the core
  `StatementCancelHandler` because, per its comment, without it a SIGINT
  segfaults the backend — an artifact of the blocking `isc`/libfq client not
  cooperating with PG's interrupt machinery (`src/firebird_fdw.c:870-898`)
  `[from-comment]`.

## Links into corpus

- [[knowledge/subsystems/contrib-postgres_fdw]] — the reference SQL→SQL wrapper
  firebird_fdw is modelled on; libfq exists to make the modelling literal.
- [[knowledge/subsystems/foreign]] — the core SQL/MED / `FdwRoutine`
  infrastructure.
- [[knowledge/idioms/fdw-routine-callbacks]] — the callback set
  `firebird_fdw_handler` populates (`src/firebird_fdw.c:794-838`).
- [[knowledge/idioms/fdw-iterate-scan]] — the per-tuple `FQexec`/`FQgetvalue`
  scan loop shape.
- Sibling foreign-RDBMS FDWs, each reaching a different remote through a
  different client library: [[knowledge/ideologies/mysql_fdw]],
  [[knowledge/ideologies/oracle_fdw]], [[knowledge/ideologies/tds_fdw]],
  [[knowledge/ideologies/mongo_fdw]]. firebird_fdw is the point on that map
  where the remote is a **legacy RDBMS reached through a purpose-built
  libpq-shaped shim (libfq) over the old InterBase isc client API** — the only
  sibling whose author wrote the client facade specifically to make the FDW read
  like postgres_fdw.

## Sources

- `https://raw.githubusercontent.com/ibarwick/firebird_fdw/master/README.md`
- `https://raw.githubusercontent.com/ibarwick/firebird_fdw/master/firebird_fdw.control`
- `https://raw.githubusercontent.com/ibarwick/firebird_fdw/master/Makefile`
- `https://raw.githubusercontent.com/ibarwick/firebird_fdw/master/src/firebird_fdw.c`
- `https://raw.githubusercontent.com/ibarwick/firebird_fdw/master/src/firebird_fdw.h`
- `https://raw.githubusercontent.com/ibarwick/firebird_fdw/master/src/convert.c`
- `https://raw.githubusercontent.com/ibarwick/firebird_fdw/master/src/connection.c`
- All seven fetched URLs returned HTTP 200; no 404s. `src/libfq.h` was NOT
  probed (it lives in the separate github.com/ibarwick/libfq repo, referenced at
  `README.md:91-93`), so libfq-internal claims are `[inferred]`/`[from-README]`.

Confidence: `[verified-by-code]` for the FdwRoutine wiring, the empty
`_PG_init`, the `RDB$DB_KEY`→CTID/XMAX row-identity smuggling, the libfq
`FQ*`/`FBconn`/`FBresult` shim shape, the connection cache, the encoding switch,
and the `SET TRANSACTION SNAPSHOT` + savepoint transaction mapping. `[from-README]`
for the feature list (TRUNCATE emulation, IMPORT FOREIGN SCHEMA, batch insert,
DECFLOAT/INT128 gaps, implicit-bool semantics) and for libfq being a
co-developed libpq-like wrapper over the `isc` API. Claims about what libfq does
*inside* the wrapper are `[inferred]` — that repo was not fetched. The
`convert.c` WHERE-deparser was grepped for its recursor/function-allow-list
shape and `canConvertOp` gate; individual operator-translation rules beyond the
cited functions are `[inferred]`.
