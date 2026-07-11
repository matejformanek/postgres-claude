# pg_wait_sampling — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `postgrespro/pg_wait_sampling` @ branch `master`. All `file:line` cites
> below point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> blobs fetched 2026-07-10 (see Sources footer). Line numbers are for the
> `master` blobs as fetched.

pg_wait_sampling turns PostgreSQL's *instantaneous* wait-event field into a
*time series*. Core exposes `pg_stat_activity.wait_event` as a point-in-time
read of each backend's `PGPROC.wait_event_info`; there is no retained history
and no server-wide aggregate. **Headline divergence:** a single
`shared_preload_libraries` background worker periodically walks the entire
`ProcGlobal->allProcs` array — under `ProcArrayLock` in shared mode — reads
every other backend's live `wait_event_info` integer straight out of its
`PGPROC`, and folds each sweep into two derived structures core never keeps: a
ring buffer of recent samples (*history*) and a `(pid, wait_event, queryid)`
count hash (*profile*) (`collector.c:148-203`, `162`, `pg_wait_sampling.c:472-494`)
`[verified-by-code]`. So it manufactures descriptive statistics of server
behavior out of external sampling — exactly what the README says core forces the
user to do by hand (`README.md:10-14`) `[from-README]`.

## Domain & purpose

pg_wait_sampling answers *what has the whole server been waiting on, over time
and in aggregate?* It collects two kinds of statistics from the same PGPROC
sweep (`README.md:25-41`) `[from-README]`: (1) **history** — an in-memory ring
buffer where each process's wait event is written every
`pg_wait_sampling.history_period` ms, so a client can poll and stitch together a
continuous timeline; (2) **profile** — an in-memory hash accumulating a *count*
of samples per `(process, wait event, query)`, resettable on demand, giving the
relative intensity of each wait event over time (`README.md:27-38`)
`[from-README]`. The control comment is `'sampling based statistics of wait
events'` (`pg_wait_sampling.control:2`) `[verified-by-code]`. When paired with
`pg_stat_statements` the captured `queryid` links each sample to per-statement
stats (`README.md:21-23,40-41`) `[from-README]`. It is the historical/aggregate
sibling of the wait-event columns in `pg_stat_activity`, reifying the time and
frequency dimensions the catalog view discards.

## How it hooks into PG

pg_wait_sampling **requires** `shared_preload_libraries`: `_PG_init` returns
immediately unless `process_shared_preload_libraries_in_progress`, and every SRF
guards on `check_shmem()` (`pg_wait_sampling.c:321-322`, `297-305`)
`[verified-by-code]`; the README states the restart requirement plainly
(`README.md:16-19`) `[from-README]`.

- **One static bgworker.** `pgws_register_wait_collector` fills a
  `BackgroundWorker` and calls **`RegisterBackgroundWorker`** — the preload-time
  path — with **`BGWORKER_SHMEM_ACCESS` only** (no
  `BGWORKER_BACKEND_DATABASE_CONNECTION`), `bgw_start_time =
  BgWorkerStart_ConsistentState`, and `bgw_restart_time = 1`
  (`collector.c:40-56`) `[verified-by-code]`. Yet the worker still calls
  `InitPostgresCompat(NULL, InvalidOid, …)` to become a full backend that
  participates in `ProcSignal` **without connecting to any database** — the
  comment explains it wants `procsignal_sigusr1_handler` to work
  (`collector.c:336-344`) `[verified-by-code]` `[from-comment]`. Contrast
  `[[pgsentinel]]`, which *does* `BackgroundWorkerInitializeConnection` because
  it samples via SQL.
- **Shmem request.** On PG ≥ 15 a `shmem_request_hook` calls
  `RequestAddinShmemSpace(pgws_shmem_size())`; on PG ≤ 14 `_PG_init` calls it
  inline (`pg_wait_sampling.c:231-245`, `324-335`) `[verified-by-code]`. Size is
  estimated with a `shm_toc` estimator over three chunks
  (`pg_wait_sampling.c:210-229`) `[verified-by-code]`.
- **Shmem startup.** `pgws_shmem_startup` carves one `ShmemInitStruct` and lays
  a `shm_toc` (table-of-contents) with three keyed chunks: the
  `CollectorShmqHeader`, a `COLLECTOR_QUEUE_SIZE` (16 KB) `shm_mq` region, and a
  `uint64[get_max_procs_count()]` per-proc queryid array, zeroed at init
  (`pg_wait_sampling.c:251-292`, `pg_wait_sampling.h:19`) `[verified-by-code]`.
- **Six GUCs**, all `PGC_SIGHUP`: `history_size` (default 5000),
  `history_period`/`profile_period` (10 ms), `profile_pid`, `profile_queries`
  (enum none/top/all), `sample_cpu` (`pg_wait_sampling.c:362-434`)
  `[verified-by-code]`. Placeholders are flushed with the **modern**
  `MarkGUCPrefixReserved("pg_wait_sampling")` (PG ≥ 15,
  `pg_wait_sampling.c:437`) `[verified-by-code]` — cleaner than pgsentinel's
  legacy `EmitWarningsOnPlaceholders`.
- **Consumer SRFs.** `pg_wait_sampling_get_current` reads PGPROC directly;
  `pg_wait_sampling_get_history` / `_get_profile` pull from the collector over
  `shm_mq`; `_reset_profile` posts a reset request (`pg_wait_sampling.c:502-862`,
  `864-955`) `[verified-by-code]`. All use the classic `SRF_FIRSTCALL` /
  `SRF_PERCALL` value-per-call idiom, not `SFRM_Materialize`.

## Where it diverges from core idioms

### 1. It reads every other backend's transient wait state from a central worker — but with lock discipline

This is the core-un-Postgres move, and the axis on which it should be compared
to `[[pgsentinel]]`. Core never lets one backend consume another backend's
transient wait field except through the `pg_stat_activity` view machinery.
pg_wait_sampling's collector loops `ProcGlobal->allProcs[0 .. allProcCount]`,
and for each reads `proc->wait_event_info` and `proc->pid` directly
(`collector.c:163-177`, `pgws_should_sample_proc`,
`pg_wait_sampling.c:472-494`) `[verified-by-code]`. Crucially it does this
**holding `LWLockAcquire(ProcArrayLock, LW_SHARED)`** for the whole sweep
(`collector.c:162,202`) `[verified-by-code]` — the same lock core takes to scan
the proc array. That is a sharp contrast with pgsentinel, which requests four
LWLock tranches and then never acquires any of them, scanning its rings and
proc slots lock-free. pg_wait_sampling reads a single 32-bit field per proc, so
a shared lock over the array is cheap and correct; it does not need pgsentinel's
implicit single-writer gamble.

### 2. It captures only the wait event + a queryid — no query text, no parse hook

pgsentinel installs a `post_parse_analyze_hook` in every backend to memcpy each
backend's *query text* into a PGPROC-indexed shmem char arena, then reads it
back via SPI. pg_wait_sampling is deliberately lighter: it captures the wait
event (already an integer in `PGPROC`) plus at most a 64-bit `queryId`. To get
the queryid it installs `planner_hook` + `ExecutorStart/Run/Finish/End` +
`ProcessUtility_hook` in every backend, and each backend writes **its own**
queryId into `pgws_proc_queryids[MyProc - ProcGlobal->allProcs]` — its slot in
the per-proc shmem `uint64` array — on entry, restoring the saved value on exit
with nesting-depth bookkeeping inside `PG_TRY`/`PG_CATCH`
(`pg_wait_sampling.c:960-1203`, esp. `973-1024`) `[verified-by-code]`. The
collector then reads `pgws_proc_queryids[i]` beside the wait event
(`collector.c:172-175`) `[verified-by-code]`. No `NAMEDATALEN` char arenas, no
text redaction, no SPI — a much smaller cross-backend channel than pgsentinel's.

### 3. The history ring and profile hash live in the worker's PRIVATE memory, not shmem

pgsentinel puts its ASH ring in shared memory and lets any PUBLIC reader scan it
directly. pg_wait_sampling instead keeps both derived structures in the
**collector's own backend-local memory**: `alloc_history` `palloc0`s the
`HistoryItem[]` ring in a `collector_context` under `TopMemoryContext`
(`collector.c:61-68`, `320-357`), and `make_profile_hash` builds a private
`HTAB` (`collector.c:285-298`) `[verified-by-code]`. The only shared regions are
the tiny header, the 16 KB `shm_mq`, and the per-proc queryid array
(`pg_wait_sampling.c:268-275`) `[verified-by-code]`. Consumers never touch the
ring; they ask the collector to *ship* it. This trades PUBLIC-readable shmem for
a request/response RPC (divergence 4) — heavier per read, but no shared ring to
corrupt and no fixed-width column arenas.

### 4. Consumers pull via a single-consumer shm_mq RPC guarded by heavyweight advisory locks

Reading history/profile is a genuine remote-procedure call, not a scan. A
consumer SRF calls `receive_array`, which: takes advisory `PGWS_QUEUE_LOCK`
(serializes all requesters) and `PGWS_COLLECTOR_LOCK` (protects the request
slot), creates a `shm_mq` in the shared 16 KB region, sets
`pgws_collector_hdr->request`, `SetLatch`es the collector, attaches as the mq
**receiver**, and streams the array out — all under
`PG_ENSURE_ERROR_CLEANUP(pgws_cleanup_callback)` so a Ctrl-C'd consumer still
detaches and releases the lock, never wedging the collector
(`pg_wait_sampling.c:644-733`, `307-313`) `[verified-by-code]` `[from-comment]`.
The collector wakes on its latch, sees `request != NO_REQUEST`, takes
`PGWS_COLLECTOR_LOCK`, attaches as **sender**, and `send_history` /
`send_profile` write a count then one item per row into the mq
(`collector.c:426-479`, `208-280`) `[verified-by-code]`. The advisory `LOCKTAG`
is hand-built with `PG_WAIT_SAMPLING_MAGIC` in field1 and `USER_LOCKMETHOD`
(`pg_wait_sampling.c:632-642`) `[verified-by-code]`. This is a far more
disciplined consumer path than pgsentinel's lock-free direct ring scan — at the
cost of only one reader at a time.

### 5. The "current" view bypasses the collector entirely — a straight PGPROC re-read

`pg_wait_sampling_get_current` does *not* talk to the collector. It takes
`ProcArrayLock` shared and reads `proc->wait_event_info` + `proc->pid` +
`pgws_proc_queryids[i]` directly, formatting names with
`pgstat_get_wait_event_type` / `pgstat_get_wait_event`
(`pg_wait_sampling.c:502-624`) `[verified-by-code]`. It is essentially a
re-implementation of `pg_stat_activity`'s wait columns plus the captured
queryid — the same read the collector does, exposed synchronously. So the
extension has *two* readers of PGPROC wait state: the sampling collector (for
history/profile) and this SRF (for now).

## Notable design decisions (with cites)

- **`get_max_procs_count()` must track `ProcGlobal->allProcCount`.** It adds
  `MaxBackends` (PG ≥ 15) or hand-computes it (`MaxConnections +
  autovacuum_max_workers + 1 + max_worker_processes + max_wal_senders`) plus
  `NUM_AUXILIARY_PROCS`, with a comment noting the ≤ 14 value may drift and
  relies on core's spare 100 kB of shmem (`pg_wait_sampling.c:155-205`)
  `[verified-by-code]` `[from-comment]`.
- **PGPROC liveness via `procLatch.owner_pid`.** Because `PGPROC->pid` is not
  reset on exit before PG 17, `pgws_should_sample_proc` skips a proc when
  `pid == 0 || proc->procLatch.owner_pid == 0 || pid == MyProcPid`
  (`pg_wait_sampling.c:481-494`) `[verified-by-code]` `[from-comment]`.
- **`sample_cpu` samples on-CPU backends.** When true, procs with
  `wait_event_info == 0` (not waiting) are still recorded, with NULL wait
  columns (`pg_wait_sampling.c:481-482`, `README.md:157-159`)
  `[verified-by-code]` `[from-README]`.
- **`profile_queries` enum gates nesting depth.** `none` → queryid 0; `top` →
  only top-level statements; `all` → nested too, via the `pgws_enabled(level)`
  macro keyed on `nesting_level` (`pg_wait_sampling.c:114-146`, `976`)
  `[verified-by-code]`.
- **Profile key width flexes with `profile_queries`.** `make_profile_hash` sets
  `keysize = offsetof(ProfileItem, count)` (includes queryId) when profiling
  queries, else `offsetof(ProfileItem, queryId)` (`collector.c:285-298`)
  `[verified-by-code]` — so the queryid is dropped from the aggregation key when
  disabled.
- **History ring realloc on GUC change.** `probe_waits` notices
  `observations->count != pgws_historySize` and `realloc_history`s mid-flight,
  preserving wraparound order (`collector.c:156-159`, `73-112`)
  `[verified-by-code]` — so `history_size` is effectively `SIGHUP`-tunable.
- **`history_size` upper bound guards `alloc_history`.** The GUC max is
  `MaxAllocSize / sizeof(HistoryItem)` with an explicit "to avoid error in
  collector.c:alloc_history" comment (`pg_wait_sampling.c:369`)
  `[verified-by-code]` `[from-comment]`.
- **Single adaptive WaitLatch.** The collector waits
  `Min(history, profile)` remaining ms on `MyProc->procLatch` with
  `WL_LATCH_SET | WL_TIMEOUT | WL_POSTMASTER_DEATH`, `proc_exit(1)` on
  postmaster death (`collector.c:417-424`) `[verified-by-code]`. Signal handlers
  are mixed-era: bespoke `handle_sigterm`, but modern
  `SignalHandlerForConfigReload` (SIGHUP) and `procsignal_sigusr1_handler`
  (SIGUSR1) (`collector.c:339-341`) `[verified-by-code]`.
- **Version compat via a `compat.h` shim, not only inline ifdefs.**
  `InitPostgresCompat`, `shm_mq_send_compat` and friends abstract the PG
  13→19 signature churn, with inline `#if PG_VERSION_NUM` only where a hook
  signature changes (planner `ExplainState`, `ExecutorRun` `execute_once`,
  `ProcessUtility` `readOnlyTree`, `TupleDescFinalize`)
  (`collector.c:14`, `pg_wait_sampling.c:35-110`, `532-534`)
  `[verified-by-code]` — cleaner than pgsentinel's all-inline ifdef sprawl.
- **`search_proc` linear-scans for `get_current(pid)`** and `ereport(ERROR)`s
  "backend with pid=%d not found" on miss (`pg_wait_sampling.c:445-466`)
  `[verified-by-code]`.

## Links into corpus

- [[pgsentinel]] — the headline sibling and the sharpest contrast: also an
  active-session/wait sampler with a preload bgworker, but pgsentinel captures
  full ASH rows *including query text* via a `post_parse_analyze_hook` + SPI over
  `pg_stat_activity`, keeps its ring in shmem, and reads lock-free;
  pg_wait_sampling captures only the wait event + a 64-bit queryid, reads PGPROC
  directly in C under `ProcArrayLock`, keeps its ring in worker-local memory, and
  serves consumers over a locked `shm_mq` RPC.
- [[pg_tracing]] — another shmem-observability extension with a bgworker; like
  pg_wait_sampling it takes real locks (unlike pgsentinel).
- `.claude/skills/bgworker-and-extensions` — static `RegisterBackgroundWorker` at
  preload, the `BackgroundWorker` flags/start-time fields, the `WaitLatch` +
  signal-handler loop (`collector.c:40-56`, `417-424`).
- `.claude/skills/pgstat-framework` — `wait_event_info`,
  `pgstat_get_wait_event_type` / `pgstat_get_wait_event`; pg_wait_sampling is a
  sampler layered on the same wait-event registry core exposes point-in-time.
- `.claude/skills/process-lifecycle` — the `PGPROC` / `ProcGlobal->allProcs`
  scan and `procLatch.owner_pid` liveness trick (`pg_wait_sampling.c:472-494`).
- `.claude/skills/locking` — the anti-example-inverse of pgsentinel: proper
  `ProcArrayLock` shared reads plus heavyweight advisory `LOCKTAG`s for the RPC
  (`collector.c:162`, `pg_wait_sampling.c:632-642`).
- Idioms: `knowledge/idioms/process-utility-hook-chain.md` (the
  save/restore-prev-hook chain in `_PG_init`, `pg_wait_sampling.c:342-359`);
  `knowledge/idioms/bgworker-and-parallel.md`. Subsystems:
  `knowledge/subsystems/storage-ipc.md` (`shm_toc` + `shm_mq`),
  `knowledge/subsystems/storage-lmgr.md` (advisory `USER_LOCKMETHOD` locks).

> Corpus gap: as noted in `[[pgsentinel]]`, there is still no idiom doc for
> **"a central worker reads other backends' transient PGPROC state on a timer."**
> pg_wait_sampling is the *disciplined* exemplar (ProcArrayLock-held, integer
> field only); pgsentinel is the *aggressive* one (lock-free, query text). A
> single `idioms/cross-backend-pgproc-sampling.md` could contrast the two.

## Sources

All fetched 2026-07-10 via `raw.githubusercontent.com` (GitHub API blocked this
run). Branch `master`. Cites verified against the fetched blobs.

- `https://raw.githubusercontent.com/postgrespro/pg_wait_sampling/master/README.md`
  — 200 (188 lines; the repo's primary README — note `README.rst` returns **404**,
  it does not exist)
- `https://raw.githubusercontent.com/postgrespro/pg_wait_sampling/master/pg_wait_sampling.c`
  — 200 (1204 lines)
- `https://raw.githubusercontent.com/postgrespro/pg_wait_sampling/master/collector.c`
  — 200 (487 lines)
- `https://raw.githubusercontent.com/postgrespro/pg_wait_sampling/master/pg_wait_sampling.h`
  — 200 (82 lines)
- `https://raw.githubusercontent.com/postgrespro/pg_wait_sampling/master/pg_wait_sampling.control`
  — 200 (5 lines)

Referenced-but-not-fetched (behavior inferred from call sites in the cited
files): `compat.h` (the `InitPostgresCompat` / `shm_mq_send_compat` version-shim
macros), the `pg_wait_sampling--*.sql` install/upgrade scripts, and `Makefile`.
No 404 gaps beyond the non-existent `README.rst`; no path substitutions needed.
