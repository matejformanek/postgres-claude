# One-shot migration background worker

You'll want a background worker that runs once and then exits without
being restarted. The launcher backend kicks it off and waits for it to
finish.

## Registering

Fill a `BackgroundWorker` struct and register it with
`RegisterBackgroundWorker` — that gives you a `BackgroundWorkerHandle`
you can use to wait on it.

```c
BackgroundWorker worker;
BackgroundWorkerHandle *handle;
pid_t pid;

memset(&worker, 0, sizeof(worker));
snprintf(worker.bgw_name, BGW_MAXLEN, "myext migration");
worker.bgw_flags = BGWORKER_SHMEM_ACCESS
                 | BGWORKER_BACKEND_DATABASE_CONNECTION;
worker.bgw_start_time   = BgWorkerStart_RecoveryFinished;
worker.bgw_restart_time = BGW_NEVER_RESTART;
strcpy(worker.bgw_library_name,  "myext");
strcpy(worker.bgw_function_name, "myext_migration_main");
worker.bgw_notify_pid = MyProcPid;

RegisterBackgroundWorker(&worker, &handle);
```

## Making sure it doesn't restart

The key field is `bgw_restart_time = BGW_NEVER_RESTART`. With that,
the postmaster will not spawn the worker again after it exits.

## Knowing when it finished

`bgw_notify_pid = MyProcPid` tells the postmaster to notify the
launcher when the worker's state changes. From the launcher you can
then call something like `WaitForBackgroundWorkerShutdown(handle)` to
block until it exits.

## Worker main

```c
void
myext_migration_main(Datum main_arg)
{
    BackgroundWorkerInitializeConnection("mydb", NULL, 0);
    /* ... do the migration ... */
}
```
