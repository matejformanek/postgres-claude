# pgGraph (Evokoa/graph) — a derived, mmap-backed CSR graph engine bolted to the side of PG

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `Evokoa/pgGraph` @ branch `main` (extension name `graph`, ~466★, new
> 2026-05, Apache-2.0). Language: **Rust / pgrx 0.18**. All `file:line` cites
> below point into that repo (cited as `graph/src/<file>:NN`), not `source/`,
> since this doc characterizes an *external* extension's divergence from core
> idioms. Cites verified against the files fetched 2026-06-17 (see Sources).

## Domain & purpose

pgGraph adds **bounded, read-heavy graph traversal** (search, shortest path,
N-hop relationship queries) over data that already lives in ordinary
PostgreSQL tables `[from-README]` (README.md:69-73). Its thesis is the inverse
of Apache AGE's: where AGE makes Postgres *store and speak* a property-graph
model, pgGraph keeps your relational tables as the system of record and builds
a **derived, rebuildable graph index** — "closer to a rebuildable graph index
than a graph database" `[from-README]` (README.md:271-280). `graph.build()`
compiles registered table/FK relationships into forward and reverse
**compressed-sparse-row (CSR)** adjacency stores, and traversals run as
graph-native memory scans rather than recursive SQL `[from-README]`
(README.md:286-308). The README explicitly frames itself as an *execution
layer*, contrasting with AGE (a storage layer) and PG19 SQL/PGQ (planner-backed
pattern matching) `[from-README]` (README.md:322-345).

## How it hooks into PG

- **Pure pgrx, no query-tree interception.** The control file declares
  `module_pathname = 'graph'`, `relocatable = false`, `superuser = true`,
  `trusted = false` `[verified-by-code]` (graph/graph.control:1-6). The entire
  user surface is **SQL-callable `#[pg_extern]` functions** in the `graph`
  schema (`graph.build()`, `graph.search()`, `graph.shortest_path()`,
  `graph.gql()`, etc.) `[from-comment]` (graph/src/lib.rs:1-7,726-727). Unlike
  AGE it installs **no** `post_parse_analyze_hook`, `planner_hook`, or
  `ProcessUtility_hook`; `_PG_init` only registers GUCs, registers transaction
  callbacks for its delta projection, and pre-warms the OS page cache
  `[verified-by-code]` (graph/src/lib.rs:754-792).
- **A separate in-process graph engine, one per backend.** State lives in a
  `thread_local!` `Engine` — "one per Postgres backend process"
  `[verified-by-code]` (graph/src/lib.rs:729-732). The `Engine` struct owns the
  node store, forward/reverse CSR edge stores, filter index, resolution index,
  and an mmap handle entirely outside PG's shared buffers `[verified-by-code]`
  (graph/src/engine.rs:60-134).
- **Persistence is an mmap'd file, not PG storage.** The graph is serialized to
  a custom `.pggraph` artifact: a 128-byte header (`magic "PGGH"`, version 3,
  CRC32) followed by 12 fixed sections (active bits, table OIDs, CSR
  offsets/targets/type-ids/weights, resolution index, primary-key bytes,
  bincode filter index + edge-type registry) `[verified-by-code]`
  (graph/src/persistence.rs:9-31,62-69). It is written atomically
  (`<path>.tmp` then rename) and mapped read-only so the **OS page cache shares
  one physical copy across isolated backends** `[from-comment]`
  (graph/src/persistence.rs:1-5,33-45; README.md:296-305). Load is lazy on
  first query (`maybe_auto_load()`); `_PG_init` only `madvise(WILLNEED)`s the
  file `[verified-by-code]` (graph/src/lib.rs:738-789).
- **Catalog of what to project lives in PG tables, accessed via SPI.** The set
  of registered tables and edges is stored in ordinary tables
  `graph._registered_tables` / `graph._registered_edges`, read and written
  through `Spi::connect` / `Spi::run_with_args` `[verified-by-code]`
  (graph/src/catalog/read.rs:6-28,70-82; graph/src/catalog/write.rs:14-28,
  42-64). So the *projection manifest* is PG-resident metadata; the *graph
  itself* is the off-heap mmap artifact.

## Where it diverges from core idioms

### 1. The hot data structure lives entirely outside PG's buffer manager and MemoryContext system

PG's contract is that on-disk relation pages flow through `shared_buffers` under
the buffer manager, and backend scratch memory is `palloc`'d in a
`MemoryContext` tree. pgGraph does neither for its graph: node and edge data are
**struct-of-arrays / CSR flat arrays** held in Rust `Vec`s or borrowed from an
mmap region (`MmapEdgeArrays`, `MmapNodeArrays` holding raw `*const u32/u8`
pointers into the mapping) `[verified-by-code]`
(graph/src/edge_store.rs:1-23,30-66; graph/src/node_store.rs:1-25,29-55). The
README is explicit that this is deliberately *not* a second buffer pool: "PG
remains responsible for table storage, WAL, MVCC, durability, and crash
recovery, while pgGraph's artifact is derived state that can be rebuilt"
`[from-README]` (README.md:299-305). Inbound traversal even derives a *separate
owned reverse CSR per backend* from the shared forward mmap
`[from-comment]` (graph/src/edge_store.rs:12-14). This is the central
divergence: a cache-friendly, mostly-immutable analytic structure layered
beside Postgres rather than inside its storage stack.

### 2. Two hand-rolled query frontends (GQL + openCypher), parser-complete, but pgrx-free and *not* spliced into PG's parse pipeline

Like AGE, pgGraph ships its own languages — but where AGE substitutes a
separately-parsed `Query` tree at `post_parse_analyze_hook`, pgGraph's parsers
are **plain library code reached only through the `graph.gql()` / `graph.cypher()`
SQL functions**. The GQL frontend owns "lexical analysis, syntax trees, and
parsing … deliberately does not touch PostgreSQL state" `[from-comment]`
(graph/src/gql/mod.rs:1-14). The openCypher frontend is a *compatibility* layer
that lowers into the same logical IR as GQL, and explicitly **refuses** features
it can't map (CALL/YIELD, UNWIND, FOREACH, LOAD CSV, START, UNION, Cypher DDL)
with `Unsupported` diagnostics `[verified-by-code]`
(graph/src/cypher/mod.rs:1-6, 52-84; tests bind both languages to an identical
logical IR, :38-49). A `COMPATIBILITY_MATRIX` even asserts "Full openCypher
compatibility … not claimed" `[verified-by-code]` (graph/src/cypher/mod.rs:
123-128). Both parsers are exposed to fuzz targets with no live backend
(`parse_gql_query`, `parse_cypher_query`) `[verified-by-code]`
(graph/src/lib.rs:136-146). So PG's planner/executor never sees graph syntax at
all — divergent from AGE, which makes core PG *execute* the foreign language.

### 3. Persistence reinvents the page/durability story as a custom binary artifact

The `.pggraph` format is a bespoke section-table file with its own magic,
versioning, CRC32 integrity, and an alignment-aware writer that even calls
`pgrx::check_for_interrupts!()` mid-serialization `[verified-by-code]`
(graph/src/persistence.rs:62-71,103-143). Beyond the base artifact there is a
**layered LSM-style projection** — base CSR + leveled delta segments (L0/L1/L2),
compaction, GC, and crash repair of dirty base chunks — all in `.pggraph-delta`
files referenced by a JSON `ProjectionManifest` `[verified-by-code]`
(graph/src/lib.rs:170-191, 437-617 bench/test fixtures exercise
`compact_generation`, `collect_projection_garbage`, `repair_active_base_chunks`,
`ProjectionManifestStore::publish`). pgGraph thus re-implements, off to the
side, an entire mini storage engine (write-atomically, checksum, version,
compact, GC, recover) that PG already provides for heap relations — justified by
its "derived state, rebuildable from source" stance `[inferred]`.

### 4. Its own error class + SQLSTATE space raised through a raw `errstart/errfinish` boundary

pgGraph defines a `GraphError` enum with custom `PG0xx` SQLSTATEs (e.g. OOM →
`PG001`, ACL denied → `PG002`) `[verified-by-code]`
(graph/src/safety.rs:18,88,295-309). Rather than route through pgrx's
`PgSqlErrorCode` enum — which only contains core's built-in codes and would be
UB to stuff custom values into — it hand-encodes the 5-char SQLSTATE the way
core's `MAKE_SQLSTATE` macro does and calls the raw C `errstart` / `errcode` /
`errmsg` / `errdetail` / `errhint` / `errfinish` functions directly via an
`extern "C-unwind"` block `[verified-by-code]`
(graph/src/safety.rs:204-281, esp. 227-236 and 250-277). This is the
pgrx panic→ereport boundary done *by hand* to get a custom SQLSTATE namespace —
a notable reach below the framework. The crate compiles with `panic = "unwind"`
on both dev and release profiles so the boundary can unwind safely
`[verified-by-code]` (graph/Cargo.toml:75-79).

### 5. ACL is delegated to core, not reimplemented — a deliberate non-divergence

Unlike AGE's parallel `agtype`/catalog world, pgGraph's `acl.rs` does **not**
build a permission model: every read/write helper calls core's
`pg_class_aclcheck(oid, GetUserId(), ACL_SELECT|INSERT|UPDATE|DELETE)` before
touching a mapped row `[verified-by-code]` (graph/src/acl.rs:18-69). Combined
with the README's "Source tables, constraints, indexes, ACLs, RLS, backups …
remain 100% standard PostgreSQL concerns" `[from-README]` (README.md:310-318),
this is the ideological tell: pgGraph diverges hard on *storage and execution*
but stays inside core for *authority* (durability, MVCC, ACL, RLS).

## Notable design decisions (cited)

- **One engine per backend, lazy-loaded, page-cache-shared.** `thread_local!`
  `Engine`; base arrays mmap-backed and shared across backends, materialized
  into owned arrays only on first sync mutation `[verified-by-code]`
  (graph/src/lib.rs:729-732; graph/src/node_store.rs:9-13;
  graph/src/engine.rs:62-68).
- **Read-only / OOM circuit breakers as engine state.** `is_read_only`,
  `ReadOnlyReason::{MemoryLimit, EdgeBufferFull}`, depth/frontier limits — an
  engine-level safety regime rather than relying on PG resource governors
  `[verified-by-code]` (graph/src/engine.rs:105-110,153-158; README.md:306-308).
- **GQL and openCypher converge on one logical IR.** Cypher is a thin
  compatibility skin over the GQL binder, asserted by a test that binds both to
  an equal logical plan `[verified-by-code]` (graph/src/cypher/mod.rs:38-49).
- **Catalog drift is tracked explicitly.** The engine keeps a
  `catalog_fingerprint` and `needs_rebuild`/`needs_vacuum`/`SchemaState` so a
  stale derived graph is detectable after source-schema changes
  `[verified-by-code]` (graph/src/engine.rs:115-125; catalog read computes a
  `catalog_fingerprint`, graph/src/catalog/read.rs imports).
- **`superuser = true`, `relocatable = false`, `trusted = false`** — the C code
  references a fixed `graph` schema and needs raw-symbol access, so it is not a
  trusted/relocatable extension `[verified-by-code]` (graph/graph.control:3-6).

## Links into corpus

- `[[knowledge/ideologies/apache-age]]` — the direct contrast: AGE is C, embeds
  openCypher by *substituting the query tree* at `post_parse_analyze_hook`;
  pgGraph is Rust/pgrx, keeps PG as system-of-record, and runs its own off-heap
  CSR engine with parsers that never enter PG's pipeline.
- `[[knowledge/ideologies/pgrx]]` — the framework underneath; pgGraph leans on
  `#[pg_extern]`/`#[pg_guard]`/`pg_module_magic!` but reaches *past* pgrx's
  `PgSqlErrorCode` to raise custom SQLSTATEs via raw `errstart/errfinish`.
- `[[knowledge/ideologies/pgvector]]` / `[[knowledge/ideologies/timescaledb]]` —
  other "specialized data structure beside the heap" extensions for comparison
  of how far each goes outside core storage.
- `[[knowledge/subsystems/storage-buffer]]` — the buffer manager pgGraph
  deliberately bypasses with mmap + OS page cache for its derived artifact.
- `[[knowledge/idioms/memory-contexts]]` — the MemoryContext discipline that
  pgGraph's Rust `Vec`/mmap-backed stores sit outside of.
- `[[knowledge/idioms/spi]]` — pgGraph's catalog read/write is pure SPI
  (`Spi::connect` / `Spi::run_with_args`) over `graph._registered_*` tables.
- `[[knowledge/idioms/error-handling]]` — the ereport/SQLSTATE machinery
  pgGraph re-enters by hand in `safety.rs`.
- `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md` — the `#[pg_extern]` + SPI surface.

## Sources

Fetched 2026-06-17 (branch `main`). Each URL is
`https://raw.githubusercontent.com/Evokoa/pgGraph/main/<path>`:

- `README.md` @ 2026-06-17T00:00Z → HTTP 200 (355 lines; positioning, CSR/mmap
  framing, AGE + SQL/PGQ contrast).
- `graph/graph.control` @ 2026-06-17 → HTTP 200 (6 lines; relocatable/superuser/
  trusted flags).
- `graph/Cargo.toml` @ 2026-06-17 → HTTP 200 (82 lines; pgrx 0.18.1,
  `panic = "unwind"`, deps: roaring/bitvec/memmap2/bincode/crc32fast).
- `graph/src/lib.rs` @ 2026-06-17 → HTTP 200 (821 lines; module map,
  `thread_local!` Engine, `_PG_init`, fuzz/bench surface).
- `graph/src/engine.rs` @ 2026-06-17 → HTTP 200 (2556 lines; Engine struct +
  ResolutionStore + read-only state — head read, error sites grepped).
- `graph/src/persistence.rs` @ 2026-06-17 → HTTP 200 (2124 lines; `.pggraph`
  format, atomic write, mmap memory model — head read).
- `graph/src/catalog.rs` @ 2026-06-17 → HTTP 200 (16 lines; module stub).
- `graph/src/catalog/read.rs` @ 2026-06-17 → HTTP 200 (254 lines; SPI catalog
  read — head read).
- `graph/src/catalog/write.rs` @ 2026-06-17 → HTTP 200 (64 lines; SPI catalog
  upsert).
- `graph/src/catalog/validate.rs` @ 2026-06-17 → HTTP 200 (527 lines; fetched,
  not deep-cited).
- `graph/src/cypher/mod.rs` @ 2026-06-17 → HTTP 200 (129 lines; compat frontend,
  unsupported-feature rejection, shared-IR test).
- `graph/src/gql/mod.rs` @ 2026-06-17 → HTTP 200 (418 lines; pgrx-free GQL
  lexer/parser frontend — head read).
- `graph/src/builder.rs` @ 2026-06-17 → HTTP 200 (1149 lines; fetched, not
  deep-cited).
- `graph/src/node_store.rs` @ 2026-06-17 → HTTP 200 (744 lines; SoA node store,
  mmap arrays — head read).
- `graph/src/edge_store.rs` @ 2026-06-17 → HTTP 200 (1346 lines; CSR edge store,
  mmap arrays — head read).
- `graph/src/acl.rs` @ 2026-06-17 → HTTP 200 (70 lines; delegates to
  `pg_class_aclcheck`).
- `graph/src/safety.rs` @ 2026-06-17 → HTTP 200 (738 lines; `GraphError`, custom
  SQLSTATE encoding, raw `errstart/errfinish` boundary).

No 404 gaps this run — all requested paths returned HTTP 200. `catalog.rs`
turned out to be a 16-line module facade (real logic in `catalog/{read,write,
validate}.rs`). Cites into `lib.rs`, `persistence.rs` (doc-comment format),
`acl.rs`, `safety.rs`, `cypher/mod.rs`, `catalog/{read,write}.rs`, and the
`edge_store.rs`/`node_store.rs` headers are `[verified-by-code]` against the
fetched files; `engine.rs`, `gql/mod.rs`, `builder.rs`, `validate.rs` were
read at the head/grep level, so claims about their bodies beyond what is cited
are `[inferred]`. README framing claims are `[from-README]`.
