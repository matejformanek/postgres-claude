# vectorchord — an IVF + RaBitQ **bit-quantized** vector index AM that keeps its posting lists in native PG pages, with an SPI-fed external centroid build

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `tensorchord/VectorChord` (vchord) @ branch `main`. The pgrx extension
> crate is the repo root (`src/`); the index AM lives under
> `src/index/vchordrq/`, storage in `src/index/storage.rs`, and the quantization
> math in the workspace crate `crates/rabitq/`. All `file:line` cites point into
> that repo (not `source/`). Cites verified against the `main` blobs fetched
> 2026-07-11 (see Sources footer); line numbers are as reported by each fetch.
> Read alongside `[[knowledge/ideologies/pgvector.md]]` (the type it reuses),
> `[[knowledge/ideologies/pgvectorscale.md]]` (the sibling Rust/pgrx AM it is most
> often confused with), and `[[knowledge/ideologies/pgrx.md]]` (the framework).

VectorChord (successor to pgvecto.rs) is the corpus's **5th distinct vector
shape**. The prior four: pgvector (custom `vector` TYPE + in-heap HNSW/IVFFlat
AMs, full-precision vectors in pages); pgvectorscale (a StreamingDiskANN *graph*
in bespoke PG "Tape" pages); lantern (an in-process usearch C++ library bridged
via retriever callbacks); zombodb (a remote engine masquerading as index
storage). **VectorChord's headline divergence:** it is an **IVF (inverted-file /
cluster-then-probe) AM whose stored form is RaBitQ *bit-quantized* codes, not
full-precision vectors.** Where pgvector stores every float and pgvectorscale
stores a full-precision-ish graph, `vchordrq` runs hierarchical K-means to build
a centroid tree, buckets each vector into a cluster, and stores a **1-bit (or
4/8-bit) quantized code** plus a handful of reconstruction factors per vector —
then reranks the shortlist. It packs those posting lists into **native
PostgreSQL index pages** through the buffer manager, Generic WAL, and the FSM
(so it is a genuine crash-safe in-PG AM, not an offloaded store), and it uniquely
exposes an **external build** path that reads precomputed centroids out of a user
table via SPI. It also swaps the Rust global allocator for **mimalloc**, moving
its hottest allocations entirely outside PG's `palloc`/MemoryContext accounting.

## Domain & purpose

VectorChord "applies RaBitQ compression together with autonomous reranking … you
can store 400,000 vectors for just \$1 … 26x more than pgvector/pgvecto.rs for
the same price" (`README.md:24`) `[from-README]`, targeting the "Billion-Scale
Era" — 100M×768-dim vectors on one i4i.xlarge, 1B-vector indexes built on 128GB
machines via hierarchical K-means + dimensionality reduction + sampling
(`README.md:4,31-41`) `[from-README]`. It is "fully compatible with pgvector data
types and syntax" (`README.md:43`) `[from-README]` and hard-`requires = 'vector'`
(`vchord.control:6`) `[verified-by-code]`: users write
`CREATE INDEX ON items USING vchordrq (embedding vector_l2_ops)` then the normal
`ORDER BY embedding <-> '[…]' LIMIT k` (`README.md:107-117`) `[from-README]`. Two
AMs ship: `vchordrq` (IVF+RaBitQ, the subject here) and `vchordg` (a RaBitQ graph
index), both registered by `CREATE ACCESS METHOD` (`src/sql/finalize.sql:393-394`)
`[verified-by-code]`.

## How it hooks into PG

A pgrx extension. `pgrx::pg_module_magic!(name = c"vchord", …)` (`src/lib.rs:23`)
stands in for `PG_MODULE_MAGIC`; top-level modules are `datatype`, `index`,
`recorder`, `upgrade` (`src/lib.rs:18-21`) `[verified-by-code]`. `_PG_init` is an
`extern "C-unwind"` shim exported by name that **refuses to load outside
`shared_preload_libraries`** — `if !process_shared_preload_libraries_in_progress
{ error!("vchord must be loaded via shared_preload_libraries.") }` — then calls
`index::init()` + `recorder::init()` and `MarkGUCPrefixReserved(c"vchord")`
(`src/lib.rs:50-64`) `[verified-by-code]`. `index::init()` fans out to
`gucs::init(); hook::init(); vchordrq::am::init(); vchordg::am::init()`
(`src/index/mod.rs:27-32`) `[verified-by-code]`.

- **AM registration.** `_vchordrq_amhandler` `palloc0`s an `IndexAmRoutine` and
  writes a `const AM_HANDLER` into it (`src/index/vchordrq/am/mod.rs:192-199,
  202-244`) `[verified-by-code]`. The routine sets `amcanorderbyop = true`,
  `amoptionalkey = true`, `amsupport = 1`, and (pg17/18) `amcanbuildparallel =
  true`, wiring `ambuild`, `aminsert`, `ambulkdelete`, `amvacuumcleanup`,
  `ambeginscan`/`amrescan`/`amgettuple`/`amendscan`, plus `amcostestimate`
  (`am/mod.rs:207-241`) `[verified-by-code]`. The SQL `CREATE ACCESS METHOD
  vchordrq TYPE INDEX HANDLER vchordrq_amhandler` is emitted from a static
  `finalize.sql` included via `extension_sql_file!` (`src/lib.rs:47-48`,
  `src/sql/finalize.sql:306-307,393`) `[verified-by-code]`.
- **Where the data lives:** in the **index relation's own pages**, via the buffer
  manager. `PostgresRelation::read` calls `ReadBufferExtended(MAIN_FORKNUM) +
  LockBuffer(BUFFER_LOCK_SHARE)` (`src/index/storage.rs:293-300`); writes go
  through `GenericXLogStart` + `GenericXLogRegisterBuffer`
  (`storage.rs:319-329`); page extension uses `ExtendBufferedRel` (pg16+) or
  `LockRelationForExtension` (pg14/15) (`storage.rs:342-402`) `[verified-by-code]`.
  Pages are ordinary `PageHeaderData` + `ItemIdData` line-pointer pages —
  `PageInit`, `PageAddItemExtended`, `PageGetFreeSpace`
  (`storage.rs:147-185`) `[verified-by-code]`. So node identity is a
  `(block, offset)` into the index relation and free space is tracked in the
  relation's own FSM (`GetPageWithFreeSpace`/`RecordPageWithFreeSpace`,
  `storage.rs:404-421`) `[verified-by-code]`. Nothing is mmap'd outside PG
  buffers; nothing is offloaded to an external process at query time.

Cross-ref `.claude/skills/access-method-apis/SKILL.md`,
`.claude/skills/buffer-manager/SKILL.md`.

## Where it diverges from core idioms

### (a) The stored form is a RaBitQ *bit-quantized* code, not a full-precision vector

This is the axis that separates VectorChord from pgvector and pgvectorscale. The
`crates/rabitq` crate is organized by bit-width — `pub mod bit;` (1-bit),
`pub mod halfbyte;` (4-bit), `pub mod byte;` (8-bit) — plus `packing`, `rotate`,
and `bits` (`crates/rabitq/src/lib.rs:15-21`) `[verified-by-code]`. Each stored
code carries a small `CodeMetadata { dis_u_2, factor_cnt, factor_ip, factor_err }`
(`crates/rabitq/src/bit.rs:19-25`) `[verified-by-code]` — the reconstruction /
error-bound factors that let a bit code approximate the true distance and drive
reranking. VectorChord also ships *native* low-bit types: `quantize_to_rabitq8`,
`quantize_to_rabitq4`, and inverse `dequantize_to_vector`/`_to_halfvec`
(`src/sql/finalize.sql:203-224`) `[verified-by-code]`, so RaBitQ4/RaBitQ8 are
first-class column types, not just an internal index encoding. Core PG (and
pgvector) never quantizes as the *storage* form; VectorChord's on-page footprint
is a fraction of the full-precision vector, which is the entire "400k vectors per
\$1" claim. Reranking the bit-code shortlist against exact distances ("autonomous
reranking", `README.md:24`) is `[from-README]`; the `epsilon` rerank parameter is
a GUC/reloption default 1.9 (`src/index/gucs.rs:66`,
`src/index/vchordrq/am/mod.rs:160-168`) `[verified-by-code]`.

### (b) IVF posting lists + a hierarchical-K-means centroid tree, not a B-tree or a graph

`vchordrq` is inverted-file: build clusters vectors under centroids and a query
"probes" a subset of clusters. Build produces `Vec<Structure>` where each
`Structure` holds `centroids` and `children` (`am_build.rs:1639-1643`), and
before packing, every centroid is passed through RaBitQ's random rotation
`rabitq::rotate::rotate_inplace` (`am_build.rs:261-265`) `[verified-by-code]`.
The centroid *tree* (multiple `Structure` levels) is the "hierarchical K-means"
of the README (`README.md:31`) `[from-README]`, and query-time probing depth is
the `probes` reloption/GUC — a per-level probe list, validated at cost-estimate
time against the tree's cell counts (`am/mod.rs:337-345`,
`src/index/gucs.rs:62`) `[verified-by-code]`. Contrast the cluster: pgvector's
HNSW is a graph; pgvectorscale is a DiskANN graph; `vchordrq` is
cluster-then-scan-posting-list — a fundamentally different index geometry sharing
the same PG-page substrate. (`vchordg`, the sibling AM, *is* a RaBitQ graph — so
VectorChord actually spans two of the vector-index geometries internally.)
Cross-ref `.claude/skills/access-method-apis/SKILL.md`.

### (c) Memory + allocator boundary: mimalloc replaces the Rust global allocator

Beyond pgrx's usual "Rust heap next to `palloc`" story, VectorChord installs
`#[global_allocator] static GLOBAL_ALLOCATOR: mimalloc::MiMalloc`
(`src/lib.rs:79-83`) `[verified-by-code]` on x86_64/aarch64 Linux/macOS. Every
Rust `Box`/`Vec`/`bumpalo` allocation in the build and scan paths therefore goes
to **mimalloc, entirely outside PG's MemoryContext accounting** — invisible to
`pg_backend_memory_contexts` and unbounded by `work_mem`/`maintenance_work_mem`
except by the algorithm's own arithmetic `[inferred]`. `aminsert` even spins up a
fresh `bumpalo::Bump` arena per inserted vector (`am/mod.rs:414-424`)
`[verified-by-code]`. This is a sharper allocator divergence than pgvectorscale
(which uses the platform allocator); it is the thing an OOM or leak audit on a
VectorChord backend must know first.

### (d) Build strategy: three sources — Default, Internal (heap-sample + K-means), and SPI-fed External — plus PG parallel build

`ambuild` dispatches on `vchordrq_options.build.source`
(`am_build.rs:234-260`) `[verified-by-code]`:

- **Internal** samples the heap via `HeapSampler` under `SnapshotAnyData` (or a
  registered MVCC snapshot when `ii_Concurrent`) and runs K-means to derive
  centroids (`am_build.rs:239-255,244`) `[verified-by-code]` — the on-box billion
  scale path, memory-controlled by sampling (`README.md:35`) `[from-README]`.
- **External** is the standout: `make_external_build` opens **SPI** and reads
  `SELECT id, parent, vector::vector FROM <table>` out of a user-provided
  centroid table, reconstructing the centroid tree from `(id, parent)` edges
  (`am_build.rs:1589-1633`) `[verified-by-code]`. Centroids can thus be computed
  by an *external* GPU/Spark job and loaded — a build-precomputation seam no core
  AM offers. Cross-ref `.claude/skills/fmgr-and-spi/SKILL.md`.
- **Parallel build** is real: `amcanbuildparallel = true` (`am/mod.rs:210-213`),
  a `VchordrqLeader` launches `vchordrq_parallel_build_main` workers coordinated
  by spinlocks + condition-variable barriers (`am_build.rs:293-360`)
  `[verified-by-code]`, with progress via `pgstat_progress_update_param`
  (`PROGRESS_CREATEIDX_*`, `am_build.rs:181-204`) `[verified-by-code]`. Build
  phases are surfaced through `ambuildphasename`
  (Initializing/Default/Internal/External/Build/Inserting/Compacting,
  `am_build.rs:43-51,163-172`) `[verified-by-code]`. Cross-ref
  `.claude/skills/parallel-query/SKILL.md`.

### (e) WAL / crash-safety: Generic WAL, with a Rust `Drop` as the abort guard

Like pgvectorscale, VectorChord is genuinely crash-safe: page writes are
WAL-logged through PG's **Generic WAL** facility (no custom rmgr). The write
guard holds a `*mut GenericXLogState`; its `Drop` impl calls `GenericXLogAbort`
if the thread is panicking, else `GenericXLogFinish` (+ optional
`RecordPageWithFreeSpace`/`FreeSpaceMapVacuumRange`) and `UnlockReleaseBuffer`
(`storage.rs:216-260`) `[verified-by-code]`. That restates the "every started
xlog is finished or aborted" C discipline as a Rust destructor invariant — the
same elegant twist the corpus flagged in pgvectorscale. `extend` registers pages
with `GENERIC_XLOG_FULL_IMAGE` (`storage.rs:387-393`) `[verified-by-code]`.
Cross-ref `.claude/skills/wal-and-xlog/SKILL.md`,
`[[knowledge/idioms/relation-extension-lock.md]]`.

## Notable design decisions (cited)

- **Index options are a TOML string reloption.** Rather than many typed
  reloptions, `vchordrq` takes `options` as "a TOML string" plus typed
  `probes`/`epsilon`/`maxsim_refine`/`maxsim_threshold`
  (`src/index/vchordrq/am/mod.rs:36-44,144-186`) `[verified-by-code]` — the whole
  build/index config (source Default/Internal/External, residual quantization,
  etc.) is parsed from that TOML at `ambuild` (`am_build.rs:213-228`)
  `[verified-by-code]`.
- **`amcostestimate` disables the index unless there's an ORDER BY/clause.** With
  no orderbys/clauses (or `vchordrq_enable_scan=false`) it returns `disable_cost`
  (`am/mod.rs:222,285-294`) `[verified-by-code]` — because `amoptionalkey=true` is
  a workaround for PG not generating a path for a pure `ORDER BY` (comment,
  `am/mod.rs:215-221`) `[from-comment]`.
- **Prefetch / read-stream aware.** `RelationPrefetch::prefetch` wraps
  `PrefetchBuffer`, and the storage layer defines a `ReadStream` type set
  (`storage.rs:17-22,424-432`) `[verified-by-code]`; per-op IO mode is a GUC
  (`vchordrq.io_search`/`io_rerank`, `src/index/gucs.rs:83-96`)
  `[verified-by-code]`. Cross-ref `[[knowledge/idioms/read-stream-prefetch.md]]`.
- **`relocatable = true`, `superuser = true`, `requires = 'vector'`**
  (`vchord.control:4-6`) `[verified-by-code]` — but load still hard-fails outside
  `shared_preload_libraries` (`src/lib.rs:53-54`) `[verified-by-code]`, because a
  background `recorder` worker and query-sampling hooks (`recorder::init`,
  `hook::init`) need preload timing.
- **pgrx `=0.17.0` with `cshim`, workspace of 12 crates**
  (`always_equal`, `distance`, `feistel`, `index`, `index_accessor`, `k_means`,
  `rabitq`, `simd`, `vchordg`, `vchordrq`, `vector`), `rusqlite` bundled, `rayon`
  for parallelism, `zerocopy` for on-page layout, edition 2024, `unsafe_code =
  "deny"` at the workspace root with `#![allow(unsafe_code)]` re-opened only in
  the pgrx crate (`Cargo.toml`, `src/lib.rs:15`) `[verified-by-code]`.
- **Native RaBitQ4/RaBitQ8 types + maxsim operators** for multi-vector
  (ColBERT-style) retrieval (`finalize.sql:43-46,203-224`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/pgvector.md]]` — the `vector` type VectorChord reuses
  (`requires='vector'`) and reads through SPI at external build; full-precision
  in-page storage is the baseline VectorChord quantizes away from.
- `[[knowledge/ideologies/pgvectorscale.md]]` — the closest sibling: also a
  Rust/pgrx durable vector AM with Generic-WAL-in-PG-pages and a `Drop`-based
  xlog abort. Divergence: pgvectorscale = DiskANN *graph* in a "Tape"; VectorChord
  = IVF posting lists + RaBitQ *bit* codes + hierarchical-K-means centroid tree.
- `[[knowledge/ideologies/lantern.md]]` — vector search via a *foreign in-process
  library* (usearch); VectorChord keeps everything in-PG instead.
- `[[knowledge/ideologies/zombodb.md]]` — index AM as a façade over an *external
  engine*; VectorChord is the opposite (real in-page store), sharing only the
  "hijack `CREATE ACCESS METHOD`" entry point.
- `[[knowledge/ideologies/pgrx.md]]` — `pg_module_magic!`, `#[pg_extern]`,
  `extension_sql_file!`, `extern "C-unwind"` callbacks, the mimalloc global
  allocator pattern.
- `[[knowledge/ideologies/paradedb.md]]` — another pgrx AM-registration extension for
  contrast.
- `.claude/skills/access-method-apis/SKILL.md` — `IndexAmRoutine`, amhandler,
  ambuild/aminsert/amgettuple/ambulkdelete, `amcanbuildparallel`, reloptions.
- `.claude/skills/wal-and-xlog/SKILL.md` — Generic WAL (`generic_xlog.c`) path.
- `.claude/skills/buffer-manager/SKILL.md` — `ReadBufferExtended`/`ExtendBufferedRel`.
- `.claude/skills/parallel-query/SKILL.md` — the leader/worker parallel build.
- `.claude/skills/fmgr-and-spi/SKILL.md` — SPI used to read the external centroid
  table.
- `[[knowledge/idioms/read-stream-prefetch.md]]`,
  `[[knowledge/idioms/relation-extension-lock.md]]` — the storage-layer primitives.

**The vector cluster, five shapes:** (1) **pgvector** — custom `vector` TYPE +
in-heap HNSW/IVFFlat AMs storing full-precision floats. (2) **pgvectorscale** — a
StreamingDiskANN *graph* in bespoke "Tape" PG pages, full-precision-ish, Rust/pgrx.
(3) **lantern** — a foreign in-process C++ usearch library bridged via retriever
callbacks. (4) **zombodb** — an index AM that offloads storage to a *remote engine*.
(5) **VectorChord/vchordrq** — **IVF cluster-then-probe with RaBitQ bit-quantized
codes** in native PG pages (bufmgr + Generic WAL + FSM), hierarchical-K-means
centroid tree, SPI-fed external centroid build, mimalloc allocator. The distinct
axis is *quantize-then-cluster*: the only shape whose primary on-disk form is a
lossy 1/4/8-bit code plus reconstruction factors, reranked against exact distances.

## Anthropology takeaway

VectorChord is the cluster's "compression-first" shape. pgvectorscale proved a
Rust/pgrx AM can re-implement a durable in-PG index faithfully; VectorChord takes
the same substrate (PG pages, Generic WAL, `Drop`-as-abort) but changes the
*information content* of a stored node from a full-precision vector to a RaBitQ
bit code — the divergence is in the payload, not the plumbing. Three seams are
worth propagating as corpus patterns: (a) **quantization as the storage form**,
with per-code error-bound factors driving a rerank pass, is a genuinely new
storage ideology versus every prior vector doc; (b) the **SPI-fed external build**
(`SELECT id, parent, vector FROM <table>`) is a clean, citable pattern for
"precompute the expensive part of an index outside PG, load it via SQL" that other
heavy-build AMs could copy; (c) the **mimalloc global allocator** makes the
Rust/pgrx "memory outside MemoryContext" hazard maximal — the entire hot path is
un-accounted. Honest gaps: I deep-read `lib.rs`, `index/mod.rs`, the `vchordrq`
`am/mod.rs` handler + `am_build.rs` dispatch/external/parallel sections,
`storage.rs`, the control/Cargo/finalize.sql surface, and skimmed `rabitq`'s
module layout + `CodeMetadata`. I did **not** audit the RaBitQ distance/rotation
math, the packing layout in `crates/rabitq/{bits,packing}.rs`, the `vchordg` graph
AM, or the scan/rerank inner loop (`scanners.rs`) — claims about quantization
*accuracy*, rerank mechanics, and posting-list on-page byte layout rest on module
names, `finalize.sql` signatures, and the README, and are tagged accordingly.

## Sources

All fetched 2026-07-11, branch `main`, via
`https://raw.githubusercontent.com/tensorchord/VectorChord/main/<path>`. The
GitHub git/trees API was blocked this run (403), so paths were discovered by
direct raw probes (`curl -w "%{http_code}"`); all listed paths returned 200.

- `README.md` — 200 (158 lines; purpose, RaBitQ/hierarchical-K-means claims,
  syntax, pgvector compatibility).
- `Cargo.toml` — 200 (workspace: 12 member crates, pgrx `=0.17.0` cshim, mimalloc
  target dep, edition 2024, lints).
- `vchord.control` — 200 (6 lines; `requires='vector'`, relocatable, superuser).
- `src/lib.rs` — 200 (83 lines; `pg_module_magic!`, `_PG_init` preload gate,
  mimalloc `#[global_allocator]`, module decls — deep-read).
- `src/index/mod.rs` — 200 (32 lines; `init()` fan-out, submodule list).
- `src/index/vchordrq/mod.rs` — 200 (21 lines; am/build/dispatch/opclass/types).
- `src/index/vchordrq/am/mod.rs` — 200 (deep-read head→460; Reloption + TOML
  reloption, `_vchordrq_amhandler`, `AM_HANDLER` IndexAmRoutine, amcostestimate,
  aminsert, ambulkdelete).
- `src/index/vchordrq/am/am_build.rs` — 200 (1830 lines; deep-read build phases,
  three build sources, internal HeapSampler/SnapshotAny, `make_external_build`
  SPI, parallel-build leader/barrier, progress reporting).
- `src/index/storage.rs` — 200 (723 lines; deep-read PostgresPage/PostgresRelation,
  ReadBufferExtended/LockBuffer, Generic WAL write guard + Drop abort, FSM,
  ExtendBufferedRel, prefetch/read-stream).
- `src/index/functions.rs` — 200 (skimmed; `_vchordrq_prewarm`, `index_open`).
- `src/index/gucs.rs` — 200 (skimmed; probes/epsilon/io_search GUC defaults).
- `src/sql/finalize.sql` — 200 (grep; `CREATE ACCESS METHOD vchordrq`/`vchordg`,
  amhandler functions, quantize/dequantize rabitq4/rabitq8, maxsim operators).
- `crates/rabitq/src/lib.rs` — 200 (module layout: bit/halfbyte/byte = 1/4/8-bit,
  packing/rotate/bits).
- `crates/rabitq/src/bit.rs` — 200 (skimmed head; `CodeMetadata` reconstruction
  factors).
- `src/recorder/mod.rs` — 200 (26 lines; background recorder `init`/`dump`).

Confidence: AM wiring, storage/bufmgr/WAL/FSM path, build-source dispatch,
external-build SPI, parallel-build coordination, control/Cargo facts, the
mimalloc allocator, and the reloption/GUC surface are `[verified-by-code]` against
the fetched blobs. Cost/scale claims, "autonomous reranking", hierarchical-K-means
naming, and pgvector compatibility are `[from-README]`. RaBitQ accuracy/rerank
mechanics, the on-page posting-list byte layout, `vchordg`, and the scan inner
loop were not audited and are tagged `[inferred]`/`[from-README]` where they
appear. No 404 gaps among cited paths. The GitHub API blockage means no tree
listing was consulted; the module graph was reconstructed from `mod`
declarations.
