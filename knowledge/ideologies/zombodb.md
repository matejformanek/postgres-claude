# ZomboDB — an index access method whose storage is a remote Elasticsearch cluster

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `zombodb/zombodb` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-07 (see Sources footer). Note: ZomboDB is written in Rust
> on **pgrx**, so cites land in `.rs` files; the design facts cross-check the
> authors' own `THINGS-TO-KNOW.md`.

## Domain & purpose

ZomboDB makes a full-text Elasticsearch index look, to SQL, like an ordinary
Postgres index. You write `CREATE INDEX ... USING zombodb (...)` and then query
with `table ==> '<elasticsearch query>'`; matching rows come back with full
MVCC correctness, including Elasticsearch aggregates answered "wholly within the
Elasticsearch cluster" (`THINGS-TO-KNOW.md:9-19`) `[from-README]`. The
historically important move: ZomboDB does this **through the index access-method
API**, synchronously — every `INSERT/UPDATE/DELETE/COPY` in a session round-trips
to Elasticsearch, and an index *scan* is an HTTP search whose hits are heap
ctids. It is the third corner of the "abuse a pluggable PG API to host a foreign
engine" triangle alongside `[[knowledge/ideologies/cstore_fdw]]` (FDW-as-storage)
and `[[knowledge/ideologies/pg_duckdb]]` (table-AM-stub + planner-swap): ZomboDB
is **index-AM-as-remote-search-engine**. Built in Rust/pgrx; current
`default_version = 3000.2.8` (`zombodb.control:2`).

## How it hooks into PG

The control file pins the extension to schema `zdb`, `superuser = true`,
`relocatable = false` (`zombodb.control:1-6`) `[verified-by-code]`. The
defining registration is a real `CREATE ACCESS METHOD`: the `amhandler`
function returns an `IndexAmRoutine` and the inline SQL runs `CREATE ACCESS
METHOD zombodb TYPE INDEX HANDLER amhandler`
(`src/access_method/mod.rs:11-41`) `[verified-by-code]`. The handler wires up a
deliberately **minimal** index-AM surface (see `access-method-apis` skill):

```
amstrategies = 4, amsupport = 0, amcanmulticol = true, amsearcharray = true
ambuild / ambuildempty / aminsert      (build + maintain the ES index)
ambulkdelete / amvacuumcleanup         (vacuum dead docs out of ES)
amcostestimate / amoptions / amvalidate
ambeginscan / amrescan / amgettuple / amgetbitmap / amendscan   (search)
```

(`src/access_method/mod.rs:19-41`). `amvalidate` is a no-op returning `true`
(`:43-46`) — there are no opclass support functions to check because the "index"
isn't a Postgres on-disk structure at all. Alongside the AM, ZomboDB installs
pgrx executor/utility/planner hooks (`PgHooks`: `executor_start`/`executor_end`
push/pop per-query state, `process_utility_hook` handles DROP cascades,
`planner` rewrites the `==>` operator) (`src/executor_manager/hooks.rs:13-47`,
`:219-245`). Cross-ref `[[knowledge/architecture/access-methods]]`,
`[[knowledge/subsystems/access-nbtree]]` (the canonical index AM it mimics the
shape of), `[[knowledge/subsystems/tcop]]`.

## Where it diverges from core idioms

### 1. The index has no local storage — `amrescan` is an HTTP search to Elasticsearch, `amgettuple` yields the ctids ES returns

This is the load-bearing divergence. A normal index AM stores entries in
Postgres pages via the buffer manager and walks them in `amgettuple`. ZomboDB's
`ambeginscan` just allocates a `ZDBScanState { index_oid, iterator }` with no
buffer at all (`src/access_method/scan.rs:8-35`) `[verified-by-code]`.
`amrescan` decodes the scan key as a `ZDBQuery`, ANDs multiple keys into an ES
`bool/must` query, opens a search against the Elasticsearch cluster, and stores
the response iterator (`src/access_method/scan.rs:37-72`). `amgettuple` then
pulls `(score, ctid, highlights)` tuples from that iterator and writes the ctid
straight into `scan.xs_heaptid`, setting `xs_recheck = false` because "ZomboDB
indices are not lossy" (`src/access_method/scan.rs:74-108`). So the index's
"pages" live in a remote ES cluster, and the AM is a thin adapter turning ES
search hits into the heap-TID stream the executor expects. `ambitmapscan`
similarly feeds every hit's ctid into a `TIDBitmap` via `tbm_add_tuples`
(`:115-138`). Cross-ref `[[knowledge/subsystems/storage-buffer]]` (the buffer
manager ZomboDB's index bypasses), `[[knowledge/data-structures/heap-tuple-layout]]`
(ctid/`ItemPointer` is the one core contract it must honor — see below).

### 2. MVCC visibility is replicated *into* Elasticsearch, and ZomboDB stores the entire row there

To return MVCC-correct results from a foreign engine that knows nothing about
xmin/xmax, ZomboDB tracks transaction-visibility values inside the ES documents
and must store "the entire document source for each indexed row" so it can
update those values on UPDATE/DELETE/vacuum — making ES indexes "perhaps close
to 2x larger" than the heap (`THINGS-TO-KNOW.md:70-79`) `[from-README]`. The ES
index therefore holds dead rows, aborted rows, and in-flight rows from active
transactions, which is exactly why searching it with external tools (Kibana,
curl) "you're going to see those rows too because you don't also have Postgres
helping you" (`THINGS-TO-KNOW.md:110-122`). This is a complete re-hosting of
core's MVCC visibility apparatus outside Postgres, kept consistent by the AM's
insert/delete/vacuum callbacks. Cross-ref `[[knowledge/architecture/mvcc]]`.

### 3. Synchronous, transaction-batched round-trips — failures abort the Postgres transaction

Unlike the typical async PG↔ES integration where index updates "appear ... some
time in the future," ZomboDB is synchronous (`THINGS-TO-KNOW.md:5-15`)
`[from-README]`. It batches ES indexing **by transaction, not by row**
(`BulkContext` flushed via the executor manager, `src/access_method/build.rs:6`,
`:12-24`), flushing automatically before a search needs to see pending writes.
The consequence the authors stress: any ZomboDB/network/Elasticsearch failure
"will cause the operating Postgres transaction to ABORT ... pushed forward to
the client" (`THINGS-TO-KNOW.md:21-24`). Tying Postgres transaction atomicity to
a remote HTTP service's availability is a durability/coupling posture core never
takes — and it interacts with vacuum: ZomboDB's `ambulkdelete` must
`?wait_for_active_shards=all` before Postgres reuses tuple slots, which is why
it defaults to **zero** ES replicas via `zdb.default_replicas`
(`THINGS-TO-KNOW.md:26-38`). Cross-ref `[[knowledge/idioms/error-handling]]`,
`[[knowledge/architecture/wal]]` (the durability story ZomboDB delegates to ES,
not WAL).

### 4. The planner hook rewrites `table ==> 'query'` into `table.ctid ==> 'query'`

`==>` is declared with the table on the left, but during planning ZomboDB
rewrites the LHS to the table's `ctid` system column —
`WHERE table ==> 'foo'` becomes `WHERE table.ctid ==> 'foo'`
(`THINGS-TO-KNOW.md:83-95`) `[from-README]`, implemented in the `planner` hook
(`src/executor_manager/hooks.rs:219`) and `access_method/rewriter.rs`. This is
what lets a single operator drive an index scan, a bitmap scan, or even a
sequential-scan recheck, all resolving to heap ctids. Manufacturing a
ctid-keyed predicate in the planner so the AM can return heap TIDs is a bespoke
query-shape transform with no core analogue. Cross-ref
`[[knowledge/architecture/planner]]`, `[[knowledge/subsystems/optimizer]]`.

### 5. Hidden internal triggers compensate for the index AM's lack of an UPDATE/DELETE visibility hook

`aminsert` sees new tuples, but the index AM API gives an AM no direct callback
when a heap tuple is *updated* or *deleted* — Postgres expects the heap+vacuum
to handle that. Because ZomboDB must push those visibility changes to ES
immediately, `CREATE INDEX ... USING zombodb` attaches two `tgisinternal`
FOR EACH ROW BEFORE UPDATE/DELETE triggers to the table
(`src/access_method/triggers.rs` via `build.rs:4`,
`THINGS-TO-KNOW.md:97-108`) `[from-README]`. They carry a catalog dependency on
the index so `DROP INDEX` removes them. Synthesizing triggers to fill a gap in
the AM lifecycle is the same "the pluggable API lacks the lifecycle seam I need,
so I bolt one on" move that cstore_fdw makes with DDL event triggers — here via
row triggers instead. Cross-ref `[[knowledge/ideologies/cstore_fdw]]`.

### 6. Per-query side state lives in an executor-manager singleton, not in the scan

Scores and highlights are properties of an ES search, but Postgres' index-scan
path has nowhere to put them. ZomboDB stashes them in a global executor manager:
`amgettuple`/`ambitmapscan` call `get_executor_manager().peek_query_state()`
and `qstate.add_score(...)`/`add_highlight(...)` keyed by `(index_oid, ctid)`
(`src/access_method/scan.rs:100-102`, `:120-133`) `[verified-by-code]`, and the
`executor_start`/`executor_end` hooks push/pop that query state
(`src/executor_manager/hooks.rs:13-29`). The SQL functions `zdb.score(ctid)` /
`zdb.highlight(ctid)` later read it back out. A code comment candidly flags the
HOT-update hazard: the stashed score relates to the *index* ctid, not the heap
ctid, so after a HOT update `zdb.score()` may return NULL
(`src/access_method/scan.rs:95-99`). Cross-ref `[[knowledge/subsystems/executor]]`.

## Notable design decisions (cited)

- **One non-shadow ZomboDB index per table; no `WHERE` predicate; no
  `CONCURRENTLY`.** `ambuild` panics on each of these
  (`src/access_method/build.rs:40-57`) `[verified-by-code]` — strong limits that
  fall out of the whole-row-to-ES model (a partial index can't hold whole-row
  source; concurrent build can't safely stream to ES).
- **`xs_recheck = false` always** (`src/access_method/scan.rs:82-83`) — ZomboDB
  declares its index lossless, so the executor never re-evaluates the qual
  against the heap tuple; correctness rests entirely on ES returning exactly the
  visible ctids.
- **Index scan returns tuples in heap order (usually).** An IndexScan over a
  ZomboDB index returns ctids in heap order — "effectively doing a sequential
  scan on the heap (just likely skipping lots of pages)" — except when
  `zdb.score()` or `LIMIT` is present, in which case results come back in
  descending score order (`THINGS-TO-KNOW.md:53-59`).
- **Default selectivity hardcoded at 2500 rows.** `amcostestimate` assumes a
  `==>` query returns 2500 rows to nudge the planner toward an IndexScan,
  overridable via `zdb.default_row_estimate` / `dsl.row_estimate()`
  (`THINGS-TO-KNOW.md:40-48`; `src/access_method/cost_estimate.rs`).
- **`amsupport = 0`, `amvalidate` returns true** (`src/access_method/mod.rs:20`,
  `:43-46`) — no opclass support-function machinery, because matching is done by
  Elasticsearch, not by Postgres operator-class procedures. The ES query DSL is
  exposed instead as a large SQL surface generated from `extension_sql_file!`
  blocks (`src/lib.rs:28-58`).

## Links into corpus

- `[[knowledge/architecture/access-methods]]` + `access-method-apis` skill — the
  `IndexAmRoutine` ZomboDB fills with ES-backed callbacks; the single most
  important cross-reference. `amsupport=0`/no-op `amvalidate` show how little of
  the opclass machinery a remote-search AM needs.
- `[[knowledge/subsystems/access-nbtree]]` — the canonical local index AM whose
  shape ZomboDB mimics while replacing the storage with Elasticsearch.
- `[[knowledge/subsystems/storage-buffer]]` + `[[knowledge/architecture/wal]]` —
  the buffer manager and WAL durability ZomboDB's index bypasses, delegating
  durability and replication to the ES cluster.
- `[[knowledge/architecture/mvcc]]` + `[[knowledge/data-structures/heap-tuple-layout]]`
  — MVCC visibility re-hosted into ES documents; ctid/`ItemPointer` is the one
  core contract the AM must honor (it writes `scan.xs_heaptid`).
- `[[knowledge/architecture/planner]]` + `[[knowledge/subsystems/optimizer]]` —
  the `==>` → `ctid ==>` planner rewrite and the hardcoded 2500-row cost
  estimate.
- `[[knowledge/subsystems/executor]]` — the executor-manager singleton holding
  per-query score/highlight state pushed/popped by executor hooks.
- `[[knowledge/ideologies/cstore_fdw]]` + `[[knowledge/ideologies/pg_duckdb]]` —
  the other two "host a foreign engine through a pluggable PG API" extensions;
  cstore_fdw = FDW-as-storage, pg_duckdb = table-AM-stub + planner-swap,
  ZomboDB = index-AM-as-remote-search. All three bolt on triggers/event-triggers
  to fill a missing lifecycle seam.
- `[[knowledge/idioms/error-handling]]` — synchronous ES failures aborting the
  Postgres transaction.
- `.claude/skills/extension-development/SKILL.md` — `CREATE ACCESS METHOD`
  registration, pgrx hook installation, internal-trigger attachment.

## Sources

Fetched 2026-06-07 (branch `master`):

- `https://api.github.com/repos/zombodb/zombodb/git/trees/master?recursive=1`
  @ 2026-06-07 → HTTP 200 (tree listing).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/README.md`
  @ 2026-06-07 → HTTP 200 (189 lines).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/THINGS-TO-KNOW.md`
  @ 2026-06-07 → HTTP 200 (122 lines).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/zombodb.control`
  @ 2026-06-07 → HTTP 200 (6 lines).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/src/lib.rs`
  @ 2026-06-07 → HTTP 200 (133 lines).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/src/access_method/mod.rs`
  @ 2026-06-07 → HTTP 200 (46 lines).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/src/access_method/scan.rs`
  @ 2026-06-07 → HTTP 200 (138 lines).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/src/access_method/build.rs`
  @ 2026-06-07 → HTTP 200 (311 lines, head read).
- `https://raw.githubusercontent.com/zombodb/zombodb/master/src/executor_manager/hooks.rs`
  @ 2026-06-07 → HTTP 200 (247 lines).

All cites are `[verified-by-code]` against the fetched `.rs`/`.control` (AM
handler shape, scan→ES search, `xs_heaptid`/`xs_recheck` handling, build-time
panics, hook registration) except the MVCC-in-ES, whole-row-storage,
transaction-batching, `==>`→ctid rewrite, hidden-trigger, replica-default, and
selectivity-default narratives, which are `[from-README]` (`THINGS-TO-KNOW.md`),
cross-checked against the matching call sites where present. The Elasticsearch
client (`src/elasticsearch/*`), the query DSL, the `rewriter.rs` and
`triggers.rs` bodies, and the executor-manager bulk-flush internals were not
deep-read; claims about *that* batching/rewrite/triggers happen rest on the
authors' design notes plus the call sites in the fetched files.
