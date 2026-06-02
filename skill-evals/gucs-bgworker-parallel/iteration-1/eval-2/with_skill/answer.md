# One-shot dynamic background worker

## Registration API

From a regular backend at runtime, use **`RegisterDynamicBackgroundWorker`**
(not `RegisterBackgroundWorker`, which is only callable from `_PG_init`
when `process_shared_preload_libraries_in_progress` is true).

It returns a `BackgroundWorkerHandle*` via its out-parameter — that
handle is the only way to later query / wait on / terminate the worker.

[verified-by-code `source/src/include/postmaster/bgworker.h:122-133`]

## Make it never restart

Two interacting knobs decide restart:

1. **`bgw_restart_time = BGW_NEVER_RESTART`** (`-1`) on the
   `BackgroundWorker` struct — postmaster will never re-fork the worker
   on exit, regardless of exit code.
2. **Return 0 / `proc_exit(0)`** from the worker's main function —
   even with a finite `bgw_restart_time`, a clean exit code of 0
   permanently retires the worker and frees the slot. Exit code 1 (or
   crash) would otherwise trigger restart.

For a migration helper the belt-and-braces approach is to set
`BGW_NEVER_RESTART` *and* return 0.

[from-comment `source/src/include/postmaster/bgworker.h:14-27`]

## BackgroundWorker fields

```c
BackgroundWorker worker;

memset(&worker, 0, sizeof(worker));
snprintf(worker.bgw_name, BGW_MAXLEN, "myext migration");
snprintf(worker.bgw_type, BGW_MAXLEN, "myext migration");
worker.bgw_flags        = BGWORKER_SHMEM_ACCESS
                        | BGWORKER_BACKEND_DATABASE_CONNECTION;
worker.bgw_start_time   = BgWorkerStart_RecoveryFinished;
worker.bgw_restart_time = BGW_NEVER_RESTART;
sprintf(worker.bgw_library_name,  "myext");
sprintf(worker.bgw_function_name, "myext_migration_main");
worker.bgw_main_arg     = Int32GetDatum(0);
worker.bgw_notify_pid   = MyProcPid;          /* so we get SIGUSR1 */

BackgroundWorkerHandle *handle;
if (!RegisterDynamicBackgroundWorker(&worker, &handle))
    ereport(ERROR,
            (errcode(ERRCODE_CONFIGURATION_LIMIT_EXCEEDED),
             errmsg("could not register background worker"),
             errhint("Consider raising max_worker_processes.")));
```

Key fields:
- `bgw_flags`: `BGWORKER_SHMEM_ACCESS` + `BGWORKER_BACKEND_DATABASE_CONNECTION`
  if the migration runs SQL.
- `bgw_library_name` / `bgw_function_name`: the .so and the
  `PGDLLEXPORT void f(Datum)` symbol postmaster will jump to.
- `bgw_notify_pid = MyProcPid`: postmaster sends the launcher SIGUSR1
  on worker start and stop transitions.

[verified-by-code `source/src/include/postmaster/bgworker.h:96-108`;
`source/src/test/modules/worker_spi/worker_spi.c:362-385`]

## Launcher-side wait API

Holding the `handle`, the launcher can:

- `WaitForBackgroundWorkerStartup(handle, &pid)` — block until worker
  is actually running, returns its PID.
- `WaitForBackgroundWorkerShutdown(handle)` — block until exit. This
  is the one you want for a "fire and join" migration:

```c
pid_t pid;
WaitForBackgroundWorkerStartup(handle, &pid);
/* worker is running now ... */
WaitForBackgroundWorkerShutdown(handle);
/* worker has exited; slot is freed */
```

`bgw_notify_pid = MyProcPid` is what makes these wait calls work
efficiently — without it they'd have to poll.

- `GetBackgroundWorkerPid(handle, &pid)` for non-blocking status.
- `TerminateBackgroundWorker(handle)` to SIGTERM it (no restart).

[verified-by-code `source/src/include/postmaster/bgworker.h:128-137`]

## Worker main skeleton

```c
pg_noreturn PGDLLEXPORT void myext_migration_main(Datum main_arg);

void
myext_migration_main(Datum main_arg)
{
    pqsignal(SIGHUP,  SignalHandlerForConfigReload);
    pqsignal(SIGTERM, die);
    BackgroundWorkerUnblockSignals();

    BackgroundWorkerInitializeConnection("mydb", NULL, 0);

    StartTransactionCommand();
    /* ... do the migration ... */
    CommitTransactionCommand();

    proc_exit(0);   /* clean exit → never restarted */
}
```

Note `pg_noreturn PGDLLEXPORT void f(Datum)` is the required signature.
Signal handlers must be installed *before* `BackgroundWorkerUnblockSignals`.

## Why dynamic, not static

Static `RegisterBackgroundWorker` can only be called from `_PG_init`
when `process_shared_preload_libraries_in_progress` is true — i.e. when
the library is in `shared_preload_libraries`. From a regular backend
(e.g. inside a user-callable function) only the dynamic API works.
