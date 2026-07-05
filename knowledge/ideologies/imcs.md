# imcs — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `knizhnik/imcs` @ branch `master` (Konstantin Knizhnik's "In-Memory
> Columnar Store"). All `file:line` cites point into that repo (not `source/`),
> since this characterizes an *external* extension's divergence from core PG
> idioms. Cites verified 2026-07-04 against the files fetched on that date (see
> Sources). Author is a prolific PG hacker (also `zson`, `imcs`, cited across
> pgsql-hackers), which shows: the code reaches deep into shmem, LWLocks, HTAB,
> and fmgr — and then does two things core PG would never do (OS threads inside a
> backend; its own shmem page allocator + disk pager outside smgr/WAL).

## Domain & purpose

imcs is an **in-memory columnar store + timeseries analytics** extension. A
user registers a normal heap table's columns into the store (via generated
`cs_*` SQL wrappers over the C functions), and each `(database, "table_column")`
pair becomes a *timeseries* — a B-Tree of fixed-size **tiles** (small arrays of
scalar values) living in a private shared-memory segment (`imcs.h:98-105`
`imcs_timeseries_t` = `{root_page, elem_type, elem_size, count}`)
`[verified-by-code]`. Over these timeseries it exposes a very large algebra of
SQL-callable operations — ~180 command codes in `enum imcs_commands`
(`imcs.h:137-318`) `[verified-by-code]` covering grid/vector arithmetic,
aggregates (`sum/avg/var/dev/median`), grouped and windowed aggregates
(`win_group_*`, `window_ema`, `window_atr`), cumulative ops, hash aggregation,
sort/rank/quantile, as-of joins, and calendar extractors. The execution model is
**tile-at-a-time through an iterator pipe** (`imcs_iterator_t`,
`imcs.h:324-344`), not tuple-at-a-time through the executor: each operator is an
`imcs_iterator_h` with `next/reset/prepare/merge` function pointers whose
operands (`opd[0..2]`) form an expression tree the store walks itself
`[verified-by-code]`. It is a member of the "columnar / analytic engine bolted
onto PG" family (`[[hydra-columnar]]`, `[[cstore_fdw]]`, `[[orioledb]]`,
`[[pg_duckdb]]`), but unlike those it is neither a table AM nor an FDW — it is a
sidecar store addressed entirely through C functions, keyed by string ids, with
no MVCC and no WAL.

## How it hooks into PG

- **Loadable module via `_PG_init`** (`imcs.c:1095`), which bails out unless it
  is loaded from `shared_preload_libraries`
  (`!process_shared_preload_libraries_in_progress` → return, `imcs.c:1105`)
  `[verified-by-code]`. So imcs is a preload-only extension, not `LOAD`-able.
- **Shared-memory request**: `imcs_shmem_request` calls
  `RequestAddinShmemSpace(shmem_size*MB)` (default 1 GB) and
  `RequestNamedLWLockTranche("IMCS", 1)` (`imcs.c:1359-1361`)
  `[verified-by-code]`. On PG ≥ 15 it chains `shmem_request_hook`; older PGs do
  the request inside `_PG_init` (`imcs.c:56, 1355`).
- **`shmem_startup_hook`** → `imcs_shmem_startup` (`imcs.c:1315-1316`): under
  `AddinShmemInitLock` it `ShmemInitStruct("imcs", ...)` for the `imcs_state_t`
  control block, grabs its LWLock from the named tranche
  (`GetNamedLWLockTranche("IMCS")`, `imcs.c:1392`), builds two `ShmemInitHash`
  tables (the timeseries hash + the string dictionary), and creates a private
  `AllocSetContextCreate(TopMemoryContext, "IMCS tempory memory", ...)` context
  for per-query iterator pipes (`imcs.c:1384-1410`) `[verified-by-code]`.
- **`ExecutorEnd_hook`** → `imcs_executor_end` and a registered
  `RegisterXactCallback(imcs_trans_callback)` (`imcs.c:1317-1318, 1419`): both
  reset the private memory context (`MemoryContextReset(imcs_mem_ctx)`) and drop
  the store's LWLock at end of statement / transaction (`imcs.c:837-878`)
  `[verified-by-code]`. This is imcs's substitute for palloc's automatic
  per-query cleanup — its iterator arena is torn down on `ExecutorEnd`.
- **~250 `PG_FUNCTION_INFO_V1` entries** (`imcs.c:291-...`) — the `columnar_store_*`
  C entry points, wrapped by the generated `cs_*` SQL functions in the install
  script. Set-returning functions use the classic `SRF_FIRSTCALL_INIT` /
  `SRF_PERCALL_SETUP` / `SRF_RETURN_NEXT` ValuePerCall protocol
  (`imcs.c:3691-3861`) `[verified-by-code]`. There is also a row-level insert
  trigger entry point `columnar_store_insert_trigger` (`imcs.c:4619`) that
  mirrors heap INSERTs into the column store.
- **Install SQL** `imcs--1.1.sql` (declared `DATA = imcs--1.1.sql`, `EXTENSION =
  imcs` in the `Makefile`) `[verified-by-code]` defines a shell `timeseries`
  type, a `cs_elem_type` enum, and a large `cs_create(table, ...)` PL/pgSQL
  generator that emits per-table load/append/search wrappers. Build is
  `MODULE_big = imcs` over PGXS (`Makefile`) with an optional `USE_DISK` →
  `-DIMCS_DISK_SUPPORT` variant that pulls in `disk.o fileio.o`
  `[verified-by-code]`. `imcs.control`: `default_version = '1.1'`, `relocatable =
  true` `[verified-by-code]`.
- **13 `DefineCustom*Variable` GUCs** (`imcs.c:1108-1305`), all `PGC_POSTMASTER`
  for the structural ones: `imcs.shmem_size`, `imcs.n_timeseries`,
  `imcs.dictionary_size`, `imcs.n_threads`, `imcs.page_size`, `imcs.cache_size`,
  `imcs.file_path`, plus behavior toggles (`imcs.use_rle`, `imcs.autoload`,
  `imcs.serializable`, `imcs.project_caching`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. OS worker threads inside a PG backend — the crown-jewel divergence

Core PG is strictly **process-per-backend, no threads in the backend**: shared
state is reached through shmem + LWLocks, and `palloc`/`ereport`/`CHECK_FOR_INTERRUPTS`
are all non-reentrant and assume a single thread of control. imcs ships its own
`pthread`-based threadpool (`threadpool.c`, `-pthread` in `PG_CPPFLAGS`,
`Makefile`) and uses it for **intra-query parallelism over its own column
arrays** `[verified-by-code]`. `imcs_create_thread_pool(n_threads)` spawns N
OS threads (default = number of CPUs, `imcs.n_threads` GUC) each running
`imcs_thread_pool_worker`, coordinated by two semaphores + two mutexes
(`threadpool.c:20-114`) `[verified-by-code]`. `imcs_parallel_execute` fans a
job out via `pool->execute` and blocks the backend's main thread until all
workers signal `finish` (`threadpool.c:40-58`, `imcs.c:1964`)
`[verified-by-code]`.

How it survives the non-reentrancy of the backend — three deliberate mechanisms:

- **It never touches PG catalogs, the executor, or snapshots from worker
  threads.** A worker only walks a *cloned* slice of the iterator tree over
  already-resident tiles: `imcs_clone_tree` gives worker *i* the sub-range
  `[i·interval, (i+1)·interval-1]` of the timeseries and each worker runs
  `clone_iterator->prepare()` independently (`imcs.c:1943-1957`)
  `[verified-by-code]`. Results are combined back on the main thread via
  `merge` under `pool->merge`'s lock (`threadpool.c:83-89`,
  `imcs_merge_job_results` `imcs.c:1932-1942`) `[verified-by-code]`. Parallelism
  is refused entirely for operators that aren't context-free
  (`imcs_parallel_execution_possible_for_operator`, `imcs.c:2007-2035`) — see
  `FLAG_CONTEXT_FREE`, "each element can be calculated independently: such
  timeseries allows concurrent execution" (`imcs.h:110`) `[from-comment]`.
- **`palloc` is made thread-safe by brute force.** `imcs_alloc` wraps
  `MemoryContextAlloc(imcs_mem_ctx, size)` in a global mutex, with the explicit
  comment "imcs_alloc can be concurrently invoked from multiple threads, so as
  far as MemoryContextAlloc is non re[e]ntrant we have to use mutex here"
  (`imcs.c:986-994`) `[verified-by-code]`. `imcs_free` (→ `pfree`) is likewise
  mutex-wrapped (`imcs.c:1010-1015`). So worker threads *do* call into PG's
  allocator — but serialized, and only into imcs's own private AllocSet context,
  never into the executor's per-tuple context.
- **`ereport` is replaced by a thread-local longjmp handler.** A worker cannot
  `ereport(ERROR)` (that longjmps into the backend's `PG_exception_stack`, which
  is main-thread-only and would corrupt across threads). Instead each worker
  installs a per-thread `imcs_error_handler_t` (a `jmp_buf` + errcode + msg) in
  thread-local storage and `setjmp`s it (`imcs_parallel_job`, `imcs.c:1944-1957`)
  `[verified-by-code]`. imcs's own `imcs_ereport` checks TLS: if a handler is
  present it `vsprintf`s the message and `longjmp`s to the *worker's* buffer;
  only if no TLS handler is set (i.e. running on the main thread) does it call
  the real `ereport(ERROR, ...)` (`imcs.c:714-730`) `[verified-by-code]`. After
  the pool drains, the main thread scans `imcs_error_handlers[0..n]` and
  re-raises the first worker error as a genuine `ereport(ERROR, ...)`
  (`imcs.c:1969-1975`) `[verified-by-code]`. This is the careful bit: errors,
  memory, and results all cross the thread boundary through
  imcs-controlled choke points, and PG's own longjmp/palloc machinery is only
  ever exercised on the main thread. Cross-ref `[[knowledge/idioms/error-handling]]`,
  `[[knowledge/idioms/memory-contexts]]`, `[[knowledge/idioms/fmgr]]`. Contrast
  the sanctioned path: `[[knowledge/idioms/parallel-context-and-dsm]]` /
  `[[knowledge/idioms/parallel-worker-coordination]]` — core parallelism uses
  *forked background workers* + DSM, never threads.

### 2. A private shmem page pool + its own disk pager, outside buffer manager / smgr / WAL

The timeseries B-Tree pages are not `shared_buffers` pages and not smgr
relations. In the in-memory build, `imcs_new_page` hands out raw
`ShmemAlloc(imcs_page_size)` blocks off a hand-rolled free-list on
`imcs_state_t.free_pages`, protected by the store's single LWLock
(`imcs.c:1024-1047`) `[verified-by-code]`. With `USE_DISK`, `disk.c` implements
a **full second buffer manager**: a fixed `imcs_cache_size`-entry cache of
`imcs_page_size` pages (all `ShmemAlloc`'d in `imcs_disk_initialize`,
`disk.c:133-157`), an intrusive LRU list, a collision-chained hash table keyed
by page offset, a dirty-page list, and `SpinLockAcquire(&cache->mutex)` around
lookup/eviction (`imcs_load_page` `disk.c:31-115`) `[verified-by-code]`. Pages
are read/written with **`pread`/`pwrite`** against a single flat file at
`imcs.file_path` (`fileio.c:79-100`, `imcs_file_read/write`)
`[verified-by-code]` — not mmap, and not through smgr. Eviction writes the
victim if dirty (`disk.c:87-91`); `imcs_disk_flush` sorts dirty pages by offset
and streams them out (`disk.c:177-196`) `[verified-by-code]`.

Durability model: **none of this is WAL-logged or crash-safe.** There is no
`XLogInsert`, no full-page-image, no redo. The only persistence hook is
`imcs_disk_flush`, called from `imcs_trans_callback` on `XACT_EVENT_COMMIT`
*only if* `imcs.flush_file` is set (`imcs.c:867-869`) `[verified-by-code]` — a
best-effort fsync-less flush of dirty pages, with no torn-page protection and no
recovery. A crash mid-flush leaves the file inconsistent; the in-memory build
loses everything on restart by construction. This is the opposite of
`[[hydra-columnar]]`'s design, which deliberately formats pages so it can ride
core WAL + buffer manager. Cross-ref `[[knowledge/subsystems/storage-buffer]]`,
`[[knowledge/idioms/wal-record-construction]]`, `[[knowledge/idioms/spinlock-discipline]]`.

### 3. Columnar tiles + an iterator pipe instead of heap rows + the executor

A stored column is a B-Tree of `imcs_tile_t` — a union of scalar arrays
(`imcs.h:54-63`) of `imcs_tile_size` elements (default 128, `imcs.c` /
`imcs.h:26`) `[verified-by-code]`. Query operators are `imcs_iterator_t` nodes
carrying `next/reset/prepare/merge` fn-pointers and up to three operands
(`imcs.h:324-344`); `imcs_new_iterator` allocates the iterator, its tile buffer,
and its context as one 16-byte-aligned blob (for SSE) out of the private context
(`imcs.c:1061-1082`, `imcs_alloc_aligned` `imcs.c:1000-1008`)
`[verified-by-code]`. So the whole vectorized engine is built *beside* the
executor: the SQL function receives ids, builds an iterator tree, and drains it,
returning either a scalar (`PG_RETURN_FLOAT8`) or a `timeseries` handle
(`PG_RETURN_POINTER`) or an SRF. Cross-ref `[[cstore_fdw]]`, `[[hydra-columnar]]`,
`[[knowledge/subsystems/executor]]`, `[[knowledge/idioms/tableam-vtable-lifecycle]]`
(the AM contract imcs pointedly does *not* implement).

### 4. Concurrency + "MVCC": one store-wide LWLock, per-backend lock-state, no tuple visibility

There is exactly one heavyweight-ish lock for the entire store:
`imcs_state_t.lock` (the named-tranche LWLock). Readers take it `LW_SHARED`,
any create/mutation upgrades to `LW_EXCLUSIVE`, and a per-backend static
`imcs_lock` remembers the current mode so a statement doesn't re-lock
(`imcs_get_timeseries` `imcs.c:895-905`, `columnar_store_lock` `imcs.c:2166-2175`)
`[verified-by-code]`. The lock is held across the statement and released in
`imcs_executor_end` / `imcs_trans_callback` (`imcs.c:837-878`) — governed by the
`imcs.serializable` GUC, which if true keeps the lock to transaction end.
**Column-store mutations are not MVCC-transactional**: writes update
shmem tiles in place under the exclusive LWLock; there is no per-row xmin/xmax,
no snapshot visibility, and a `ROLLBACK` does *not* undo tile mutations (the
xact callback only releases the lock + resets the temp context; it never
reverts store contents) `[inferred]` from `imcs.c:860-878` + the absence of any
undo/versioning path `[verified-by-code]`. The `(db, id)` → timeseries mapping
is a `ShmemInitHash` HTAB with a custom string hash/match/keycopy (keys
`ShmemAlloc`'d, `imcs.c:735-782`) `[verified-by-code]`, sized `n_timeseries`
(default 10000). A second HTAB is the string→code dictionary for RLE/dictionary
encoding (`imcs.c:818-834`). Cross-ref `[[knowledge/idioms/locking-overview]]`,
`[[knowledge/idioms/lwlock-rank-discipline]]`,
`[[knowledge/data-structures/dynahash-hashctl]]`,
`[[knowledge/idioms/heap-tuple-visibility-mvcc]]` (the model it forgoes).

## Notable design decisions (cited)

- **Its own thread abstraction layer.** `smp.h` defines a portable
  vtable-of-fn-pointers façade — `imcs_thread_t`, `imcs_mutex_t`,
  `imcs_semaphore_t`, `imcs_tls_t`, `imcs_thread_pool_t` (`smp.h:11-57`) — with
  Windows + POSIX backends in `smp.c`. A PG extension shipping its own portable
  threading library is itself the tell. `[verified-by-code]`
- **`setjmp` error unwinding predates and parallels PG's.** `imcs_error_handler_t`
  = `{jmp_buf unwind_buf; int err_code; char err_msg[256]}` (`imcs.h:116-121`)
  is a miniature re-implementation of PG's `PG_TRY`/`elog` stack, but
  thread-local. `[verified-by-code]`
- **Structural GUCs are `PGC_POSTMASTER`.** `imcs.n_threads`, `imcs.page_size`,
  `imcs.shmem_size`, `imcs.cache_size` can only be set at postmaster start
  (`imcs.c:1147-1170`) — consistent with a fixed shmem arena carved at startup.
  `[verified-by-code]`
- **Autoload from the heap on cache miss.** `imcs_get_timeseries(..., create)`
  with `imcs.autoload` will, on a miss, reconstruct the column by reading the
  backing heap table (two-attempt autoload, `palloc`'d table/column-name
  buffers, `imcs.c:913-963`) — the store treats itself as a rebuildable cache of
  the heap, reinforcing that it is not the system of record. `[verified-by-code]`
- **16-byte tile alignment for SSE.** `imcs_alloc_aligned` over-allocates +16 and
  rounds up, and `imcs_tile_t` is `__attribute__((aligned(16)))` (`imcs.h:37-63`,
  `imcs.c:1000-1008`) — vectorization is a first-class goal. `[verified-by-code]`

## Links into corpus

- `[[knowledge/idioms/parallel-context-and-dsm]]` +
  `[[knowledge/idioms/parallel-worker-coordination]]` +
  `[[knowledge/idioms/bgworker-and-parallel]]` — core PG's *sanctioned*
  intra-query parallelism (forked bgworkers + DSM), the exact contrast to imcs's
  OS-thread pool. The single most important cross-reference.
- `[[knowledge/idioms/error-handling]]` — imcs re-implements ereport unwinding
  thread-locally with `setjmp`/`longjmp` to keep worker errors off PG's
  main-thread exception stack.
- `[[knowledge/idioms/memory-contexts]]` (+ `[[knowledge/data-structures/estate]]`,
  `[[knowledge/subsystems/utils-mmgr]]`) — the private `AllocSet` iterator arena,
  mutex-wrapped `MemoryContextAlloc`, and `MemoryContextReset` on `ExecutorEnd`.
- `[[knowledge/subsystems/storage-buffer]]` + `[[knowledge/idioms/wal-record-construction]]`
  + `[[knowledge/idioms/spinlock-discipline]]` — the private page pool + spinlocked
  disk cache that bypasses buffer manager / smgr / WAL, with no crash safety.
- `[[knowledge/idioms/locking-overview]]` + `[[knowledge/idioms/lwlock-rank-discipline]]`
  — the single store-wide named-tranche LWLock and per-backend lock-state cache.
- `[[knowledge/data-structures/dynahash-hashctl]]` — the `ShmemInitHash`
  `(db,id)`→timeseries + string dictionary tables.
- `[[knowledge/idioms/fmgr]]` + `[[knowledge/idioms/spi]]` — the ~250
  `PG_FUNCTION_INFO_V1` entry points + SRF ValuePerCall protocol.
- `[[knowledge/idioms/heap-tuple-visibility-mvcc]]` — the MVCC model imcs forgoes
  (in-place tile mutation, no xmin/xmax, no rollback of store contents).
- Sibling ideology docs: `[[hydra-columnar]]` (columnar-as-table-AM *with* WAL —
  the mature contrast), `[[cstore_fdw]]` (columnar-as-FDW, WAL-less predecessor),
  `[[orioledb]]` (a full alternative storage engine), `[[pg_duckdb]]` /
  `[[timescaledb]]` (other analytic/timeseries engines on PG).

## Sources

Fetched 2026-07-04 from `raw.githubusercontent.com/knizhnik/imcs/master/…`
(the GitHub git/trees API **and** the codeload tarball endpoint were
proxy-blocked this session with HTTP 403 "not enabled for this session", so all
retrieval was via `raw.githubusercontent.com`, which was open):

- Deep-read (all HTTP 200): `imcs.c` (5823 lines — `_PG_init`, shmem/GUC/hook
  wiring, `imcs_ereport`, HTAB init, `imcs_alloc`, parallel job machinery, SRFs,
  lock lifecycle), `imcs.h` (380 — iterators/tiles/timeseries/`enum
  imcs_commands`/error handler), `disk.c` (264 — spinlocked shmem page cache +
  LRU + `pread`/`pwrite` pager), `threadpool.c` (114 — the OS-thread pool),
  `smp.h` (59 — threading vtable façade), `Makefile`, `imcs.control`, `README.md`
  (4 lines).
- Probed (HTTP 200, not deep-read): `fileio.c` (`open`/`pread`/`pwrite` — confirms
  no mmap), `imcs--1.1.sql` (`create type timeseries`, `cs_elem_type` enum,
  `cs_create` PL/pgSQL generator), `smp.c` (424 — POSIX/Windows backends),
  `func.c`, `btree.c`, `imcs.conf`.

Every behavioral claim above carries a `file:line` cite `[verified-by-code]`
except: the "not crash-safe / ROLLBACK does not revert tiles" durability
characterization, marked `[inferred]` from the absence of any WAL/undo path
plus the commit-only best-effort `imcs_disk_flush`; and `[from-comment]` /
`[from-README]` tags where noted inline.
