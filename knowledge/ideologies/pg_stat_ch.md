# pg_stat_ch — ideology / divergence notes

Extension: **ClickHouse/pg_stat_ch** (`main`, control `default_version = '0.3'`,
`relocatable = false`, `module_pathname = '$libdir/pg_stat_ch'`,
`comment = 'Query telemetry exporter to ClickHouse'`)
`[verified-by-code: pg_stat_ch.control:1-4]`. `META.json` reports the packaged
release as `0.3.11` (`META.json:33,52`) `[verified-by-code]`. It is a
per-query **telemetry exporter**: PostgreSQL hooks capture a raw event per
executed statement (timing, rows, buffers, WAL, JIT, parallel-worker counts,
CPU-time, SQLSTATE), push it into a fixed shared-memory MPSC ring buffer, and a
background worker drains the ring, builds Arrow record-batches, and ships them
to ClickHouse over the native protocol — *aggregation happens in ClickHouse, not
in PG* (`README.md:10,57-67`) `[from-README]`. It is, explicitly, the **inverse
of pg_stat_statements**: "Unlike pg_stat_statements which aggregates statistics
in PostgreSQL, pg_stat_ch exports **raw events** to ClickHouse where aggregation
happens" (`README.md:10`) `[from-README]`.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites below point into the fetched repo files — `pg_stat_ch.control`,
> `CMakeLists.txt`, `README.md`, `META.json`, `src/pg_stat_ch.c` (main entry),
> `src/config/guc.c`, `src/hooks/hooks.c`, `src/queue/shmem.c`,
> `src/queue/event.h`, `src/queue/query_intern.h`, `src/worker/bgworker.c`,
> `src/export/exporter_interface.h`, `src/export/arrow_batch.cc`,
> `src/export/stats_exporter.cc`, and the small headers `pg_stat_ch.h` /
> `config/guc.h` / `export/arrow_batch.h` — **not** `source/`. Cites verified
> against files fetched 2026-07-15 (see Sources footer). Cluster framing: this
> is the **pg_stat_statements-adjacent observability** cluster —
> `[[pg_stat_monitor]]`, `[[pgsentinel]]`, `[[pg_stat_kcache]]`,
> `[[pg_wait_sampling]]`, `[[pg_tracing]]`, `[[sql_firewall]]` — but pg_stat_ch
> is the member that *ships events off-box* rather than folding them into a PG
> shmem hash. Its egress sibling is `[[pg_net]]` (bgworker doing async network
> I/O) and the ClickHouse-integration cluster `[[pg_clickhouse]]` /
> `[[clickhouse_fdw]]`; its Arrow sibling is `[[pg_parquet]]`. `[[pg_turret]]`
> (produced this same run) is the log-export counterpart to this metric-export
> design.

## Domain & purpose

pg_stat_ch answers *"what did every individual query execution look like, at
raw event granularity, queryable with a real OLAP engine?"* — percentiles,
per-app drill-downs, and time-series are computed by ClickHouse over an
`events_raw` table plus materialized views, not by the extension
(`README.md:76,200-214`) `[from-README]`. The four stated design principles are
the whole ideology: **zero network I/O on the query path** (events are queued in
shmem, never sent synchronously), **raw events not aggregates**, **bounded
memory** (fixed ring + overflow counters; drops never block queries), and
**minimal overhead** (~5μs p99 per captured statement) (`README.md:63-68`)
`[from-README]`. PostgreSQL 16/17/18 are supported, with unconditional struct
fields zeroed on older versions (`README.md:89-91`, `event.h:88-92`)
`[verified-by-code]`.

## How it hooks into PG

Requires `shared_preload_libraries`: `_PG_init` warns and returns early unless
`process_shared_preload_libraries_in_progress` (`pg_stat_ch.c:26-29`)
`[verified-by-code]`. `_PG_init` does four things in order —
`PschInitGuc()`, `PschInstallShmemHooks()`, `PschInstallHooks()`,
`PschRegisterBgworker()` (`pg_stat_ch.c:34-43`) `[verified-by-code]`.

- **Seven hooks installed, prior pointer saved for chaining**
  (`hooks.c:898-926`) `[verified-by-code]`: `post_parse_analyze_hook`,
  `ExecutorStart_hook`, `ExecutorRun_hook`, `ExecutorFinish_hook`,
  `ExecutorEnd_hook`, `ProcessUtility_hook`, plus **`emit_log_hook`** — the
  same eight-minus-planner shape `[[pg_stat_monitor]]` uses. `EnableQueryId()`
  is called (PG14+) so core jumbling is always on (`hooks.c:899-901`)
  `[verified-by-code]`.
- **Two shmem hooks** installed separately (`shmem.c:278-288`): the PG15+
  `shmem_request_hook` (falls back to a direct `RequestSharedResources()` on
  <15) and `shmem_startup_hook` (`shmem.c:279-287`) `[verified-by-code]`.
- **Shmem request.** `RequestSharedResources` calls
  `RequestAddinShmemSpace(PschShmemSize())` and
  `RequestNamedLWLockTranche("pg_stat_ch", 1 + PschQueryInternLockCount())` —
  **one main queue lock plus N interner-partition locks in a single tranche**
  (`shmem.c:181-187`) `[verified-by-code]`.
- **Shmem startup.** `PschShmemStartupHook` carves ONE
  `ShmemInitStruct("pg_stat_ch", …)` contiguous block laid out
  `[PschSharedState][PschRingEntry × capacity][DSA area]`
  (`shmem.c:165-173,248-249`), then initializes the DSA in place
  (`PschDsaInit`, `shmem.c:224-228`) and a separately-named partitioned HTAB for
  the query-text interner (`PschQueryInternShmemInit`, `shmem.c:261-263`)
  `[verified-by-code]`.
- **GUCs.** 27 `DefineCustom*Variable` calls in `PschInitGuc`
  (`guc.c:83-406`), closed with the legacy `EmitWarningsOnPlaceholders("pg_stat_ch")`
  (`guc.c:406`) rather than `MarkGUCPrefixReserved` `[verified-by-code]`. All
  ClickHouse-connection knobs are `PGC_POSTMASTER` (restart-only), while
  `enabled`, `flush_interval_ms`, `batch_max`, and the Arrow/OTel budgets are
  `PGC_SIGHUP`, and the sampling / min-duration / log-level knobs are `PGC_SUSET`
  (`guc.c:91,101,226,237,309,322,346`) `[verified-by-code]`. `queue_capacity`
  carries a check-hook enforcing **power-of-two** (`check_psch_queue_capacity`,
  `guc.c:63-80`) so the ring can mask instead of divide `[verified-by-code]`.
- **Background worker.** `PschRegisterBgworker` fills a `BackgroundWorker` with
  `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`,
  `bgw_start_time = BgWorkerStart_ConsistentState`, `bgw_restart_time = 10`
  (10s crash restart), `bgw_function_name = "PschBgworkerMain"`, and
  `RegisterBackgroundWorker` (static, at preload time) (`bgworker.c:249-264`)
  `[verified-by-code]`. The worker `BackgroundWorkerInitializeConnection("postgres", …)`,
  stores its PID in shmem for `pg_stat_ch_flush()` signalling, eagerly attaches
  the DSA, and loops `RunExportCycle` forever (`bgworker.c:187-228`)
  `[verified-by-code]`.

## Where it diverges from core idioms

### 1. Raw events out, not aggregates in — the inverse of pg_stat_statements

The headline. Core pgss (and `[[pg_stat_monitor]]`, `[[pgsentinel]]`) fold every
execution into a shared hash keyed on `(userid,dbid,queryid,…)` and keep running
counters. pg_stat_ch keeps **no aggregate at all**: `PschExecutorEnd` builds one
`PschEvent` per top-level execution and `PschEnqueueEvent`s it
(`hooks.c:620-622`), and the bgworker ships those events verbatim to ClickHouse
(`stats_exporter.cc:288-351`) `[verified-by-code]`. The extension's only durable
PG-side state is a handful of atomic counters (`enqueued`/`dropped`/`exported`/
`send_failures`) surfaced by `pg_stat_ch_stats()` (`pg_stat_ch.c:67-145`,
`shmem.c:470-511`) `[verified-by-code]`. Percentiles and top-N are ClickHouse's
job (`README.md:65,200-214`) `[from-README]`. The `PschEvent` struct is a wide
fixed record (~4.5KB) carrying the whole telemetry surface —
buffers/IO-timing/WAL/CPU/JIT/parallel-workers/SQLSTATE — as flat columns
(`event.h:93-171`) `[verified-by-code]`, deliberately isomorphic to a ClickHouse
row.

### 2. Network egress from a bgworker to an external OLAP system

Unlike every in-shmem observability sibling, the terminal sink is **off-box**.
The bgworker owns a `StatsExporter` that opens a ClickHouse native-protocol
connection (TLS optional) and `CommitBatch`es rows, or ships Arrow IPC buffers
via `SendArrowBatch` (`stats_exporter.cc:406-487`, `exporter_interface.h:84-98`)
`[verified-by-code]`. This is the `[[pg_net]]` shape (a worker doing the network
I/O the foreground must never do) but for a columnar analytics target. Failure
is first-class: `PschExportBatch` records `send_failures` + `last_error_text`,
`RunExportCycle` applies **exponential backoff** (`kBaseDelayMs`=1s doubling to
`kMaxDelayMs`=60s over ≤10 failures) (`stats_exporter.cc:32-34,502-520`,
`bgworker.c:159-168`), and ClickHouse being down "doesn't block PostgreSQL"
(`README.md:87`) `[verified-by-code]`/`[from-README]`. Socket timeouts (30s) in
the exporter bound how long a barrier signal can be stalled behind network I/O
(`bgworker.c:170-177`) `[from-comment]`.

### 3. Bounded MPSC ring with overflow-drop — never an LWLock-held hash insert on the query path

Core pgss takes an exclusive tranche LWLock to insert a new hash entry on the
storing backend. pg_stat_ch instead enqueues into a lock-free-fast-path ring:
`PschEnqueueEvent` reads `head`/`tail` atomics with a read barrier and, **if
full, drops the event with pure atomics — no lock acquired** (`shmem.c:328-336`)
`[verified-by-code]`. If not full it takes the queue lock *non-blocking*
(`LWLockConditionalAcquire`); on contention it does **not** wait — it buffers the
event in a per-backend local batch flushed at transaction end
(`PschLocalBatchAdd`, `shmem.c:339-358`) `[verified-by-code]`. Overflow is
`HandleOverflow`: bump `dropped`, and warn exactly once via a
`pg_atomic_test_set_flag(overflow_logged)` guard to avoid log spam — explicitly
the `[[pg_stat_monitor]]` pattern (`shmem.c:76-85`) `[verified-by-code]`/`[from-comment]`.
The consumer (`PschDequeueEvent`) is **fully lock-free** — single consumer,
atomics + `pg_read_barrier`/`pg_write_barrier`, "pattern from shm_mq.c"
(`shmem.c:402-459`) `[verified-by-code]`/`[from-comment]`. `head`/`tail` are
`uint64` so wraparound is a non-issue (~584 years at 1M/s) (`shmem.c:419-421`)
`[from-comment]`. This is a *telemetry-is-best-effort* stance: correctness of the
user's query is never traded for a captured event.

### 4. C plugin / C++ exporter split, enforced by a CMake GLOB guard

The single most distinctive build-policy divergence. The PG-facing plugin layer
is **pure C** (`src/*.c`); the exporter is **C++** confined to `src/export/*.cc`
(`CMakeLists.txt:37-44`). CMake then actively *rejects* any C++ that fell outside
that one legitimate glob: it globs `src/*.cc|*.cxx|*.cpp|*.c++`, filters out the
allowed `src/export/*.cc`, and `message(FATAL_ERROR …)` on anything left
(`CMakeLists.txt:49-59`) `[verified-by-code]`. The stated reason: keeping the
PG↔extension boundary in pure C "is what prevents an uncaught C++ throw from
unwinding across PG's longjmp frames" (`CMakeLists.txt:37-42`) `[from-comment]`.
Defense in depth: Clang builds compile the exporter with
`-Werror=global-constructors` to forbid namespace-scope objects needing
load-time/exit-time ctors/dtors that would run outside PG's lifecycle
(`CMakeLists.txt:79-83`) `[verified-by-code]`/`[from-comment]`, and the link
hides ~45k static-archive symbols (grpc/Arrow/protobuf) with
`--exclude-libs,ALL` so a `RTLD_GLOBAL` dlopen can't interpose them across other
backends/extensions (`CMakeLists.txt:117-123`) `[verified-by-code]`/`[from-comment]`.

### 5. Memory-context boundary: Arrow/C++ allocations live outside PG MemoryContexts, guarded by exception barriers

Because the exporter allocates with `::operator new` / Arrow / protobuf / ZSTD —
heap memory PG's `MemoryContext` machinery does not track and `longjmp` will not
reclaim — the C++/C seam is a wall of explicit barriers. Every `extern "C"`
entry point (`PschExporterInit`, `PschExportBatch`, `PschExporterShutdown`, …)
wraps its body in `try { … } catch (std::bad_alloc / std::exception / …)` and
converts the throw to `ereport(WARNING)`/`RecordExporterFailure` instead of
letting it cross a PG frame (`stats_exporter.cc:406-487,522-543`)
`[verified-by-code]`. A process-wide `std::set_terminate(PschTerminateHandler)`
is installed as the last-resort backstop: an escaped exception becomes
`ereport(FATAL)` → clean `proc_exit(1)` → postmaster respawns just the bgworker,
*instead of* `std::terminate`→`SIGABRT`→DB-wide crash recovery
(`stats_exporter.cc:55,71-86,410`) `[verified-by-code]`/`[from-comment]`. The
inverse hazard — a PG `longjmp` skipping C++ destructors and leaking heap — is
called out as an explicit invariant: RAII objects (`ArrowBatchBuilder`,
`std::vector<PschEvent>`) must not be live across any PG call that can longjmp
(`stats_exporter.cc:195-208,463-475`) `[from-comment]`. `arrow_batch.cc` itself
opens with `extern "C" { #include "postgres.h" }` to pull PG's C headers into a
C++ translation unit (`arrow_batch.cc:1-3`) `[verified-by-code]`.

### 6. Parse-time normalization cached per-backend, decoupled from the executor event

pg_stat_ch reuses core query-jumbling but does **not** re-implement the jumbler
(contrast `[[sql_firewall]]` / `[[pg_tracing]]` which vendor pgss's walker). It
decides query text at `post_parse_analyze_hook` time — the only place the
`JumbleState` constant-locations exist — and stashes the exported text in a
**per-backend LRU cache** keyed by `queryId` (`PschRememberNormalizedQuery`,
`hooks.c:423-464`) `[verified-by-code]`. Constant-bearing statements are
normalized (`PschNormalizeQuery`), constant-free ones stored verbatim, and at
`ExecutorEnd` the event pulls text back out by `queryId`
(`PschLookupNormalizedQuery`, `hooks.c:322-325,450-457`) `[verified-by-code]`.
On a cache miss the event ships with **empty** query text rather than falling
back to raw SQL — a deliberate no-leak-of-literals choice (`hooks.c:315-325`)
`[from-comment]`. The cache size is a GUC (`normalize_cache_max`, default 32768,
`guc.c:324-334`) `[verified-by-code]`.

### 7. A shared refcounted query-text interner in DSA — not pgss's on-disk text file

Where core pgss spills query text to an external on-disk file and
`[[pg_stat_monitor]]` uses a per-entry DSA pointer, pg_stat_ch **de-duplicates**
query bodies across queued events. Each distinct `(dbid, queryid, query_hash,
query_len)` maps to one DSA-allocated object with a refcount tracked in a
32-partition `HASH_PARTITION` HTAB; ring slots store only a `dsa_pointer`
(`query_intern.h:1-23,38-40,69`) `[verified-by-code]`/`[from-comment]`. Rationale:
without interning, live DSA footprint is `queued_events × query_len`, which
"exhausts the bounded DSA pool well before the queue fills"
(`query_intern.h:5-12`) `[from-comment]`. `TryEnqueueLocked` interns on enqueue
(`PschQueryInternAcquire`, `shmem.c:128-138`); `PschDequeueEvent` resolves and
drops a reference on dequeue (`PschQueryInternResolveAndRelease`,
`shmem.c:451-452`) `[verified-by-code]`. A hash collision against different text
is treated as a miss (empty query text preferred over wrong SQL)
(`query_intern.h:60-65`) `[from-comment]`.

### 8. Sampling and duration-thresholding on the capture path

Core pgss records everything. pg_stat_ch has a two-stage capture filter:
`ShouldSampleEvent` always captures queries ≥ `min_duration_us`, and randomly
samples sub-threshold queries at `sample_rate` via `pg_prng_double`
(`hooks.c:224-238`, GUCs `guc.c:312-346`) `[verified-by-code]`. Transaction-control
utility statements (BEGIN/COMMIT/ROLLBACK/SAVEPOINT) and PREPARE/EXECUTE/DEALLOCATE
are skipped outright — no telemetry value and they'd burn "2 of 7 events per
pgbench TPC-B transaction" of queue capacity (`ShouldTrackUtility`,
`hooks.c:672-689`) `[verified-by-code]`/`[from-comment]`.

## Notable design decisions (with cites)

- **Fixed-size event, DSA only for the two long strings.** `PschEvent` is a
  fixed record; the ring stores a compact `PschRingEntry` whose fixed prefix is
  block-copied with one `memcpy(kFixedPrefixSize = offsetof(PschRingEntry,
  err_message_dsa))`, with query text + err_message held by `dsa_pointer`
  (`shmem.c:87-91,113-141`, `event.h:167-171`) `[verified-by-code]`. The header
  even documents the trade vs pg_stat_monitor's full-DSA approach explicitly
  (`event.h:3-22`) `[from-comment]`.
- **On DSA OOM the event still enqueues, numeric data intact — only the string
  is dropped** (`shmem.c:118-141`), and `dsa_oom_count` is surfaced in stats
  (`shmem.c:493`, `pg_stat_ch.c:140`) `[verified-by-code]`.
- **emit_log_hook recursion guard.** Error capture runs inside `errfinish`; a
  throw during capture would re-enter the hook and recurse to PANIC. A
  `disable_error_capture` guard bounds recursion at one level and a `PG_CATCH`
  restores the guard + `FlushErrorState` (`hooks.c:790-887`). `PschEnqueueEvent`
  also holds the guard because `HandleOverflow`'s `ereport(WARNING)` would
  re-enter the hook and deadlock on the queue lock (`shmem.c:317-322`)
  `[verified-by-code]`/`[from-comment]`.
- **SIGUSR1 must stay PostgreSQL's.** The worker uses
  `procsignal_sigusr1_handler` for SIGUSR1 (barriers — a prior custom handler
  hung `DROP DATABASE`) and takes **SIGUSR2** for its own immediate-flush signal
  (`bgworker.c:2-22,54-80`) `[verified-by-code]`/`[from-comment]`. Barriers are
  processed before interrupts in the drain loop (`bgworker.c:102-111`).
- **`pg_stat_ch_flush()` signals the worker by PID**, with a stale-PID
  compare-exchange reset if `kill` returns `ESRCH` (`bgworker.c:233-247`,
  `pg_stat_ch.c:158-163`) `[verified-by-code]`.
- **`mallopt(M_ARENA_MAX, 4)`** is set before any gRPC/Arrow thread spawns, to
  cap glibc malloc arenas / virtual-memory bloat (`bgworker.c:187-193`)
  `[verified-by-code]`/`[from-comment]`.
- **Cardinality-typed exporter interface.** `StatsExporter` declares columns as
  `StatLC*` (low-cardinality → ClickHouse `LowCardinality` / Arrow dictionary /
  OTel metric dimension) vs `StatHC*` (high-cardinality → plain / log-attribute
  only), so one column model drives three backends (ClickHouse, Arrow-IPC, OTel)
  (`exporter_interface.h:24-98`) `[verified-by-code]`/`[from-comment]`.
- **Arrow batch is dictionary-encoded + ZSTD-compressed IPC.** `ArrowBatchBuilder`
  builds a 57-column RecordBatch (low-cardinality dims as `StringDictionary32`,
  timestamps as `NANO`/UTC), writes a ZSTD-compressed IPC stream, and estimates
  bytes for a soft flush budget (`arrow_batch.cc:143-208,213-270,536-581`)
  `[verified-by-code]`. Timestamps are offset from PG epoch to Unix epoch
  (`kPostgresEpochOffsetUs`, `arrow_batch.cc:36,276-278`) `[verified-by-code]`.
- **Version compat by inline `#if PG_VERSION_NUM`** throughout (16→18, with
  14/15/17/18/19 guards): the `ExecutorRun`/`ProcessUtility` signatures, the
  PG17 IO-timing field split, PG15 JIT + temp-blk timing, PG18 parallel-worker
  counts, and PG19 `INSTR_TIME_GET_MICROSEC` are all inline ifdefs
  (`hooks.c:254-268,355-388,507-526,651-670`) `[verified-by-code]`.
- **Session-stable value cache.** Client IP / datname / username are resolved
  once per backend (username re-resolved on `SET ROLE`), explicitly "following
  pg_stat_monitor's pattern" (`hooks.c:72-142`) `[verified-by-code]`/`[from-comment]`.
- **Dual sink.** A `use_otel` GUC switches the exporter to OpenTelemetry
  (OTLP/gRPC) instead of ClickHouse, optionally passing Arrow IPC as opaque
  OTLP LogRecord bodies (`guc.c:95-103,348-357`, `stats_exporter.cc:413-417`)
  `[verified-by-code]`.

## Links into corpus

- `[[pg_stat_monitor]]` — the most-cited sibling: pg_stat_ch borrows its
  session-value cache (`hooks.c:72-73`), the once-only overflow-warn flag
  (`shmem.c:79`), and contrasts its full-DSA query-text model (`event.h:19-22`).
  Both take the `emit_log_hook`; both save-prior-pointer chain the executor
  hooks.
- `[[pg_net]]` — the egress sibling: a bgworker doing the async network I/O the
  foreground path must never do; pg_stat_ch's ClickHouse exporter + backoff loop
  (`bgworker.c:159-185`) is the telemetry analogue.
- `[[pg_stat_statements]]` — the direct foil: pg_stat_ch inverts its
  aggregate-in-shmem model into raw-events-out (`README.md:10`); it reuses core
  jumbling (`EnableQueryId`, `hooks.c:900`) without forking the walker.
- `[[pg_tracing]]` / `[[sql_firewall]]` — the query-jumble-copy siblings;
  pg_stat_ch is the counter-example that reuses core jumbling rather than
  vendoring `fill_in_constant_lengths`.
- `[[pg_parquet]]` — Arrow sibling: both marshal PG rows into Arrow, but
  pg_stat_ch streams dictionary-encoded ZSTD IPC to a network sink
  (`arrow_batch.cc:536-581`) rather than writing Parquet files.
- `[[pg_clickhouse]]` / `[[clickhouse_fdw]]` — the ClickHouse-integration
  cluster; pg_stat_ch pushes telemetry *to* ClickHouse via the native protocol,
  the inverse of an FDW pulling data *from* it.
- `[[pgsentinel]]` / `[[pg_stat_kcache]]` / `[[pg_wait_sampling]]` — the
  shmem-sampler observability siblings that keep their aggregate in PG.
- `[[pg_turret]]` — produced this same run; the log-export counterpart to this
  metric/telemetry-export design (both are ClickHouse-adjacent bgworker
  exporters).
- `[[bgworker-and-parallel]]` / `[[process-utility-hook-chain]]` /
  `[[guc-variables]]` / `[[memory-contexts]]` / `[[locking-overview]]` — the
  core idioms this leans on: `RegisterBackgroundWorker` (`bgworker.c:249-264`),
  the seven-hook chain (`hooks.c:898-926`), 27 GUCs (`guc.c:83-406`), the
  cross-lifetime C++-heap boundary (`stats_exporter.cc:55,195-208`), and the
  single named LWLock tranche + partitioned interner HTAB (`shmem.c:181-187`).

> Corpus gap: there is no `idioms/telemetry-egress-bgworker.md` capturing the
> *ship raw events off-box from a background worker* pattern (fixed shmem ring +
> overflow-drop + backoff + external sink). pg_stat_ch and `[[pg_turret]]` are
> the canonical instances; `[[pg_net]]` is the general-purpose primitive.
> Corpus gap: no `idioms/c-plugin-cpp-exporter-boundary.md` for the
> pure-C-plugin / C++-exporter split enforced by build policy plus
> `set_terminate` + per-entry `try/catch` barriers + longjmp-vs-destructor
> invariants (`CMakeLists.txt:37-59`, `stats_exporter.cc:71-86,195-208`). This
> is a distinct hazard family from the usual pure-C extension.

## Sources

All fetched 2026-07-15 (branch `main`) via `raw.githubusercontent.com`. The
header/source layout was discovered from `src/pg_stat_ch.c`'s includes
(`config/`, `hooks/`, `queue/`, `worker/`, `export/` subdirs under both `src/`
and `include/`); the flat-name probes (`src/hooks.c`, `src/shmem.c`,
`src/bgworker.c`, `src/guc.c`, `include/*.h`) all 404'd before the subdir layout
was found.

- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/pg_stat_ch.control` — 200 (4 lines)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/CMakeLists.txt` — 200 (149 lines; the GLOB guard + link policy)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/README.md` — 200 (238 lines; design principles + GUC table)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/Makefile` — 200 (fetched; PGXS/META shim, not cited in body)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/META.json` — 200 (53 lines; version 0.3.11, maintainers)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/pg_stat_ch.c` — 200 (163 lines; `_PG_init`, SQL funcs)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/config/guc.c` — 200 (407 lines; 27 GUCs)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/hooks/hooks.c` — 200 (926 lines; deep-read — 7-hook chain, event build, emit_log recursion guard, sampling)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/queue/shmem.c` — 200 (580 lines; deep-read — MPSC ring, overflow-drop, DSA layout, interner call sites)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/queue/event.h` — 200 (180 lines; `PschEvent` struct)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/queue/query_intern.h` — 200 (91 lines; refcounted DSA interner)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/queue/psch_dsa.h` — 200 (132 lines; fetched, DSA API — not deep-cited)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/worker/bgworker.c` — 200 (264 lines; deep-read — bgworker lifecycle, signals, backoff, flush)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/export/exporter_interface.h` — 200 (124 lines; cardinality-typed C++ column interface)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/export/arrow_batch.cc` — 200 (705 lines; deep-read — 57-col Arrow RecordBatch + ZSTD IPC)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/export/arrow_batch.h` — 200 (41 lines; `ArrowBatchBuilder` pimpl)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/export/stats_exporter.cc` — 200 (545 lines; deep-read — C/C++ exception barriers, `set_terminate`, export loop)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/src/export/stats_exporter.h` — 200 (29 lines; fetched, C-ABI decls — not deep-cited)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/include/pg_stat_ch/pg_stat_ch.h` — 200 (24 lines; version macro + SQL func decls)
- `https://raw.githubusercontent.com/ClickHouse/pg_stat_ch/main/include/config/guc.h` — 200 (47 lines; GUC externs)

**404 gaps / manifest notes:** flat-layout probes 404'd before the real subdir
layout was discovered — `src/hooks.c`, `src/shmem.c`, `src/ringbuffer.c`,
`src/bgworker.c`, `src/worker.c`, `src/guc.c`, `src/capture.c`, `src/events.c`,
`src/export/clickhouse_export.cc`, `src/export/client.cc`, and all
`include/<flat>.h` names. The actual ClickHouse client implementation
(`clickhouse_exporter.cc`, referenced at `stats_exporter.cc:18`) and the OTel
exporter (`otel_exporter.cc`, `stats_exporter.cc:20`) were **not** fetched — the
30s socket-timeout claim (§2) rests on the `bgworker.c:170-177` comment, tagged
`[from-comment]`. Docs linked by the README (`docs/clickhouse.md`,
`docs/version-compatibility.md`, `docs/testing.md`, `docs/troubleshooting.md`)
were not fetched; supported-version and schema claims rest on `README.md` and
the inline `#if PG_VERSION_NUM` guards, tagged accordingly. `third_party/clickhouse-c`
(vendored submodule) is out of scope and its internals are `[inferred]` from the
CMake `SYSTEM PRIVATE` include (`CMakeLists.txt:101-105`).

Cites verified against blobs fetched 2026-07-15.
