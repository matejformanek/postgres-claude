# pointcloud — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgpointcloud/pointcloud` @ branch `master`. All `file:line` cites
> below point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> files fetched on 2026-07-04 (see Sources footer). The GitHub git/trees API
> and codeload tarball endpoint were proxy-blocked this session; every file was
> pulled individually via `raw.githubusercontent.com`.

## Domain & purpose

pointcloud stores LIDAR / point-cloud data inside PostgreSQL as two varlena
types: `pcpoint` (one multi-dimensional point) and `pcpatch` (a compressed
collection of points sharing a schema). The extension's headline commitment is
that **a point's byte layout is not fixed at compile time** — it is described by
an XML schema stored in a catalog table (`pointcloud_formats`) and interpreted
at runtime. Each point/patch on disk carries a 4-byte `pcid` foreign key into
that table; the actual C struct layout of the dimensions (X/Y/Z/intensity/GPS
time/…), their interpretations (`int8_t`…`double`), scale, and offset are all
data, not code (`pgsql/pc_pgsql.h:53-66`, `lib/pc_api.h:64-90`)
`[verified-by-code]`. This is the same architecture PostGIS uses and the two
are designed to interoperate (see §geometry below).

## How it hooks into PG

**Postgis-style two-layer split.** The repo is `lib/` — a standalone C engine
("libpc") that includes *no* PostgreSQL headers and could run outside a backend
— plus `pgsql/` — the fmgr glue that includes `postgres.h`
(`pgsql/pc_pgsql.h:12-21`) `[verified-by-code]`. `lib/` speaks only its own
`PCPOINT`/`PCPATCH`/`PCSCHEMA` structs (`lib/pc_api.h`); `pgsql/` translates
between those and PG's `Datum`/varlena world. This mirrors PostGIS's
`liblwgeom/` + `postgis/` split exactly.

**Types + I/O + accessors via fmgr.** `pgsql/pc_inout.c` defines the type I/O
functions with `PG_FUNCTION_INFO_V1` — `pcpoint_in`/`pcpoint_out`,
`pcpatch_in`/`pcpatch_out` (`pgsql/pc_inout.c:50-166`), the typmod trio
(`pc_typmod_in`/`pc_typmod_out`/`pc_typmod_pcid`, `pgsql/pc_inout.c:368+`), and
`bytea`/text projection functions. `pgsql/pc_access.c` holds ~40 more SQL
functions (`pcpatch_compress`, `pcpatch_unnest`, `pcpatch_filter`,
`pcpoint_get_value`, plus the aggregate transfn/finalfn that build a patch from
a set of points) `[verified-by-code]`.

**The `pointcloud_formats` catalog table** is the schema registry. It is a plain
user table (schema-qualified `<install_schema>.pointcloud_formats` with columns
`pcid`, `srid`, `schema`) — not a `pg_catalog` relation — and is read at runtime
via **SPI**: `pc_schema_from_pcid_uncached` issues
`select schema, srid from <formats> where pcid = N` through `SPI_connect` /
`SPI_exec` / `SPI_getvalue` / `SPI_finish` (`pgsql/pc_pgsql.c:343-419`)
`[verified-by-code]`.

**typmod carries the pcid.** A column declared `pcpatch(1)` stores pcid 1 in the
low 16 bits of the attribute typmod; `pcid_from_typmod` is literally
`typmod & 0x0000FFFF` (`pgsql/pc_pgsql.c:240-247`) `[verified-by-code]`.

**Cast to geometry/bytea.** The bridge to PostGIS is WKB, not a C link:
`pcpatch_envelope_as_bytea` / `pcpatch_bounding_diagonal_as_bytea` emit
OGC well-known-binary into a `bytea` (`pgsql/pc_inout.c:303-368`)
`[verified-by-code]`, which PostGIS's `geometry` can ingest. The `.control`
file's `requires = 'postgis'` line is **commented out**
(`pgsql/pointcloud.control.in:7`) `[verified-by-code]`, so PostGIS is an
*optional* companion, not a hard dependency.

**PGXS build**, non-relocatable, `superuser = true`, with a versioned
`module_pathname = $libdir/pointcloud-<major>` (`pgsql/pointcloud.control.in`)
`[verified-by-code]`.

## Where it diverges from core idioms

### 1. Runtime schema-driven serialization (vs core's fixed-layout types)

Core PG types have a C struct known at compile time. pointcloud's on-disk point
is a raw byte blob whose interpretation is computed at runtime from the XML
schema: `pc_schema_calculate_byteoffsets` walks the dimension list and lays out
`byteoffset`/`size` per dimension from an interpretation→size table
(`lib/pc_schema.c:20-31, 176-191`) `[verified-by-code]`. `pc_point_deserialize`
therefore cannot trust the bytes — it re-checks that the schema's computed width
equals the stored width and `elog(ERROR, "schema size and disk size mismatch,
repair the schema")` if not (`pgsql/pc_pgsql.c:531-533`) `[verified-by-code]`.
The schema itself is parsed from XML with **libxml2** (`pc_schema_from_xml`,
`lib/pc_schema.c:352`, `#include <libxml/parser.h>` at `:13`)
`[verified-by-code]`.

### 2. Custom in-varlena compression (vs relying on TOAST)

The serialized patch is a hand-rolled varlena whose first field is a raw
`uint32_t size` written with `SET_VARSIZE` and read with `VARSIZE` — i.e. the
type provides its own 4-byte length header rather than the `struct varlena`
convenience (`pgsql/pc_pgsql.h:78-86`, `pgsql/pc_pgsql.c:512-518`)
`[verified-by-code]`. A patch stores a `compression` discriminator
(`PC_NONE`/`PC_DIMENSIONAL`/`PC_LAZPERF`, `lib/pc_api.h:35-40`) and
`pc_patch_compress` dispatches on it (`lib/pc_patch.c:116`) `[verified-by-code]`.
The **dimensional** scheme compresses each column independently with one of
RLE / significant-bits / zlib (`PC_DIM_RLE`, `PC_DIM_SIGBITS`, `PC_DIM_ZLIB`,
`lib/pc_api_internal.h:66-69`; `pc_bytes_encode`/`pc_bytes_run_length_encode`,
`:245-251`) `[verified-by-code]`. So compression lives *inside* the value and is
column-aware, rather than deferring to TOAST's opaque whole-datum pglz/lz4. The
extension still cooperates with TOAST for reads: accessors that only need the
patch header use `PG_DETOAST_DATUM_SLICE` to fetch just the fixed prefix
(`PG_GETHEADER_SERPATCH_P`, `pgsql/pc_pgsql.h:28-40`) `[verified-by-code]`,
avoiding a full detoast of a large compressed patch.

### 3. Memory: `lib/` allocates through swappable hooks, `pgsql/` points them at palloc

`lib/` never calls `malloc` directly in hot paths — it calls `pcalloc` /
`pcrealloc` / `pcfree`, which indirect through a global `pc_context` of function
pointers (`lib/pc_mem.c:17-27, 109-132`) `[verified-by-code]`. Standalone, those
default to `malloc`/`realloc`/`free` (`lib/pc_mem.c:37-79`). Inside a backend,
`_PG_init` calls `pc_set_handlers(pgsql_alloc, pgsql_realloc, pgsql_free, …)`
(`pgsql/pc_pgsql.c:226-231`) so every `lib/` allocation lands in
`CurrentMemoryContext` via `palloc`/`repalloc`/`pfree`
(`pgsql/pc_pgsql.c:152-178`) `[verified-by-code]`. `pcalloc` additionally
`memset`s to zero on every allocation (`lib/pc_mem.c:115`) — a `palloc0`-like
guarantee baked into the engine. Where the glue needs an allocation to outlive
an SPI teardown it switches contexts explicitly: the schema loader copies the
XML into `SPI_palloc` before `SPI_finish` and builds the `PCSCHEMA` under
`fcinfo->flinfo->fn_mcxt` so it survives to statement scope
(`pgsql/pc_pgsql.c:394-403, 489-492`) `[verified-by-code]`.

### 4. Error handling: `lib/` calls `pcerror`, `pgsql/` reroutes it into ereport

The same handler-indirection covers messaging. `lib/` reports via
`pcerror`/`pcwarn`/`pcinfo`, thin wrappers over `pc_context.err/warn/info`
function pointers (`lib/pc_mem.c:134-156`) `[verified-by-code]`. The standalone
default error handler prints to stdout and **`exit(1)`** (`lib/pc_mem.c:64-69`)
— fine for a CLI, fatal in a backend. So `pgsql/` overrides it: `pgsql_error`
funnels into `pgsql_msg_handler`, which `vsnprintf`s the message and calls
`ereport(sig, (errmsg_internal("%s", msg)))` with `sig` = `ERROR`/`WARNING`/
`NOTICE` (`pgsql/pc_pgsql.c:180-214, 229-230`) `[verified-by-code]`. This is the
same "route a foreign library's error surface into PG's longjmp-based ereport"
pattern PostGIS uses. `pgsql/` code that runs entirely in the backend also calls
`elog`/`ereport` directly (e.g. the SPI lookup path, `pgsql/pc_pgsql.c:351-413`).

### 5. Per-statement schema cache in `fn_extra` (vs syscache/relcache)

Because schema lookups are SPI queries, not catalog scans, pointcloud rolls its
own tiny cache: a 16-slot `SchemaCache` hung off `fcinfo->flinfo->fn_extra`,
searched linearly, refilled round-robin on miss (`pgsql/pc_pgsql.c:426-506`)
`[verified-by-code]`. There is also a separate `CacheMemoryContext`-lived
`PC_CONSTANTS` cache that memoizes the install schema name and the
`pointcloud_formats` table/column identifiers (`pgsql/pc_pgsql.c:108-146`)
`[verified-by-code]`. Neither participates in PG's normal syscache invalidation
— staleness is bounded by statement lifetime for the schema cache.

## Notable design decisions

- **`pcid` in the low 16 bits of typmod** caps a database at 65535 distinct
  point-cloud formats and makes `ALTER TYPE`-free schema binding possible
  (`pgsql/pc_pgsql.c:240-247`) `[verified-by-code]`.
- **Interpretation parsing by first characters**, not a lookup: e.g.
  `pc_interpretation_number` branches on `str[0]`/`str[3]` to map `"int32_t"`→
  `PC_INT32` (`lib/pc_schema.c:43-60`) `[verified-by-code]`. Fast but brittle to
  new type names.
- **Three concrete patch structs share a macro-defined common header**
  (`PCPATCH_COMMON`, `lib/pc_api.h:165-197`) and are dispatched by an `int type`
  first field — a hand-rolled tagged union / vtable-by-switch
  (`lib/pc_patch.c:22-104`) `[verified-by-code]`.
- **Stats (min/avg/max point) are serialized inline** at the front of a patch's
  data buffer before the dimension bytes (`pc_patch_stats_serialize`, called in
  `pgsql/pc_pgsql.c:620-647, 663-684`) `[verified-by-code]`, so bounding-box and
  summary queries can read a slice without decompressing.
- **`superuser = true`, non-relocatable** — the extension trusts its SPI-issued
  SQL against `pointcloud_formats` and hardcodes install-schema discovery
  (`pgsql/pointcloud.control.in`, `pgsql/pc_pgsql.c:120-146`) `[verified-by-code]`.

## Links into corpus

- [[postgis]] — the sibling ideology doc; pointcloud copies its `lib/`+`pgsql/`
  split, its handler-indirection for memory/error, and its WKB geometry bridge.
- [[toast-storage-strategies]] / [[detoast-stream-consumption]] — contrast:
  pointcloud compresses *inside* the varlena and slice-detoasts headers rather
  than leaning on TOAST's whole-datum compression.
- [[memory-contexts]] / [[memory-context-api-and-dispatch]] — the
  `pc_set_handlers`→`palloc` bridge and the `fn_mcxt`/`SPI_palloc` context
  discipline in the schema loader.
- [[error-handling]] — `pcerror`→`ereport` rerouting; the standalone-vs-backend
  `exit(1)` divergence.
- [[spi]] — the runtime `pointcloud_formats` lookup is an SPI query, not a
  catalog scan.
- [[fmgr]] — `PG_FUNCTION_INFO_V1` I/O + accessor entry points.
- [[catalog-conventions]] — contrast: the "catalog" here is a user table read
  via SPI, not a `pg_catalog` BKI relation.
- [[varatt-varlena]] — the hand-rolled `uint32 size` varlena header and
  `PG_DETOAST_DATUM_SLICE` header reads.

## Sources

All fetched 2026-07-04 via `raw.githubusercontent.com/pgpointcloud/pointcloud/master/…`.
GitHub git/trees API and codeload tarball endpoint were **unusable** this
session (403 "not enabled for this session"); files fetched individually.

- `README.md` — 200 (badges + CI matrix only; no prose docs)
- `lib/pc_api.h` — 200
- `lib/pc_api_internal.h` — 200
- `lib/pc_mem.c` — 200 (default + PG allocator/message handlers)
- `lib/pc_point.c` — 200
- `lib/pc_patch.c` — 200
- `lib/pc_schema.c` — 200 (libxml2 schema parsing, byteoffset layout)
- `lib/pc_util.c` — 200
- `pgsql/pc_pgsql.h` — 200
- `pgsql/pc_pgsql.c` — 200
- `pgsql/pc_inout.c` — 200
- `pgsql/pc_access.c` — 200
- `pgsql/pointcloud.control.in` — 200
- `Makefile` — 200
- `pgsql/pointcloud.control` — 404 (generated from `.control.in`)
- `pgsql/Makefile` — 404
- `pgsql/pc_pgsql.control` — 404
