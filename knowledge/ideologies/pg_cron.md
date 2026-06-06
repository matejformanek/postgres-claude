# pg_cron — a scheduler bgworker that runs jobs over libpq connections to its own postmaster

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `citusdata/pg_cron` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-05 (see Sources footer).

## Domain & purpose

pg_cron is a cron-syntax job scheduler that runs *inside* the database: you
`SELECT cron.schedule('0 3 * * *', 'VACUUM')` and a background process fires the
SQL on schedule. Its thesis is that a scheduler should live in the server (so it
survives restarts, replicates its job catalog, and needs no external daemon),
but that *running* a scheduled job must not block the scheduler nor inherit its
transaction. It is the worked answer to: *how does a single long-lived backend
launch arbitrary, possibly-long-running SQL in fresh isolated sessions, many
concurrently, without a transaction of its own getting in the way?* pg_cron's
answer — the design choice that defines it — is to **open ordinary libpq client
connections from the scheduler back to its own postmaster**, one per job, and
drive them asynchronously. (An opt-in second mode uses dynamic background
workers instead.)

## How it hooks into PG

pg_cron **requires** `shared_preload_libraries` and `ereport(ERROR)`s with a
hint otherwise — `_PG_init` checks `process_shared_preload_libraries_in_progress`
(`src/pg_cron.c:217-220`) `[verified-by-code]`. Module magic is plain
`PG_MODULE_MAGIC` (`src/pg_cron.c:113`).

`_PG_init` registers **one static background worker**, the launcher
(`src/pg_cron.c:354-369`): `bgw_flags = BGWORKER_SHMEM_ACCESS |
BGWORKER_BACKEND_DATABASE_CONNECTION`, `bgw_start_time =
BgWorkerStart_RecoveryFinished`, `bgw_restart_time = 1` (restart after 1s),
entrypoint `PgCronLauncherMain` (`src/pg_cron.c:354-364`). It defines a stack of
GUCs along the way — `cron.database_name`, `cron.log_run`, `cron.log_statement`,
`cron.host`, **`cron.use_background_workers`**, `cron.max_running_jobs`,
`cron.timezone`, `cron.enable_superuser_jobs` (`src/pg_cron.c:227-343`).

The launcher (`PgCronLauncherMain`, `src/pg_cron.c:549-660`) installs signal
handlers (`SIGHUP`→reload, `SIGTERM`→`die`, `SIGINT`→ignore,
`src/pg_cron.c:555-557`), connects to the configured database with
`BackgroundWorkerInitializeConnection` (`src/pg_cron.c:563-567`), advertises
itself as `pg_cron scheduler` in `pg_stat_activity`
(`pgstat_report_appname`, `src/pg_cron.c:570`), marks interrupted runs failed
(`src/pg_cron.c:576`), then runs an infinite loop: handle config reload,
`RefreshTaskHash`, `StartAllPendingRuns`, `WaitForCronTasks`, `ManageCronTasks`,
resetting a per-iteration memory context each pass (`src/pg_cron.c:622-657`).

## Where it diverges from core idioms

### 1. It runs a libpq *client* inside a backend — connecting to its own server

The defining divergence. In the default (`!UseBackgroundWorkers`) mode, each due
job is started by `PQconnectStartParams` with `host`/`port` taken from the job's
`nodeName`/`nodePort` (default the local `cron.host`), plus `dbname`/`user`/
`fallback_application_name=pg_cron`/`client_encoding`
(`src/pg_cron.c:1323-1353`) `[verified-by-code]`. The connection is put in
non-blocking mode (`PQsetnonblocking`, `src/pg_cron.c:1354`) and driven through
`PQconnectPoll` as a state machine (`src/pg_cron.c:1570`). A backend module
linking `libpq-fe.h` (`src/pg_cron.c:80`) and dialling its *own* postmaster is
squarely outside the in-process idiom — core never connects to itself — but it
is how pg_cron gets every job its own independent session, free of the
scheduler's lifetime and transaction. Cross-ref
`[[knowledge/subsystems/libpq-backend]]`, `[[knowledge/subsystems/tcop]]`.

### 2. The scheduler's event loop is `poll(2)` over libpq socket fds, not a WaitEventSet

Because the in-flight work is a set of libpq sockets rather than latches, pg_cron
includes `<poll.h>` (`src/pg_cron.c:52`) and waits on the connections'
file descriptors directly (`WaitForCronTasks`/`PollForTasks`,
`src/pg_cron.c:151-153`), capping the block at `MaxWait = 1000` ms
(`src/pg_cron.c:176`); it only falls back to `WaitLatch(MyLatch, ...,
PG_WAIT_EXTENSION)` when there are no sockets to watch (`src/pg_cron.c:1017-1025`).
Core backends almost always centre their wait on a `WaitEventSet`/latch; pg_cron
centres on raw `poll()` because it is multiplexing client connections.

### 3. Each task is a hand-written async state machine

`ManageCronTask` (`src/pg_cron.c:1265+`) is a switch over task states —
`CRON_TASK_START` → connecting (`PQconnectPoll` loop) → sending → running →
collecting feedback (`src/pg_cron.c:1312-1700`) — bridging libpq's asynchronous
API to a cooperative scheduler. It even bounds connection setup with a
`CronTaskStartTimeout` (default 10s, `src/pg_cron.c:175`) and clamps
`MaxRunningTasks` against `MaxConnections`, `max_files_per_process`, and the
process's `RLIMIT_NOFILE` (`src/pg_cron.c:579-603`) — because every running job
costs a real socket fd. Reasoning about fd limits is unusual for a PG extension.

### 4. Job metadata lives in ordinary tables in a `cron` schema, read like a catalog

pg_cron stores its jobs in plain user tables — `cron.job`, `cron.job_run_details`
— under `CRON_SCHEMA_NAME "cron"` with `cron.jobid_seq`/`cron.runid_seq`
sequences (`src/job_metadata.c:66-71`). But it reads and mutates them with the
**low-level relation/systable API** core reserves for real catalogs: a generated
`cron_job.h` defines `Anum_cron_job_jobid`, `Anum_cron_job_jobname`,
`Anum_cron_job_username`, and `cron_unschedule`/`cron_unschedule_named` open the
table and `systable`-scan it with `ScanKeyInit(... Anum_cron_job_jobid ...)`
(`src/job_metadata.c:649-722`), while inserts go through SPI
(`SPI_execute_with_args`, `src/job_metadata.c:348`). Treating an *ordinary* table
as if it were a bootstrapped catalog — hand-numbered attributes and all — is a
notable inversion of the catalog-conventions idiom. Cross-ref
`[[knowledge/idioms/catalog-conventions]]`, `[[knowledge/idioms/spi]]`.

### 5. It installs its SQL objects into `pg_catalog`

`pg_cron.control` sets `schema = pg_catalog` with `relocatable = false`
(`pg_cron.control`), so `cron.schedule(...)` and friends land in `pg_catalog`
and are visible everywhere without a search-path entry. Deliberately colonizing
`pg_catalog` from an extension is something most extensions avoid.

## Notable design decisions (cited)

- **Two execution backends, chosen by one GUC.** `cron.use_background_workers`
  flips between the libpq-connection path and a `RegisterDynamicBackgroundWorker`
  path that hands the job to a `CronBackgroundWorker` via a DSM segment
  (`src/pg_cron.c:1472-1501`, with `bgw_main_arg = dsm_segment_handle(task->seg)`,
  `BGW_NEVER_RESTART`). The bgworker mode avoids a network round-trip but is
  bounded by `max_worker_processes` (`src/pg_cron.c:595-598`).
- **`log_min_messages` is force-set on the launcher** to `cron.log_min_messages`
  via `SetConfigOption(..., PGC_POSTMASTER, PGC_S_OVERRIDE)` on startup and after
  every reload (`src/pg_cron.c:617-636`) — so scheduler chatter obeys its own
  knob independent of the server default.
- **Crash recovery for jobs.** On launcher start, `MarkPendingRunsAsFailed`
  rewrites any run left "running" by a crash to failed (`src/pg_cron.c:576`), so
  the audit table in `cron.job_run_details` never lies about in-flight work.
- **Notice forwarding.** A `PQsetNoticeReceiver(connection, CronNoticeReceiver,
  task)` (`src/pg_cron.c:1355`) pipes the job session's NOTICE/WARNING output
  back into the scheduler's log, since the job runs in a *different* session.
- **`cron.enable_superuser_jobs`** gates whether jobs may run as superuser
  (`src/job_metadata.c:302`), a hardening knob added because in-database
  scheduling is a privilege-escalation surface.

## Links into corpus

- `[[knowledge/subsystems/libpq-backend]]` — pg_cron links `libpq-fe.h` and
  opens client connections from a backend to its own postmaster.
- `[[knowledge/subsystems/storage-ipc]]` — static + dynamic background-worker
  registration, DSM hand-off, `BGWORKER_SHMEM_ACCESS`.
- `[[knowledge/subsystems/tcop]]` — the job sessions are ordinary backends
  spawned by the postmaster on each libpq connect.
- `[[knowledge/idioms/catalog-conventions]]` — `cron.job` read via the
  systable/`Anum_*` API as though it were a real catalog.
- `[[knowledge/idioms/spi]]` — inserts/updates to the job tables go through SPI.
- `.claude/skills/gucs-bgworker-parallel/SKILL.md` — `RegisterBackgroundWorker`
  vs `RegisterDynamicBackgroundWorker`, `BackgroundWorkerInitializeConnection`,
  the `bgw_flags`/`bgw_start_time`/`bgw_restart_time` fields pg_cron sets.
- `.claude/skills/extension-development/SKILL.md` — `shared_preload_libraries`
  enforcement and `_PG_init` worker registration.

## Sources

Fetched 2026-06-05 (branch `main`):

- `https://raw.githubusercontent.com/citusdata/pg_cron/main/src/pg_cron.c`
  @ 2026-06-05 → HTTP 200 (2375 lines).
- `https://raw.githubusercontent.com/citusdata/pg_cron/main/src/job_metadata.c`
  @ 2026-06-05 → HTTP 200 (1587 lines).
- `https://raw.githubusercontent.com/citusdata/pg_cron/main/include/cron.h`
  @ 2026-06-05 → HTTP 200 (275 lines; the bundled Vixie-cron entry parser).
- `https://raw.githubusercontent.com/citusdata/pg_cron/main/pg_cron.control`
  @ 2026-06-05 → HTTP 200 (5 lines).
- `https://raw.githubusercontent.com/citusdata/pg_cron/main/README.md`
  @ 2026-06-05 → HTTP 200 (472 lines).
- Tree listing
  `https://api.github.com/repos/citusdata/pg_cron/git/trees/main?recursive=1`
  @ 2026-06-05 → HTTP 200.

All `src/pg_cron.c` / `src/job_metadata.c` cites are `[verified-by-code]`
against the fetched files (the libpq-to-self connection path, the bgworker
registration, the `poll()` loop, the systable access to `cron.job`). The
`cron.h` Vixie-cron schedule parser and the `bin/`-less single-extension layout
were noted but not exhaustively traced.
