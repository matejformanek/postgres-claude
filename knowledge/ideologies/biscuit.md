# biscuit — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `CrystallineCore/Biscuit` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* index AM's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-23 (see Sources footer).

Biscuit is a `CREATE ACCESS METHOD … TYPE INDEX` AM whose control comment is
`'Bitmap-based index access method for fast pattern matching (LIKE/ILIKE).'`
(`biscuit.control:5`) `[verified-by-code]`. It accelerates `LIKE / ILIKE /
NOT LIKE / NOT ILIKE` on `text` by maintaining, per character (0-255), per
character-*position*, a Roaring bitmap of the record indices that have that
byte at that position. **Headline divergence:** Biscuit is a *disk-resident
index AM that stores almost nothing on disk* — its only persistent page is a
4-field metapage (`biscuit.control` notwithstanding), and the entire bitmap
corpus is rebuilt into a process-local `CacheMemoryContext` heap on first
access, warmed by a registered background worker, and served from a hand-rolled
session-global linked-list cache rather than the buffer manager. The B-tree it
nominally resembles (`amstrategies=4`, `amsupport=2`, `biscuit.c:203-247`) keeps
its tree on disk; Biscuit keeps a single sentinel page and treats the heap as
the source of truth, re-deriving everything in RAM.

## Domain & purpose

Biscuit answers: *how do you make `col LIKE '%abc%'` index-accelerated without a
trigram GIN index?* It indexes each string by character position — a positive
index for offsets from the start (`'abc%'` → query positions 0,1,2) and a
negative index for offsets from the end (`'%xyz'` → query positions -3,-2,-1)
(`docs/source/architecture.md:30-35`) `[from-README]`. A pattern match becomes a
sequence of Roaring `AND`s over per-position character bitmaps plus a
length-`>=` filter; the result bitmap's set bits are record indices, which map
back to heap TIDs via a parallel `tids[]` array (`biscuit_common.h:192`,
`biscuit_pattern.c:769-859`) `[verified-by-code]`. Multi-byte UTF-8 is handled by
indexing *every byte of a character at the same character position*
(`docs/source/architecture.md:20`, `biscuit_index.c:286-315`) `[from-comment]`,
so `'caf_'` matches `'café'` by character position 3, not byte position 3.
Separate case-sensitive and case-insensitive (pre-lowercased) bitmap families
serve LIKE vs ILIKE (`biscuit_common.h:126-142`) `[verified-by-code]`.

## How it hooks into PG

- **Index AM handler.** `biscuit_handler` returns an `IndexAmRoutine`
  (`biscuit.c:197-248`) `[verified-by-code]`. It implements `ambuild`,
  `ambuildempty`, `aminsert`, `ambulkdelete`, `amvacuumcleanup`, `amcanreturn`,
  `amcostestimate`, `amoptions`, `amvalidate`, `amadjustmembers`, and the full
  scan set `ambeginscan / amrescan / amgettuple / amgetbitmap / amendscan`, plus
  the three parallel callbacks `amestimateparallelscan / aminitparallelscan /
  amparallelrescan`. `ammarkpos / amrestrpos / amproperty / ambuildphasename`
  are NULL (`biscuit.c:232-245`) `[verified-by-code]`.
- **Flags.** `amcanorder=false`, `amcanbackward=false`, `amcanreturn`-callback
  present but returns `false` so it is *not* an index-only-scan AM
  (`biscuit.c:207-208,229`, `biscuit_index.c:1599-1605`) `[verified-by-code]`.
  `amcanmulticol=true`, `amoptionalkey=true`, `amcanparallel=true`,
  `amsearchnulls=false`, `amstorage=false`, `ampredlocks=false`,
  `amparallelvacuumoptions=0` (`biscuit.c:209-222`) `[verified-by-code]`.
- **Strategies / support.** Four custom strategy numbers
  (`BISCUIT_LIKE_STRATEGY`=1 … `BISCUIT_NOT_ILIKE_STRATEGY`=4,
  `biscuit_common.h:69-72`) and one support function (`amsupport=2` but only
  `FUNCTION 1` is registered) `[verified-by-code]`.
- **Opclass registration.** `sql/biscuit.sql:120-126` declares
  `CREATE OPERATOR CLASS biscuit_text_ops DEFAULT FOR TYPE text USING biscuit`
  binding `~~ / !~~ / ~~* / !~~*` to strategies 1-4 and `FUNCTION 1
  biscuit_like_support(internal)` `[verified-by-code]`. `biscuit_like_support`
  is a stub that returns `true` (`biscuit.c:254-259`); a SQL-comment FIX note
  records it was wrongly declared `RETURNS bool` before (`sql/biscuit.sql:36-45`)
  `[from-comment]`.
- **`_PG_init`.** Only calls `biscuit_preload_init()` (`biscuit.c:50-54`); no
  GUCs are defined `[verified-by-code]`. `biscuit_preload_init` installs
  `shmem_request_hook` + `shmem_startup_hook` (saving prior pointers) and
  `RegisterBackgroundWorker`s a persistent "biscuit preload worker"
  (`biscuit_preload.c:148-175`) `[verified-by-code]`.
- **WAL.** The metapage write goes through `GenericXLogStart /
  GenericXLogRegisterBuffer(GENERIC_XLOG_FULL_IMAGE) / GenericXLogFinish`
  (`biscuit_index.c:38-50`) `[verified-by-code]` — the *only* WAL Biscuit emits.
- **Shmem / locking.** `RequestAddinShmemSpace(biscuit_preload_shmem_size())` +
  `RequestNamedLWLockTranche("biscuit_preload", 1)` (`biscuit_preload.c:105-106`);
  one LWLock guards a 64-slot OID ring buffer plus per-OID
  `pg_atomic_uint32` state slots (`biscuit_preload.h:47-72`) `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. The index is in memory, not on disk; the buffer manager holds one sentinel page

Core index AMs (nbtree, gin, gist, brin) lay their entire structure out in
8 KB relation pages managed by the buffer manager and WAL-log every change.
Biscuit writes exactly one page — `BISCUIT_METAPAGE_BLKNO` (block 0) — carrying
`{magic, version, root=0, num_records}` (`biscuit_common.h:116-121`,
`biscuit_index.c:41-49`) `[verified-by-code]`. The architecture doc is explicit:
"Bitmaps are **not serialized**. On index load: read metadata marker, scan heap
table, rebuild **all bitmaps** in memory" (`docs/source/architecture.md:923-931`)
`[from-README]`. `biscuit_load_index()` literally re-runs the heap-scanning
`biscuit_build()` to reconstruct everything (`biscuit_index.c:937-955`)
`[verified-by-code]`. So an index "open" after a restart is an O(heap) rebuild,
not a page fetch. `amcostestimate` reflects this fiction by reporting
`numPages = RelationGetNumberOfBlocks(index)` (usually 1) as the index size
(`biscuit_index.c:1614-1648`) `[verified-by-code]`.

### 2. All index state lives in `CacheMemoryContext`, deliberately bypassing `rd_indexcxt`

Every BiscuitIndex is `palloc`'d in `CacheMemoryContext`, not the relation's
`rd_indexcxt`, with an explicit comment that PG calls
`MemoryContextDelete(rd_indexcxt)` inside `RelationClearRelation` on any relcache
invalidation, which "would free all our data while the cache entry still holds
the pointer" (`biscuit_index.c:543-552`, mirrored in
`biscuit_preload.c:282-288`) `[from-comment]`. This is the inverse of the core
contract, where AM-scoped allocations belong in `rd_indexcxt` precisely so they
*are* swept on invalidation. Biscuit instead pins its data in the never-reset
`CacheMemoryContext` and manages eviction itself (see #3). `index->rd_amcache`
is used as the per-relation fast pointer but is treated as untrustworthy — it is
re-fetched from the global cache on every entry because "rd_amcache was cleared
by a relcache invalidation" (`biscuit_index.c:979-994`) `[from-comment]`.

### 3. A bespoke session-global linked-list cache with its own relcache callback

Rather than relying on `rd_amcache` lifecycle, Biscuit keeps a process-global
singly-linked list `biscuit_cache_head` of `{indexoid, BiscuitIndex*}` entries
in `CacheMemoryContext` (`biscuit_cache.c:18-83`) `[verified-by-code]`. It
registers a `CacheRegisterRelcacheCallback` + `on_proc_exit` hook
(`biscuit_cache.c:148-158`) to unlink entries when a relation is dropped or the
backend exits — a hand-rolled parallel to the relcache it is sidestepping.
Crucially, `biscuit_insert` writes the mutated index back into this global cache
*after every tuple* so a subsequent `SELECT` sees in-flight inserts
(`biscuit_index.c:1377`, `biscuit_cache.c:54-69`) `[from-comment]` — the cache,
not any page, is the system of record within a session.

### 4. Lazy skeleton + background-worker warm-up, with an O(n) `strstr` fallback path

`ambeginscan` does *not* build bitmaps. On a cache miss it calls
`biscuit_load_skeleton()` — one heap scan that fills `tids[]` and the raw
`data_cache` (and a pre-lowercased `data_cache_lower`), leaving *all* bitmap
fields NULL — then enqueues the OID via `biscuit_preload_request()` and returns
(`biscuit_scan.c:127-139`, `biscuit_preload.c:271-506`) `[verified-by-code]`.
`amrescan` consults `idx->preload_state`: if `>= BISCUIT_PRELOAD_DONE` it takes
the Roaring fast path; otherwise it runs `biscuit_fallback_scan()`, "a plain
strstr / strcasestr walk of data_cache" that is "correct but slower"
(`biscuit_scan.c:50-66,730-922`) `[from-comment]`. The result set is exact, so
`xs_recheck` is held `false` even on the fallback path
(`biscuit_scan.c:66,937-938`) `[verified-by-code]`. The five preload states form
a small state machine: `NONE / SKELETON / RUNNING / DONE / FAILED`
(`biscuit_preload.h:37-41`) `[verified-by-code]`.

### 5. The background worker does not actually ship bitmaps — it only flips an atomic flag

The natural reading of "preload worker" is wrong here. `biscuit_complete_preload`
(run in the worker) opens the relation for a validity check and then *only*
writes `BISCUIT_PRELOAD_DONE` into the shmem slot — it deliberately does **not**
build any bitmap, because "the worker's address space is separate from every
session, so nothing built here is reachable by foreground backends"
(`biscuit_preload.c:613-652`) `[from-comment]`. The actual bitmap construction
happens *foreground*, in `biscuit_complete_preload_local()`, which each session
runs once over its own already-loaded skeleton when it next observes the DONE
flag (`biscuit_preload.c:673-699`, `biscuit_scan.c:519-554`) `[verified-by-code]`.
The worker is thus a cross-process *signal*, not a data producer — an inversion
of the usual bgworker-as-compute-engine idiom. Worker main is a standard
`SIGTERM=die / SignalHandlerForConfigReload / BackgroundWorkerInitializeConnection
/ WaitLatch(WL_EXIT_ON_PM_DEATH)` loop (`biscuit_preload.c:1132-1227`)
`[verified-by-code]`, but on error it writes `BISCUIT_PRELOAD_FAILED` and the
foreground scan silently keeps using the strstr fallback (`biscuit_scan.c:555-561`)
`[from-comment]`.

### 6. Per-position character bitmaps replace a search tree; matching is bitmap-algebra

There is no comparison-driven descent. `biscuit_match_part_at_pos` walks the
pattern character-by-character, fetches `biscuit_get_pos_bitmap(idx, ch, pos)`
(a binary search over a sorted `PosEntry[]` per character,
`biscuit_pattern.c:24-36`), and `AND`s the position bitmaps together, finishing
with a `length_ge` filter (`biscuit_pattern.c:769-859`) `[verified-by-code]`.
Prefix `'abc%'`, suffix `'%xyz'` (negative-index lookups), exact, and substring
`'%abc%'` (char-cache presence + brute verification) are dispatched as distinct
shapes in `biscuit_query_pattern` (`biscuit_pattern.c:1713-1900`)
`[verified-by-code]`. `NOT LIKE` is computed by *inverting* the match bitmap
against the live non-null set (`length_ge_bitmaps[0]`, which equals the set of
indexed non-null rows) minus tombstones — explicitly so NULL rows are excluded
because "NULL LIKE x is NULL, not TRUE" (`biscuit_scan.c:629-663`)
`[from-comment]`. This is a genuinely different query model from
ordered-key descent; it is closer to an inverted index over (char, position).

### 7. Deletes are O(1) tombstones with slot reuse; VACUUM is bitmap `andnot`, not page reclaim

`aminsert` doubles as the UPDATE path: it scans `tids[]` for a matching
`ht_ctid`, and on a hit removes the old record from every bitmap and rewrites the
slot (`biscuit_index.c:1021-1060`) `[verified-by-code]`. Deletes don't free
anything: `ambulkdelete` adds the record index to a Roaring `tombstones` bitmap,
pushes the slot onto a `free_list` for reuse, and `andnot`s the deleted set out
of every position/char/length bitmap (`biscuit_index.c:1388-1586`)
`[verified-by-code]`. Only when `tombstone_count >= TOMBSTONE_CLEANUP_THRESHOLD`
(1000) does it purge and recreate the tombstone bitmap (`biscuit_index.c:1563-1577`,
`biscuit_common.h:80`) `[verified-by-code]`. `amvacuumcleanup` is a no-op
returning `stats` (`biscuit_index.c:1592-1597`); `stats->num_pages` is hardcoded
to 1 (`biscuit_index.c:1581`) `[verified-by-code]`. There is no free-space map,
no page deletion — the entire VACUUM contract is reinterpreted as bitmap
maintenance over in-memory record indices.

### 8. Parallel scan ships no TIDs through the DSM — every worker re-evaluates deterministically

The parallel design exploits that bitmap evaluation is read-only and
deterministic: every participant computes the *identical* sorted TID array
locally, then a one-time atomic CAS (`pdesc->initialized` 0→1→2) elects an
initializer that range-partitions `[0, total_tids)` into per-participant
`slots[]` keyed by `MyParallelWorkerNumber` (leader=-1→slot 0, worker N→slot
N+1); others spin with `CHECK_FOR_INTERRUPTS` + 1 µs sleep until ready
(`biscuit_tid.h:28-114`, `biscuit_scan.c:1-66,257-272`) `[from-comment]`. The
DSM segment carries only the partition table, not the result — a deliberate
departure from PG's normal shm_toc-keyed data hand-off, justified by the
determinism of the bitmap (`biscuit_tid.h:40-78`) `[from-comment]`. The header
comment frames this as the fix for an N× row-duplication bug where each Gather
participant returned the full set (`biscuit_scan.c:7-33`) `[from-comment]`.

## Notable design decisions (with cites)

- **Roaring is optional at compile time.** `HAVE_ROARING` switches between
  CRoaring and a hand-rolled `uint64_t blocks[]` bitset; the whole AM is written
  against a `biscuit_roaring_*` abstraction (`biscuit_common.h:48-57`,
  `biscuit_bitmap.c:13-89`) `[verified-by-code]`. (Contrast the sibling
  `pg_roaringbitmap` extension, which exposes Roaring as a SQL *type*.)
- **Negative-position index for suffix queries.** Each character is also indexed
  at `-remaining_chars`, enabling `'%xyz'` to query a negative position directly
  rather than reversing strings (`biscuit_index.c:302-309`,
  `docs/source/architecture.md:31`) `[verified-by-code]`.
- **`length_ge_bitmaps[k]` = "rows with char-length ≥ k"** doubles as the
  non-null live-row set and the length filter that ends every positional match
  (`biscuit_index.c:654-690`, `biscuit_pattern.c:843-856`) `[verified-by-code]`.
- **EXPLAIN "Index Searches" counter is incremented by hand** in `amrescan`
  (version-guarded for PG 17 `xs_numIndexSearches` vs PG 18 `instrument->nsearches`)
  because "genam.h does not do so automatically" (`biscuit_scan.c:495-500`)
  `[from-comment]`.
- **`amcostestimate` poisons the cost when there are no index clauses**
  (`1.0e10`) so a bare `SELECT *` falls back to seqscan instead of using Biscuit
  with zero scan keys and returning 0 rows (`biscuit_index.c:1629-1642`)
  `[from-comment]`.
- **`amgetbitmap` chunks `tbm_add_tuples` at 10 000 with `CHECK_FOR_INTERRUPTS`**
  and always passes `recheck=false` (`biscuit_scan.c:951-981`) `[verified-by-code]`.
- **Heavy embedded incident log.** Source comments carry numbered post-mortems
  ("FIX 1 — SELECT → INSERT crash (segfault at 0xfffffffffffffff8)",
  "FIX 5 — multi-column length bitmaps never updated on insert") that document
  real `repalloc(NULL)` and off-by-one (`j <= max_length`) bugs
  (`biscuit_index.c:996-1014,1515-1521`) `[from-comment]` — a window into the
  fragility of maintaining many parallel arrays by hand.
- **`SnapshotAny` heap scan at build/skeleton time** (`biscuit_index.c:600-604`,
  `biscuit_preload.c:381-385`) `[verified-by-code]` — it indexes all heap tuples
  regardless of visibility, relying on the heap recheck for MVCC correctness.

## Links into corpus

- [[access-method-apis]] — the `IndexAmRoutine` callback surface; Biscuit
  implements the full `amgettuple` + `amgetbitmap` + parallel set but reinterprets
  `ambuild` as a full in-memory rebuild and `amvacuumcleanup` as a no-op.
- [[access-nbtree]] / [[btree]] subsystem — the AM Biscuit mimics in its flag
  table (`amstrategies=4`) but inverts on storage: nbtree is page-resident, Biscuit
  is RAM-resident with a 1-page sentinel.
- [[memory-contexts]] — the deliberate `CacheMemoryContext` (not `rd_indexcxt`)
  home for all index data is the load-bearing memory-management divergence.
- [[relcache-build]] / [[cache-invalidation-registration]] — the hand-rolled
  global cache + `CacheRegisterRelcacheCallback` shadows the relcache lifecycle.
- [[wal-page-format]] / [[wal-record-construction]] — Biscuit's sole WAL is one
  `GenericXLog` full-image metapage write; contrast the per-change WAL of core AMs.
- [[background-worker-startup]] — the preload worker follows
  `RegisterBackgroundWorker` + `WaitLatch(WL_EXIT_ON_PM_DEATH)`, but as a *signal
  emitter*, not a compute engine.
- [[locking-overview]] / [[spinlock-discipline]] — one named LWLock tranche over
  the OID ring buffer; per-OID `pg_atomic_uint32` state slots; the parallel-scan
  CAS spin-wait.
- [[parallel-context-and-dsm]] / [[parallel-state-propagation]] — contrast: PG's
  shm_toc data hand-off vs Biscuit's "ship only a partition table, re-evaluate
  the bitmap in every worker" determinism trick.
- [[catalog-conventions]] — opclass / strategy / support registration via
  `CREATE OPERATOR CLASS … USING biscuit` rather than a `pg_opclass.dat` entry.
- [[tidbitmap-build-and-iterate]] — `amgetbitmap` feeds a core `TIDBitmap` via
  `tbm_add_tuples`.
- Sibling ideologies: [[pg_roaringbitmap]] (Roaring as a SQL type vs Biscuit's
  internal use), [[pgroonga]] / [[zombodb]] / [[pg_textsearch]] (FTS-flavored
  index extensions that, unlike Biscuit, persist their structures), [[lantern]]
  / [[pgvector]] (custom index AMs that DO write real on-disk pages — the
  sharpest contrast to Biscuit's rebuild-on-load model).

> Corpus gap: there is no idiom doc for the **"in-memory index AM that treats the
> heap as the source of truth and rebuilds on open"** pattern (the
> `CacheMemoryContext` + lazy-skeleton + bgworker-signal triad here). Biscuit is
> the cleanest specimen in the corpus; worth an
> `idioms/in-memory-index-am-rebuild.md`.
> Corpus gap: no idiom doc for **deterministic-recompute parallel scans** (ship a
> partition table through DSM, not the data) — Biscuit's `BiscuitParallelScanDesc`
> is a distinct alternative to the shm_toc data hand-off documented in
> [[parallel-context-and-dsm]].

## Sources

All fetched 2026-06-23.

- Tree listing: `https://api.github.com/repos/CrystallineCore/Biscuit/git/trees/main?recursive=1` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/README.md` — 200 (741 lines; skimmed)
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/docs/source/architecture.md` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/biscuit.control` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit.c` — 200 (436 lines)
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_index.c` — 200 (1674 lines)
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_index.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_bitmap.c` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_scan.c` — 200 (1001 lines)
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_tid.c` — 200 (647 lines; head + parallel section)
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_tid.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_pattern.c` — 200 (2535 lines; SECTION 1/4 read)
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_pattern.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_cache.c` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_cache.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_common.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_preload.c` — 200 (1227 lines)
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_preload.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_bitmap.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/src/biscuit_scan.h` — 200
- `https://raw.githubusercontent.com/CrystallineCore/Biscuit/main/sql/biscuit.sql` — 200

No 404s encountered — all requested paths resolved against the tree listing; no
substitutions needed.

Skimmed-but-not-fetched: `src/biscuit_utf8.c` / `src/biscuit_utf8.h` (UTF-8
char-length / char-count / tolower helpers, behavior inferred from call sites),
`src/biscuit_pattern.h` (interface only), the `sql/biscuit--2.2.3--2.3.0.sql`
upgrade script, the `tests/*` suite, and the prebuilt `docs/build/html/*` HTML.
