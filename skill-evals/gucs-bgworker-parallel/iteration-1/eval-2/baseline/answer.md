# One-shot dynamic background worker — baseline

For launching a background worker from a regular backend at runtime
(not from `_PG_init`), you use `RegisterDynamicBackgroundWorker`. It
takes a `BackgroundWorker` struct and an output `BackgroundWorkerHandle**`
that you'll use later to interact with the worker.

```c
BackgroundWorker worker;
BackgroundWorkerHandle *handle;

memset(&worker, 0, sizeof(worker));
snprintf(worker.bgw_name, BGW_MAXLEN, "my migration worker");
worker.bgw_flags = BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION;
worker.bgw_start_time = BgWorkerStart_RecoveryFinished;
worker.bgw_restart_time = BGW_NEVER_RESTART;  /* don't restart */
strcpy(worker.bgw_library_name, "myext");
strcpy(worker.bgw_function_name, "my_migration_main");
worker.bgw_notify_pid = MyProcPid;

RegisterDynamicBackgroundWorker(&worker, &handle);
```

To make it never restart, set `bgw_restart_time = BGW_NEVER_RESTART`.
That tells the postmaster not to bring it back after it exits.

The `bgw_notify_pid` field is important — set it to your own PID so
the postmaster signals you (SIGUSR1) when the worker starts and stops.

For the launcher to know when the worker has finished, use the wait
APIs:

- `WaitForBackgroundWorkerStartup(handle, &pid)` blocks until the
  worker is running.
- `WaitForBackgroundWorkerShutdown(handle)` blocks until the worker
  has exited.

You can also do non-blocking checks with `GetBackgroundWorkerPid` if
you don't want to block.

The worker's main function should have signature
`void func(Datum main_arg)` and be exported with `PGDLLEXPORT`. It
should set up signal handlers, call `BackgroundWorkerUnblockSignals`,
optionally connect to a database with
`BackgroundWorkerInitializeConnection`, do its work, and then call
`proc_exit(0)` to exit cleanly.
