# deltax — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `xataio/deltax` @ branch `main`. All `file:line` cites below point into
> *that* repo (not `source/`), since this doc characterizes an external
> extension's divergence from core idioms. Cites verified against files fetched
> 2026-06-27 (see Sources footer).

DeltaX (`pg_deltax`, "δx") is a columnar time-series compression engine that
stores its compressed data **inside ordinary heap tables** and bends the PG
planner/executor — via five chained hooks and five `CustomScan` node types — to
read those tables transparently. The queue's "time-series compression" label
undersells it: the compression codecs (`src/compression/*`) are a small fraction
of the code; the bulk is a vectorized columnar scan/aggregate engine
(`src/scan/exec/*`, some files >150 KB) plus a planner integration layer. The
headline divergence is the deliberate *refusal* to introduce a new on-disk
format or a table AM: compressed segment blobs are `BYTEA` rows in companion
heap tables (`src/compress.rs:2375-2378`) `[verified-by-code]`, so replication,
crash recovery, backups, and `pg_dump` "work as for any other Postgres table"
(`README.md:15-18`) `[from-README]` — and the read path is reconstructed
entirely at plan time with `set_rel_pathlist_hook` + `CustomScan`, not at the
storage layer.

## Domain & purpose

δx turns a timestamp-bearing table into a time-range-partitioned table, then
compresses sealed (past) partitions column-by-column into companion tables,
making them read-only (`README.md:8-18,129`) `[from-README]`. During compression
it transposes row-oriented partitions into column-oriented segments of ~30 K rows
each (`README.md:98-100`; `deltax_deltatable.segment_size DEFAULT 30000`,
`src/lib.rs:173`) `[verified-by-code]` and picks a type-specific codec per
segment: Gorilla XOR for floats, Gorilla delta-of-delta for
timestamps/dates, Constant/FoR+bitpacking/Delta-Varint for integers, dictionary
(+optional LZ4) or block-LZ4 for text/JSONB, bitmap for booleans
(`README.md:102-110`; codec tags `src/compression/mod.rs:11-21`)
`[verified-by-code]`. It also harvests per-segment metadata (min/max/sum/counts,
bloom filters, value-presence bitmaps, text-length sidecars,
`README.md:114-123`) used to *prune segments* or *answer aggregates without
decompressing*. The control file declares the extension `superuser`,
non-`relocatable`, fixed `schema = 'deltax'` (`pg_deltax.control:4-6`)
`[verified-by-code]`. It is positioned as an Apache-2.0 alternative to
TimescaleDB and an in-Postgres alternative to ClickHouse/DuckDB
(`README.md:10-13`) `[from-README]`.

## How it hooks into PG

Built on [[pgrx]] 0.17, pgrx pg17/pg18 only (`Cargo.toml:18-19,23`)
`[verified-by-code]`. `_PG_init` (annotated `#[pg_guard] pub extern "C-unwind"`,
the pgrx FFI-safety pattern) wires up *everything* (`src/lib.rs:223-348`)
`[verified-by-code]`:

- **GUCs** — 13 `DefineCustom*Variable` registrations via pgrx `GucRegistry`
  (`src/lib.rs:225-336`) `[verified-by-code]`, spanning parallelism, bloom
  filters, blob-cache sizing, JSON-extract mode, and several
  correctness-A/B-test escape hatches (`disable_meta_agg_fastpath`,
  `disable_parallel_agg`, `src/lib.rs:277-292`).
- **Five planner/executor hooks**, each chained (previous pointer saved in an
  `AtomicPtr`): `set_rel_pathlist_hook`, `create_upper_paths_hook`,
  `get_relation_info_hook`, `planner_hook` (`src/scan/mod.rs:77-118`), plus
  `ExecutorStart_hook` (`src/scan/mod.rs:124-132`) and `ProcessUtility_hook`
  (`src/copy.rs:35-42`) `[verified-by-code]`.
- **Five named `CustomScanMethods`** registered with `RegisterCustomScanMethods`
  so parallel workers can rebuild custom nodes from DSM: `DeltaXDecompress`,
  `DeltaXAppend`, `DeltaXCount`, `DeltaXMinMax`, `DeltaXAgg`
  (`src/scan/path.rs:264-270`; names `src/scan/mod.rs:35-47`) `[verified-by-code]`.
- **Background workers** via pgrx `BackgroundWorkerBuilder`: a static *launcher*
  registered at `_PG_init` with `BgWorkerStartTime::RecoveryFinished`
  (`src/worker.rs:58-66`) that, post-recovery, reads the `target_database` GUC
  and `load_dynamic()`s one SPI-connected maintenance worker **per database**
  (`src/worker.rs:70-98`) `[verified-by-code]`.
- **Shared-memory blob cache** via `shmem_request_hook`/`shmem_startup_hook`
  registered from `_PG_init` (`src/blob_cache/mod.rs:131-134`,
  doc `:19-22`) `[verified-by-code]`.
- **SQL-callable functions** as pgrx `#[pg_extern]` (e.g. the blob-cache stats
  SRFs returning `TableIterator`, `src/blob_cache/mod.rs:219-263`), plus a
  large `extension_sql!` block that bootstraps the internal catalog tables
  (`src/lib.rs:159-221`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. Compressed data lives in heap tables, not a custom storage format or table AM

The defining choice. Rather than implement a columnar table AM (cf.
[[citus-columnar]]/Hydra) or a bespoke on-disk file, δx writes each segment's
compressed column as one `BYTEA` row in a per-partition `_blobs` companion table:
`CREATE TABLE … (_col_idx SMALLINT, _segment_id INT, _data BYTEA[ COMPRESSION
lz4], PRIMARY KEY (_col_idx, _segment_id))` (`src/compress.rs:2375-2378`)
`[verified-by-code]`. Sibling companions `_meta`, `_colstats`, `_blooms`,
`_text_lengths`, `_valbitmap` hold the pruning metadata (`src/compress.rs:2333-2384`;
enumerated `src/catalog.rs:844-847`) `[verified-by-code]`, all in a dedicated
`_deltax_compressed` schema (`src/lib.rs:161`, `src/compress.rs:2332`)
`[verified-by-code]`. The stated payoff: physical/logical replication, crash
recovery, backups, and `pg_dump` all work unchanged because the bytes are just
heap tuples (`README.md:15-18`) `[from-README]`. Companion tables are set
`autovacuum_enabled = off` on the parent partition (`src/compress.rs:1116`)
`[verified-by-code]`. The columnar wire format is δx's own: a 1-byte codec tag +
4-byte row count + null-bitmap + codec bytes (`src/compression/mod.rs:40-94`)
`[verified-by-code]` — i.e. δx owns the *intra-blob* encoding but leans on the
core heap for durability. Cross-ref [[access-method-apis]] (the table-AM road it
declined), [[wal-and-xlog]].

### 2. The read path is reconstructed at plan time with CustomScan, not at the AM layer

Because the heap of a compressed partition is truncated, δx must replace the
scan in the planner. `set_rel_pathlist_hook` detects a compressed partition and
injects a `DeltaXDecompress` custom path (`src/scan/mod.rs:1-4`,
`src/scan/hook.rs:550`) `[verified-by-code]`; `create_upper_paths_hook` injects
aggregate-pushdown nodes (`DeltaXCount`/`DeltaXMinMax`/`DeltaXAgg`,
`src/scan/hook.rs:1912-1944`) `[verified-by-code]`. A subtle planner-cost divergence
forced a *third* hook: `get_relation_info_hook` patches `rel->tuples`/`rel->pages`
because a compressed partition's `curpages` is 0 (heap truncated), which would
otherwise collapse `estimate_rel_size` to 0 tuples and zero out every
selectivity (`src/scan/mod.rs:92-104`) `[verified-by-code]`. Each
`CustomScanMethods` carries a `CreateCustomScanState` callback that builds the
Rust executor state (`src/scan/path.rs:231,246`) `[verified-by-code]`. This is
the [[executor-and-planner]] custom-scan API driven from Rust — the same seam
[[timescaledb]] and [[pg_duckdb]] use, but here it is the *entire* read path, not
an accelerator beside it.

### 3. Vectorized filtering/aggregation bypasses ExecQual and core agg nodes

δx decodes a segment into a column batch and evaluates `=,<>,<,<=,>,>=,LIKE,IN`
in "tight Rust loops over decoded batches, bypassing PostgreSQL's per-row
`ExecQual`" (`README.md:146`) `[from-README]`. Aggregates (`COUNT(*)`, `MIN/MAX`,
`SUM`, `AVG`, `COUNT(col)`, `GROUP BY`) are answered either *from segment
metadata* or by a vectorized aggregator inside the scan node
(`README.md:147`) `[from-README]`; the meta-only fast paths are
`DeltaXCount`/`DeltaXMinMax` and can be disabled for A/B correctness testing
(`src/lib.rs:48-51,277-284`) `[verified-by-code]`. This relocates the executor's
per-tuple expression machinery into Rust SIMD-friendly loops — a deliberate
inversion of the core per-row [[fmgr-and-spi]] calling convention.

### 4. Parallelism is two-layered: PG parallel workers *and* an internal Rayon-style thread pool

δx exposes a PG-level `Partial → Gather → FinalAgg` parallel-aware path for
`SUM`/`AVG`/`COUNT` (`README.md:149`; partial-path activation gated by
`disable_parallel_agg`, `src/lib.rs:53-60`) `[verified-by-code]` — which is why
the `CustomScanMethods` must be name-registered for DSM deserialization in
workers (`src/scan/path.rs:256-270`) `[verified-by-code]`. Separately, the
"complete" CustomScan path runs its *own* in-process worker threads
(`pg_deltax.parallel_workers`, auto = `num_cpus` capped at 16,
`src/lib.rs:40,107-114`) `[verified-by-code]`, including a thread-safe Rust-regex
path for parallel `REGEXP_REPLACE` in GROUP BY (`src/lib.rs:42,127-129`)
`[verified-by-code]`. Running OS threads inside a PG backend is squarely outside
core's single-threaded-backend model and pgrx's main-thread-only FFI contract
(see [[pgrx]] §main-thread); δx confines the threads to pure-Rust decode/aggregate
work that never re-enters `pg_sys`. Cross-ref [[parallel-query]],
[[bgworker-and-extensions]]. Top-N (`ORDER BY ts LIMIT N`) is explicitly
excluded from the parallel path because workers can't prune top-N locally
(`src/scan/path.rs:93-94`) `[verified-by-code]`.

### 5. A DSA-backed, sharded, LWLock-protected cross-backend blob cache

δx adds its own shared-memory cache of detoasted compressed blobs, keyed by
`(companion_oid, segment_id, col_idx)` (12-byte `#[repr(C)]` key,
`src/blob_cache/mod.rs:44-62`) `[verified-by-code]`, stored in DSA-backed shmem
indexed by a sharded `dshash` table with per-shard LRU eviction and byte
accounting (`src/blob_cache/mod.rs:1-22`) `[verified-by-code]`. Shard count is a
power-of-two GUC, each shard owning one LWLock (`src/lib.rs:311-320`,
`src/blob_cache/mod.rs:207-212`) `[verified-by-code]`. Auto-sizing reads
`/proc/meminfo` for 1/6 of physical RAM, with a documented OOM rationale: at
RAM/4 the non-reclaimable cache plus high-cardinality agg hash maps OOM-killed
the backend (`src/blob_cache/mod.rs:167-205`) `[verified-by-code]`. Building a
bespoke shmem cache *beside* `shared_buffers` and the TOAST detoast path is a
divergence from relying on the buffer manager; cross-ref [[memory-contexts]],
[[locking]].

### 6. Direct backfill via a ProcessUtility hook that hijacks `COPY ... FORMAT deltax_compress`

`COPY … WITH (FORMAT deltax_compress[_csv])` is intercepted by the
`ProcessUtility_hook` (`src/copy.rs:1-3,388-407`) `[verified-by-code]`, which
compresses incoming TSV/CSV/Parquet rows in-flight and writes them straight into
the `_blobs` companions, "bypassing the heap and its WAL / index / MVCC overhead"
(`README.md:160`) `[from-README]`. Inventing a private `COPY` FORMAT name and
servicing it from a utility hook (rather than registering a `COPY` handler or a
foreign-data wrapper) is a non-standard ingest seam. Parquet backfill pulls in
the `parquet` crate with zstd/snappy (`Cargo.toml:33`) `[verified-by-code]`.

### 7. DML on compressed partitions is rejected at executor start (and by a trigger)

Compressed partitions are read-only by policy. `ExecutorStart_hook` walks
`plannedstmt.resultRelations`, and if any maps to a compressed partition raises
`cannot {INSERT into|UPDATE|DELETE from} compressed partition …, decompress it
first` (`src/scan/hook.rs:4650-4719`) `[verified-by-code]`, backed by a
defensive plpgsql trigger emitting SQLSTATE `object_not_in_prerequisite_state`
(`src/lib.rs:207-218`) `[verified-by-code]`. An internal `DML_BYPASS`
thread-local lets δx's own decompress path write (`src/scan/hook.rs:4666-4670`)
`[verified-by-code]`. Enforcing immutability in the executor rather than via
relation permissions is a deliberate, extension-level access-control divergence.

### 8. JSONB field extraction with transparent plan rewrite

At compression time δx can pull JSON paths out of a `jsonb` column into synthetic
typed columns compressed with the matching native codec, then have the
`planner_hook` walk the *final* plan tree (post-`set_plan_references`) and rewrite
`data->>'field'` chains into `Var(OUTER_VAR, attno)` pointing at the synthetic
columns (`src/scan/mod.rs:28-32`; mode GUC `src/lib.rs:62-75,131-157`)
`[verified-by-code]`. Rewriting an already-finalized plan tree from an extension
hook is well beyond ordinary extension practice. Cross-ref
[[parser-and-nodes]], [[executor-and-planner]].

## Notable design decisions (with cites)

- **Internal catalog is plain SQL tables, bootstrapped by `extension_sql!`.**
  `deltax.deltax_deltatable` and `deltax.deltax_partition` (with JSONB metadata
  columns added by idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS`) are the
  registry, not a `pg_*` system catalog (`src/lib.rs:163-205`) `[verified-by-code]`.
  Cross-ref [[catalog-conventions]].
- **One bgworker per database, fanned out post-recovery.** Because a worker's SPI
  binds to a single database for life, δx uses the pg_cron/pg_partman launcher
  pattern; GUC values aren't reliably visible in `_PG_init`, so the fan-out is
  deferred (`src/worker.rs:45-98`) `[verified-by-code]`.
- **Worker pins `search_path` to `pg_catalog, pg_temp`** because it runs as
  superuser and would otherwise be vulnerable to object-shadowing
  (`src/worker.rs:115-120`) `[verified-by-code]`.
- **`panic = "unwind"` in both dev and release profiles** (`Cargo.toml:41,46`)
  `[verified-by-code]` — required so Rust panics can be caught at the pgrx FFI
  boundary and converted to `ereport` rather than aborting the backend (see
  [[pgrx]]).
- **Codec chosen per segment by trying several and keeping the smallest** for
  integers (Constant / FoR+bitpacked / Delta-Varint) (`README.md:104`)
  `[from-README]`; codec identity is recorded in the blob's 1-byte tag
  (`src/compression/mod.rs:8-38`) `[verified-by-code]`.
- **Null handling is uniform across codecs**: nulls are stripped into a separate
  bitmap before the codec runs, so each codec only sees non-null values
  (`src/compression/mod.rs:40-53,128-151`; `README.md:112`) `[verified-by-code]`.
- **`COMPRESSION lz4` on companion BYTEA columns is best-effort**: emitted only
  when PG was built `--with-lz4`, with graceful DDL fallback + one-shot WARNING
  otherwise (`src/lib.rs:88-99`, `src/compress.rs:2297-2303`) `[verified-by-code]`.
- **Correctness invariant**: δx must return identical results to plain PG on the
  uncompressed table; a four-policy comparison harness enforces it
  (`README.md:261-273`) `[from-README]`.

## Links into corpus

- [[pgrx]] — the substrate: every `#[pg_extern]`, `#[pg_guard]`, GUC
  registration, bgworker builder, and the panic↔`ereport` boundary the
  `panic = "unwind"` profiles depend on. Primary link.
- [[timescaledb]] — the C hypertable engine δx positions itself against; both
  partition time-series data and compress old partitions, but TimescaleDB owns
  its hypertable AM/chunk machinery while δx stays on plain heap + CustomScan.
- [[timescaledb-toolkit]] — the closest pgrx sibling, but a contrast: Toolkit
  exposes aggregate *state* as custom varlena types; δx exposes *nothing* as a
  type and instead rebuilds the scan path. Different divergence shape.
- [[pg_duckdb]] / [[pgvectorscale]] / [[pglite-fusion]] — fellow CustomScan /
  hook-driven query-acceleration extensions; δx is unusual in making CustomScan
  the *only* read path for its data.
- [[executor-and-planner]] — the CustomScan path/scan API + the five hooks,
  including the `get_relation_info_hook` cost-estimate patch and the
  `planner_hook` final-tree rewrite.
- [[access-method-apis]] — the table-AM road δx explicitly *declined* in favor of
  companion heap tables.
- [[catalog-conventions]] — the SQL-table internal catalog (not `pg_*`).
- [[memory-contexts]] / [[locking]] — the DSA-backed sharded LWLock blob cache.
- [[parallel-query]] / [[bgworker-and-extensions]] — PG partial-agg parallelism
  plus an internal Rust thread pool, and the launcher/worker fan-out.
- [[fmgr-and-spi]] — the per-row `ExecQual` convention δx bypasses with
  vectorized Rust loops; SPI used by the maintenance worker.
- [[wal-and-xlog]] — relevant to the "blobs are heap tuples → WAL/recovery free"
  claim (and the COPY-backfill WAL bypass).

> Corpus gap: no idiom doc on the "columnar-data-in-companion-heap-tables"
> pattern (storing a private columnar format as `BYTEA` rows to inherit
> replication/backup for free) — δx's central architectural move, shared in
> spirit with TimescaleDB's compressed chunks but distinct from a columnar
> table AM.
> Corpus gap: no idiom doc on running native OS threads inside a backend for
> pure-compute work while honoring pgrx's main-thread-only FFI contract.
> Corpus gap: no idiom doc on the multi-hook "rewrite the finalized plan tree"
> technique (`planner_hook` post-`set_plan_references` Var substitution).

## Sources

All fetched 2026-06-27 (branch `main`).

Tree listing:
- `https://api.github.com/repos/xataio/deltax/git/trees/main?recursive=1` → HTTP 200
  (used to resolve the `README.md,*.control,src/*.rs` manifest).

Files via `raw.githubusercontent.com/xataio/deltax/main/`:
- `README.md` → HTTP 200, 296 lines (purpose, codecs, features, limitations,
  correctness harness — primary `[from-README]` source).
- `pg_deltax.control` → HTTP 200, 6 lines (superuser, non-relocatable, schema=deltax).
- `Cargo.toml` → HTTP 200, 47 lines (pgrx 0.17, pg17/pg18, parquet, panic=unwind).
- `src/lib.rs` → HTTP 200, 370 lines (`_PG_init`, 13 GUCs, hook/bgworker/cache
  registration, `extension_sql!` catalog bootstrap).
- `src/compression/mod.rs` → HTTP 200, 230 lines (codec tags, blob wire format,
  null bitmap extraction).
- `src/compression/gorilla.rs` → HTTP 200, 717 lines (bit-level Gorilla
  XOR/delta-of-delta — header + BitWriter read).
- `src/scan/mod.rs` → HTTP 200, 132 lines (hook registration, the five CustomScan
  names, get_relation_info rationale).
- `src/scan/hook.rs` → HTTP 200, 4890 lines (DML reject at ExecutorStart;
  set_rel_pathlist/create_upper_paths entry points — targeted reads + grep).
- `src/scan/path.rs` → HTTP 200, 3080 lines (CustomPath/ScanMethods statics,
  RegisterCustomScanMethods, top-N parallel exclusion — targeted reads).
- `src/blob_cache/mod.rs` → HTTP 200, 318 lines (DSA/dshash/sharded-LWLock cache,
  key type, auto-size heuristic).
- `src/worker.rs` → HTTP 200, 425 lines (launcher + per-database dynamic worker,
  search_path pin).
- `src/copy.rs` → HTTP 200, 3866 lines (ProcessUtility hook, FORMAT
  deltax_compress interception — header + grep).
- `src/compress.rs` → HTTP 200, 4932 lines (companion-table DDL incl. `_blobs`
  BYTEA layout, autovacuum_enabled=off, lz4 clause — targeted reads).
- `src/catalog.rs` → HTTP 200, 1146 lines (companion-table enumeration — grep).
- `src/ddl.rs` → HTTP 200, 1090 lines (ALTER tier classification — grep, skimmed).

Skimmed-but-not-deep-read (size noted from tree, not fetched in full): the large
`src/scan/exec/*` engine files (`decompress.rs` ~187 KB, `segments.rs` ~183 KB,
`parallel_mixed.rs` ~202 KB, `serial.rs` ~90 KB), `src/stats.rs`,
`src/partition.rs`, `src/copyparquet.rs`, `src/copyparse.rs`, the remaining
`src/compression/*` codecs, and `src/functions/*` (`time_bucket`, `first`/`last`).
Claims drawn only from the README without a code cite are tagged `[from-README]`.
No 404s encountered.
