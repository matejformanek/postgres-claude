# TimescaleDB — time-series analytics as a versioned, two-tier extension

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `timescale/timescaledb` @ branch `main`. All `file:line` cites below
> point into **that repo** (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> the files fetched on 2026-06-02 (see Sources footer).

## Domain & purpose

TimescaleDB is a PostgreSQL extension for "high-performance real-time
analytics on time-series and event data" `[from-README]` (`README.md:10`). Its
central abstraction is the **hypertable**: a single logical table that is
automatically partitioned in time (and optionally in a second "space"
dimension) into many physical child tables called **chunks**
`[from-README]` (`README.md:226-232`). On top of that sit a **columnstore**
(columnar compression of older chunks, `convert_to_columnstore` /
`compress_chunk`) and **continuous aggregates** (incrementally-refreshed
materialized views backed by a hypertable) `[from-README]`
(`README.md:248-313`). The user creates one via reloptions on a plain
`CREATE TABLE ... WITH (tsdb.hypertable)` or `WITH (timescaledb.continuous)`
`[from-README]` (`README.md:108-110`, `:255-256`).

The interesting question this repo answers is *different* from Citus'. Citus
asks "how far can a single extension re-route query execution?"; TimescaleDB
asks **"how can an extension ship, version, and license a very large body of
in-database C — including a closed-source tier — while staying installable as
a normal `CREATE EXTENSION`?"** Its most idiom-divergent machinery is in the
*packaging and loading* layer, not just the query layer.

## How it hooks into PG

TimescaleDB is a `shared_preload_libraries` extension, but with a structure no
other mainstream extension uses: a **two-tier loader**.

| Tier | Library | Role |
|---|---|---|
| Loader (stable) | `$libdir/timescaledb` (thin) | Goes in `shared_preload_libraries`. Its `_PG_init` runs in the postmaster: registers the bgw launcher, reserves shmem, defines the launcher GUC, and installs a `post_parse_analyze_hook` as a trampoline (`src/loader/loader.c:662-722`). |
| Versioned (per-release) | `$libdir/timescaledb-<version>` | The real extension. Loaded lazily, *by the loader*, the first time a query runs in a database where the extension is installed (`src/loader/loader.c:725-800`). Its `_PG_init` installs all the query-layer hooks (`src/init.c:91-133`). |

The version stamp is baked into the control file: `module_pathname =
'$libdir/timescaledb-@PROJECT_VERSION_MOD@'` `[verified-by-code]`
(`timescaledb.control.in:4`). So the `.so` filename itself encodes the
version, which is the linchpin of the coexistence story below.

Once the versioned library is loaded, its `_PG_init` wires the familiar core
hook surface `[verified-by-code]` (`src/init.c:112-122`):

| Core mechanism | TimescaleDB use |
|---|---|
| `_planner_init` (`planner_hook` + path hooks) | Detect hypertables, do chunk exclusion, inject custom scan nodes. |
| `_process_utility_init` (`ProcessUtility_hook`) | Intercept DDL on hypertables/chunks (add/drop chunk, compress, policies). |
| `_event_trigger_init` | Catch DDL via event triggers where utility-hook interception is awkward. |
| `_executor_init` | Execution-time instrumentation + custom-scan execution. |
| Custom scan nodes | `_constraint_aware_append_init`, `_chunk_append_init` register `ConstraintAwareAppend` / `ChunkAppend` custom-scan node types (`src/init.c:116-117`). |
| Caches | `_hypertable_cache_init`, `_cache_invalidate_init` — TS-managed relcache-style caches over its own catalog (`src/init.c:113-114`). |
| Background workers | The loader starts a **cluster-wide bgw launcher** (`ts_bgw_cluster_launcher_init`, `loader.c:673`) that spawns a per-database **scheduler** worker driving compression / retention / continuous-aggregate-refresh / telemetry jobs. |

The control file is `relocatable = false` (it uses multiple schemas, which PG
forbids relocating) and `trusted = true` — a database owner with `CREATE` can
install it without being a superuser `[verified-by-code]`
(`timescaledb.control.in:5-8`). Compare the `extension-development` skill's
trusted/relocatable table.

## Where it diverges from core idioms

### 1. The headline: a versioned two-tier loader (no other core extension does this)

A normal extension is a single `.so` at `$libdir/<name>`, named by the
`module_pathname` in its control file, and `shared_preload_libraries` loads
*that* file directly. TimescaleDB instead preloads a **stable thin loader**
whose only job is to dynamically `load_external_function()` the
**version-stamped** real library on demand (`src/loader/loader.c:751`,
`:782-783`). The payoff is documented in the FATAL path of `do_load`: if a
session already has one version mapped and a *different* version is now
current (e.g. an `ALTER EXTENSION ... UPDATE` happened), the session is killed
rather than allowed to run mismatched C against new catalogs
`[verified-by-code]` (`src/loader/loader.c:735-748`):

```c
ereport(FATAL,
        (errcode(ERRCODE_DUPLICATE_OBJECT),
         errmsg("\"%s\" already loaded with a different version", ext->name),
         ...));
```

This lets multiple extension versions coexist across a cluster's databases and
makes an in-place upgrade cost a *session* restart, not a *postmaster*
restart. Core's single-`.so` model has no equivalent — upgrading a normal
preloaded extension's binary means restarting the server.

Why a hook instead of checking at preload time? The loader's own comment block
spells out the constraint `[from-comment]` (`src/loader/loader.c:46-81`):
`shared_preload_libraries` runs in `PostmasterMain`, *before* `InitPostgres`
and even before the backend fork, so there is no assigned database and no
syscache to ask "is the extension installed here?". The earliest hook that
runs with a transaction and caches available is `post_parse_analyze_hook`, so
the loader trampolines through it (`loader.c:710-717`).

The load itself is wrapped in `PG_TRY`/`PG_CATCH` purely to protect the hook
chain: the loader saves `post_parse_analyze_hook`, NULLs it across the load,
and restores it afterward, asserting the versioned library did **not** install
its own analyze hook (`src/loader/loader.c:773-799`). Cross-ref the
`error-handling` skill's PG_TRY rules and `[[knowledge/idioms/error-handling]]`.

### 2. Single repo, two licenses, runtime-gated at module-load granularity

Every source file opens with a license header. Apache-licensed files
(`src/...`) say so (`src/chunk.h:1-5`, `src/hypertable.h:1-5`,
`src/init.c:1-5`); the `tsl/` tree carries the proprietary **Timescale
License** (`tsl/LICENSE-TIMESCALE` exists in the tree; top-level `LICENSE`,
`LICENSE-APACHE`). The community/enterprise boundary is enforced **at
runtime**: the versioned library defers loading the TSL submodule out of
`_PG_init` and into a separately-called SQL function `ts_post_load_init`,
which calls `ts_license_enable_module_loading()` `[verified-by-code]`
(`src/init.c:135-145`). The reason given is concrete and gnarly: if the TSL
`.so` were loaded during `_PG_init`, parallel workers would try to load it
before timescaledb itself, causing link-time errors (`src/init.c:138-141`).
No core extension ships a license split enforced by deferred dynamic loading —
this is an ideology unique to TimescaleDB's open-core business model. Cross-ref
`[[knowledge/idioms/bgworker-and-parallel]]` for why parallel-worker library
state is restored separately.

### 3. Its own partitioning model and catalog — parallel to, not built on, native PG partitioning

A chunk is *conceptually a hypercube in N-dimensional space*; each of its N
slices corresponds to a `CHECK` constraint on the chunk table
`[verified-by-code]` (`src/chunk.h:55-76`). Chunks can be `RELKIND_RELATION`
or `RELKIND_FOREIGN_TABLE` (`src/chunk.h:274`). TimescaleDB predates PG's
declarative partitioning and keeps its **own** dimension/hypercube model and
**own catalog tables** (`FormData_hypertable`, `FormData_chunk`, accessed via
`ts_catalog/catalog.h`; `src/hypertable.h:42-50`, `src/chunk.h:63-76`). Chunk
selection for a query point is TimescaleDB code (`ts_chunk_find_for_point`,
`ts_chunk_point_find_chunk_id`, `src/chunk.h:153-157`) plus the
`ConstraintAwareAppend` / `ChunkAppend` custom scan nodes — **not** core's
`partition pruning`. Contrast `[[knowledge/subsystems/partitioning]]`: core
prunes declarative partitions in the planner/executor; TimescaleDB reinvents
the equivalent over its own metadata. The hypertable struct caches its chunks
in a TS-managed `SubspaceStore *chunk_cache` (`src/hypertable.h:48`),
analogous to but separate from core's relcache.

### 4. Persisted status bitmasks with a hand-maintained on-disk compatibility contract

Chunk state lives in a status field that is **persisted and used as a bitmask
of powers of two**, with an explicit in-code warning that values must never
change and that new flags need special handling in the **downgrade** script
because older binaries won't understand them `[verified-by-code]`
(`src/chunk.h:277-307`): `CHUNK_STATUS_COMPRESSED` (1),
`CHUNK_STATUS_COMPRESSED_UNORDERED` (2), `CHUNK_STATUS_FROZEN` (4),
`CHUNK_STATUS_COMPRESSED_PARTIAL` (8). Core handles cross-version on-disk
compatibility with a single global `CATALOG_VERSION_NO` bump and an initdb
(see `[[knowledge/idioms/catalog-conventions]]` and the `catalog-conventions`
skill); TimescaleDB, which must support `ALTER EXTENSION ... UPDATE` **and
downgrade** on a live cluster with no initdb, instead pins the wire format of
each catalog field by hand and ships per-version up/down SQL migration
scripts. This is a fundamentally different durability/compatibility philosophy
forced by being an extension rather than the server.

### 5. Compression as a shadow "compressed chunk" relation

A compressed chunk is a *separate relation*; the uncompressed chunk's catalog
row carries a `compressed_chunk_id` and the `CHUNK_STATUS_COMPRESSED` flag
(`src/chunk.h:208-209`, `:283-289`). The hypertable itself can be in one of
three compression states including a `HypertableInternalCompressionTable`
sentinel for the internal table that stores compressed batches
(`src/hypertable.h:28-41`). Insert-into-compressed-chunk leaves data
"unordered" until a `recompress_chunk` restores the configured order — encoded
as `CHUNK_STATUS_COMPRESSED_UNORDERED` with an explicit need for a `Sort` step
in the meantime (`src/chunk.h:290-296`). This columnar-over-row shadow-table
design has no analogue in heap-only core.

### 6. Wrapped module magic and explicit symmetric init/fini ordering

TimescaleDB does not call `PG_MODULE_MAGIC` directly; it uses a wrapper
`TS_MODULE_MAGIC("timescaledb")` / `TS_MODULE_MAGIC("timescaledb-loader")`
that embeds the module name so the loader and versioned library are
distinguishable (`src/init.c:26`, `src/loader/loader.c:83`). And unlike most
extensions — which never define a working `_PG_fini` — TimescaleDB registers
an `on_proc_exit` cleanup (`cleanup_on_pg_proc_exit`) that tears modules down
in **strict reverse order of `_PG_init`**, documented as a maintained
invariant (`src/init.c:67-89`, `:130-131`). Cross-ref the
`extension-development` skill's note that `_PG_fini` "is effectively never
called" — TimescaleDB sidesteps that by using `on_proc_exit` instead.

## Notable design decisions (cited)

- **Version in the `.so` filename** (`timescaledb-<version>`,
  `timescaledb.control.in:4`) is what makes multi-version coexistence and
  session-scoped upgrades possible (§1).
- **`EXTENSION_STATE_TRANSITIONING` forces an immediate load** so the library
  is present *before* any `CREATE FUNCTION` in the install script triggers an
  uncontrolled implicit `.so` load (`src/loader/loader.c:805-815`).
- **`init_done` guard in `_PG_init`** tolerates eager loads calling it more
  than once (`src/init.c:94`, `:104-110`) — the lazy/preload duality means
  `_PG_init` is genuinely re-entrant in a way most extensions never face.
- **shmem reserved in the loader's `shmem_request_hook`**, chaining the
  previous hook first (`src/loader/loader.c:640-651`): bgw counter, message
  queue, LWLocks, function-telemetry. Textbook chain-of-responsibility, but
  notable that it's the *loader* (not the versioned lib) that owns shmem, so
  shmem layout is stable across version upgrades. Cross-ref
  `[[knowledge/idioms/locking-overview]]`.
- **`CalledInParallelWorker()` is a TS-defined macro**, not core's
  `IsParallelWorker()`, because the latter's backing variable isn't
  dll-exported correctly on Windows (`src/loader/loader.c:88-97`); the loader
  must skip loading in parallel workers since the parallel infrastructure
  restores library state itself (`loader.c:753-761`).
- **`trusted = true`** lets non-superuser database owners install it
  (`timescaledb.control.in:8`), a deliberate accessibility choice given the
  large C surface.

## Links into corpus

- `[[knowledge/idioms/catalog-conventions]]` — core's single `CATALOG_VERSION_NO`
  + initdb model vs TimescaleDB's hand-pinned, per-field on-disk compatibility
  and up/down migration scripts (§4).
- `[[knowledge/subsystems/partitioning]]` — native declarative partitioning &
  pruning vs TimescaleDB's own hypercube/chunk model and custom-scan exclusion
  (§3).
- `[[knowledge/idioms/error-handling]]` — the `PG_TRY`/`PG_CATCH` discipline
  around hook restoration in `do_load` (§1).
- `[[knowledge/idioms/bgworker-and-parallel]]` — the cluster-wide bgw launcher,
  per-database scheduler workers, and the parallel-worker library-load caveat
  (§2, design decisions).
- `[[knowledge/idioms/locking-overview]]` — shmem + LWLock reservation done in
  the loader's `shmem_request_hook`; per-chunk `LOCKMODE` handling.
- `[[knowledge/idioms/guc-variables]]` — `timescaledb.disable_load`,
  `bgw_launcher_poll_time`, `enable_direct_compress_insert`.
- `[[knowledge/architecture/planner]]` + `[[knowledge/subsystems/optimizer]]` —
  `planner_hook` entry, chunk exclusion, `ConstraintAwareAppend`/`ChunkAppend`.
- `[[knowledge/architecture/executor]]` + `[[knowledge/subsystems/executor]]` —
  custom-scan node execution for chunk append.
- `.claude/skills/extension-development/SKILL.md` — the `_PG_init`,
  `shared_preload_libraries`, hook-chaining, trusted/relocatable, and
  `module_pathname` idioms TimescaleDB both exemplifies and stretches (the
  versioned `.so` and the `on_proc_exit`-instead-of-`_PG_fini` patterns).

## Sources

Fetched 2026-06-02 (branch `main`):

- `https://raw.githubusercontent.com/timescale/timescaledb/main/README.md`
  @ 2026-06-02T11:17Z → HTTP 200 (458 lines; marketing/quickstart, thin on
  architecture — `[from-README]` cites are to its "Behind the Scenes" prose).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/docs/SECURITY.md`
  @ 2026-06-02T11:17Z → **HTTP 404** (manifest gap — file not present at this
  path on `main`; security model not characterized here as a result).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/chunk.h`
  @ 2026-06-02T11:17Z → HTTP 200 (310 lines).
- `https://raw.githubusercontent.com/timescale/timescaledb/main/src/hypertable.h`
  @ 2026-06-02T11:17Z → HTTP 200 (160 lines).
- Supplementary (not in manifest, fetched to ground the loader/license
  divergence claims):
  - `.../src/loader/loader.c` @ 2026-06-02T11:18Z → HTTP 200 (829 lines).
  - `.../src/init.c` @ 2026-06-02T11:18Z → HTTP 200 (146 lines).
  - `.../timescaledb.control.in` @ 2026-06-02T11:18Z → HTTP 200 (8 lines).
- Tree listing
  `https://api.github.com/repos/timescale/timescaledb/git/trees/main?recursive=1`
  @ 2026-06-02T11:17Z → HTTP 200 (2938 entries, not truncated).

Header struct, loader, and control-file cites are `[verified-by-code]` against
the fetched revision. README behavior claims are `[from-README]`. The loader's
preload-timing rationale is `[from-comment]` (the loader.c design block). The
`docs/SECURITY.md` manifest file 404'd; per the recipe's failure mode this gap
is logged here and the doc proceeds on the files that fetched.
</content>
