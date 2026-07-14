# oracle_fdw (laurenz/oracle_fdw) — an FdwRoutine bolted onto Oracle's OCI client, split across a header firewall

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `laurenz/oracle_fdw` @ branch `master`. ~546★, language **C**. All
> `file:line` cites below point into that repo (`oracle_fdw.c:NN`,
> `oracle_utils.c:NN`, `oracle_fdw.h:NN`, `oracle_gis.c:NN`), not `source/`,
> since this doc characterizes an *external* extension's divergence from core
> idioms. Cites verified against the files fetched on 2026-07-13 (see Sources
> footer). Backend target: an Oracle database, reached over Oracle's
> proprietary **OCI** (Oracle Call Interface) C client library.

oracle_fdw makes an Oracle table (or an arbitrary Oracle `query`) appear as a
PostgreSQL foreign table, "including pushdown of WHERE conditions and required
columns as well as comprehensive EXPLAIN support" (`README.oracle_fdw:4-6`
`[from-README]`). Structurally the PG-facing side is a fully-conformant
`FdwRoutine` with scan + modify + join pushdown + ANALYZE + IMPORT FOREIGN
SCHEMA. The **headline divergence** is *below* the FdwRoutine: the "remote
server" is reached through Oracle's OCI library, whose headers **cannot be
`#include`d in the same translation unit as `postgres.h`**, so the extension is
deliberately cleaved into a PG half (`oracle_fdw.c`, includes `postgres.h`,
never `oci.h`) and an Oracle half (`oracle_utils.c` + `oracle_gis.c`, include
`oci.h`, never `postgres.h`), communicating only through an opaque
`oracleSession *` handle defined in `oracle_fdw.h`. Every OCI error is funneled
back across that firewall through a family of `oracleError*` shims that the
Oracle half calls and the PG half implements with `ereport`.

## Domain & purpose

The control comment is `'foreign data wrapper for Oracle access'`, default
version `1.2`, `relocatable = true` (`oracle_fdw.control:1-4`)
`[verified-by-code]`. Where postgres_fdw answers "talk to another Postgres over
libpq", oracle_fdw answers "talk to an Oracle instance over OCI". Beyond the
handler/validator, the install script creates three extra SQL functions:
`oracle_close_connections()`, `oracle_diag(name)` (reports oracle_fdw /
PostgreSQL / OCI client / server versions), and `oracle_execute(server,
statement)` (run an arbitrary result-less statement on Oracle)
(`oracle_fdw--1.2.sql:15-34`) `[verified-by-code]`. The internal version string
is `ORACLE_FDW_VERSION "2.9.0"` (`oracle_fdw.h:19`) `[verified-by-code]`.

## How it hooks into PG

- **Handler / validator**: both declared `PG_FUNCTION_INFO_V1`
  (`oracle_fdw.c:322-323`) `[verified-by-code]` — the standard
  `[[knowledge/idioms/fmgr]]` handler pattern. `oracle_fdw_handler` allocates a
  `makeNode(FdwRoutine)` (`oracle_fdw.c:454`) and wires the **full** callback
  set (`oracle_fdw.c:456-482`) `[verified-by-code]`:
  - Planning/scan: `GetForeignRelSize`→`oracleGetForeignRelSize`
    (`:802`), `GetForeignPaths` (`:894`), `GetForeignJoinPaths`
    (`:932`, join pushdown **is** present), `GetForeignPlan` (`:1052`),
    `ExplainForeignScan`, `BeginForeignScan` (`:1263`), `IterateForeignScan`
    (`:1368`), `ReScanForeignScan`, `EndForeignScan`.
  - Modify: `AddForeignUpdateTargets`, `PlanForeignModify`,
    `BeginForeignModify`, `BeginForeignInsert`/`EndForeignInsert`,
    `ExecForeignInsert`/`Update`/`Delete` (`:2070`/`:2119`/`:2169`),
    `EndForeignModify`, `ExplainForeignModify`, `IsForeignRelUpdatable`.
  - `AnalyzeForeignTable`→`oracleAnalyzeForeignTable` (`:1216`) and
    `ImportForeignSchema`→`oracleImportForeignSchema` (`:2272`)
    `[verified-by-code]`. So unlike the read-only `[[knowledge/ideologies/tds_fdw]]`,
    oracle_fdw is a full read/write FDW.
- **`_PG_init` is a version gate plus one exit hook**: it reads
  `server_version_num`, hard-`ereport(ERROR)`s on a blocklist of known-broken PG
  minor releases, then registers `on_proc_exit(&exitHook, …)`
  (`oracle_fdw.c:770-793`) `[verified-by-code]`. No shmem, no GUCs, no
  `shared_preload_libraries` requirement — the whole extension is
  backend-local plus the linked OCI client.
- **Options validator** dispatches on catalog `Relation` OID the textbook way;
  notably `nls_lang` is attached to `ForeignDataWrapperRelationId` and
  `isolation_level` / `dbserver` to `ForeignServerRelationId`
  (`oracle_fdw.c:228-231`) `[verified-by-code]`, with per-option value checks
  raising `ERRCODE_FDW_INVALID_ATTRIBUTE_VALUE` (`:544-637`) `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. A hard translation-unit firewall: `postgres.h` and `oci.h` never meet

The reason the codebase is split at all is stated in the header's own banner:
"It is necessary to split oracle_fdw into two source files because PostgreSQL
and Oracle headers cannot be #included at the same time" (`oracle_fdw.h:6-7`)
`[from-comment]`. The split is real and verifiable:
- `oracle_fdw.c` opens with `#include "postgres.h"` and dozens of `catalog/…`,
  `optimizer/…`, `foreign/fdwapi.h` includes (`oracle_fdw.c:8-80`), and **never**
  includes `oci.h` `[verified-by-code]`.
- `oracle_utils.c` opens with `#include <oci.h>` then `#include "oracle_fdw.h"`
  and **no** `postgres.h` (`oracle_utils.c:22-24`) `[verified-by-code]`.
  `oracle_gis.c` does the same (`oracle_gis.c:15,22`) `[verified-by-code]`.
- The seam is `oracle_fdw.h`: OCI-typed structs (`connEntry` holding
  `OCISvcCtx *svchp` / `OCISession *userhp` / `OCIType *geomtype`,
  `srvEntry` holding `OCIServer *`, `envEntry` holding `OCIEnv *`/`OCIError *`)
  are guarded behind `#ifdef OCI_ORACLE` (`oracle_fdw.h:22-55`) so the PG half
  never sees them, while the opaque `struct oracleSession` is defined with the
  explicit comment "This is necessary to be able to pass them back to
  oracle_fdw.c without having to #include oci.h there" (`oracle_fdw.h:57-73`)
  `[from-comment]`. This is a divergence from every libpq-based FDW, where one
  `.c` file freely mixes PG and client headers because libpq's headers are
  PG-clean.

### 2. The "connection" is an OCI session/service-context tree, not a libpq PGconn

`oracleGetSession` (`oracle_utils.c:107`) builds a three-level cached handle
tree — env (`OCIEnv`/`OCIError`, keyed by `nls_lang`) → server
(`OCIServer`, keyed by connect string) → connection (`OCISvcCtx`/`OCISession`,
keyed by user) — reflecting that "Oracle sessions can be multiplexed over one
server connection" (`oracle_fdw.h:24-25`) `[from-comment]`. Establishment is a
sequence of OCI calls: `OCIEnvCreate` (`oracle_utils.c:198`), `OCIServerAttach`
(`:311`), `OCITransStart` (`:538`), each wrapped in `checkerr(…)`
`[verified-by-code]`. There is no handshake protocol object like `PGconn`; the
cached payload is a linked list of OCI handles that outlive the transaction.

### 3. Oracle errors cross the firewall through `oracleError*` → `ereport`

The Oracle half cannot call `ereport` (no `postgres.h`), so error text is
captured by `checkerr`, which on `OCI_ERROR`/`OCI_SUCCESS_WITH_INFO` calls
`OCIErrorGet` into a static `oraMessage[ERRBUFSIZE]` buffer, strips the trailing
newline, and synthesizes an `ORA-00100` message for `OCI_NO_DATA`
(`oracle_utils.c:2917-2941`) `[verified-by-code]`. The Oracle half then calls
one of the `oracleError_*` shims (`oracleError_d`, `oracleError_sd`,
`oracleError_ssdh`, `oracleError_i`, `oracleError_ii`, `oracleError`), passing an
`oraError` enum + the captured `oraMessage`. Those shims live in the PG half and
are the *only* place OCI failures become `ereport(ERROR)`
(`oracle_fdw.c:7235-7320`) `[verified-by-code]`. The `oraError` enum is mapped to
a real SQLSTATE by a `to_sqlstate` macro that special-cases deadlock, NOT NULL,
check, and FK violations, defaulting to `ERRCODE_FDW_ERROR`
(`oracle_fdw.c:7215-7228`) `[verified-by-code]`. Two idiomatic touches survive
the crossing: `oracleError_d` runs `CHECK_FOR_INTERRUPTS()` first so a
cancelled backend reports the cancel rather than the Oracle error
(`oracle_fdw.c:7238`), and `oracleError` routes `%m`-containing messages through
`errcode_for_file_access()` (`oracle_fdw.c:7302-7315`) `[verified-by-code]` —
see `[[knowledge/idioms/error-handling]]`.

### 4. Transactions are coupled to an Oracle OCI transaction with a chosen isolation level

oracle_fdw registers `RegisterXactCallback(transactionCallback, …)` +
`RegisterSubXactCallback(subtransactionCallback, …)` (`oracle_fdw.c:7161-7162`)
`[verified-by-code]`. `transactionCallback` maps PG xact events onto OCI:
`XACT_EVENT_PRE_COMMIT` → `oracleEndTransaction(arg, 1, 0)`,
`XACT_EVENT_ABORT` → `oracleEndTransaction(arg, 0, 1)`, and
`XACT_EVENT_PRE_PREPARE` is hard-rejected — "cannot prepare a transaction that
used remote tables" (`oracle_fdw.c:6480-6518`) `[verified-by-code]`, so 2PC
across the Oracle link is refused (the same stance
`[[knowledge/ideologies/sqlite_fdw]]` takes). The remote commit/rollback are OCI
calls `OCITransCommit` / `OCITransRollback` (`oracle_utils.c:732,745`)
`[verified-by-code]`. Subtransactions map to Oracle savepoints:
`subtransactionCallback` calls `oracleEndSubtransaction` on abort/pre-commit-sub
(`oracle_fdw.c:6018-6023`; `oracle_utils.c:762`) `[verified-by-code]`.

The isolation level is a *first-class option* because Oracle's snapshot model
matters for scan stability: `isolation_level` defaults to
`ORA_TRANS_SERIALIZABLE` (`oracle_fdw.c:192,214`), validated by
`getIsolationLevel` to `serializable`/`read_committed`/`read_only`
(`oracle_fdw.c:6957-6973`) `[verified-by-code]`, and mapped in the Oracle half
to `OCI_TRANS_SERIALIZABLE` / `OCI_TRANS_NEW` / `OCI_TRANS_READONLY` before
`OCITransStart` (`oracle_utils.c:124-138`) `[verified-by-code]`. The README
explains why serializable is the default: "the transaction isolation level must
guarantee read stability … only guaranteed with Oracle's SERIALIZABLE or READ
ONLY" (`README.oracle_fdw:176-179`) `[from-README]`. A PG-side
`transaction_read_only` GUC of `on` overrides the option to `ORA_TRANS_READ_ONLY`
at scan begin (`oracle_fdw.c:1341-1343`) `[verified-by-code]`.

### 5. Character-set bridging via `NLS_LANG` and `putenv`, not per-value encoding

Rather than converting each value, oracle_fdw configures the OCI client's
globalization once. `guessNlsLang` derives an `NLS_LANG` string from the PG
server encoding when the option is unset (`oracle_fdw.c:2494,2809`)
`[verified-by-code]`, and the Oracle half's `setOracleEnvironment` pins Oracle
formats process-wide with `putenv("NLS_DATE_LANGUAGE=AMERICAN")`,
`putenv("NLS_DATE_FORMAT=YYYY-MM-DD HH24:MI:SS BC")`, etc.
(`oracle_utils.c:1395-1408`) `[verified-by-code]`. The `nchar` option selects a
more expensive national-character conversion path
(`OCI_NCHAR_LITERAL_REPLACE_ON`, `oracle_utils.c:190`; README rationale at
`README.oracle_fdw:188-198`) `[verified-by-code]`/`[from-README]`. Because the
env cache is keyed by `nls_lang` (`oracle_utils.c:160-168`), two different
`NLS_LANG` settings get two `OCIEnv` handles.

### 6. `SDO_GEOMETRY` ↔ PostGIS EWKB is a whole separate translation unit

`oracle_gis.c` exists solely "to convert between Oracle SDO_GEOMETRY and PostGIS
EWKB" (`oracle_gis.c:3-4`) `[from-comment]` and "relies heavily on the PostGIS
internal data structure … in liblwgeom.h" (`oracle_gis.c:9-12`)
`[from-comment]`. It hand-rolls the EWKB type constants and Z/M/SRID flag bits
(`oracle_gis.c:24-42`) `[verified-by-code]` and provides `oracleEWKBToGeom`
(build an Oracle `MDSYS.SDO_GEOMETRY` OCI object from EWKB, `:366`) and
`oracleGetEWKBLen` / the `ewkb*Fill` family (serialize an OCI geometry back to
EWKB, `:437`+) `[verified-by-code]`. PostGIS's presence is detected lazily in
the Oracle-session path: `initializePostGIS` runs `SearchSysCacheList2` for a
`geometry_recv(internal)` function and sets `GEOMETRYOID`, giving up if it finds
more than one PostGIS install (`oracle_fdw.c:7331-7360`) `[verified-by-code]` —
done there rather than in `_PG_init` "because we need to look up system
catalogs" (`oracle_utils.c:153-157` calls it before the cache scan)
`[from-comment]`. Geometry binds via a dedicated `BIND_GEOMETRY` path
(`oracle_fdw.c:6067`) `[verified-by-code]`.

## Notable design decisions (with cites)

- **A rich Oracle type enum drives conversion.** `oraType`
  (`oracle_fdw.h:78-104`) enumerates 23 Oracle types (VARCHAR2, NUMBER,
  BINARYFLOAT, INTERVALY2M, BLOB/CLOB/NCLOB, BFILE, LONG, GEOMETRY, XMLTYPE …);
  `convertTuple` (`oracle_fdw.c:415,1403`) turns fetched Oracle values into PG
  Datums per column `[verified-by-code]`.
- **Modify parameters are bind-typed from the Oracle column type.** `addParam`
  maps each `oraType` to a `bindType` (NUMBER→BIND_NUMBER, CLOB→BIND_LONG,
  RAW+UUID→BIND_STRING, BLOB→BIND_LONGRAW, GEOMETRY→BIND_GEOMETRY) and
  explicitly `ereport`s that a `BFILE` column cannot be inserted/updated
  (`oracle_fdw.c:6030-6076`) `[verified-by-code]`.
- **ANALYZE really samples Oracle.** `oracleAnalyzeForeignTable` returns `true`
  and installs `acquireSampleRowsFunc` (`oracle_fdw.c:1218`,
  `:3621`) `[verified-by-code]`, which reservoir-samples rows through the same
  `convertTuple` path under a short-lived memory context
  (`oracle_fdw.c:3638-3766`) `[verified-by-code]` — unlike
  `[[knowledge/ideologies/sqlite_fdw]]`, whose ANALYZE is a no-op.
- **Qual/column pushdown with a bespoke deparser.** `createQuery`
  (`oracle_fdw.c:2946`) builds the Oracle SELECT; `getUsedColumns` prunes to
  referenced columns (`:2972`), `deparseWhereConditions` splits remote vs local
  quals (`:394,844`), and `deparseExpr` (`:390`) renders shippable expressions
  to Oracle SQL, with `deparseDate`/`deparseTimestamp`/`deparseInterval`
  handling Oracle literal formats (`:403-405`) `[verified-by-code]`. ORDER BY
  pushdown is `pushdownOrderBy` (`:425`) `[verified-by-code]`.
- **Plan data is serialized as a `List` of `Const`s** across the
  planner/executor boundary: `serializePlanData` / `deserializePlanData`
  (`oracle_fdw.c:398,400`) round-trip the `OracleFdwState` (isolation level,
  columns, query) through `serializeInt`/`serializeString`
  (`oracle_fdw.c:5545,5655`) `[verified-by-code]`.
- **Shutdown is a single `on_proc_exit` hook.** `exitHook`
  (`oracle_fdw.c:412,792`) closes OCI connections at backend exit;
  `oracle_close_connections()` exposes the same teardown to SQL
  (`oracle_fdw.c:662`; `oracle_fdw--1.2.sql:15-17`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/subsystems/foreign]]` — the `FdwRoutine` dispatch + catalog
  accessors this extension plugs into; the single most important cross-ref.
- `[[knowledge/subsystems/contrib-postgres_fdw]]` — the in-core libpq FDW to
  contrast against: oracle_fdw is the "same FdwRoutine, but the client is OCI and
  lives behind a header firewall" cousin.
- `[[knowledge/ideologies/tds_fdw]]` — the read-only single-source-C FDW foil;
  oracle_fdw is its full read/write + join-pushdown + ANALYZE counterpart over a
  different proprietary client.
- `[[knowledge/ideologies/sqlite_fdw]]` — closest structural sibling: another C
  FDW that maps a foreign type system onto PG and refuses 2PC; contrast its
  in-process `sqlite3*` vs oracle_fdw's networked OCI session tree.
- `[[knowledge/ideologies/wrappers]]` — the high-divergence Rust FDW *framework*;
  oracle_fdw is the hand-written-C, single-backend point on that spectrum.
- `[[knowledge/ideologies/postgis]]` — the PostGIS internals (`liblwgeom` /
  serialized geometry) that `oracle_gis.c` targets when transporting EWKB.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` handler/validator +
  the `oracle_diag`/`oracle_execute`/`oracle_close_connections` SQL functions.
- `[[knowledge/idioms/fdw-routine-callbacks]]` + `[[knowledge/idioms/fdw-iterate-scan]]`
  — the callback set and the scan loop this extension implements.
- `[[knowledge/idioms/error-handling]]` — the `oracleError*` → `ereport` bridge,
  `to_sqlstate` mapping, `CHECK_FOR_INTERRUPTS`, and `errcode_for_file_access`.
- `[[knowledge/idioms/memory-contexts]]` — the short-lived `convertTuple` context
  used during scan and ANALYZE sampling.
- `[[knowledge/idioms/catalog-conventions]]` — the `valid_options[]`-by-catalog-OID
  validator (`ForeignDataWrapperRelationId` / `ForeignServerRelationId` / …).

> Corpus gap: there is still no idiom doc for the **cross-header-firewall FDW**
> pattern — a client library whose headers clash with `postgres.h`, forcing a
> two-TU split communicating through an opaque handle + an error-shim family.
> oracle_fdw is the canonical example; worth an
> `idioms/fdw-header-firewall.md`.

## Sources

Fetched 2026-07-13 (branch `master`), all via
`https://raw.githubusercontent.com/laurenz/oracle_fdw/master/<path>`:

- `README.oracle_fdw` @ 2026-07-13T00:00Z → HTTP 200 (cookbook / options /
  internals; isolation + nchar rationale read in depth).
- `oracle_fdw.control` @ 2026-07-13T00:00Z → HTTP 200 (4 lines).
- `oracle_fdw--1.2.sql` @ 2026-07-13T00:00Z → HTTP 200 (handler/validator +
  `oracle_close_connections`/`oracle_diag`/`oracle_execute` + CREATE FDW).
- `oracle_fdw.h` @ 2026-07-13T00:00Z → HTTP 200 (256 lines; the header firewall,
  `#ifdef OCI_ORACLE` struct tree, opaque `oracleSession`, `oraType` enum).
- `oracle_fdw.c` @ 2026-07-13T00:00Z → HTTP 200 (7373 lines; FdwRoutine wiring,
  `_PG_init`, deparse/pushdown, xact callbacks, `oracleError*` bridge,
  `initializePostGIS`).
- `oracle_utils.c` @ 2026-07-13T00:00Z → HTTP 200 (3438 lines; the OCI half —
  `oracleGetSession`, isolation mapping, `checkerr`/`OCIErrorGet`,
  `setOracleEnvironment`, `OCITransStart`/`Commit`/`Rollback`).
- `oracle_gis.c` @ 2026-07-13T00:00Z → HTTP 200 (1516 lines; SDO_GEOMETRY ↔ EWKB
  conversion; only the entry points + EWKB header constants read in depth).

No 404 gaps — all seven requested paths returned HTTP 200. Not deep-read: the
full `deparseExpr` shippability walker, the LOB-streaming code in
`oracle_utils.c`, the per-`ewkb*Fill` geometry serializers, and the
`fold_case`/IMPORT FOREIGN SCHEMA type-mapping table.
