# Iteration 1 — answers (with_skill vs baseline)

## Eval 1 — Periodic 30s bgworker scanning pg_stat_activity

### with_skill answer

Files / structure for `contrib/idle_killer`:

- `idle_killer.c` — implements `_PG_init` (registers worker) and `idle_killer_main` (worker entry).
- `idle_killer.control` and `idle_killer--1.0.sql` — extension metadata (covered by `extension-development` skill).
- Add to `shared_preload_libraries` so `_PG_init` fires during postmaster startup.

In `_PG_init` use **static registration** (because we need it from `shared_preload_libraries`):

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
- NOT `BGWORKER_CLASS_PARALLEL` — that's reserved for parallel-query workers.
[verified-by-code `source/src/include/postmaster/bgworker.h:50-75`]

`bgw_start_time = BgWorkerStart_RecoveryFinished` because pg_stat_activity scanning only makes sense once we're past recovery. [verified-by-code `source/src/include/postmaster/bgworker.h:84-89`]

`bgw_restart_time = 10` — restart 10s after a crash. A clean `proc_exit(0)` retires the slot regardless of this value; only `proc_exit(1)` / crash triggers the restart. [from-comment `source/src/include/postmaster/bgworker.h:14-27`]

Worker main function (signature is `pg_noreturn PGDLLEXPORT void idle_killer_main(Datum)`):

```c
void
idle_killer_main(Datum main_arg)
{
    /* 1. Signal handlers BEFORE unblocking. */
    pqsignal(SIGHUP,  SignalHandlerForConfigReload);
    pqsignal(SIGTERM, die);
    BackgroundWorkerUnblockSignals();

    /* 2. Connect to a DB (requires BGWORKER_BACKEND_DATABASE_CONNECTION flag). */
    BackgroundWorkerInitializeConnection("postgres", NULL, 0);

    for (;;)
    {
        int rc = WaitLatch(MyLatch,
                           WL_LATCH_SET | WL_TIMEOUT | WL_EXIT_ON_PM_DEATH,
                           30 * 1000L,           /* 30 seconds */
                           PG_WAIT_EXTENSION);
        ResetLatch(MyLatch);
        CHECK_FOR_INTERRUPTS();

        if (ConfigReloadPending)
        {
            ConfigReloadPending = false;
            ProcessConfigFile(PGC_SIGHUP);
        }

        /* Open a transaction, SPI_connect, run a SELECT against
           pg_stat_activity WHERE state='idle in transaction' AND
           now() - state_change > '10s'::interval, log matches via ereport. */
        StartTransactionCommand();
        SPI_connect();
        /* SPI_execute(...); iterate SPI_tuptable. */
        SPI_finish();
        CommitTransactionCommand();
    }
}
```

Hard rules being honored:
- WaitLatch with `WL_EXIT_ON_PM_DEATH` — without it an orphaned worker would survive postmaster death. NO `sleep()` / `usleep()`.
- `BackgroundWorkerInitializeConnection` called exactly once, AFTER `BackgroundWorkerUnblockSignals()`.
- SQL runs inside a StartTransactionCommand / CommitTransactionCommand pair, via SPI.
- `CHECK_FOR_INTERRUPTS()` inside the loop so SIGTERM/cancel can break out.
- `PG_WAIT_EXTENSION` for the wait-event class (so pg_stat_activity can attribute the wait).
[verified-by-code `source/src/test/modules/worker_spi/worker_spi.c:159-225`]

Canonical example to copy from: `source/src/test/modules/worker_spi/`.

### baseline answer

I'd create a `contrib/idle_killer` extension. In `_PG_init` I call `RegisterBackgroundWorker` with a `BackgroundWorker` struct describing the worker. Important fields: `bgw_name`, `bgw_library_name` (the .so), `bgw_function_name` (entry function), `bgw_start_time` (probably "after recovery finished"), `bgw_restart_time` (some number of seconds), `bgw_flags`. I'd set a flag asking for database connection — I believe it's `BGWORKER_BACKEND_DATABASE_CONNECTION`, and probably also a shared-memory-access flag. The main function takes a `Datum` and should install signal handlers (SIGHUP, SIGTERM), unblock signals, connect to a DB via something like `BackgroundWorkerInitializeConnection`, then loop. The loop should NOT call sleep — it should wait on the process latch with a timeout so that the postmaster's death can wake it. I think the call is `WaitLatch` with some flags including LATCH_SET, TIMEOUT, and something for postmaster death. Inside the loop, run the query in a transaction, probably via SPI. I don't remember the exact names of all the flags (POSTMASTER_DEATH? PM_DEATH? EXIT_ON_PM_DEATH?), or the exact prototype of the entry function.

---

## Eval 2 — Layering planner_hook from _PG_init

### with_skill answer

`_PG_init` is called by `internal_load_library()` after the magic-block check at `source/src/backend/utils/fmgr/dfmgr.c:297-299`. It's invoked exactly once per backend per `.so`, when the library is first loaded — either via `shared_preload_libraries` at postmaster startup or lazily on first use of a function from that library.

The canonical hook-chain pattern:

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

    /* ... my modifications / logging of `result` ... */
    return result;
}

void
_PG_init(void)
{
    /* Save previous, chain ours on top. */
    prev_planner_hook = planner_hook;
    planner_hook      = my_planner;
}
```

Three rules of the pattern:
1. Save the previous value (so chain composes — the previous extension expects to still be called).
2. Call either `prev_planner_hook` (if non-NULL) or the `standard_planner` default — never both, never neither.
3. Decide whether your work goes BEFORE or AFTER the chained call (audit logging is after — you want the final plan).
[verified-by-code `source/contrib/pg_stat_statements/pg_stat_statements.c:279,482-483,924-928`]

Hook prototype must match `planner_hook_type` exactly:
[verified-by-code `source/src/include/optimizer/planner.h:28-33`]

```c
typedef PlannedStmt *(*planner_hook_type) (Query *parse,
                                           const char *query_string,
                                           int cursorOptions,
                                           ParamListInfo boundParams,
                                           ExplainState *es);
```

(Five parameters — `ExplainState *es` is the last one. Easy to miss if you're writing from memory.)

Unload story — three sub-points:

1. **There is no `_PG_fini`.** PG's dynamic-loader (`dfmgr.c`) calls `_PG_init` after the magic-block check (line 297), but never calls a teardown function. Libraries loaded into a backend are **never unloaded** for the life of that backend. So once your hook is installed, it stays installed.

2. **`DROP EXTENSION` doesn't unload the .so.** Dropping the extension removes its SQL-level catalog entries (the function bindings created by the install script). It does NOT unload the shared library — `_PG_init` already ran and your hook is still wired in. New backends will still load the .so if it's in `shared_preload_libraries`. If it's only in `session_preload_libraries` / `local_preload_libraries`, a fresh backend simply won't load it.

3. **Postmaster shutdown.** Each backend exits; OS reclaims the .so. The hook variable is a process-local; no global cleanup needed.

Other commonly chained hooks (same save-previous-then-install pattern, all in the relevant header):
`ProcessUtility_hook`, `ExecutorStart_hook`, `ExecutorRun_hook`, `ExecutorFinish_hook`, `ExecutorEnd_hook`, `emit_log_hook`, `shmem_request_hook`, `shmem_startup_hook`.

### baseline answer

In `_PG_init` you save the current `planner_hook` to a static variable, then assign your own function to `planner_hook`. Your function's signature must match the `planner_hook_type` typedef from `optimizer/planner.h` — something like `PlannedStmt *(*)(Query *, const char *, int, ParamListInfo)`. Inside your hook, you call the saved previous hook if non-NULL, otherwise fall back to `standard_planner`, then optionally inspect / log / mutate the returned plan tree.

Unload story: PG extensions generally don't have a clean unload path. `DROP EXTENSION` removes the SQL bindings but the shared library stays loaded in the backend until the backend exits. There's no `_PG_fini` that I know of — once your `_PG_init` ran, your hook is installed for the life of every backend that loaded the library. On postmaster shutdown each backend exits and the OS unmaps the .so.

I don't remember if the planner_hook signature has 4 or 5 parameters in the current source — there may have been an addition recently (something like an `ExplainState`?). The chain pattern is correct regardless.

---

## Eval 3 — Why `die` for SIGTERM and `SignalHandlerForConfigReload` for SIGHUP

### with_skill answer

**SIGTERM: why `die` is correct**

`die` is the standard PG SIGTERM handler defined at `source/src/backend/tcop/postgres.c:3023-3058`. It does the minimum signal-safe thing:
- Sets `ProcDiePending = true` and `InterruptPending = true`.
- Records the sender PID.
- Calls `SetLatch(MyLatch)` to wake any pending WaitLatch.
- Returns immediately.

The actual exit happens later in `ProcessInterrupts()` (called from `CHECK_FOR_INTERRUPTS()`), inside the main loop, OUTSIDE the signal-handler context. By then it's safe to:
- Abort an open transaction (`AbortCurrentTransaction()`).
- Run `proc_exit` callbacks (release locks, flush stats, unregister shmem, etc.).
- Walk longjmp-style error cleanup.

**What goes wrong with a custom `proc_exit(0)` in the handler:**

1. **Signal-unsafe operations.** `proc_exit()` runs atexit-style callbacks: shmem detach, lock-table cleanup, stats flush, snapshot release. Many of these `palloc`, take LWLocks, or write to syscache. **None of that is async-signal-safe.** Hitting SIGTERM mid-`malloc` would deadlock the allocator.
2. **Open transaction left dangling.** If we exit straight from the handler we never run `AbortCurrentTransaction()`. The transaction's locks, snapshots, and resowner state get cleaned up by ipc-level callbacks in an inconsistent order — some buffer pins or LWLocks may leak briefly or trigger asserts in debug builds.
3. **`proc_exit(0)` retires the slot.** Even if it worked, return code 0 means "clean exit, do not restart" per the postmaster's logic at `source/src/include/postmaster/bgworker.h:14-27`. SIGTERM from a `pg_ctl stop` is "clean" by definition; SIGTERM from a `TerminateBackgroundWorker()` is also clean. But SIGTERM during a transient situation (e.g. someone DROPped our DB and we have `BGWORKER_INTERRUPTIBLE`) would also kill us forever — `bgw_restart_time` becomes moot.

The right pattern is **always**: trip a flag in the signal handler, do the real work in the main loop after `CHECK_FOR_INTERRUPTS()` notices. That's exactly what `die` implements.

**SIGHUP: why `SignalHandlerForConfigReload`**

Same reason. `SignalHandlerForConfigReload` (in `source/src/backend/postmaster/interrupt.c:60-65`) is two lines: `ConfigReloadPending = true; SetLatch(MyLatch);`. Both are async-signal-safe. The actual `ProcessConfigFile(PGC_SIGHUP)` is called from the main loop body when `ConfigReloadPending` is observed.

Why not call `ProcessConfigFile()` from the handler itself? `ProcessConfigFile` opens files, allocates memory through palloc, takes locks on GUC state, may report errors via `ereport`. All of that is signal-unsafe. A SIGHUP delivered mid-`palloc` would corrupt the allocator. The flag-and-latch pattern is the only safe shape.

The general rule: **the only things you can safely do in a PG signal handler are set a `sig_atomic_t`-style flag, set the latch, and (sometimes) record the sender PID.** Anything else lives in the main loop.

### baseline answer

`die` is the standard SIGTERM handler shared by regular backends and bgworkers. It's signal-safe — it sets `ProcDiePending = true`, sets the latch, and returns. The actual exit happens later when the backend hits `CHECK_FOR_INTERRUPTS()` and `ProcessInterrupts()` notices the flag and calls `proc_exit`.

If you replaced it with a handler that calls `proc_exit(0)` directly, several things go wrong:
- `proc_exit` runs callbacks that release shared-memory state, take locks, flush stats — none of that is async-signal-safe, so you'd risk deadlocks or corruption.
- An open transaction would not be cleanly aborted (no `AbortCurrentTransaction()` path).
- `proc_exit(0)` means "clean exit, do not restart" per the bgworker contract — even on transient SIGTERMs the worker would never come back.

For SIGHUP and `SignalHandlerForConfigReload`: same idea. The handler just sets `ConfigReloadPending = true` and the latch; the main loop calls `ProcessConfigFile(PGC_SIGHUP)` when convenient. You don't call `ProcessConfigFile` from inside the handler because it does allocation, file I/O, locking, ereport — all signal-unsafe.

General PG rule: signal handlers set flags and the latch; the main loop does the actual work after observing the flag.
