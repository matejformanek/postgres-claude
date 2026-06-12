---
name: bgworker-and-extensions
description: Background workers + extension entry-point integration in PostgreSQL — RegisterBackgroundWorker (static) vs RegisterDynamicBackgroundWorker (runtime), BackgroundWorker struct (bgw_flags BGWORKER_SHMEM_ACCESS / BGWORKER_BACKEND_DATABASE_CONNECTION, bgw_start_time, bgw_restart_time, bgw_main_arg, bgw_notify_pid), BackgroundWorkerInitializeConnection, signal handler skeleton (SignalHandlerForConfigReload + die), WaitLatch idiom with WL_EXIT_ON_PM_DEATH, GetBackgroundWorkerPid / WaitForBackgroundWorkerStartup / TerminateBackgroundWorker. Use whenever a patch or extension registers a bgworker, changes worker lifecycle, or layers hooks on top of an existing _PG_init. Skip generic worker-pool / job-queue questions.
when_to_load: Register a background worker (static or dynamic); write a worker main function; layer extension hooks (`ProcessUtility_hook`, `planner_hook`, `ExecutorStart_hook`) on top of an existing _PG_init.
companion_skills:
  - gucs-config
  - parallel-query
  - extension-development
  - locking
  - coding-style
---

# bgworker-and-extensions — background workers + extension integration

This is the procedural cookbook for registering and writing PostgreSQL
background workers and for layering extension hooks on the postmaster
lifecycle. For the conceptual model see
`knowledge/idioms/bgworker-and-parallel.md`.

This skill is one of three siblings that share the `_PG_init` /
postmaster-lifecycle boundary:
- `gucs-config` — custom GUC variables.
- **bgworker-and-extensions** (this skill) — background workers + hooks.
- `parallel-query` — ParallelContext + parallel-safe markings.

## 1. Static vs dynamic registration

| API | Where to call | Restart? |
|---|---|---|
| `RegisterBackgroundWorker(&w)` | `_PG_init`, only when `process_shared_preload_libraries_in_progress` | Yes per `bgw_restart_time` |
| `RegisterDynamicBackgroundWorker(&w, &handle)` | Any backend at runtime | Yes per `bgw_restart_time`, but worker is forgotten once `handle` goes away unless re-registered |

[verified-by-code `source/src/include/postmaster/bgworker.h:122-133`]

`RegisterBackgroundWorker` errors out unless called from `_PG_init` during
shared-library preload (i.e. `process_shared_preload_libraries_in_progress`
is true). From any other site — including a regular backend at runtime —
use `RegisterDynamicBackgroundWorker` instead.

## 2. Filling the `BackgroundWorker` struct

```c
BackgroundWorker worker;

memset(&worker, 0, sizeof(worker));
snprintf(worker.bgw_name, BGW_MAXLEN, "my_ext worker %d", i);
snprintf(worker.bgw_type, BGW_MAXLEN, "my_ext");      /* shown in pg_stat_activity */
worker.bgw_flags        = BGWORKER_SHMEM_ACCESS
                        | BGWORKER_BACKEND_DATABASE_CONNECTION;
worker.bgw_start_time   = BgWorkerStart_RecoveryFinished;
worker.bgw_restart_time = BGW_NEVER_RESTART;          /* or seconds */
sprintf(worker.bgw_library_name,  "my_ext");          /* shared object name */
sprintf(worker.bgw_function_name, "my_ext_main");
worker.bgw_main_arg     = Int32GetDatum(i);
/* bgw_extra: up to BGW_EXTRALEN bytes of arbitrary blob */
worker.bgw_notify_pid   = MyProcPid;                  /* 0 = no SIGUSR1 */

RegisterBackgroundWorker(&worker);
```

[verified-by-code `source/src/include/postmaster/bgworker.h:96-108`;
`source/src/test/modules/worker_spi/worker_spi.c:362-385`]

## 3. Flag cheatsheet

[verified-by-code `source/src/include/postmaster/bgworker.h:50-75`]

| Flag | Meaning |
|---|---|
| `BGWORKER_SHMEM_ACCESS` | Required for any worker that touches shared buffers / LWLocks. |
| `BGWORKER_BACKEND_DATABASE_CONNECTION` | Worker may call `BackgroundWorkerInitializeConnection*`. Requires `SHMEM_ACCESS`. |
| `BGWORKER_INTERRUPTIBLE` | Worker exits if its DB is CREATE/ALTER/DROP'd. Requires the two above. |
| `BGWORKER_CLASS_PARALLEL` | **Don't set** — internal, counts against `max_parallel_workers`. See `parallel-query`. |

## 4. Start times

[verified-by-code `source/src/include/postmaster/bgworker.h:84-89`]

- `BgWorkerStart_PostmasterStart` — earliest. No DB access yet; replication / archive only.
- `BgWorkerStart_ConsistentState` — DB is consistent (during recovery, after WAL apply reached a consistent point). Hot-standby readers can run here.
- `BgWorkerStart_RecoveryFinished` — primary mode only, or standby promotion. This is what you usually want.

## 5. Restart policy

Two knobs decide restart; both must allow it.

| `bgw_restart_time` | Worker exit | Restarted? |
|---|---|---|
| `BGW_NEVER_RESTART` (`-1`) | any | No — slot is freed. |
| N seconds | `proc_exit(0)` (return 0) | No — clean exit retires the slot regardless of `bgw_restart_time`. |
| N seconds | `proc_exit(1)` (return 1) | Yes, after N seconds. |
| N seconds | crash / signal | Yes, after N seconds. |

[from-comment `source/src/include/postmaster/bgworker.h:14-27`]

## 6. Worker main function skeleton

```c
pg_noreturn PGDLLEXPORT void my_ext_main(Datum main_arg);

void
my_ext_main(Datum main_arg)
{
    /* Install signal handlers BEFORE unblocking signals. */
    pqsignal(SIGHUP,  SignalHandlerForConfigReload);
    pqsignal(SIGTERM, die);
    BackgroundWorkerUnblockSignals();

    /* Optional: connect to a database. Requires
       BGWORKER_BACKEND_DATABASE_CONNECTION in bgw_flags. */
    BackgroundWorkerInitializeConnection("mydb", NULL, 0);

    for (;;)
    {
        int rc = WaitLatch(MyLatch,
                           WL_LATCH_SET | WL_TIMEOUT | WL_EXIT_ON_PM_DEATH,
                           naptime_ms,
                           PG_WAIT_EXTENSION);
        ResetLatch(MyLatch);
        CHECK_FOR_INTERRUPTS();

        if (ConfigReloadPending)
        {
            ConfigReloadPending = false;
            ProcessConfigFile(PGC_SIGHUP);
        }

        /* ... do work, possibly inside StartTransactionCommand() ... */
    }
}
```

[verified-by-code `source/src/test/modules/worker_spi/worker_spi.c:134-225`]

### Hard rules inside a worker

- **Never `sleep()` / `usleep()`** — always wait on `MyLatch` with
  `WL_EXIT_ON_PM_DEATH`, otherwise an orphaned worker survives the
  postmaster's death.
- Connect to a DB only via `BackgroundWorkerInitializeConnection` /
  `BackgroundWorkerInitializeConnectionByOid` — these set up locks, xact
  state, etc. `flags` is currently `BGWORKER_BYPASS_ALLOWCONN` and/or
  `BGWORKER_BYPASS_ROLELOGINCHECK`.
  [verified-by-code `source/src/include/postmaster/bgworker.h:154-167`]
- Run SQL inside `StartTransactionCommand()` / `CommitTransactionCommand()`
  pairs, or via SPI.

## 7. Querying / terminating dynamic workers

`RegisterDynamicBackgroundWorker` returns a `BackgroundWorkerHandle*`.
With it the launcher backend can:

- `GetBackgroundWorkerPid(handle, &pid)` — non-blocking status.
- `WaitForBackgroundWorkerStartup(handle, &pid)` — block until started.
- `WaitForBackgroundWorkerShutdown(handle)` — block until exit.
- `TerminateBackgroundWorker(handle)` — SIGTERM, no restart.

If `bgw_notify_pid` is set to the launcher's PID, the launcher gets
`SIGUSR1` on worker start/stop transitions — useful with the wait calls.
[verified-by-code `source/src/include/postmaster/bgworker.h:128-137`]

## 8. Layering hooks on `_PG_init`

Extensions installed via `shared_preload_libraries` (or
`session_preload_libraries`) get their `_PG_init` called at the right
time to install hooks. The canonical pattern: save the previous hook,
install yours, call the previous one inside yours so chains compose.

```c
static planner_hook_type prev_planner_hook = NULL;

static PlannedStmt *
my_planner(Query *parse, const char *query_string,
           int cursorOptions, ParamListInfo boundParams)
{
    PlannedStmt *result;

    if (prev_planner_hook)
        result = prev_planner_hook(parse, query_string,
                                   cursorOptions, boundParams);
    else
        result = standard_planner(parse, query_string,
                                  cursorOptions, boundParams);

    /* ... my modifications to result ... */
    return result;
}

void
_PG_init(void)
{
    prev_planner_hook = planner_hook;
    planner_hook = my_planner;

    /* ... other hooks, GUCs, RegisterBackgroundWorker ... */
}
```

Common hook variables to chain (all in their respective header):
`ProcessUtility_hook`, `planner_hook`, `ExecutorStart_hook`,
`ExecutorRun_hook`, `ExecutorFinish_hook`, `ExecutorEnd_hook`,
`emit_log_hook`, `shmem_request_hook`, `shmem_startup_hook`.

## 9. Checklist

- [ ] `bgw_flags` has at minimum `BGWORKER_SHMEM_ACCESS`; add
      `BGWORKER_BACKEND_DATABASE_CONNECTION` if the worker touches a DB.
- [ ] `bgw_library_name` and `bgw_function_name` are correct strings
      (no quotes, fit in `MAXPGPATH` / `BGW_MAXLEN`).
- [ ] Main function is `pg_noreturn PGDLLEXPORT void f(Datum)`.
- [ ] Signal handlers (`SIGHUP`, `SIGTERM`) installed before
      `BackgroundWorkerUnblockSignals()`.
- [ ] Main loop waits on `MyLatch` with `WL_EXIT_ON_PM_DEATH`. No `sleep()`.
- [ ] `CHECK_FOR_INTERRUPTS()` somewhere in the loop body.
- [ ] DB-connecting workers call `BackgroundWorkerInitializeConnection*`
      *once* after unblocking signals.
- [ ] Restart policy explicit (`BGW_NEVER_RESTART` or finite seconds).
- [ ] Static registration in `_PG_init` guarded by
      `if (!process_shared_preload_libraries_in_progress) return;` before
      `RegisterBackgroundWorker`.
- [ ] Each chained hook saves the previous and invokes it (or the
      `standard_*` default) before / after its own logic.

## 10. Useful greps

- All bgworker registrations:
  `grep -RIn 'RegisterBackgroundWorker\|RegisterDynamicBackgroundWorker' source/src source/contrib`
- All hook installations:
  `grep -RIn '_hook = ' source/contrib`
- BackgroundWorker struct usage examples:
  `source/src/test/modules/worker_spi/worker_spi.c`

## Open questions / [unverified]

- `[unverified]` Whether `BGWORKER_INTERRUPTIBLE` is recommended for
  long-running general-purpose workers — most contrib examples don't
  set it.
- `[unverified]` Exact behaviour of `bgw_notify_pid` when the notify-target
  backend exits before the worker starts (likely: silently ignored).

## Cross-references

- `.claude/skills/gucs-config/SKILL.md` — custom GUCs in `_PG_init`; SIGHUP signal-handler reloads them.
- `.claude/skills/parallel-query/SKILL.md` — `BGWORKER_CLASS_PARALLEL` is NOT for extensions; this is the parallel-query worker side.
- `.claude/skills/extension-development/SKILL.md` — `.control`, install SQL, `shared_preload_libraries`, PGXS vs meson.
- `.claude/skills/locking/SKILL.md` — shmem hook + LWLock allocation for workers that need shared state.
- `.claude/skills/coding-style/SKILL.md` — `pg_noreturn`, `PGDLLEXPORT`, backend C conventions.
- `knowledge/idioms/bgworker-and-parallel.md` — conceptual model.
- `knowledge/docs-distilled/bgworker.md` — SGML-distilled reference.
- `knowledge/files/src/include/postmaster/bgworker.h.md` — per-file doc for the public API.
- `source/src/test/modules/worker_spi/` — canonical in-tree example.
