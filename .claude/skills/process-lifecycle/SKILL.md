---
name: process-lifecycle
description: PostgreSQL's per-connection multi-process model — postmaster fork, backend startup / initialization / query loop / clean shutdown, auxiliary processes (checkpointer, bgwriter, walwriter, autovacuum launcher, WAL summarizer, pgarch), background workers (bgworker.c registry + parallel/logical-rep workers), signal handling, and the FATAL/ERROR/PANIC hierarchy. Loads when the user asks about how a connection becomes a backend, what runs before the first query, why a query dies mid-flight, how signals + ProcessInterrupts + CHECK_FOR_INTERRUPTS work together, how autovacuum / bgworker workers get scheduled, or when planning a feature that hooks a startup phase / adds a new auxiliary process / touches shutdown ordering. Skip when the question is about client-side (libpq, drivers) or about the SQL-level session properties (that's `tcop` for query dispatch, `gucs-config` for GUCs).
when_to_load: Understand the fork model + backend startup phases; add a new auxiliary process / bgworker; wire a startup-time hook; investigate signal handling / interrupt processing; debug "why did my query get canceled"; touch shutdown ordering.
companion_skills:
  - bgworker-and-extensions
  - error-handling
  - locking
---

# process-lifecycle — postmaster, backends, aux processes, bgworkers

PostgreSQL uses a **per-connection process model, not threads**. Every client connection gets its own OS process, forked from the postmaster. New backends do NOT inherit query state — every connection starts fresh through `InitPostgres`. This model shapes almost every feature.

## The five process classes

| Class | Files | Lifetime | Example |
|---|---|---|---|
| **Postmaster** | `postmaster/postmaster.c`, `pmchild.c`, `launch_backend.c`, `fork_process.c` | Cluster-lifetime | The parent process — accepts connections, forks children, reaps exits, restarts on crash. |
| **Regular backend** | `tcop/postgres.c`, `tcop/backend_startup.c` | Connection-lifetime | The child that runs SQL for one client. |
| **Auxiliary process** | `postmaster/auxprocess.c` + one file each: `checkpointer.c`, `bgwriter.c`, `walwriter.c`, `walsummarizer.c`, `startup.c`, `pgarch.c`, `syslogger.c`, `interrupt.c` | Cluster-lifetime | Always-on infrastructure processes; not for user queries. |
| **Bgworker** | `postmaster/bgworker.c` + registered by extensions | Configurable (per session / for lifetime of cluster / restart on crash) | Autovacuum workers, parallel query workers, logical-rep apply workers, extension workers. |
| **Autovacuum launcher/worker** | `postmaster/autovacuum.c` | Cluster-lifetime launcher + short-lived workers | Special case: launcher is aux, workers are bgworkers. |

## Backend lifecycle (regular query-serving backend)

Every incoming connection follows this sequence:

1. **Postmaster accepts** — `postmaster.c` `ServerLoop` sees a new socket, calls `BackendStartup` in `launch_backend.c`.
2. **Fork or exec-and-fork** — On Unix, `fork()` copies the postmaster into a child. On Windows or `EXEC_BACKEND` builds, the child re-execs and re-attaches to shmem via `SubPostmasterMain`.
3. **Auth handshake** — `backend_startup.c` runs the startup message exchange, TLS/GSS, SCRAM/MD5/etc. authentication. Fails here → child exits before any query state exists.
4. **`InitPostgres`** — This is the big one (in `utils/init/postinit.c`). Loads GUC per-role/per-db settings, opens the database's relcache/syscache, checks CONNECT permission, runs the login `_PG_init` hooks, ends up in `PostgresMain`.
5. **`PostgresMain` loop** — the SQL query loop (in `tcop/postgres.c`). ReadCommand → exec → send RowDescription/DataRow/CommandComplete → ReadyForQuery → next iteration.
6. **Shutdown** — Client sends X (Terminate), or postmaster signals shutdown, or fatal error. `proc_exit` runs registered callbacks (see `on_shmem_exit` / `on_proc_exit` in `storage/ipc/ipc.c`), releases locks + LWLocks, detaches from shmem.

## The interrupt / signal system

Because backends can be interrupted between statements (query cancel, admin shutdown, sighup, deadlock), there's a specific pattern:

- **Signal handlers** must be async-signal-safe. They set flags (`InterruptPending`, `QueryCancelPending`, `ProcDiePending`, `ConfigReloadPending`) and set the process latch (`SetLatch(MyLatch)`).
- **`CHECK_FOR_INTERRUPTS()`** — macros sprinkled through the code that check the flags at safe points and call `ProcessInterrupts` (in `tcop/postgres.c`) if any are set.
- **`ProcessInterrupts`** — the actual interrupt handler. Runs at safe points, may call `ereport(FATAL/ERROR)` to unwind or `LATCH_WAIT_TIMEOUT` handling.
- **Safe interruption points** — the code base has thousands. Long-running loops need to include `CHECK_FOR_INTERRUPTS()` — a missing one → uncancelable query.

Common signals + their flags:
- `SIGINT` (query cancel) → `QueryCancelPending`.
- `SIGTERM` (shutdown) → `ProcDiePending`.
- `SIGHUP` (reload conf) → `ConfigReloadPending`.
- `SIGUSR1` (procsignal — multiplexed) → reason-specific flags via `procsignal.c`.

## Auxiliary processes at a glance

Each aux process has its own file with a Main function that the postmaster spawns via `SubPostmasterMain` (Windows / EXEC_BACKEND) or forks directly:

| File | Function | Purpose |
|---|---|---|
| `startup.c` | `StartupProcessMain` | Runs crash recovery / WAL replay at startup. Exits once redo completes. |
| `checkpointer.c` | `CheckpointerMain` | Runs periodic checkpoints; writes the shutdown stats file. |
| `bgwriter.c` | `BackgroundWriterMain` | Writes dirty buffers to smooth checkpoint I/O. |
| `walwriter.c` | `WalWriterMain` | Flushes WAL buffers asynchronously. |
| `walsummarizer.c` | `WalSummarizerMain` | (PG 17+) Summarizes WAL for incremental backup. |
| `pgarch.c` | `PgArchiverMain` | Archives completed WAL segments (archive_command / archive_library). |
| `syslogger.c` | `SysLoggerMain` | Rotates + captures postmaster/backend stderr when `logging_collector=on`. |
| `interrupt.c` | Shared aux-process signal helpers | Not a process itself — the signal handlers shared across aux processes. |

## Bgworker registration

Extensions and core code both use `RegisterBackgroundWorker` (in `postmaster/bgworker.c`):

- **Static** — called from `_PG_init` at postmaster start. Fixed slot count (`max_worker_processes` GUC).
- **Dynamic** — `RegisterDynamicBackgroundWorker` at runtime; used by parallel query (from a backend) and by extensions.

Bgworkers have flags controlling: shared-memory access, database connection, restart-on-crash policy, restart interval. See `knowledge/idioms/background-worker-startup.md` for the flag matrix and lifecycle diagram.

## Common patch shapes

### Add a startup-lifecycle hook

The scenario `add-startup-hook` (see `knowledge/scenarios/add-startup-hook.md`) covers this end-to-end. Short version:

- Hook typically lives in `PostmasterMain` (postmaster-wide) or `InitPostgres` (per-backend).
- Decide: cluster-once vs backend-per-connection.
- Existing patterns: `shared_preload_libraries` (postmaster startup), `local_preload_libraries` + `session_preload_libraries` (per-backend), `ClientAuthentication_hook` (auth-time), `emit_log_hook` (per log record).

### Add a new auxiliary process

Rare. Requires:
- New file under `src/backend/postmaster/<name>.c` with a `<Name>Main` function.
- Registration in `postmaster/postmaster.c` (grep for `StartChildProcess` / `StartAuxiliaryProcess`).
- Signal handlers (usually delegated to `interrupt.c` helpers).
- Shmem region if it exchanges data with backends (via `ShmemInit`).
- Consider whether it should restart on crash (postmaster's `HandleChildCrash`).

Note: for most "run something periodically" use cases, a **bgworker** is preferable — less core code to touch, extensions can add without a core patch.

### Add a signal / interrupt reason

- New `PROCSIGNAL_*` constant in `src/include/storage/procsignal.h`.
- Signal-dispatcher `procsignal_sigusr1_handler` case in `storage/ipc/procsignal.c`.
- Flag + `ProcessInterrupts` case in `tcop/postgres.c`.
- Setter helper if the reason is per-target-backend (e.g. `procsignal_ProcSendSignal(pid, PROCSIG_...)`)`.
- Docs for what "kills" or "cancels" this new interrupt cause.

## Pitfalls

- **Fork copies memory but not open file descriptors semantically** — a `palloc` before fork is fine (COW), but a `dsm_attach` before fork is not (the child would double-detach). This is why aux processes and bgworkers do shmem init in their own Main, not inherited state.
- **Signal handlers cannot log via ereport** — that's `elog(LOG, ...)` calls internally allocating in `ErrorContext`, which is not async-signal-safe. Set a flag, return, let the main loop pick it up via `CHECK_FOR_INTERRUPTS`.
- **`InitPostgres` reads pg_authid + pg_database + role/db GUC settings BEFORE the user has issued any SQL** — extensions in `_PG_init` need to be careful about assuming database context is complete.
- **`shared_preload_libraries` vs `session_preload_libraries` vs `local_preload_libraries`** — different postmaster/backend load points; different capabilities (shmem allocation is only possible from `shared_preload_libraries`).
- **Bgworker signal setup** — a bgworker inherits SIG_IGN/SIG_DFL from postmaster. It MUST reset signal handlers in its Main via `pqsignal` calls before doing any interruptible work.
- **`proc_exit` vs `_exit` vs `abort`** — `proc_exit(0)` runs registered callbacks (releases locks, detaches shmem, closes files); `_exit` skips them; `abort` (PANIC) triggers a cluster-wide restart. Never call `_exit` in a place that's holding a lock.
- **`EXEC_BACKEND` builds are Windows-native but also used for testing on Unix** — a patch that "works" on your Linux dev box may still fail EXEC_BACKEND CI because the fork-then-exec path is different. Test with `-DEXEC_BACKEND` locally when touching startup code.

## Related corpus

- **Subsystems**: `tcop` (the query loop side), `main` (backend entry), `libpq-backend` (auth handshake), `access-transam` (WAL / xact IDs, needed at startup).
- **Idioms**: `background-worker-startup`, `apply-worker-loop`, `process-utility-hook-chain`, `abort-transaction-cleanup`, `crash-recovery-startup`.
- **Data structures**: `pgproc-fields` (the per-backend PGPROC slot in shmem).
- **Scenarios**: `add-startup-hook`, `add-new-bgworker`.
- **File docs**: 20 files under `knowledge/files/src/backend/postmaster/` + `src/backend/tcop/`.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --scenario add-startup-hook
python3 scripts/corpus-chain.py --file src/backend/tcop/postgres.c
python3 scripts/corpus-chain.py --file src/backend/postmaster/postmaster.c
```

Third command in particular surfaces the full 20-file neighborhood of the postmaster tree.

## Boundary

**Use this skill** for backend/aux/bgworker/postmaster lifecycle questions.

**Don't use** for:
- **libpq / client-side driver** — that's `src/interfaces/libpq/`; different codebase, different lifecycle.
- **Individual SQL commands' handling** — that's `tcop` (dispatch) + `commands/` (per-statement).
- **GUC config loading** — use `gucs-config` skill; touches lifecycle but focused on the config side.
- **Extension `_PG_init` details** — use `bgworker-and-extensions`; this skill covers the invocation timing, not the extension-authoring surface.
