# pg-strom — pushing scan/join/aggregation out of the backend and onto the GPU (+ NVMe-SSD-direct, Arrow)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `heterodb/pg-strom` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Line numbers are approximate — they
> are the positions reported by the file-fetch pass on 2026-06-14 (see Sources
> footer) and should be re-verified before being quoted as exact.

## Domain & purpose

pg-strom is "an extension for PostgreSQL database … designed to accelerate
mostly batch and analytics workloads with utilization of GPU and NVME-SSD, and
Apache Arrow columnar" (`README.md`) `[from-README]`. Where pg_duckdb and
cstore_fdw ask *"can an extension replace Postgres' executor for a query
class?"*, pg-strom asks the harder hardware question: *"can scan / join /
group-by run on a GPU, with the data streamed straight from NVMe SSD into GPU
memory, bypassing the backend's address space entirely?"* The headline feature
set is GPU-accelerated `CustomScan` nodes (GpuScan, GpuJoin, GpuPreAgg, GpuSort),
**GPU-Direct SQL** (SSD→GPU DMA that skips host RAM and the buffer cache), and an
Arrow/Parquet foreign-data-wrapper as a columnar source `[from-README]`
`[verified-by-code]` (subsystem enumeration in `src/pg_strom.h`). It is the
maximal "offload execution to a co-processor" member of the family that also
includes [[pg_duckdb]] (offload to an embedded engine) and [[zombodb]] (offload
to an external service).

## How it hooks into PG

pg-strom layers onto core through the standard extension surfaces, but the
**executor work itself does not run in the calling backend** (see next section).

- **`_PG_init`** (`src/main.c:576-629`) `[verified-by-code]` delegates to a long
  list of subsystem initializers — `pgstrom_init_gpu_device()`,
  `pgstrom_init_gpu_scan()`, `pgstrom_init_gpu_join()`,
  `pgstrom_init_gpu_preagg()`, `pgstrom_init_codegen()`,
  `pgstrom_init_gpu_service()`, `pgstrom_init_select_into()` — declared in
  `src/pg_strom.h:~932` and around `pgstrom_init_*` `[verified-by-code]`. The
  `pgstrom_init_gpu_service()` initializer is where the GPU-service background
  worker is set up `[inferred]`.

- **planner_hook** (`src/main.c:606-607`) `[verified-by-code]`:
  `planner_hook_next = (planner_hook ? planner_hook : standard_planner);
  planner_hook = pgstrom_post_planner;` — chains the prior hook / `standard_planner`
  and installs `pgstrom_post_planner()` to post-process the finished plan tree
  (per the fetch summary, to strip dummy nodes) `[verified-by-code]`.

- **ExecutorStart_hook** (`src/main.c:609-610`) `[verified-by-code]`:
  `executor_start_hook_next = ExecutorStart_hook; ExecutorStart_hook =
  pgstrom_executor_start;` — wraps executor init, used to arm "SELECT INTO
  direct" mode `[verified-by-code]`.

- **set_rel_pathlist_hook** (`src/gpu_scan.c:~486`) `[verified-by-code]`:
  `set_rel_pathlist_hook = GpuScanAddScanPath;` — this is the classic
  "inject a CustomPath into the planner during base-rel path generation" idiom.
  `GpuScanAddScanPath()` (`src/gpu_scan.c:~317`) proposes a GPU scan path whose
  cost can use `pgstrom_gpu_direct_seq_page_cost` when GPU-Direct SQL is
  available for the relation (`src/gpu_scan.c:~225-232`) `[verified-by-code]`.

- **CustomScan provider** (`src/gpu_scan.c:~15-18`) `[verified-by-code]`: three
  method tables — `CustomPathMethods gpuscan_path_methods` (with
  `PlanCustomPath = PlanGpuScanPath`), `CustomScanMethods gpuscan_plan_methods`
  (with `CreateCustomScanState = CreateGpuScanState`), and
  `CustomExecMethods gpuscan_exec_methods` (with `BeginCustomScan` /
  `ExecCustomScan` / `EndCustomScan` / `ReScanCustomScan`). The
  Path→Plan→PlanState pipeline is `GpuScanAddScanPath` →
  `PlanGpuScanPath()` (`~468`) → `CreateGpuScanState()` (`~510`) →
  `pgstromCreateTaskState()` `[verified-by-code]`. This is the textbook
  [[executor-and-planner]] CustomScan contract (see also the
  [[access-method-apis]] / custom-scan idiom).

- **GUCs** (`src/main.c:79-131`, `pgstrom_init_gucs()`) `[verified-by-code]`:
  `pg_strom.enabled` (bool, default true), `pg_strom.cpu_fallback` (enum:
  whether a GPU op that can't run falls back to CPU vs ERRORs),
  `pg_strom.regression_test_mode`, `pg_strom.explain_developer_mode`,
  `pg_strom.enable_select_into_direct`. Cost-model GUCs
  (`pgstrom_gpu_setup_cost`, `pgstrom_gpu_tuple_cost`,
  `pgstrom_gpu_operator_cost`, `pgstrom_gpu_direct_seq_page_cost`) are declared
  in `src/pg_strom.h:~495-496` `[verified-by-code]`. See [[gucs-config]].

- **Background worker** — a dedicated **GPU service** process
  (`src/gpu_service.c`) owns the CUDA contexts and brokers all GPU work for the
  cluster's backends `[verified-by-code]` (see below). This is the bgworker
  idiom ([[bgworker-and-extensions]]) but used as a *device-arbitration daemon*,
  not a periodic job.

- **Arrow FDW** — a foreign-data-wrapper exposing Arrow/Parquet files as a
  columnar scan source feeding the same GPU path machinery `[verified-by-code]`
  (subsystem listed in `src/pg_strom.h`) `[from-README]`.

## Where it diverges from core idioms

This is the crux: pg-strom does the actual relational work **outside** the
backend's MemoryContext, outside the backend's executor loop, and (for
GPU-Direct SQL) **outside the backend's address space and the shared buffer
cache altogether**.

- **Memory: device memory + `malloc`/`free`, not palloc.** XPU commands sent to
  the GPU service are allocated from GPU-managed memory chunks or with plain
  `malloc(3)` for pre-session commands, and freed with `free(3)` — explicitly
  *never* `palloc` (`src/gpu_service.c:~3440`, comment
  `packed->chunk = NULL; /* be released by free(3) */`) `[verified-by-code]`.
  The service maintains its own GPU allocator: two pools per device
  (`pool_raw` for raw device memory, `pool_managed` for CUDA unified memory),
  with buddy-style splitting for >4MB chunks and LRU maintenance via
  `gpuMemoryPoolMaintenance()` `[verified-by-code]`. None of this is reachable
  from `MemoryContextStats`, `pg_backend_memory_contexts`, or the OOM-throws-
  `ereport` contract that the rest of the backend assumes (cf.
  [[memory-contexts]]). A GPU OOM is a CUDA error, not an `errcode(OUT_OF_MEMORY)`.

- **Execution: a separate process and its own worker threads.** GPU work runs in
  dedicated worker threads inside the GPU-service bgworker, "asynchronous,
  non-blocking … independent of PostgreSQL's executor context"
  `[verified-by-code]` (architecture of `src/gpu_service.c`). The backend's
  `ExecGpuScan` is effectively a client that ships an XPU command and pulls back
  result chunks. This breaks the core assumption that one `PlanState` tree is
  driven by one backend on one thread — PG core is rigorously single-threaded
  per backend; pg-strom introduces multithreaded CUDA execution next door.

- **IPC: Unix-domain socket + shared memory, not the executor's tuple flow.**
  The service listens on `.pg_strom.%u.gpuserv.sock`
  (`src/gpu_service.c:~1980`, `gpuservOpenServerSocket()`); backends submit XPU
  commands through `__gpuServiceAllocCommand` / `__gpuServiceAttachCommand` onto
  per-GPU-context command queues guarded by mutexes; a `gpuServSharedState`
  in shared memory carries atomic readiness flags (`gpuserv_ready_accept`) and
  counters `[verified-by-code]`. Cross-process mutexes + atomics are a different
  concurrency model than core's LWLock/spinlock partition discipline (cf.
  [[locking]] / [[parallel-query]], whose DSM+shm_toc machinery pg-strom does
  *not* reuse for GPU dispatch).

- **I/O: GPU-Direct SQL bypasses the buffer cache.** `gpuDirectFileReadIOV()`
  loads data straight to the device, and `gpuDirectMapGpuMemory()` /
  `gpuDirectUnmapGpuMemory()` manage the I/O mapping; segments carry an
  `iomap_handle` for NVMe / legacy-Strom direct paths `[verified-by-code]`. Data
  can travel SSD→GPU without passing through `shared_buffers` or even host RAM.
  This sidesteps the entire storage-buffer subsystem ([[storage-buffer]]) and
  its visibility/pin/dirty bookkeeping for the GPU-Direct read path
  `[inferred]`. (Heap visibility still has to be honored; pg-strom carries MVCC
  snapshot info into the kernel rather than going through the normal
  `heap_getnext` path `[unverified]`.)

- **Codegen: SQL expressions compiled to CUDA.** A `codegen_context`
  (`src/pg_strom.h`) and `pgstrom_init_codegen()` turn qualifier/projection
  expressions into device code; `gpuservSetupFatbin()` (`src/gpu_service.c:~1860`)
  compiles CUDA to fatbin `[verified-by-code]`. Core PG interprets expression
  trees via `ExecInterpExpr` (or JITs to LLVM); pg-strom JITs to a *different
  ISA* on a *different device*.

- **WAL / replication: read-side acceleration, so largely orthogonal.** The
  GPU paths characterized here are scan/join/aggregation — read-side. No WAL or
  replication hooks were observed in the fetched files `[inferred]`. The
  "SELECT INTO direct" write path (`pgstrom_init_select_into`,
  `selectIntoState` at `src/pg_strom.h:~860`) buffers direct table writes
  `[verified-by-code]`; whether/how it interacts with WAL was not examined here
  `[unverified]` and is the natural place to look for replication-correctness
  concerns.

- **Catalog conventions: conventional.** pg-strom registers SQL functions, the
  Arrow FDW, and GUCs through ordinary extension mechanisms (`CREATE EXTENSION`
  install script) `[inferred]`; it does not appear to abuse the catalog the way
  it abuses the executor/memory model. The divergence is *runtime*, not
  *catalog-shape*.

## Notable design decisions

- **CustomScan as the one true integration seam** — every GPU operator
  (scan/join/preagg/sort) is a `CustomScan` node carrying a `pgstromPlanInfo`
  payload (`src/pg_strom.h`), planned via `set_rel_pathlist_hook` +
  `CustomPathMethods` (`src/gpu_scan.c:~15-18,~486`) `[verified-by-code]`.
  pg-strom never forks core; it adds paths and lets `add_path` cost-pruning
  decide. The whole "abuse a pluggable API to offload execution" thesis rides on
  CustomScan being expressive enough.

- **A cluster-wide GPU-service daemon, not per-backend CUDA contexts** — CUDA
  context creation is expensive and the device is shared, so pg-strom centralizes
  it in one bgworker that pools device memory and serializes/parallelizes work
  across all backends (`src/gpu_service.c`, `gpuServSharedState`,
  `gpuContextSwitchTo()` at `~1280`) `[verified-by-code]`. Backends are thin
  clients over a socket. This is the inversion of PG's "every backend is
  self-sufficient" model.

- **Cost-model integration via dedicated GUCs** — rather than hard-routing,
  pg-strom prices GPU setup/tuple/operator cost and GPU-Direct page cost as GUCs
  (`src/pg_strom.h:~495-496`) so the planner can choose CPU vs GPU per query
  `[verified-by-code]`. Contrast [[pg_duckdb]]'s `force_execution` blunt switch.

- **`cpu_fallback` as a correctness/availability dial** — a GPU op that can't be
  expressed on-device can fall back to CPU, NOTICE, or hard-ERROR depending on
  the `pg_strom.cpu_fallback` enum GUC (`src/main.c:79-131`)
  `[verified-by-code]`. This is an explicit acknowledgment that the offload is
  *partial* — not every expression has a device kernel.

- **GPU-Direct SQL as a first-class plan-cost input** — availability of SSD→GPU
  DMA literally changes the path cost (`src/gpu_scan.c:~225-232`)
  `[verified-by-code]`, so the I/O architecture leaks (intentionally) into the
  optimizer.

## Links into corpus

- [[executor-and-planner]] — CustomPath/CustomScan/CustomExec contract and
  `add_path` cost pruning that pg-strom rides on.
- [[memory-contexts]] — the palloc/MemoryContext model pg-strom deliberately
  steps outside of (GPU memory via `malloc`/`free` + CUDA allocator).
- [[bgworker-and-extensions]] — the background-worker idiom, here used as a
  device-arbitration daemon (the GPU service).
- [[gucs-config]] — `DefineCustom*Variable` usage for the cost-model and
  fallback GUCs.
- [[parallel-query]] — core's DSM + shm_toc worker model, which pg-strom does
  *not* reuse for GPU dispatch (it rolls its own socket+shmem queue).
- [[locking]] — core LWLock/spinlock discipline vs pg-strom's cross-process
  mutexes + atomics.
- [[storage-buffer]] — the buffer cache that GPU-Direct SQL bypasses.
- [[pg_duckdb]], [[zombodb]], [[cstore_fdw]] — sibling "offload execution
  elsewhere / abuse a pluggable API" ideologies.

## Sources

Fetched 2026-06-14 (timestamps UTC). The `api.github.com` tree endpoint was
blocked (403) and the GitHub MCP tooling is repo-scoped to `postgres-claude`, so
file paths were taken from the manifest hint and verified by successfully
fetching each raw file (a 404 would have signaled a wrong path; none of the
fetched paths 404'd).

- `https://api.github.com/repos/heterodb/pg-strom/git/trees/master?recursive=1`
  — 2026-06-14T23:09Z — **HTTP 403 Forbidden** (could not enumerate tree;
  fell back to manifest-hint paths). SUBSTITUTION/NOTE: tree listing unavailable.
- `https://raw.githubusercontent.com/heterodb/pg-strom/master/README.md`
  — 2026-06-14T23:09Z — HTTP 200.
- `https://raw.githubusercontent.com/heterodb/pg-strom/master/src/pg_strom.h`
  — 2026-06-14T23:09Z — HTTP 200.
- `https://raw.githubusercontent.com/heterodb/pg-strom/master/src/main.c`
  — 2026-06-14T23:09Z — HTTP 200.
- `https://raw.githubusercontent.com/heterodb/pg-strom/master/src/gpu_service.c`
  — 2026-06-14T23:10Z — HTTP 200.
- `https://raw.githubusercontent.com/heterodb/pg-strom/master/src/gpu_scan.c`
  — 2026-06-14T23:10Z — HTTP 200.

Manifest substitutions: none for source files — all five hinted/likely paths
(`README.md`, `src/pg_strom.h`, `src/main.c`, `src/gpu_service.c`,
`src/gpu_scan.c`) resolved with HTTP 200. The only failure was the GitHub tree
API (403), which forced reliance on the manifest hint rather than a verified
tree listing. `src/relscan.c` from the hint was not fetched (kept fetch count to
the GPU-offload core: gpu_service.c + gpu_scan.c).
