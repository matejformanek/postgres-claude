# ParadeDB (pg_search) — a BM25 index AM whose segments are a Tantivy index, with transaction-deferred commits

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `paradedb/paradedb` @ branch `main` (the `pg_search` crate). All
> `file:line` cites below point into that repo (not `source/`), since this doc
> characterizes an *external* extension's divergence from core idioms. pg_search
> is Rust on **pgrx**, so cites land in `.rs` files. Cites verified against the
> files fetched on 2026-06-11 (see Sources footer). pg_search is a large
> monorepo crate (CustomScan aggregation, DataFusion, parallel workers); this
> doc covers the **index-AM core** (`build.rs`, `insert.rs`, `scan.rs`,
> `index.rs`, `fake_aminsertcleanup.rs`), not the analytics/CustomScan side.

## Domain & purpose

ParadeDB "is a PostgreSQL extension that brings Elastic-quality full-text search
and analytics directly inside Postgres" with "BM25 Scoring" full-text search
(`README.md`, What-is-ParadeDB section) `[from-README]`. The user-facing object
is `CREATE INDEX ... USING bm25 (...)`; queries then use ParadeDB's `@@@`
search operators and get Lucene-style relevance scoring, snippets, and
aggregations. Architecturally, pg_search is **a real Postgres index access
method whose stored segments are a Tantivy index** — Tantivy being the Rust
full-text engine in the Lucene family. Unlike `[[knowledge/ideologies/zombodb]]`
(which puts the index in a *remote* Elasticsearch cluster and bypasses the buffer
manager entirely), pg_search keeps the Tantivy segments *inside Postgres storage*
— it builds Tantivy on top of PG's block/WAL machinery via a custom rmgr. It is
the "embed a foreign storage/search engine through the index-AM API, but host its
bytes in PG pages" corner, complementing zombodb (remote) and
`[[knowledge/ideologies/hydra-columnar]]` (table-AM columnar in PG pages).

## How it hooks into PG

The control file: `comment = 'pg_search: Full text search ... using BM25'`,
`module_pathname = '$libdir/pg_search'`, `relocatable = false`,
`superuser = false`, `schema = paradedb` (`pg_search/pg_search.control`)
`[verified-by-code]`. pg_search registers an **index AM** (`USING bm25`) whose
`IndexAmRoutine` callbacks are the `#[pg_guard] pub extern "C-unwind"` functions
`ambuild` (`build.rs:33-38`), `ambuildempty` (`build.rs:111-112`), `aminsert`
(`insert.rs:224-235`), `ambeginscan`/`amrescan`/`amendscan`/`amgettuple`
(`scan.rs:45, 64, 266, 279`) `[verified-by-code]`. It also installs a **custom
rmgr** for WAL (`custom_rmgr::emit_init_record()`, `build.rs:101`) and — on
PG 15/16 — three **executor/utility hooks** to polyfill `aminsertcleanup`
(`fake_aminsertcleanup.rs:22-24`). So pg_search spans three extensibility
surfaces at once: the index AM, a custom WAL resource manager, and executor
hooks. The AM core opens/writes the Tantivy index through a `SearchIndex` /
`SerialIndexWriter` abstraction (`insert.rs:23, 52`) that reads and writes PG
blocks. Cross-ref the `access-method-apis` skill (the `IndexAmRoutine` it fills),
`[[knowledge/architecture/access-methods]]`, `[[knowledge/subsystems/access-nbtree]]`
(the canonical local index AM it parallels), and `wal-and-xlog` skill (the custom
rmgr it registers).

## Where it diverges from core idioms

### 1. The index payload is a Tantivy (Lucene-family) index, stored in PG blocks under a custom rmgr

A B-tree AM writes `IndexTuple`s into PG pages it understands. pg_search instead
serializes a *Tantivy* index — segments, postings, fast-fields, a schema with a
reserved `ctid` field — into Postgres storage. `ambuild` builds an empty index
(`build_empty`), then `build_index` streams heap tuples into the Tantivy writer
(`build.rs:53-84`) `[verified-by-code]`; the Tantivy schema is constructed with
field types mapped to `tantivy::schema` codecs and a mandatory `ctid` field
(`build.rs:286-327`) `[verified-by-code]`. The name `ctid` is *reserved*: trying
to index a user column called `ctid` panics (`build.rs:204-205`)
`[verified-by-code]`, because pg_search stores the heap `ctid` as a Tantivy
fast-field so a search hit can be resolved back to a heap TID. Hosting an entire
foreign inverted-index format inside PG's block storage (rather than as opaque
bytes in a remote system) is the central divergence. Cross-ref
`[[knowledge/subsystems/storage-buffer]]`,
`[[knowledge/data-structures/heap-tuple-layout]]` (the ctid contract).

### 2. WAL is *deferred* behind a build-time feature flag, then emitted in bulk via `log_newpage_range`

Core index builds WAL-log as they go (or rely on `wal_level` + the relation's
`need_wal`). pg_search adds a `deferred_wal` cargo feature: when on, `ambuild`
*disables* per-write WAL (`index_relation.set_need_wal(false)`,
`build.rs:46-51`), builds the whole index unlogged, then at the end issues one
`pg_sys::log_newpage_range(indexrel, MAIN_FORKNUM, 0, nblocks, true)` to WAL-log
every page of the finished index at once (`build.rs:88-98`) `[verified-by-code]`,
followed by `custom_rmgr::emit_init_record()` (`build.rs:100-102`). Choosing
between "let Postgres decide per-write" and "build unlogged, bulk-WAL at the end"
via a compile-time feature is a durability-knob most AMs don't expose; it trades
incremental crash-safety during build for throughput. Cross-ref `wal-and-xlog`
skill, `[[knowledge/architecture/wal]]`.

### 3. `aminsert` does not commit — Tantivy commits are deferred to transaction end

A naive search-index AM would commit each `aminsert` immediately, which is both
slow and wrong under MVCC (an aborted txn would leave docs in the index). pg_search
accumulates inserts in an `InsertState` and defers the Tantivy commit. The state
is cached in `IndexInfo.ii_AmCache`, leaked into the `ii_Context` memory context
so that "when that memory context is freed by Postgres is when we'll do our
tantivy commit/abort" (`insert.rs:200-220`) `[verified-by-code]`. On PG 17+ it
uses core's real `aminsertcleanup`; for logical-replication apply workers — where
"Postgres closes relations earlier, before our final cleanup work is complete" —
it instead registers `PreCommit`/`Abort` **xact callbacks** to flush at
transaction end (`insert.rs:155-178`) `[verified-by-code]`, "effectively
deferring tantivy index commits to the end of the postgres transaction"
(`insert.rs:163-165`) `[from-comment]`. Tying foreign-engine commit/abort to PG's
memory-context teardown and xact-callback lifecycle is a sophisticated graft of
Tantivy's transactional model onto Postgres's. Cross-ref
`[[knowledge/idioms/memory-contexts]]` (the `ii_Context`-keyed cleanup),
`[[knowledge/architecture/mvcc]]`.

### 4. A hand-built `aminsertcleanup` polyfill via an executor-hook frame stack on PG 15/16

Decision #3 needs a post-statement cleanup seam. PG 17 added `aminsertcleanup`;
on 15/16 pg_search rebuilds it. `fake_aminsertcleanup.rs` hooks `ExecutorRun`,
`ExecutorFinish`, and `ProcessUtility`, and each invocation that can produce
`aminsert` calls pushes an `InsertFrame` onto an `EXECUTOR_RUN_STACK` via a
`FrameGuard` whose `Drop` runs `insertcleanup` for every accumulated
`InsertState` (`fake_aminsertcleanup.rs:22-49`) `[from-comment]`. The module
documents its own invariants (stack length == live guards; nested DML pushes
independent frames; `Drop` checks `std::thread::panicking()` to avoid
double-panic during unwind, relying on PG rolling back storage on abort)
(`:36-65`) `[from-comment]`. Reconstructing a core lifecycle callback out of
three executor hooks plus an RAII frame stack — purely to backport one
AM API seam — is a striking "the API I need doesn't exist on this version, so I
synthesize it from hooks" move, the same genus as zombodb's hidden triggers.
Cross-ref `[[knowledge/subsystems/executor]]`, `[[knowledge/ideologies/zombodb]]`.

### 5. `amgettuple` resolves a Tantivy doc-address to a heap ctid via a fast-field, `xs_recheck = false`

The scan side is a thin adapter from Tantivy search results to the heap-TID
stream the executor expects. `amgettuple` sets `xs_recheck = false` (the index is
treated as lossless, `scan.rs:291`), pulls the next `(score, doc_address)` from
the Tantivy `SearchIndexReader`, then calls `resolve_ctid(&mut state.ctid_cache,
searcher, doc_address)` to read the stored ctid fast-field and writes it into
`(*scan).xs_heaptid` via `u64_to_item_pointer` (`scan.rs:296-314`)
`[verified-by-code]`. It caches the per-segment ctid fast-field reader to avoid
re-opening the column each row (`scan.rs:40-42`). For index-only scans
(`xs_want_itup`), it reconstructs an `IndexTuple` from the key fast-field, even
reaching across the FFI boundary to call core's `heap_compute_data_size` /
`heap_fill_tuple` directly (`scan.rs:316-367`) `[verified-by-code]`. The core
contract pg_search honors absolutely is the same one zombodb honors: write a
valid heap `ItemPointer` into `xs_heaptid`. Cross-ref the `access-method-apis`
skill, `[[knowledge/ideologies/zombodb]]` (identical `xs_heaptid`/`xs_recheck`
adapter shape, different storage backend).

## Notable design decisions (cited)

- **One `USING bm25` index per relation** — `ambuild` scans the heap's existing
  indices and panics if another bm25 index exists (accounting for REINDEX and
  CONCURRENTLY) (`build.rs:57-75`) `[verified-by-code]`; the same single-index
  restriction zombodb imposes, for the same whole-document-model reasons.
- **Partitioned-index awareness** — `IndexKind::for_index` detects
  `RELKIND_PARTITIONED_INDEX` and resolves child partition OIDs via an SPI query
  over `pg_inherits`/`pg_class`, opening each child with `AccessShareLock`
  (`index.rs:31-60`) `[verified-by-code]`; the AM models a partitioned bm25 index
  as a fan-out over child Tantivy indexes.
- **`superuser = false`, AGPL-3.0** (`pg_search.control:5`; license headers,
  e.g. `index.rs:6`) `[verified-by-code]` — installable by non-superusers, but
  under AGPL rather than the PostgreSQL license, a licensing posture (shared with
  pgrouting/zombodb) that matters for upstream/redistribution.
- **`set_is_create_index()` on the index relation** (`build.rs:41`) — pg_search
  tags the relation during build so downstream code can distinguish a fresh
  CREATE INDEX from steady-state inserts, part of its build-vs-maintain split.
- **Lazy segment claiming for parallel scans** — `amrescan` deliberately does
  *not* claim Tantivy segments up front because "PostgreSQL might call amrescan
  for a worker but never call amgettuple/amgetbitmap"; segments are claimed
  lazily in `search_next_segment` (`scan.rs:173-219`) `[from-comment]`, a
  parallel-worker-aware optimization. Cross-ref `gucs-bgworker-parallel` skill.

## Links into corpus

- `access-method-apis` skill + `[[knowledge/architecture/access-methods]]` — the
  `IndexAmRoutine` pg_search fills (`ambuild`/`aminsert`/`amgettuple` over a
  Tantivy backend); the single most important cross-reference, and the
  `xs_heaptid`/`xs_recheck`/`xs_want_itup` contracts it must honor.
- `[[knowledge/ideologies/zombodb]]` — the closest sibling: index-AM-as-search-
  engine. zombodb's storage is a *remote* Elasticsearch cluster (bypasses buffer
  manager + WAL); pg_search's storage is a *local* Tantivy index in PG blocks
  under a custom rmgr. Both: one index per table, `xs_recheck=false`, synthesize
  a missing AM lifecycle seam (zombodb via hidden triggers, pg_search via the
  executor-hook `aminsertcleanup` polyfill).
- `[[knowledge/ideologies/hydra-columnar]]` — the other "foreign format in PG
  blocks via formatted pages + custom storage" extension (table AM, not index
  AM).
- `wal-and-xlog` skill + `[[knowledge/architecture/wal]]` — the custom rmgr and
  the `deferred_wal` build-unlogged-then-`log_newpage_range` strategy.
- `[[knowledge/idioms/memory-contexts]]` — `InsertState` leaked into
  `IndexInfo.ii_Context`, with Tantivy commit/abort driven by context teardown.
- `[[knowledge/subsystems/executor]]` — the `ExecutorRun`/`ExecutorFinish`/
  `ProcessUtility` hook frame-stack that polyfills `aminsertcleanup` on pg15/16.
- `[[knowledge/ideologies/pgrx]]` — the `#[pg_guard] extern "C-unwind"` +
  `pg_guard_ffi_boundary` machinery used for every AM callback and the direct
  `heap_fill_tuple` FFI call.
- `gucs-bgworker-parallel` skill — lazy per-worker Tantivy segment claiming in
  `amrescan`/`amgettuple`.

## Sources

Fetched 2026-06-11 (branch `main`, `pg_search` crate):

- `https://api.github.com/repos/paradedb/paradedb/git/trees/main?recursive=1`
  @ 2026-06-11 → HTTP 200 (tree listing; 1531 blobs; AM file set located).
- `https://raw.githubusercontent.com/paradedb/paradedb/main/README.md`
  @ 2026-06-11 → HTTP 200 (104 lines; What-is/feature list read).
- `https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/pg_search.control`
  @ 2026-06-11 → HTTP 200 (6 lines).
- `https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/src/postgres/index.rs`
  @ 2026-06-11 → HTTP 200 (72 lines; `IndexKind`/partition fan-out).
- `https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/src/postgres/build.rs`
  @ 2026-06-11 → HTTP 200 (515 lines; `ambuild`, deferred-WAL, single-index
  guard, Tantivy schema/ctid-field read; sort-by-field helpers sampled).
- `https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/src/postgres/insert.rs`
  @ 2026-06-11 → HTTP 200 (447 lines; `aminsert`, deferred-commit state,
  logical-worker xact callbacks read; writer internals sampled).
- `https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/src/postgres/scan.rs`
  @ 2026-06-11 → HTTP 200 (507 lines; `amgettuple` ctid resolution + index-only
  tuple reconstruction read; `amrescan` segment-claiming comments read).
- `https://raw.githubusercontent.com/paradedb/paradedb/main/pg_search/src/postgres/fake_aminsertcleanup.rs`
  @ 2026-06-11 → HTTP 200 (364 lines; module doc on the executor-hook frame-stack
  polyfill read; hook bodies sampled).

All structural cites (AM callback signatures, `ambuild` deferred-WAL +
single-index panic, reserved `ctid` Tantivy field, `aminsert` deferred-commit via
`ii_AmCache`/`ii_Context`, logical-worker xact callbacks, `amgettuple`
ctid-fast-field resolution + `xs_recheck=false`, partitioned-index SPI fan-out)
are `[verified-by-code]` against the fetched `.rs`/`.control`; the
"Elastic-quality BM25 search inside Postgres" framing is `[from-README]`, and the
deferred-commit / `aminsertcleanup`-polyfill / lazy-segment-claim *rationales* are
`[from-comment]` (the authors' own module docs and inline comments),
cross-checked against the call sites. The Tantivy reader/writer internals
(`index/reader/index.rs`, `index/writer/index.rs`), the custom rmgr redo
function, the CustomScan/aggregation/DataFusion side, and `ambulkdelete`/`amvacuum`
were not deep-read.
