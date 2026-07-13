# ogr_fdw (pramsey/pgsql-ogr-fdw) — an FdwRoutine over the GDAL/OGR geospatial data-access *library*

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pramsey/pgsql-ogr-fdw` @ branch `master`. ~262★, language **C**. All
> `file:line` cites below point into that repo (cited as `ogr_fdw.c:NN`,
> `ogr_fdw_common.c:NN`, etc.), not `source/`, since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-07-13 (see Sources footer). Backend target: **OGR**, the
> vector half of the GDAL library, linked into the backend process — not a
> network server (`README.md:6` `[from-README]`).

ogr_fdw exposes any OGR/GDAL *vector* data source — Shapefile, GeoJSON,
GeoPackage, CSV, KML, or even a remote PostGIS/Oracle/WFS layer that OGR itself
knows how to reach — as a set of PostgreSQL foreign tables. The control comment
is exactly `'foreign-data wrapper for GIS data access'` (`ogr_fdw.control:2`),
`default_version = '1.1'`, `relocatable = true` (`ogr_fdw.control:3-5`)
`[verified-by-code]`. Where `[[knowledge/subsystems/contrib-postgres_fdw]]`
answers "talk to another Postgres over libpq" and
`[[knowledge/ideologies/sqlite_fdw]]` answers "talk to a SQLite file via the
linked-in engine", ogr_fdw answers "talk to *whatever GDAL can open* via the
linked-in GDAL library". **Headline divergence:** the "foreign server" is not a
server at all but an OGR **data-source handle** (`GDALDatasetH`) plus a layer
handle (`OGRLayerH`) opened in the backend's own address space
(`ogr_fdw.h:157-158` `[verified-by-code]`) — so a single FDW abstracts an entire
*format-abstraction layer*, and the extension inherits GDAL's whole driver
catalog for free (schema autodiscovery, geometry transport, and read/write
capability all delegate to whatever OGR driver backs the source).

## Domain & purpose

A foreign server carries `datasource` (the OGR connection string, required),
`format` (driver name), `config_options`, `open_options`, `character_encoding`,
and `updateable`; a foreign table carries `layer` (required) and `updateable`;
a column carries `column_name` (`ogr_fdw.c:88-109` `[verified-by-code]`). There
is no host/port/user/password surface at all — postgres_fdw's network/auth
options are replaced by an OGR datasource string and GDAL open flags. If PostGIS
is installed, OGR geometries surface as `geometry`; if not, they surface as
`bytea` WKB (`README.md:33` `[from-README]`, enforced at
`ogr_fdw.c:349`/`:378`).

## How it hooks into PG

Standard `CREATE FOREIGN DATA WRAPPER ogr_fdw HANDLER ogr_fdw_handler VALIDATOR
ogr_fdw_validator` wiring (`ogr_fdw--1.1.sql:16-18`). Both entry points are
`PG_FUNCTION_INFO_V1` (`ogr_fdw.c:117-118` `[verified-by-code]`), the
`[[knowledge/idioms/fmgr]]` handler pattern. `ogr_fdw_handler` allocates a
`makeNode(FdwRoutine)` and fills it (`ogr_fdw.c:392-417` `[verified-by-code]`):

- **Read support** (`ogr_fdw.c:395-401`): `GetForeignRelSize` →
  `ogrGetForeignRelSize`, `GetForeignPaths`, `GetForeignPlan`,
  `BeginForeignScan`, `IterateForeignScan`, `ReScanForeignScan`,
  `EndForeignScan`.
- **Write support** (`ogr_fdw.c:404-410`): `AddForeignUpdateTargets`,
  `BeginForeignModify`, `ExecForeignInsert`/`Update`/`Delete`,
  `EndForeignModify`, and `IsForeignRelUpdatable`. Unlike tds_fdw (read-only by
  omission) ogr_fdw *does* register the modify callbacks — but see §(e): whether
  they actually work is decided at runtime by the OGR driver.
- **DDL** (`ogr_fdw.c:412-415`): `ImportForeignSchema` → `ogrImportForeignSchema`,
  guarded on PG ≥ 9.5. It deliberately omits JOIN/UPPER-rel pushdown
  (`GetForeignJoinPaths`/`GetForeignUpperPaths`), direct-modify, batch, and
  async callbacks — those fields are simply never set.

`_PG_init` is tiny: it registers `on_proc_exit(&ogr_fdw_exit, …)` — which calls
`OGRCleanupAll()` (`ogr_fdw.c:272-276`) — and, on GDAL ≥ 2.1, routes GDAL's
`CPLSetErrorHandler` into PG `elog()` so library errors surface as backend
messages (`ogr_fdw.c:257-267` `[verified-by-code]`). No shmem, no GUCs, no
background worker.

The **options validator** is the textbook `valid_options[]`-by-catalog-OID table
(`ForeignServerRelationId` / `ForeignTableRelationId` / `AttributeRelationId`),
dispatched on the passed catalog OID with `optrequired` flags for `datasource`
and `layer` (`ogr_fdw.c:88-109`, validator body from `ogr_fdw.c:485+`
`[verified-by-code]`) — the same shape file_fdw and postgres_fdw use.
Two SRFs round out the SQL surface: `ogr_fdw_version()` and `ogr_fdw_drivers()`
(returning `text[]` of available OGR drivers) (`ogr_fdw--1.1.sql:20-32`
`[verified-by-code]`).

## Where it diverges from core idioms — THE headline

### (a) The "foreign server" is an in-process GDAL data-source handle, not a network peer

`ogrGetConnectionFromServer` reads the server's `datasource`/`format`/
`config_options`/`open_options`/`character_encoding`/`updateable` options into an
`OgrConnection` and calls `ogrGetDataSource` (`ogr_fdw.c:640-696`), which
ultimately calls `GDALOpenEx(ds_str, GDAL_OF_VECTOR | GDAL_OF_UPDATE/READONLY,
driver_list, open_option_list, NULL)` (`ogr_fdw.c:458-478` `[verified-by-code]`).
The layer handle is then `GDALDatasetGetLayerByName(ds, lyr_str)`
(`ogr_fdw.c:761`). Notable consequences of the embedded-library model:

- **No connection pool** — and the author flags this as the top performance
  drag. A `TODO` at `ogr_fdw.c:685-688` reads "Connections happen twice for each
  query, having a connection pool will certainly make things faster"
  `[from-comment]`; the README repeats "each query makes (and disposes of) two
  new [OGR connections]" (`README.md:16` `[from-README]`). This is the sharpest
  contrast with the postgres_fdw/sqlite_fdw connection-cache idiom (an `HTAB`
  keyed by server OID with xact callbacks) — ogr_fdw has none of it.
- **Cleanup is `OGR_L_SyncToDisk` + `GDALClose`**, not `PQfinish`.
  `ogrFinishConnection` flushes pending writes to the layer and closes the
  dataset per use (`ogr_fdw.c:607-623` `[verified-by-code]`).
- **Open mode is a per-datasource flag**, not a role: the `updateable` option and
  the requested access select `GDAL_OF_UPDATE` vs `GDAL_OF_READONLY`
  (`ogr_fdw.c:431-440`, `665-676` `[verified-by-code]`).

### (b) Schema autodiscovery: OGR layer field definitions → generated `CREATE FOREIGN TABLE` DDL

The introspection engine is `ogrLayerToSQL` in `ogr_fdw_common.c:271-408`: given
an `OGRLayerH`, it walks the layer's `OGRFeatureDefnH`, emits a `CREATE FOREIGN
TABLE` string that always leads with `fid bigint` (`ogr_fdw_common.c:311`), then
one column per geometry field (`:314-387`) and one per attribute field
(`:390-396`), and closes with `SERVER <name> OPTIONS (layer '<ogr layer name>')`
(`:402-405`) `[verified-by-code]`. This single function is reached **two ways**:

- **`IMPORT FOREIGN SCHEMA`** (`ogrImportForeignSchema`, `ogr_fdw.c:3219-3356`):
  loops every layer in the datasource (`GDALDatasetGetLayerCount`), honours the
  magic remote schema `ogr_all` vs a layer-name prefix, applies `LIMIT TO` /
  `EXCEPT`, respects `launder_table_names`/`launder_column_names` statement
  options, and `lappend`s each `ogrLayerToSQL` string into the returned command
  list (`ogr_fdw.c:3234-3346` `[verified-by-code]`). It passes
  `use_postgis_geometry = (ogrGetGeometryOid() != BYTEAOID)`, so geometry columns
  come out as `Geometry(…)` when PostGIS is present and `bytea` otherwise
  (`ogr_fdw.c:3337`).
- **A standalone CLI, `ogr_fdw_info`** (`ogr_fdw_info.c:1-9`): a *commandline
  utility* linked against GDAL directly (not the backend) that prints a server +
  table definition for a layer, or `-f` to list supported drivers. Its
  `ogrGenerateSQL` opens the source and calls the *same* `ogrLayerToSQL`
  (`ogr_fdw_info.c:270`, `:368` `[verified-by-code]`). Reusing the DDL generator
  in both a client tool and the in-server IMPORT path is a notable design choice
  — the same C module runs with a real backend or a stub `quote_identifier`
  (`ogr_fdw_common.c:19`, stub at `ogr_fdw_info.c:59+`).

Names are sanitized by `ogrStringLaunder`: lowercase, non-`[A-Za-z0-9]` → `_`,
leading digit prefixed with `n`, truncated to `NAMEDATALEN`
(`ogr_fdw_common.c:53-89` `[verified-by-code]`); when the laundered name differs
from the OGR name, the generated column carries `OPTIONS (column_name '<orig>')`
(`ogr_fdw_common.c:248-256`) so the runtime match can find it again.

### (c) Type mapping: OGR field types ↔ PG types, and OGR geometry ↔ PostGIS/WKB

`ogrTypeToPgType` (`ogr_fdw_common.c:91-170` `[verified-by-code]`) is the
authoritative table: `OFTInteger` → `integer` (or `boolean` if the OGR subtype
is `OFSTBoolean`), `OFTReal` → `double precision`, `OFTString` → `varchar(n)` at
the OGR field width (or `jsonb` if subtype `OFSTJSON`), `OFTBinary` → `bytea`,
`OFTDate`/`OFTTime`/`OFTDateTime` → `date`/`time`/`timestamp`,
`OFTIntegerList`/`OFTRealList`/`OFTStringList` → the `[]` array types,
`OFTInteger64` → `bigint`. Geometry types map through
`ogrGeomTypeToPgGeomType` (`ogr_fdw_common.c:172-238`): `wkbPoint` → `Point`,
`wkbPolygon` → `Polygon`, `wkbMultiPolygon` → `MultiPolygon`, …, with `Z`/`M`
dimensionality suffixes, wrapped as `Geometry(<type>,<srid>)` where the SRID is
recovered by `OSRAutoIdentifyEPSG` on the layer's spatial reference
(`ogr_fdw_common.c:335-364` `[verified-by-code]`).

**Runtime column binding is by name, not position.** `ogrReadColumnData`
(`ogr_fdw.c:1407-1600`) builds a `bsearch`-able array of the OGR layer's field
names (both original and laundered, `:1458-1472`) and, per PG column,
special-cases a `fid` int4/int8 column to `OGR_FID` (`:1521-1533`), matches the
first geometry-typed PG column to the first OGR geometry field *irrespective of
name* (`:1537-1544`), honours the `column_name` option override (`:1556-1566`),
then name-matches the rest — calling `ogrCheckConvertToPg` to *error* on a
type-inconsistent name match (`:1578` `[verified-by-code]`). Unmatched PG columns
become `OGR_UNMATCHED` and read as NULL.

Geometry values cross the boundary as **WKB**: `ogrFeatureToSlot` calls
`OGR_G_ExportToWkb(geom, wkbNDR, …)` into a `bytea` varlena
(`ogr_fdw.c:1914-1919`), then either passes it straight through for a `bytea`
column, or — for a PostGIS `geometry` column — hexifies it and calls the type's
*input* function on HEXWKB (chosen over `recv` because the input function is more
lax about unclosed polys) (`ogr_fdw.c:1927-1951`, comment `:1938-1943`
`[verified-by-code]`; default `OGR_FDW_HEXWKB` at `ogr_fdw.h:85`). Non-geometry
values go through the type's cstring *input* function via `pgDatumFromCString`,
with `pg_any_to_server` charset decoding when `character_encoding` is set
(`ogr_fdw.c:1777-1806`, `:1791-1792` `[verified-by-code]`).

### (d) Pushdown: OGR attribute filter (SQL string) + `SetSpatialFilter` (bbox only)

Restriction quals are deparsed by `ogrDeparse` (`ogr_fdw_deparse.c:672`), invoked
from `ogrGetForeignPlan` (`ogr_fdw.c:1146`). The pushdown surface is deliberately
narrow — `ogrOperatorIsSupported` bsearches a sorted 10-entry table
`{ "!=", "&&", "<", "<=", "<>", "=", ">", ">=", "~~", "~~*" }`
(`ogr_fdw_deparse.c:330-339` `[verified-by-code]`); anything else forces the
clause to stay local. Two distinct sinks:

- **Non-spatial quals become an OGR SQL attribute-filter string** applied via
  `OGR_L_SetAttributeFilter(lyr, sql)` in `ogrBeginForeignScan`
  (`ogr_fdw.c:1738-1762` `[verified-by-code]`). OGR's SQL dialect supports only a
  minimal operator set, which is why the whitelist is short (`README.md:14`
  `[from-README]`).
- **The bounding-box overlap operator `&&` becomes a spatial filter.**
  `ogrDeparseOpExprSpatial` requires a geometry `T_Const` on one side and an
  `OGR_GEOMETRY` `T_Var` on the other, converts the constant to an OGR geometry
  via `pgDatumToOgrGeometry`, takes its envelope, and stashes an
  `OgrFdwSpatialFilter` (min/max x/y + field number) into the deparse context
  (`ogr_fdw_deparse.c:341-419` `[verified-by-code]`). At scan start that becomes
  `OGR_L_SetSpatialFilterRectEx(lyr, fldnum, minx, miny, maxx, maxy)`
  (`ogr_fdw.c:1729-1735`). Notably the spatial handler returns `false`
  (`ogr_fdw_deparse.c:418`) so `&&` is *not* also emitted into the attribute
  string — it is pushed purely as the bbox filter. Only bounding-box spatial
  filtering is pushed down, never true `ST_Intersects` refinement
  (`README.md:15` `[from-README]`).

Row-count estimation asks OGR: `ogrGetForeignRelSize` calls
`OGR_L_GetFeatureCount` when the driver advertises `OLCFastFeatureCount`
(`ogr_fdw.c:992-996` `[verified-by-code]`); there is no remote-EXPLAIN costing
analogue to postgres_fdw's `use_remote_estimate`.

### (e) Writes round-trip through OGR's mutable-layer API — gated by driver capability

ogr_fdw *does* implement INSERT/UPDATE/DELETE, but updatability is decided at
runtime by interrogating the OGR driver. `ogrIsForeignRelUpdatable` first
requires a `fid` int column (`ogrGetFidColumn`, `ogr_fdw.c:2701-2718`), opens the
layer read/write, then builds a per-command bitmask from OGR capability probes:
`OLCRandomWrite` → `CMD_UPDATE`, `OLCSequentialWrite` → `CMD_INSERT`,
`OLCDeleteFeature` → `CMD_DELETE` (`ogr_fdw.c:3193-3206` `[verified-by-code]`).
So the *same* SQL is writable against a GeoPackage but read-only against a
Shapefile-with-no-write-driver, and that is reported through core's standard
updatability mechanism rather than a runtime ereport. The execution callbacks map
straight onto OGR mutators: `ExecForeignInsert` → `OGR_L_CreateFeature`
(`ogr_fdw.c:3061`), `ExecForeignUpdate` → `OGR_L_SetFeature` (`:2910`),
`ExecForeignDelete` → `OGR_L_DeleteFeature(lyr, fid)` (`:3131`)
`[verified-by-code]`. The row identity is the OGR feature id: rather than the
resjunk-column route, `ogrAddForeignUpdateTargets` builds a `Var` on the `fid`
column and registers it via `add_row_identity_var(planinfo, var, rte_index,
"fid")` (`ogr_fdw.c:2730-2760` `[verified-by-code]`). Geometry writes reverse the
read path: `pgDatumToOgrGeometry` (using the column's `send` function) then
`OGR_F_SetGeometryDirectly` / `OGR_F_SetGeomFieldDirectly`
(`ogr_fdw.c:2236`, `:2342-2349`).

## Notable design decisions (with cites)

- **PostGIS is optional and discovered lazily.** `ogrGetGeometryOid` looks up the
  `postgis` extension's `geometry` type OID via the syscache and caches it; if
  PostGIS is absent it caches `BYTEAOID` and every geometry degrades to WKB bytea
  (`ogr_fdw.c:333-382` `[verified-by-code]`). A syscache-vs-search_path bug fix
  (`get_extension_nsp_oid`, `ogr_fdw.c:284-326`, referencing issue #263) sidesteps
  `TypenameGetTypid` search-path hazards.
- **GDAL errors are wired into `elog`.** `CPLSetErrorHandler(ogrErrorHandler)` at
  init (`ogr_fdw.c:264`) means OGR driver failures surface as PG NOTICE/ERROR with
  `ERRCODE_FDW_*` SQLSTATEs (e.g. the attribute-filter failure NOTICE at
  `ogr_fdw.c:1747-1757`) `[verified-by-code]`, matching
  `[[knowledge/idioms/error-handling]]`.
- **Character encoding is a data-source property.** If the OGR layer advertises
  `OLCStringsAsUTF8` or the user supplies `character_encoding`, values are decoded
  with `pg_any_to_server` on read (`ogr_fdw.c:774`, `:1791-1792`
  `[verified-by-code]`).
- **All columns are always fetched.** A `TODO` notes the OGR API supports column
  subsetting but the FDW retrieves every field each row (`ogr_fdw.c:1721-1722`,
  `README.md:17` `[from-comment]`/`[from-README]`) — a deliberate simplicity-over-
  efficiency call.
- **The state structs share a discriminated-union prefix.** `OgrFdwState` /
  `OgrFdwPlanState` / `OgrFdwExecState` / `OgrFdwModifyState` all begin with an
  `OgrFdwStateType` tag so one `getOgrFdwState` allocator serves plan/exec/modify
  phases (`ogr_fdw.h:161-210` `[verified-by-code]`).

## Links into corpus

- `[[knowledge/subsystems/foreign]]` — the `FdwRoutine` dispatch + catalog
  accessors (`GetForeignServer`, `GetForeignColumnOptions`) this extension plugs
  into; the single most important cross-ref.
- `[[knowledge/subsystems/contrib-postgres_fdw]]` — the reference FDW; ogr_fdw is
  "postgres_fdw shape, but the remote is a GDAL library handle with no connection
  cache and only bbox+minimal-operator pushdown."
- `[[knowledge/subsystems/contrib-file_fdw]]` — the other "read a local source"
  FDW; same `valid_options[]`-by-catalog-OID validator shape.
- `[[knowledge/ideologies/sqlite_fdw]]` — closest ideological sibling: another
  embedded-library FDW (SQLite engine vs GDAL library). Contrast sqlite_fdw's
  full connection cache + affinity-normalization layer against ogr_fdw's
  no-pool, capability-probed, geometry-centric model.
- `[[knowledge/ideologies/tds_fdw]]` — the read-only-by-omission foil; ogr_fdw
  instead ships modify callbacks whose reach is decided by OGR driver capability.
- `[[knowledge/ideologies/postgis]]` — the geometry type ogr_fdw discovers at
  runtime and transports as WKB/HEXWKB; the optional-dependency relationship is
  central to the type mapping.
- `[[knowledge/ideologies/pointcloud]]` / `[[knowledge/ideologies/pgrouting]]` —
  other spatial-stack extensions in the corpus for the geospatial neighbourhood.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` handler/validator +
  the `ogr_fdw_version`/`ogr_fdw_drivers` SRFs.
- `[[knowledge/idioms/fdw-routine-callbacks]]` + `[[knowledge/idioms/fdw-iterate-scan]]`
  — the callback set and the per-row slot-fill loop (`ogrFeatureToSlot`).
- `[[knowledge/idioms/memory-contexts]]` — per-use `palloc`/`GDALClose` teardown
  outside PG's context discipline (GDAL handles are freed by hand in
  `ogrFinishConnection`).
- `[[knowledge/idioms/error-handling]]` — `CPLSetErrorHandler` → `elog` bridge and
  the `ERRCODE_FDW_*` NOTICE/ERROR usage.

> Corpus gap (echoing the sqlite_fdw note): no idiom doc yet for the **FDW
> connection-cache pattern** — and ogr_fdw is the instructive *counter*-example
> that deliberately has none (two datasource opens per query, flagged as its
> biggest perf drag). Worth pairing with an `idioms/fdw-connection-cache.md`.
> Corpus gap: no idiom for **capability-probed updatability**
> (`IsForeignRelUpdatable` returning a per-command bitmask driven by the remote's
> declared abilities), which ogr_fdw's `OLC*` probes exemplify.

## Sources

Fetched 2026-07-13 (branch `master`), all via
`https://raw.githubusercontent.com/pramsey/pgsql-ogr-fdw/master/<path>`:

- `README.md` @ 2026-07-13T23:07Z → HTTP 200 (463 lines).
- `ogr_fdw.control` @ 2026-07-13T23:07Z → HTTP 200 (5 lines).
- `ogr_fdw--1.1.sql` @ 2026-07-13T23:07Z → HTTP 200 (32 lines; handler/validator
  DDL + `ogr_fdw_version`/`ogr_fdw_drivers` SRFs).
- `ogr_fdw.h` @ 2026-07-13T23:07Z → HTTP 200 (216 lines; `OgrConnection`,
  `OgrFdwColumn`, the state-struct family, shared signatures).
- `ogr_fdw.c` @ 2026-07-13T23:07Z → HTTP 200 (3363 lines; the FdwRoutine, scan +
  modify lifecycle, column matching, datasource open, IMPORT FOREIGN SCHEMA).
- `ogr_fdw_common.c` @ 2026-07-13T23:07Z → HTTP 200 (409 lines; `ogrTypeToPgType`,
  `ogrGeomTypeToPgGeomType`, `ogrStringLaunder`, `ogrLayerToSQL`).
- `ogr_fdw_info.c` @ 2026-07-13T23:07Z → HTTP 200 (480 lines; the standalone CLI
  that shares `ogrLayerToSQL`).
- `ogr_fdw_deparse.c` @ 2026-07-13T23:07Z → HTTP 200 (729 lines; operator
  whitelist, attribute-filter deparse, `&&` → spatial-filter path).

No 404 gaps — all eight requested paths returned HTTP 200. Not deep-read:
`ogr_fdw_gdal.h`/`ogr_fdw_common.h` (GDAL version-compat shims), the
`ogrFeatureToSlot` array-field and typmod-SRID branches beyond the geometry
path, and the `data/`/`expected/` test corpora. The `ogr_fdw_version` /
`ogr_fdw_drivers` C bodies were not located in the fetched files (declared in
`ogr_fdw--1.1.sql`; likely in a source file outside the manifest) — their
existence is `[verified-by-code]` via the SQL, their implementation `[unverified]`.
