# pgvector — vector similarity search as a type + two index AMs

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgvector/pgvector` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-03 (see Sources footer).

## Domain & purpose

pgvector adds approximate (and exact) nearest-neighbor search over dense and
sparse float vectors to PostgreSQL. It ships a `vector` data type (plus
`halfvec`, `bit`, `sparsevec` variants) and **two index access methods** —
`hnsw` (a multilayer proximity graph) and `ivfflat` (inverted-file with
k-means centroids) — wired through the standard opclass/strategy machinery so
that `ORDER BY embedding <-> '[3,1,2]' LIMIT k` becomes an index scan
`[from-README]` (`README.md:195-205`, `vector.control:1`). It is the canonical
worked answer to: *can a third-party extension add a brand-new indexable
datatype with first-class index support, entirely outside core?* — and the
answer is yes, by implementing the full `IndexAmRoutine` callback surface
twice.

## How it hooks into PG

pgvector is a **lazy-loaded** extension (no `shared_preload_libraries`
requirement) — everything is reachable through SQL-registered C functions and
the two access methods registered via `CREATE ACCESS METHOD` in the install
script. The control file is minimal and relocatable
(`vector.control:1-4`) `[verified-by-code]`.

| Core mechanism | pgvector use |
|---|---|
| **Type system** (varlena) | `Vector` is a varlena with `int16 dim` + `float x[FLEXIBLE_ARRAY_MEMBER]`; standard `PG_DETOAST_DATUM` getarg macro (`src/vector.h:11-17`, `:7-9`). Max 16 000 dims for the type, but only 2 000 are indexable (`vector.h:4`, `hnsw.h:25`). |
| **Index AM** `IndexAmRoutine` | Two full callback tables. `hnswbuild`/`hnswinsert`/`hnswgettuple`/`hnswbulkdelete`/`hnswvacuumcleanup`/`hnswbeginscan`/`hnswrescan`/`hnswendscan` (`src/hnsw.h:456-469`) and the `ivfflat*` mirror (`src/ivfflat.h:335-348`). |
| **Opclass / support functions** | Distance proc is support function #1 for both AMs; HNSW adds a norm proc (#2) and a type-info proc (#3) (`hnsw.h:29-31`); IVFFlat adds kmeans-distance / kmeans-norm / type-info procs (#3–#5) (`ivfflat.h:36-40`). Each distance operator (`<->` L2, `<#>` inner product, `<=>` cosine, `<+>` L1, plus bit Hamming/Jaccard) is its own opclass (`README.md:212-248`). |
| **Generic WAL** (`access/generic_xlog.h`) | IVFFlat logs page changes through `GenericXLogState` — it `#include "access/generic_xlog.h"` and threads a `GenericXLogState **state` through its page helpers (`ivfflat.h:7`, `:324-329`). |
| **Parallel index build** (`access/parallel.h`, DSM, `shm_toc`) | Both AMs do parallel builds: `HnswParallelBuildMain(dsm_segment *seg, shm_toc *toc)` / `IvfflatParallelBuildMain(...)` are `PGDLLEXPORT` worker entry points launched via a `ParallelContext` (`hnsw.h:453`, `ivfflat.h:332`). |
| **Custom GUCs** | `hnsw.ef_search`, `hnsw.iterative_scan`, `hnsw.max_scan_tuples`, `hnsw.scan_mem_multiplier` (`hnsw.h:121-124`); `ivfflat.probes`, `ivfflat.iterative_scan`, `ivfflat.max_probes` (`ivfflat.h:93-95`). |
| **Custom LWLock tranche** | `hnsw_lock_tranche_id` + `HnswInitLockTranche()` register a named tranche for per-element `LWLock`s (`hnsw.h:125`, `:451`). |
| **reloptions** | `HnswOptions`/`IvfflatOptions` are varlena option structs (`vl_len_` first) parsed by the AM's `amoptions` callback (`hnsw.h:191-196`, `ivfflat.h:121-125`). |

## Where it diverges from core idioms

### 1. HNSW rolls its own page-lock protocol instead of using buffer content locks the core way

HNSW reserves two block numbers as *lock pages* — `HNSW_UPDATE_LOCK = 0` and
`HNSW_SCAN_LOCK = 1`, with a comment that they "must correspond to page
numbers since page lock is used" (`hnsw.h:41-43`). Rather than the
nbtree-style buffer content-lock coupling, HNSW serializes graph insert vs.
scan by locking these sentinel relation pages. This is a deliberate
divergence from `[[knowledge/subsystems/storage-buffer]]` content-lock idiom:
the graph is mutable and concurrent inserts must not corrupt neighbor lists,
so the AM invents a coarse page-as-mutex layer on top of the buffer manager.
Each in-memory `HnswElementData` *also* carries its own `LWLock lock`
(`hnsw.h:163`) for the build phase. Cross-ref `[[knowledge/idioms/locking-overview]]`.

### 2. HNSW does NOT use Generic WAL — IVFFlat does

The split is striking. `ivfflat.h` includes `access/generic_xlog.h` and every
page mutation goes through a `GenericXLogState` (`ivfflat.h:7`, `:324-329`),
so IVFFlat is crash-safe and replicates via the generic-xlog redo path with
no custom rmgr. HNSW's header includes **no** xlog header at all; it manages
durability through direct buffer writes + the sentinel-page locks above and a
metapage `insertPage` pointer (`hnsw.h:324`, `HnswUpdateMetaPage` at `:438`).
This is the single biggest WAL-divergence in the extension and the reason the
README warns that HNSW results can change and that replication semantics
differ between the two AMs. Cross-ref `[[knowledge/architecture/wal]]` —
Generic WAL is exactly the "extension that needs durability without a custom
rmgr" escape hatch, and IVFFlat takes it while HNSW opts out.

### 3. Dual absolute/relative pointers so the same graph code runs in-process and in shared memory

HNSW's most idiom-divergent C trick is `HnswPtrDeclare`, a macro generating a
`union { type *ptr; relptrtype relptr; }` (`hnsw.h:137-146`). Every graph link
(`HnswElementPtr`, `HnswNeighborsPtr`, `DatumPtr`) is accessed through
`HnswPtrAccess(base, hp)` which branches on whether `base == NULL`: if so it's
a normal backend-local pointer; otherwise it's a `relptr` offset resolved
against the DSM segment base (`hnsw.h:104`, `:111-114`). This lets the
*identical* graph-construction code (`HnswFindElementNeighbors`,
`HnswSearchLayer`) run both in a single backend's memory context and inside a
`ParallelContext` DSM segment during a parallel build, where absolute pointers
would be meaningless across processes. Core's `relptr.h` exists precisely for
this, but using it pervasively as the *primary* linkage of a data structure —
with a runtime base-switch on every dereference — is well beyond typical core
usage. Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/idioms/memory-contexts]]`.

### 4. Parallel build state machine with a hand-rolled shared graph + condition variable

`HnswShared` / `IvfflatShared` (`hnsw.h:220-237`, `ivfflat.h:134-156`) are the
DSM-resident coordination blocks: a `slock_t mutex` guards mutable counters
(`nparticipantsdone`, `reltuples`), a `ConditionVariable workersdonecv`
parks the leader until workers finish, and — for HNSW — the entire
`HnswGraph graphData` (with its own `slock_t`, multiple `LWLock`s for entry
point / allocator / flush state) lives *inline* in shared memory
(`hnsw.h:198-218`). The `ParallelTableScanFromHnswShared` macro hangs a
`ParallelTableScanDesc` off the end of the struct via `BUFFERALIGN` pointer
arithmetic (`hnsw.h:239-240`) — the same trailing-struct trick core uses for
parallel heap scans, reused for a custom shared payload. Cross-ref
`[[knowledge/idioms/bgworker-and-parallel]]`, `[[knowledge/subsystems/storage-ipc]]`.

### 5. A custom bump-style allocator behind a function pointer

HNSW build memory goes through an `HnswAllocator` — a struct holding
`void *(*alloc)(Size, void *state)` plus opaque state (`hnsw.h:251-255`,
`HnswAlloc` at `:433`). During an in-memory build it allocates from a
`MemoryContext graphCtx`; during a parallel build the same interface allocates
out of the shared `hnswarea` with `memoryUsed`/`memoryTotal` accounting guarded
by `graph->allocatorLock` (`hnsw.h:210-213`, `:303-311`). This indirection
exists so graph nodes can be placed either in a normal palloc context or in a
fixed DSM arena without changing call sites — a divergence from the usual
"just palloc into CurrentMemoryContext" idiom forced by the shared-memory
build. Cross-ref `[[knowledge/idioms/memory-contexts]]`,
`[[knowledge/subsystems/utils-mmgr]]`.

### 6. Iterative index scans: the AM keeps scanning to compensate for post-index filtering

Approximate indexes have a correctness-adjacent UX problem core indexes don't:
because a `WHERE` filter is applied *after* the index returns its k candidates,
a selective filter can leave fewer than `LIMIT` rows (`README.md:450`). Since
0.8.0 pgvector added **iterative scans** (`hnsw.iterative_scan`,
`ivfflat.iterative_scan` with `off` / `relaxed_order` / `strict_order`,
`hnsw.h:127-132`, `ivfflat.h:97-101`): when the executor asks for more tuples,
the AM transparently visits *more* of the graph/lists up to
`hnsw.max_scan_tuples` or `ivfflat.max_probes`. The scan opaque carries a
`pairingheap *discarded` and a `visited_hash v` to resume correctly without
re-emitting (`hnsw.h:379-388`). This is an AM working around the planner/
executor's filter-after-index ordering — a behavior the README explicitly
documents (`README.md:468-538`). Cross-ref `[[knowledge/architecture/executor]]`,
`[[knowledge/architecture/access-methods]]`.

### 7. Pervasive `PG_VERSION_NUM` compat shims in headers

Unlike core (which targets one version), pgvector's headers are dense with
`#if PG_VERSION_NUM >= NNNNNN` branches: `typedef Pointer Item` for PG19
(`hnsw.h:21-23`), PRNG vs `random()` macro selection at 150000
(`hnsw.h:81-87`, `ivfflat.h:82-90`), `varatt.h` include at 160000
(`ivfflat.h:17-19`), `relptr_offset` backfill below 140005 (`hnsw.h:106-108`),
`FUNCTION_PREFIX`/`PGDLLEXPORT` toggling at 160000 (`vector.h:24-28`). This
multi-version-in-one-tree discipline is an out-of-tree extension reality with
no core analogue — core deletes old-version code paths; an extension must
straddle every supported major at once.

## Notable design decisions (cited)

- **Two index types, opposite tradeoffs, same opclass surface.** HNSW: no
  training step, buildable on an empty table, better speed-recall, more memory
  (`README.md:208`). IVFFlat: k-means training (`PROGRESS_IVFFLAT_PHASE_KMEANS`,
  `ivfflat.h:58`), needs data present first, smaller. Both expose the *same*
  distance operators so the choice is `USING hnsw` vs `USING ivfflat` at
  `CREATE INDEX` time only.
- **simplehash specializations for the visited set.** HNSW instantiates three
  `lib/simplehash.h` templates (`tidhash`, `pointerhash`, `offsethash`) and a
  `visited_hash` union over them (`hnsw.h:362-367`, `:481-519`) — chosen at
  runtime by whether the scan addresses elements by TID, absolute pointer, or
  DSM offset (mirrors the base-switch from divergence #3).
- **Build-progress integration.** Both AMs report `PROGRESS_*_PHASE_*` subphases
  through core's `pg_stat_progress_create_index` machinery (`hnsw.h:66-68`,
  `ivfflat.h:56-60`) — an extension correctly participating in core's progress
  reporting rather than inventing its own.
- **HNSW_HEAPTIDS = 10 for non-HOT updates.** Each element stores up to 10
  heap TIDs so the graph stays "robust against non-HOT updates"
  (`hnsw.h:60-61`, `:151`) — a deliberate denormalization to avoid graph
  surgery on every heap update. Cross-ref `[[knowledge/architecture/mvcc]]`
  (HOT) and `[[knowledge/subsystems/access-heap]]`.
- **Page identification magic.** Each AM stamps `page_id` (`HNSW_PAGE_ID
  0xFF90`, `IVFFLAT_PAGE_ID 0xFF84`) into the page opaque (`hnsw.h:36`,
  `:333`, `ivfflat.h:44`, `:246`) plus a metapage `magicNumber` — so a corrupt
  or mismatched page is detectable, the same defensive idiom core AMs use.

## Links into corpus

- `[[knowledge/architecture/access-methods]]` + `[[knowledge/subsystems/access-nbtree]]`
  — the `IndexAmRoutine` callback contract pgvector implements twice; nbtree is
  the reference AM to contrast HNSW's graph against a balanced tree.
- `[[knowledge/architecture/wal]]` — Generic WAL as the extension durability
  escape hatch (IVFFlat takes it, HNSW does not).
- `[[knowledge/idioms/bgworker-and-parallel]]` + `[[knowledge/subsystems/storage-ipc]]`
  — `ParallelContext` + DSM + `shm_toc` parallel builds; the trailing
  `ParallelTableScanDesc` trick.
- `[[knowledge/idioms/locking-overview]]` + `[[knowledge/subsystems/storage-lmgr]]`
  — HNSW's sentinel-page locks + per-element LWLocks + custom tranche.
- `[[knowledge/subsystems/storage-buffer]]` — buffer manager the AMs build their
  page protocols on.
- `[[knowledge/idioms/memory-contexts]]` + `[[knowledge/subsystems/utils-mmgr]]`
  — the `HnswAllocator` function-pointer indirection over palloc vs DSM arena.
- `[[knowledge/idioms/catalog-conventions]]` — opclass / support-function /
  strategy-number registration the install script performs (`CREATE OPERATOR
  CLASS`).
- `[[knowledge/architecture/mvcc]]` + `[[knowledge/subsystems/access-heap]]` —
  HOT / non-HOT update handling behind `HNSW_HEAPTIDS`.
- `.claude/skills/access-method-apis/SKILL.md` — the index-AM callback surface;
  pgvector is a complete worked example of a non-tree, non-heap index AM.
- `.claude/skills/extension-development/SKILL.md` — `CREATE ACCESS METHOD`,
  reloptions, custom-GUC, lazy-load patterns.

## Sources

Fetched 2026-06-03 (branch `master`):

- `https://raw.githubusercontent.com/pgvector/pgvector/master/README.md`
  @ 2026-06-03T23:05Z → HTTP 200 (1351 lines).
- `https://raw.githubusercontent.com/pgvector/pgvector/master/src/vector.h`
  @ 2026-06-03T23:05Z → HTTP 200 (30 lines).
- `https://raw.githubusercontent.com/pgvector/pgvector/master/src/hnsw.h`
  @ 2026-06-03T23:05Z → HTTP 200 (521 lines).
- `https://raw.githubusercontent.com/pgvector/pgvector/master/src/ivfflat.h`
  @ 2026-06-03T23:05Z → HTTP 200 (350 lines).
- `https://raw.githubusercontent.com/pgvector/pgvector/master/vector.control`
  @ 2026-06-03T23:05Z → HTTP 200 (4 lines).
- Tree listing
  `https://api.github.com/repos/pgvector/pgvector/git/trees/master?recursive=1`
  @ 2026-06-03T23:05Z → HTTP 200.

All manifest files fetched successfully — no gaps. Header struct/macro cites
are `[verified-by-code]` against the fetched `.h` files; design-narrative and
SQL-surface cites are `[from-README]` (the project's own documentation, not
independently re-verified against the `.c` sources, which were not in the
manifest). The `.c` implementation files (`hnswbuild.c`, `hnswscan.c`,
`ivfbuild.c`, etc.) were listed in the tree but not fetched; claims about
runtime control flow are therefore inferred from the header declarations +
README and tagged accordingly where they go beyond a struct/signature.
</content>
