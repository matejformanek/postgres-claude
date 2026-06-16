# Iteration 2 — answers (with_skill vs baseline)

The 3 prompts are unchanged from iter-1. The with_skill answer now uses the updated SKILL.md (Edits 1, 2/local_preload, 3, 4, 5 applied). The baseline cohort is the same general PG knowledge as iter-1.

## Eval 1 — Periodic 30s bgworker scanning pg_stat_activity

### with_skill answer

Files / structure for `contrib/idle_killer`:

- `idle_killer.c` — implements `_PG_init` (registers worker) and `idle_killer_main` (worker entry).
- `idle_killer.control` and `idle_killer--1.0.sql` — extension metadata (covered by `extension-development` skill).
- Add to `shared_preload_libraries` so `_PG_init` fires during postmaster startup.

`_PG_init` uses **static registration** (because we need it from `shared_preload_libraries`):

```c
void
_PG_init(void)
{
    BackgroundWorker worker;

    /* GUCs (DefineCustomIntVariable for naptime / idle_threshold), then guard. */
    if (!process_shared_preload_libraries_in_progress)
        return;

    memset(&worker, 0, sizeof(worker));
    snprintf(worker.bgw_name, BGW_MAXLEN, "idle_killer");
    snprintf(worker.bgw_type, BGW_MAXLEN, "idle_killer");
    worker.bgw_flags        = BGWORKER_SHMEM_ACCESS
                            | BGWORKER_BACKEND_DATABASE_CONNECTION;
    worker.bgw_start_time   = BgWorkerStart_RecoveryFinished;
    worker.bgw_restart_time = 10;          /* restart after 10s on crash */
    sprintf(worker.bgw_library_name,  "idle_killer");
    sprintf(worker.bgw_function_name, "idle_killer_main");
    worker.bgw_main_arg     = (Datum) 0;
    worker.bgw_notify_pid   = 0;            /* nobody to notify */
    RegisterBackgroundWorker(&worker);
}
```

Flags chosen:
- `BGWORKER_SHMEM_ACCESS` — required, every worker needs it.
- `BGWORKER_BACKEND_DATABASE_CONNECTION` — we'll connect via SPI to read pg_stat_activity.
- NOT `BGWORKER_INTERRUPTIBLE` — we don't want to die on CREATE/ALTER/DROP of our DB.
- NOT `BGWORKER_CLASS_PARALLEL` — reserved for parallel-query workers.
[verified-by-code `source/src/include/postmaster/bgworker.h:50-75`]

`bgw_start_time = BgWorkerStart_RecoveryFinished` — pg_stat_activity scanning only makes sense once we're past recovery.
[verified-by-code `source/src/include/postmaster/bgworker.h:84-89`]

`bgw_restart_time = 10` — restart 10s after a crash. A clean `proc_exit(0)` retires the slot regardless of this value; only `proc_exit(1)` / crash triggers restart.
[from-comment `source/src/include/postmaster/bgworker.h:14-27`]

Worker main (`pg_noreturn PGDLLEXPORT void idle_killer_main(Datum)`):

```c
void
idle_killer_main(Datum main_arg)
{
    pqsignal(SIGHUP,  SignalHandlerForConfigReload);
    pqsignal(SIGTERM, die);
    BackgroundWorkerUnblockSignals();

    BackgroundWorkerInitializeConnection("postgres", NULL, 0);

    for (;;)
    {
        int rc = WaitLatch(MyLatch,
                           WL_LATCH_SET | WL_TIMEOUT | WL_EXIT_ON_PM_DEATH,
                           30 * 1000L,
                           PG_WAIT_EXTENSION);
        ResetLatch(MyLatch);
        CHECK_FOR_INTERRUPTS();

        if (ConfigReloadPending)
        {
            ConfigReloadPending = false;
            ProcessConfigFile(PGC_SIGHUP);
        }

        StartTransactionCommand();
        SPI_connect();
        /* SPI_execute("SELECT ... FROM pg_stat_activity WHERE state='idle in transaction'
            AND now() - state_change > '10s'::interval", true, 0);
           Iterate SPI_tuptable, ereport(LOG, ...) per offender. */
        SPI_finish();
        CommitTransactionCommand();
    }
}
```

Hard rules honored: WaitLatch with `WL_EXIT_ON_PM_DEATH` (no `sleep()`); signal handlers installed BEFORE `BackgroundWorkerUnblockSignals()`; `BackgroundWorkerInitializeConnection` called exactly once after unblocking; SQL inside `StartTransactionCommand` / `CommitTransactionCommand` pair via SPI; `CHECK_FOR_INTERRUPTS()` inside loop body; `PG_WAIT_EXTENSION` for the wait-event class.
[verified-by-code `source/src/test/modules/worker_spi/worker_spi.c:159-225`]

Canonical example: `source/src/test/modules/worker_spi/`.

### baseline answer

(Same as iter-1; baseline didn't change.) `_PG_init` calls `RegisterBackgroundWorker` with a `BackgroundWorker` struct describing the worker. Important fields: `bgw_name`, `bgw_library_name`, `bgw_function_name`, `bgw_start_time` ("after recovery finished"), `bgw_restart_time`, `bgw_flags`. Flag for DB connection is `BGWORKER_BACKEND_DATABASE_CONNECTION` plus probably a shared-memory-access flag. The main function takes a `Datum`, installs SIGHUP and SIGTERM handlers, unblocks signals, connects to a DB via `BackgroundWorkerInitializeConnection`, then loops. Loop must NOT sleep — wait on the process latch with timeout. I think `WaitLatch` flags include LATCH_SET, TIMEOUT, and something for postmaster death (not sure if it's POSTMASTER_DEATH, PM_DEATH, or EXIT_ON_PM_DEATH). SQL via SPI, in a transaction.

---

## Eval 2 — Layering planner_hook from _PG_init

### with_skill answer

`_PG_init` is called by the dynamic loader at `source/src/backend/utils/fmgr/dfmgr.c:295-299` after the magic-block check. It runs exactly once per backend per `.so` — either via `shared_preload_libraries` at postmaster startup, `session_preload_libraries` on backend startup, or `local_preload_libraries` on backend startup by an unprivileged user.

Canonical hook-chain pattern:

```c
#include "optimizer/planner.h"

static planner_hook_type prev_planner_hook = NULL;

static PlannedStmt *
my_planner(Query *parse, const char *query_string,
           int cursorOptions, ParamListInfo boundParams,
           ExplainState *es)
{
    PlannedStmt *result;

    if (prev_planner_hook)
        result = prev_planner_hook(parse, query_string,
                                   cursorOptions, boundParams, es);
    else
        result = standard_planner(parse, query_string,
                                  cursorOptions, boundParams, es);

    /* audit-log `result` here — after the chained call so we see
       the final plan a downstream hook (if any) produced. */
    return result;
}

void
_PG_init(void)
{
    prev_planner_hook = planner_hook;
    planner_hook      = my_planner;
}
```

Three rules: save the previous value; call `prev_planner_hook` (if non-NULL) or `standard_planner`, never both/neither; decide BEFORE vs AFTER the chained call (audit-logging belongs AFTER — final plan).

Prototype matches `planner_hook_type` exactly — **five parameters** with `ExplainState *es` trailing:
[verified-by-code `source/src/include/optimizer/planner.h:28-32`]

```c
typedef PlannedStmt *(*planner_hook_type) (Query *parse,
                                           const char *query_string,
                                           int cursorOptions,
                                           ParamListInfo boundParams,
                                           ExplainState *es);
```

Unload story:

1. **No `_PG_fini`.** `dfmgr.c:295-299` `dlsym`s `_PG_init` and calls it once; PG never unloads the library for the life of the backend.
2. **`DROP EXTENSION` doesn't unload the .so.** It removes the SQL-level catalog bindings (functions registered by the install script) but `_PG_init` already ran — your hook is still wired in. Backends that load the library at startup (via `shared_preload_libraries`) will still load it for new sessions.
3. **Postmaster shutdown.** Each backend exits and the OS unmaps the .so. The hook variable is process-local; no global cleanup needed.

Other chainable hooks (same save-previous-then-install pattern): `ProcessUtility_hook`, `ExecutorStart_hook`, `ExecutorRun_hook`, `ExecutorFinish_hook`, `ExecutorEnd_hook`, `emit_log_hook`, `shmem_request_hook`, `shmem_startup_hook`.

### baseline answer

(Same as iter-1.) Save current `planner_hook` to a static; assign your own. Inside the hook, call the saved previous hook if non-NULL else `standard_planner`. The signature matches `planner_hook_type` from `optimizer/planner.h` — I think it has 4 or 5 parameters; I recall a recent addition of something like `ExplainState`. Unload story: no `_PG_fini`, library stays loaded for life of backend, `DROP EXTENSION` removes SQL bindings but doesn't unload the .so, on postmaster shutdown OS unmaps each backend's libraries.

---

## Eval 3 — Why `die` for SIGTERM and `SignalHandlerForConfigReload` for SIGHUP

### with_skill answer

**SIGTERM: why `die` is correct.**

`die` (`source/src/backend/tcop/postgres.c:3023-3058`) is signal-safe: it sets `ProcDiePending = true`, `InterruptPending = true`, records sender PID, calls `SetLatch(MyLatch)`, returns. The actual exit happens later in `ProcessInterrupts()` (via `CHECK_FOR_INTERRUPTS()`), out of signal-handler context — which is when it's safe to:
- `AbortCurrentTransaction()`.
- Run `proc_exit` callbacks (release locks, flush stats, unregister shmem, etc.).
- Walk longjmp error-cleanup.

**What goes wrong with a custom `proc_exit(0)` handler:**

1. **Signal-unsafe operations** — `proc_exit` runs atexit callbacks that `palloc`, take LWLocks, write to syscache; none of that is async-signal-safe. SIGTERM mid-`malloc` deadlocks the allocator.
2. **Open transaction dangling** — no `AbortCurrentTransaction()` path; resowner / lock / snapshot state get cleaned up by ipc-level callbacks in inconsistent order; assert failures possible in debug builds.
3. **`proc_exit(0)` retires the slot** — per `source/src/include/postmaster/bgworker.h:14-27`, return code 0 means "clean exit, do not restart". Even transient SIGTERMs would kill the worker forever regardless of `bgw_restart_time`.

The right pattern: trip a flag in the handler, do the work in the main loop after `CHECK_FOR_INTERRUPTS()` observes it. That's exactly what `die` implements.

**SIGHUP: why `SignalHandlerForConfigReload`.**

Two lines (`source/src/backend/postmaster/interrupt.c:60-65`): `ConfigReloadPending = true; SetLatch(MyLatch);`. Both async-signal-safe. The real `ProcessConfigFile(PGC_SIGHUP)` runs in the main loop when `ConfigReloadPending` is observed.

Calling `ProcessConfigFile` from the handler itself would open files, palloc, take GUC locks, possibly `ereport` — all signal-unsafe. SIGHUP mid-`palloc` corrupts the allocator. Flag-and-latch is the only safe shape.

**General rule:** in a PG signal handler you may set a `sig_atomic_t`-style flag, call `SetLatch(MyLatch)`, and (sometimes) record the sender PID. Nothing else. Everything else lives in the main loop.

### baseline answer

(Same as iter-1.) `die` is the standard SIGTERM handler — signal-safe, sets `ProcDiePending` + latch + returns. Real exit via `CHECK_FOR_INTERRUPTS` / `ProcessInterrupts` / `proc_exit`. A custom `proc_exit(0)` handler is wrong because: signal-unsafe (palloc / LWLocks / stats flush), skips `AbortCurrentTransaction`, and exit 0 retires the slot forever per the bgworker contract. `SignalHandlerForConfigReload` is the same idea — sets `ConfigReloadPending` + latch, main loop calls `ProcessConfigFile(PGC_SIGHUP)`. General rule: signal handlers flip flags + set latch only; everything else in the main loop.
