# One-shot dynamic background worker

## Registration API — must be dynamic

Use `RegisterDynamicBackgroundWorker(&worker, &handle)`. The static
`RegisterBackgroundWorker` errors out unless called from `_PG_init`
during shared-library preload (`process_shared_preload_libraries_in_progress`
is true) — a regular backend at runtime cannot use it.
[verified-by-code `source/src/include/postmaster/bgworker.h:122-133`]

## BackgroundWorker fields

```c
BackgroundWorker worker;
BackgroundWorkerHandle *handle;
pid_t pid;

memset(&worker, 0, sizeof(worker));
snprintf(worker.bgw_name, BGW_MAXLEN, "myext migration");
snprintf(worker.bgw_type, BGW_MAXLEN, "myext migration");
worker.bgw_flags        = BGWORKER_SHMEM_ACCESS
                        | BGWORKER_BACKEND_DATABASE_CONNECTION;
worker.bgw_start_time   = BgWorkerStart_RecoveryFinished;
worker.bgw_restart_time = BGW_NEVER_RESTART;          /* -1 */
sprintf(worker.bgw_library_name,  "myext");
sprintf(worker.bgw_function_name, "myext_migration_main");
worker.bgw_main_arg     = (Datum) 0;
worker.bgw_notify_pid   = MyProcPid;                  /* SIGUSR1 to us */

if (!RegisterDynamicBackgroundWorker(&worker, &handle))
    ereport(ERROR, (errmsg("could not register background worker")));
```

[verified-by-code `source/src/include/postmaster/bgworker.h:96-108`;
`source/src/test/modules/worker_spi/worker_spi.c:362-385`]

## Belt-and-suspenders against restart

Two knobs cooperate (§2.5):

| `bgw_restart_time` | Worker exit | Restarted? |
|---|---|---|
| `BGW_NEVER_RESTART` (`-1`) | any | No — slot freed |
| N seconds | `proc_exit(0)` | No — clean exit retires slot |
| N seconds | `proc_exit(1)` | Yes after N seconds |
| N seconds | crash | Yes after N seconds |

For a one-shot worker: set `bgw_restart_time = BGW_NEVER_RESTART`, and
end the worker main with `proc_exit(0)`. Either condition alone
disables restart, but doing both makes the intent explicit.
[from-comment `source/src/include/postmaster/bgworker.h:14-27`]

## Joining from the launcher

`bgw_notify_pid = MyProcPid` makes the postmaster send the launcher
**SIGUSR1** on each start/stop transition, which is what lets the wait
calls return promptly instead of polling. With the handle:

- `WaitForBackgroundWorkerStartup(handle, &pid)` — block until running.
- `WaitForBackgroundWorkerShutdown(handle)` — block until exit.
- `GetBackgroundWorkerPid(handle, &pid)` — non-blocking probe.
- `TerminateBackgroundWorker(handle)` — SIGTERM, no restart.

For a fire-and-join migration:

```c
WaitForBackgroundWorkerStartup(handle, &pid);
WaitForBackgroundWorkerShutdown(handle);
```

[verified-by-code `source/src/include/postmaster/bgworker.h:128-137`]

## Worker main function

```c
pg_noreturn PGDLLEXPORT void myext_migration_main(Datum main_arg);

void
myext_migration_main(Datum main_arg)
{
    /* Signal handlers BEFORE unblocking. */
    pqsignal(SIGHUP,  SignalHandlerForConfigReload);
    pqsignal(SIGTERM, die);
    BackgroundWorkerUnblockSignals();

    BackgroundWorkerInitializeConnection("mydb", NULL, 0);

    StartTransactionCommand();
    /* ... do the migration ... */
    CommitTransactionCommand();

    proc_exit(0);   /* clean — slot retired, no restart */
}
```

[verified-by-code `source/src/test/modules/worker_spi/worker_spi.c:134-225`]

## Checklist hits (§2.8)

- [x] `bgw_flags` has `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`.
- [x] `bgw_library_name` / `bgw_function_name` set.
- [x] Main fn is `pg_noreturn PGDLLEXPORT void f(Datum)`.
- [x] Signal handlers installed before `BackgroundWorkerUnblockSignals`.
- [x] `BackgroundWorkerInitializeConnection` once after unblocking.
- [x] Restart explicit: `BGW_NEVER_RESTART` + `proc_exit(0)`.
