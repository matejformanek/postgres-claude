# lantern — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `lanterndata/lantern` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> the files fetched on 2026-06-20 (see Sources footer). The PG extension lives
> under `lantern_hnsw/`; the core is C despite GitHub's language label.

Lantern is a vector-similarity-search extension that ships a custom index
access method `lantern_hnsw`, backed by the external single-header **usearch**
HNSW library (`README.md:11`) `[from-README]`. Control-file comment:
`'Lantern: Fast vector embedding processing in Postgres'`
(`lantern_hnsw/cmake/lantern.control.template:1`) `[verified-by-code]`. **The
headline divergence:** the actual HNSW graph is built and traversed *inside*
usearch's own C++/header code, and the Postgres index relation is demoted to a
serialization substrate — usearch is compiled with `LANTERN_INSIDE_POSTGRES`
so it allocates *no* storage of its own and reads/writes graph nodes through
retriever callbacks that hand it raw pointers into PG buffer pages
(`lantern_hnsw/CMakeLists.txt:216-218`, `lantern_hnsw/src/hnsw/build.c:514-515`)
`[verified-by-code]`.

Where it sits in the corpus's vector triangle: `[[pgvector]]` owns the *type*
(`vector`) and its own AMs; `[[pgvectorscale]]` is a *rival index AM*
(StreamingDiskANN) that owns its on-disk graph; `[[zombodb]]` is an AM whose
storage is a *remote* engine. Lantern is a fourth shape — an index AM that is a
**thin bridge over a foreign in-memory graph library**, where the graph is
neither PG-native (unlike pgvectorscale) nor remote (unlike zombodb) but lives
in a vendored C++ header whose memory backing is borrowed from PG's own buffer
cache. It indexes both `real[]`/`integer[]` arrays and pgvector's `vector` type
(`lantern_hnsw/sql/lantern.sql:124-153`) `[verified-by-code]`.

## Domain & purpose

Lantern speeds up `ORDER BY <dist>(col, query) LIMIT k` nearest-neighbor
queries on vector columns (`README.md:9`) `[from-README]`. A
`CREATE INDEX ... USING lantern_hnsw (col dist_l2sq_ops)` builds an HNSW graph;
queries that ORDER BY a registered distance operator are routed to it as an
order-by-op index scan that streams approximate-nearest-neighbor TIDs. It is an
ANN index, not a type or a planner extension; it deliberately complements
pgvector (and reuses pgvector's `vector` type when present) rather than
replacing it (`lantern_hnsw/sql/lantern.sql:110-153`) `[verified-by-code]`.

## How it hooks into PG

- **CREATE ACCESS METHOD**: `CREATE ACCESS METHOD lantern_hnsw TYPE INDEX
  HANDLER hnsw_handler` is run from a `DO` block in the install SQL
  (`lantern_hnsw/sql/lantern.sql:120`); the handler is declared
  `CREATE FUNCTION hnsw_handler(internal) RETURNS index_am_handler`
  (`lantern_hnsw/sql/lantern.sql:2-3`) `[verified-by-code]`.
- **IndexAmRoutine fill-in** (`lantern_hnsw/src/hnsw.c:226-294`)
  `[verified-by-code]`: `amsupport = 4`, `amstrategies = 0`;
  `amcanorder = false` but **`amcanorderbyop = true`** (this is an order-by-op
  index, the pgvector-family idiom); `amcanbackward = false`,
  `amcanparallel = false`, `amcanunique = false`, `amcanmulticol = false`,
  `amoptionalkey = true`, `amsearchnulls = false`, `amstorage = false`,
  `ampredlocks = false`, `amcanreturn = NULL` (no index-only scans).
- **Callbacks wired**: `ambuild = ldb_ambuild`, `ambuildempty =
  ldb_ambuildunlogged`, `aminsert = ldb_aminsert`, `ambulkdelete`,
  `amvacuumcleanup`, `ambeginscan/amrescan/amgettuple/amendscan`,
  `amcostestimate = hnswcostestimate`, `amoptions = ldb_amoptions`,
  `ambuildphasename`, `amvalidate = hnswvalidate` (a stub returning `true`).
  `amgetbitmap = NULL`, `ammarkpos/amrestrpos = NULL`, all parallel-scan hooks
  `NULL` (`lantern_hnsw/src/hnsw.c:264-291`) `[verified-by-code]`.
- **pg_am / pg_opclass / pg_amproc / pg_amop registration** is entirely in the
  install SQL, not `.dat` BKI: operator classes are built by a plpgsql helper
  `_lantern_internal._create_ldb_operator_classes(am)` that EXECUTEs dynamic
  `CREATE OPERATOR CLASS` strings (`lantern_hnsw/sql/lantern.sql:63-104`)
  `[verified-by-code]`.
- **Operator classes / strategy + support numbers**: three array opclasses
  `dist_l2sq_ops` (DEFAULT), `dist_cos_ops`, `dist_hamming_ops`, plus
  `dist_vec_*` mirrors for pgvector's type. Each registers **STRATEGY 1** to a
  deprecated `<?>` operator and **STRATEGY 2** to the real distance operator
  (`<->` L2sq, `<=>` cos, `<+>` hamming), both `FOR ORDER BY float_ops` /
  `integer_ops`; **SUPPORT FUNCTION 1** and **2** are the distance functions
  (`lantern_hnsw/sql/lantern.sql:71-94, 141-153`) `[verified-by-code]`. The
  `<?>` operator is a deprecated generic that always raises an error at runtime
  (`lantern_hnsw/src/hnsw.c:347-352`) `[verified-by-code]`.
- **Distance support functions** (`lantern_hnsw/src/hnsw.c:354-405`): all four
  (`l2sq_dist`, `cos_dist`, `hamming_dist`, and `vector_*` variants) are thin
  wrappers that call `usearch_distance(...)` directly — even the SQL-callable
  distance is delegated to usearch (`lantern_hnsw/src/hnsw.c:317-344`)
  `[verified-by-code]`.
- **GUCs** (`lantern_hnsw/src/hnsw/options.c:324-399`): `lantern_hnsw.init_k`,
  `lantern_hnsw.ef`, `lantern.external_index_host/port/secure`, and
  `_lantern_internal.is_test`, all `PGC_USERSET`; prefixes reserved via
  `MarkGUCPrefixReserved` on PG ≥ 15 (`options.c:395-399`) `[verified-by-code]`.
  Index-build params (`m`, `ef_construction`, `ef`, `dim`, `pq`, `quant_bits`,
  `external`) are **reloptions**, registered in `_PG_init` via
  `add_*_reloption` and parsed in `ldb_amoptions` (`options.c:163-323`)
  `[verified-by-code]`.
- **External library linkage**: usearch is a git **submodule** at
  `lantern_hnsw/third_party/usearch` (`git tree type: commit`), and its
  `c/lib.cpp` is compiled straight into `lantern.so`
  (`lantern_hnsw/CMakeLists.txt:88-89, 117-119`); libstdc++ is statically
  linked in (`CMakeLists.txt:213-214`) `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. The on-disk index is a serialization substrate, not the data structure

Core nbtree/gist *are* the on-disk structure: pages hold the tree and the AM
walks pages directly. Lantern inverts this. The HNSW graph lives in usearch;
the PG index relation only persists a serialized usearch image plus a header.
At build, usearch builds the whole graph in memory, `usearch_save`s it to a
temp file, the file is `mmap`'d, and `StoreExternalIndex` copies that image
into index pages (`lantern_hnsw/src/hnsw/build.c:576-628`) `[verified-by-code]`.
At scan/insert, the header page (`BlockNumber 0`) holds an
`HnswIndexHeaderPage` with the 136-byte `usearch_header`, and
`usearch_view_mem_lazy` re-attaches usearch to that image without copying
(`lantern_hnsw/src/hnsw/scan.c:49-110`,
`lantern_hnsw/src/hnsw/external_index.h:38-56`) `[verified-by-code]`. usearch is
told the objects are "managed externally" by installing retriever callbacks
(`ldb_wal_index_node_retriever` / `_mut`) so it never tries to load nodes from
its own stream (`lantern_hnsw/src/hnsw/build.c:510-516`) `[verified-by-code]`.

### 2. Persistence goes through GenericXLog, not a custom rmgr

Lantern emits no custom WAL resource manager. Inserts open a
`GenericXLogStart`, register the header buffer plus the touched node/blockmap
pages (up to GenericXLog's 4-page limit, which the code explicitly budgets
for), and `GenericXLogFinish` (`lantern_hnsw/src/hnsw/insert.c:103-229`)
`[verified-by-code]`. Graph mutation thus happens *as a side effect of the
retriever handing usearch writable pointers into WAL-registered pages* — the
node bytes usearch scribbles into are inside a `GenericXLogRegisterBuffer`
delta image. The header page is held `BUFFER_LOCK_EXCLUSIVE` for the entire
insert "to make sure nobody else changes the block structure"
(`insert.c:219-245`) `[verified-by-code]`, a coarse index-wide write
serialization. `ambuildempty` writes the empty image to the **INIT_FORKNUM**
for unlogged tables (`build.c:653-689`) `[verified-by-code]`.

### 3. usearch allocates outside PG MemoryContexts

usearch's C++ graph and its scratch allocations are plain C++/`malloc`-side
heap, not `palloc` in a MemoryContext (it is a foreign library;
`build.c:517` `usearch_init`, freed by `usearch_free`) `[verified-by-code]`.
Lantern therefore polices memory *manually* against PG's budget GUCs: a
`CheckMem(maintenance_work_mem, ...)` / `CheckMem(work_mem, ...)` guard is
called before each `usearch_reserve`/search to approximate the contexts'
spill discipline (`build.c:118-124, 536-543`,
`lantern_hnsw/src/hnsw/insert.c:176-182`, `scan.c:214-218`)
`[verified-by-code]`. PG-side scratch (detoast buffers, label/distance arrays)
*does* use AllocSet contexts that are reset per build-callback / freed per scan
(`build.c:412-413, 156-177`, `scan.c:136-140`) `[verified-by-code]`.

### 4. Build-time "external indexing" via a separate daemon over a socket

`WITH (external = true)` diverts the whole build off-process: instead of
building locally, Lantern opens a socket to a **lantern daemon**
(`create_external_index_session`), streams each tuple's vector+label over it
(`external_index_send_tuple`), then receives back a finished usearch image to
store into PG pages (`build.c:111-113, 527-534, 564-574`) `[verified-by-code]`.
The daemon host/port/TLS are GUCs (`options.c:361-394`); a TLS variant
(`external_index_socket_ssl.c`) exists in the tree `[verified-by-code]`. This
is a third storage topology distinct from in-process build and from a remote
*query* engine: a remote *builder* whose output is re-internalized into PG.

### 5. Cost estimation is bespoke and order-by-only

`hnswcostestimate` returns `DBL_MAX` for every dimension when
`path->indexorderbys == NULL` — i.e. the index is unusable without an ORDER BY,
and "ALWAYS use index when asked" otherwise (`lantern_hnsw/src/hnsw.c:150-209`)
`[verified-by-code]`. It models HNSW's logarithmic visit count analytically
(`expected_number_of_levels`, `estimate_number_tuples_accessed`,
`hnsw.c:89-145`) rather than reusing core's generic selectivity, and pins
`*indexCorrelation = 0` because index tuples are appended at the last datablock
with no heap order (`hnsw.c:196-201`) `[verified-by-code]`.

### 6. Product quantization & sub-bit scalar quantization

Lantern carries a product-quantization path (`pq = true` loads a
`[tablename]_pq_codebook`, `build.c:498-501`) and a `quant_bits` reloption
mapping to usearch scalar kinds (`f16`/`i8`/`b1`; `options.c:137-158, 300-314`)
`[verified-by-code]`. Hamming distance reinterprets `integer[]` dimensions as
*bits* (`dim *= sizeof(int32)*CHAR_BIT`, `build.c:504-509`, `scan.c:84-88`)
`[verified-by-code]`. This is feature surface pgvector's stock HNSW lacks.

> usearch internals (the actual HNSW insert/search, node layout, SIMD distance
> kernels) live in the vendored submodule and were **not fetched** here; claims
> about usearch behavior are `[inferred]` from Lantern's call sites and the
> `usearch_storage.hpp` bridge declarations (`usearch_storage.hpp:9-26`).

## Notable design decisions (with cites)

- **TID-as-label**: the heap `ItemPointerData` (6 bytes) is memcpy'd into a
  `usearch_label_t` and used as the graph node's external key; a `static_assert`
  guards the size (`lantern_hnsw/src/hnsw/insert.c:203-205`, `hnsw.c:107-109`)
  `[verified-by-code]`. A scan reads labels back out as TIDs into
  `scan->xs_heaptid` (`scan.c:294-335`) `[verified-by-code]`.
- **Append-only index pages → static pins**: a long comment notes the AM never
  compacts pages, so "we always have a static pin on all index pages" and
  `amgettuple` skips the per-page pin core normally requires; deletions are a
  bitmap, not physical removal (`scan.c:310-334`) `[from-comment]`.
- **Streaming search re-expansion**: `amgettuple` first fetches `init_k`, then
  on exhaustion either re-runs with `k*2` or asks usearch for a streaming
  continuation, capping at 1000 with a WARNING (`scan.c:240-292`)
  `[verified-by-code]`.
- **Dimension inference from the heap**: if `dim` is unset, Lantern reads the
  first heap tuple (or evaluates the index expression) to infer vector length
  (`build.c:242-369`) `[verified-by-code]`.
- **Metric resolved from catalog at runtime**: `ldb_HnswGetMetricKind` looks up
  the opclass support function via `SearchSysCacheList1(AMPROCNUM, ...)` and
  switches on the C function *pointer* (`l2sq_dist` vs `cos_dist` vs
  `hamming_dist`) to pick the usearch metric (`options.c:105-128`)
  `[verified-by-code]`.
- **SIGSEGV/SIGABRT gdb-wait debug hook** installed from `_PG_init` in non-NDEBUG
  builds (`options.c:200-216, 401-404`) `[verified-by-code]`.

## Links into corpus

- `[[pgvector]]` — owns the `vector` type Lantern optionally indexes and the
  `<->`/`<=>` operator vocabulary it mirrors.
- `[[pgvectorscale]]` — the closest rival: a StreamingDiskANN index AM that, by
  contrast, owns its own on-disk graph rather than borrowing usearch's.
- `[[zombodb]]` — the other "AM as a front-end to a foreign engine"; zombodb's
  engine is *remote* (Elasticsearch), Lantern's is a *vendored in-process*
  library whose memory is PG buffers.
- `[[pg_textsearch]]` — another bespoke index AM (BM25) registering custom
  opclasses/operators.
- Idioms: `[[tableam-index-fetch]]`, `[[memory-contexts]]`,
  `[[catalog-conventions]]`, `[[guc-variables]]`,
  `[[wal-record-construction]]`, `[[relation-extension-lock]]`,
  `[[snapshot-acquisition]]`.

> Corpus gap: there is no `idioms/access-method-apis.md`; the IndexAmRoutine
> contract lives only in the `access-method-apis` **skill** and the
> `subsystems/access-nbtree.md` doc. An idiom doc summarizing the
> `amcanorderbyop` order-by-operator scan path (shared by pgvector / lantern /
> pgvectorscale) would be the natural home for cross-refs.
> Corpus gap: no `idioms/generic-xlog.md` — GenericXLog (the persistence
> mechanism Lantern, and bloom/contrib, rely on) is uncovered; cited here only
> via `[[wal-record-construction]]`.

## Sources

Tree listing (used to discover paths, not guess):
- `https://api.github.com/repos/lanterndata/lantern/git/trees/main?recursive=1` — 200, fetched 2026-06-20

Files fetched (raw.githubusercontent.com/lanterndata/lantern/main/...), all fetched 2026-06-20:
- `README.md` — 200 (top-level; `lantern_hnsw/README.md` → 404, not present)
- `lantern_hnsw/cmake/lantern.control.template` — 200 (control file is a template; `default_version = @RELEASE_ID@`)
- `lantern_hnsw/sql/lantern.sql` — 200
- `lantern_hnsw/src/hnsw.c` — 200
- `lantern_hnsw/src/hnsw.h` — 200 (skimmed)
- `lantern_hnsw/src/hnsw/build.c` — 200
- `lantern_hnsw/src/hnsw/insert.c` — 200
- `lantern_hnsw/src/hnsw/scan.c` — 200
- `lantern_hnsw/src/hnsw/options.c` — 200
- `lantern_hnsw/src/hnsw/external_index.h` — 200
- `lantern_hnsw/src/hnsw/usearch_storage.hpp` — 200 (bridge header; declarations only)
- `lantern_hnsw/CMakeLists.txt` — 200

Not fetched / out of scope:
- `lantern_hnsw/third_party/usearch/**` — git submodule (tree type `commit`); usearch internals not in this repo. usearch-behavior claims tagged `[inferred]`.
- `lantern_hnsw/src/hnsw/external_index.c`, `external_index_socket*.c`, `retriever.c`, `product_quantization.c`, `pqtable.c`, `delete.c` — skimmed via the tree + headers/call-sites, not fetched in full.
