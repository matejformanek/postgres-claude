# PostGIS — bridging a stack of foreign C libraries into PG's memory/error/index model

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `postgis/postgis` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against files fetched
> on 2026-06-06 (see Sources footer).

## Domain & purpose

PostGIS turns PostgreSQL into a full GIS engine: it adds `geometry` /
`geography` / `raster` types implementing the OGC Simple Features model,
hundreds of spatial functions (`ST_Intersects`, `ST_DWithin`, `ST_Buffer`, …),
and the index machinery to make spatial predicates fast. Architecturally it is
*not* one library: it is a thin PG-facing shim (`postgis/`, `libpgcommon/`) over
a portable geometry core (`liblwgeom/`) plus heavyweight third-party native
libraries — **GEOS** (computational geometry), **PROJ** (coordinate
reprojection), and optionally GDAL/SFCGAL/protobuf. The central engineering
problem PostGIS solves, and the reason it's a good anthropology subject, is
*impedance-matching three foreign C libraries into Postgres's memory, error,
interrupt, and planner conventions* without those libraries knowing Postgres
exists. The `README.postgis:8-10` framing: "implements GIS simple features,
ties the features to R-tree indexing, and provides many spatial functions".

## How it hooks into PG

`PG_MODULE_MAGIC_EXT(.name="postgis", .version=POSTGIS_LIB_VERSION)`
(`postgis/postgis_module.c:46-53`) `[verified-by-code]`. Notably, **PostGIS
installs no executor/planner/utility hooks at all** — `_PG_init`
(`postgis/postgis_module.c:113-131`) does only four things, and all four are
*outbound bridges* into the foreign libraries:

1. `GEOS_interruptRegisterCallback(interrupt_geos_callback)` — lets a long GEOS
   computation be cancelled by PG query cancel.
2. `lwgeom_register_interrupt_callback(interrupt_liblwgeom_callback)` — same for
   liblwgeom.
3. `pg_install_lwgeom_handlers()` — redirects liblwgeom's malloc/realloc/free
   and error/notice through PG (see Divergence 1).
4. `proj_log_func(NULL,NULL,pjLogFunction)` — pipes PROJ log lines to `elog`.

Everything else is wired declaratively in SQL, not C: the `geometry` type, the
`&&` bounding-box operators, the GiST/SP-GiST/BRIN opclasses, and — the clever
part — `SUPPORT postgis_index_supportfn` clauses on the friendly `ST_*`
functions that make them index-aware at plan time (see Divergence 3). The
control file is `relocatable = false` (`extensions/postgis/postgis.control.in:5`).

## Where it diverges from core idioms

### 1. It routes three foreign libraries' memory + error + interrupt surface through PG

The defining divergence. A core backend assumes all C code uses `palloc`/
`ereport`/`CHECK_FOR_INTERRUPTS`. GEOS, PROJ, and liblwgeom do none of that —
they use libc `malloc` and return error codes / call abort handlers. PostGIS
makes them behave by *installing PG-flavored callbacks into each library*.
`pg_install_lwgeom_handlers` (`libpgcommon/lwgeom_pg.c:408-418`) calls
`lwgeom_set_handlers(pg_alloc, pg_realloc, pg_free, pg_error, pg_notice)` and
`lwgeom_set_debuglogger(pg_debug)`. The handlers are pure PG-idiom adapters:
`pg_alloc` → `palloc` *plus a `CHECK_FOR_INTERRUPTS()` on every allocation*
(`lwgeom_pg.c:315-329`), `pg_error` → `ereport(ERROR, errmsg_internal(...))`
(`:355-364`), `pg_notice` → `ereport(NOTICE, ...)` (`:381-390`),
`pg_debug` → `ereport` at a `DEBUG1..5` level chosen from the liblwgeom level
(`:394-406`). The interrupt callbacks (`postgis_module.c:56-92`) read PG's
global `QueryCancelPending`/`ProcDiePending` and flip the corresponding
"please stop" flag inside GEOS (`GEOS_interruptRequest()`) and liblwgeom
(`lwgeom_request_interrupt()`). Net effect: a foreign geometry library
allocates from the current `MemoryContext`, throws via `longjmp`, and honours
`pg_cancel_backend()` — all without a single `#include "postgres.h"` in its own
source. Cross-ref `[[knowledge/idioms/memory-contexts]]`,
`.claude/skills/error-handling/SKILL.md`.

### 2. Type OIDs are *dynamic* and cached per-session, because the install schema isn't fixed

Core builtin types have compile-time-stable OIDs in `pg_type.dat`. PostGIS
types get whatever OID `CREATE EXTENSION` assigns, in whatever schema the user
picked — and `relocatable = false` plus a non-fixed schema means C code can't
hardcode them. So `getPostgisConstants` (`libpgcommon/lwgeom_pg.c:153-201`)
resolves the install schema (via `get_extension_oid("postgis")` →
`postgis_get_extension_schema`, scanning `pg_extension` directly,
`:68-98`), then looks up `geometry`/`geography`/`box2df`/`box3d`/`gidx`/`raster`
OIDs by `(typename, nsp_oid)` and **caches the whole struct in a child of
`CacheMemoryContext`** (`:172-178`) so it survives statement end. `postgis_oid()`
(`:203-252`) is the dispatch every other C file calls instead of a literal OID.
There's even an SPI fallback (`postgis_get_full_version_schema`, `:100-149`)
that runs `SELECT pronamespace FROM pg_proc WHERE proname='postgis_full_version'`
when the extension-OID path fails. A core type never has to ask "what's my own
OID?"; PostGIS asks constantly and memoizes the answer. Cross-ref
`[[knowledge/idioms/syscache]]`, `[[knowledge/idioms/memory-contexts]]`,
`.claude/skills/catalog-conventions/SKILL.md`.

### 3. Planner *support functions*, not operators, are the index entry point

This is the most elegant divergence and worth studying. Users write
`WHERE ST_Intersects(geom, :box)` — a plain function call, not an indexable
operator. PostGIS makes it use a GiST/SP-GiST/BRIN index by attaching
`SUPPORT postgis_index_supportfn` to the SQL definition of every such function
(`postgis/gserialized_supportfn.c:303-318` shows the `CREATE FUNCTION ... SUPPORT`
shape). At plan time the planner calls the support function with a
`SupportRequestIndexCondition`, and PostGIS *rewrites the function call into a
bounding-box operator clause* `geom && :box` carrying the right R-tree strategy
number (`gserialized_supportfn.c:351-359` and the `GeometryStrategies[]` /
`GeographyStrategies[]` tables, `:76-115`). The mapping is metadata-driven: the
`IndexableFunctions[]` table (`:156-175`) names each function, its strategy
index, arg count, and — for distance predicates like `ST_DWithin` — which arg is
the radius. For those, PostGIS synthesizes an *expanded* box by looking up and
injecting a call to `ST_Expand` (`expandFunctionOid`, `:277-301`) so the index
scan returns a superset that the exact function then rechecks. The same support
function also answers `SupportRequestSelectivity` by calling PostGIS's own
spatial selectivity estimators (`gserialized_sel_internal`/
`gserialized_joinsel_internal`, `:331-345`). Core extensions rarely touch
`nodes/supportnodes.h` at all; PostGIS leans its entire index story on it.
Cross-ref `[[knowledge/subsystems/optimizer]]`,
`.claude/skills/executor-and-planner/SKILL.md`.

### 4. Custom GiST/SP-GiST/BRIN opclasses with a lossy float-box compressed key

Underneath the support-function rewrite sit hand-written index AMs. The 2D GiST
opclass stores not the geometry but a `BOX2DF` — a *float-based*, deliberately
lossy bounding box — as its compressed key, via `gserialized_gist_compress_2d`
(`postgis/gserialized_gist_2d.c:81`), with matching `consistent`, `decompress`,
`penalty`, `union`, `same`, and a custom `picksplit`
(`gserialized_gist_2d.c:80-84`). The float key is intentionally rounded
*outward* so the index never produces false negatives, only false positives the
recheck removes (`box2df_from_gbox_p`, `:201`). The ND opclass uses a `GIDX`
variable-dimension box instead. This is a textbook-but-rare full custom-AM
implementation: a lossy key type with its own I/O functions
(`box2df_in`/`box2df_out`, `:74-75`) registered as a first-class type purely to
serve as an index key. Cross-ref `.claude/skills/access-method-apis/SKILL.md`,
`[[knowledge/subsystems/access-gist]]`.

### 5. It copy-pastes core's private `find_option` to detect GUC conflicts

`postgis_guc_find_option` (`libpgcommon/lwgeom_pg.c:537-566`) reaches into the
GUC machinery to tell whether a name is a *real* GUC vs a placeholder — needed
to avoid clobbering a custom GUC during extension upgrade. On PG ≥ 16 it calls
core's `find_option((void*)&key, false, true, ERROR)` directly; on older PGs it
hand-rolls a `bsearch` over `get_guc_variables()` with its own ASCII-only
comparator (`postgis_guc_name_compare`, `:491-516`) and *casts* `const char**`
to `struct config_generic*` on the documented assumption that "the name field is
first in config_generic" (`:543-546`). Depending on the private layout of a core
struct, version-gated by `POSTGIS_PGSQL_VERSION`, is exactly the kind of
internal-coupling core's stability contract discourages — and exactly what a
20-year-old extension accumulates. Cross-ref
`.claude/skills/gucs-bgworker-parallel/SKILL.md`.

### 6. It backfills missing fmgr conveniences

`CallerFInfoFunctionCall3` (`libpgcommon/lwgeom_pg.c:570-592`) reimplements a
3-argument `FunctionCall` variant with caller `FmgrInfo`/collation that core
never shipped, building the `LOCAL_FCINFO` by hand. A small but telling sign of
an extension old and broad enough to keep its own private patch of the fmgr API.
Cross-ref `.claude/skills/fmgr-and-spi/SKILL.md`.

## Notable design decisions (cited)

- **No `shared_preload_libraries` requirement.** Because PostGIS installs zero
  process-wide hooks and reserves no shmem, it loads lazily on first function
  call (`postgis_module.c:113-131` has no `RequestAddinShmemSpace`/hook
  installs). Contrast the hook-based extensions (pg_stat_statements, pg_cron)
  that *must* preload.
- **`SET_VARSIZE` after serialization.** `geometry_serialize`/
  `geography_serialize` (`lwgeom_pg.c:424-449`) call into liblwgeom to produce a
  `GSERIALIZED` then stamp the PG varlena header — the one place the foreign
  serialization format meets PG's varlena ABI.
- **`geography` forces geodetic on serialize** (`lwgeom_pg.c:429`) — the type
  distinction (planar `geometry` vs spherical `geography`) is enforced at the
  serialization boundary, not just in functions.
- **Every allocation is an interrupt check.** Routing `pg_alloc`/`pg_realloc`
  through `CHECK_FOR_INTERRUPTS()` (`lwgeom_pg.c:320,336`) means a tight
  geometry loop that allocates is implicitly cancellable even between the
  coarse-grained GEOS/liblwgeom interrupt callbacks.
- **Multiple sub-extensions share the binary model**: `postgis_raster`,
  `postgis_topology`, `postgis_sfcgal` each ship their own `.control.in`
  (`extensions/*/`), composing on the base `postgis` extension.

## Links into corpus

- `[[knowledge/idioms/memory-contexts]]` — the `palloc`/`CacheMemoryContext`
  adapters PostGIS installs into liblwgeom, and the per-session constants cache.
- `[[knowledge/subsystems/optimizer]]` — `SupportRequestIndexCondition` /
  `SupportRequestSelectivity`, the planner entry point PostGIS rewrites through.
- `[[knowledge/idioms/syscache]]` — `SearchSysCache`/`get_extension_oid` and the
  dynamic type-OID resolution.
- `[[knowledge/ideologies/pgvector]]` — the other "custom index AM as the whole
  point" extension; pgvector adds its own AM, PostGIS adds opclasses for the
  builtin GiST/SP-GiST/BRIN AMs plus the support-function rewrite layer.
- `.claude/skills/access-method-apis/SKILL.md` — the GiST opclass support
  routines and the lossy `BOX2DF`/`GIDX` key types.
- `.claude/skills/error-handling/SKILL.md` — the `ereport`-from-foreign-library
  bridge (`pg_error`/`pg_notice`/`pg_debug`).
- `.claude/skills/catalog-conventions/SKILL.md` — why PostGIS *can't* use fixed
  OIDs and resolves them at runtime instead.

## Sources

Fetched 2026-06-06 (branch `master`). Manifest drift: the queue listed
`liblwgeom/liblwgeom.h` and `postgis/postgis.h`; the real header is generated
from `liblwgeom/liblwgeom.h.in` (fetched), and `postgis/postgis.h` does **not**
exist in the tree (the PG-facing declarations live in `postgis/postgis_module.c`
+ `libpgcommon/lwgeom_pg.h`, fetched the former). Substituted the high-value
`postgis/postgis_module.c`, `libpgcommon/lwgeom_pg.c`,
`postgis/gserialized_supportfn.c`, `postgis/gserialized_gist_2d.c`, and
`extensions/postgis/postgis.control.in` to cover the bridge/support/AM story.

- `https://raw.githubusercontent.com/postgis/postgis/master/README.postgis`
  @ 2026-06-06 → HTTP 200 (329 lines; version 3.6.0rc2).
- `https://raw.githubusercontent.com/postgis/postgis/master/liblwgeom/liblwgeom.h.in`
  @ 2026-06-06 → HTTP 200 (2668 lines).
- `https://raw.githubusercontent.com/postgis/postgis/master/postgis/postgis_module.c`
  @ 2026-06-06 → HTTP 200 (143 lines).
- `https://raw.githubusercontent.com/postgis/postgis/master/libpgcommon/lwgeom_pg.c`
  @ 2026-06-06 → HTTP 200 (592 lines).
- `https://raw.githubusercontent.com/postgis/postgis/master/postgis/gserialized_supportfn.c`
  @ 2026-06-06 → HTTP 200 (542 lines).
- `https://raw.githubusercontent.com/postgis/postgis/master/postgis/gserialized_gist_2d.c`
  @ 2026-06-06 → HTTP 200 (2172 lines; cites only the opclass declaration block).
- `https://raw.githubusercontent.com/postgis/postgis/master/extensions/postgis/postgis.control.in`
  @ 2026-06-06 → HTTP 200 (5 lines).
- Tree listing
  `https://api.github.com/repos/postgis/postgis/git/trees/master?recursive=1`
  @ 2026-06-06 → HTTP 200 (2415 paths).

All cites into `postgis_module.c`, `lwgeom_pg.c`, and the declaration/table
blocks of `gserialized_supportfn.c` are `[verified-by-code]` against the fetched
files. The `SupportRequestIndexCondition` rewrite *body* below line 359 of
`gserialized_supportfn.c` (the actual `OpExpr` construction and `ST_Expand`
injection) was located by its surrounding code and the `expandFunctionOid`
helper but not transcribed line-by-line; the box-expansion narrative is
`[verified-by-code]` for the helper, `[inferred]` for the exact node assembly.
</content>
