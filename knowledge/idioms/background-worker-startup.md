# Background worker startup — the bgworker registration pattern

PostgreSQL's background-worker (bgworker) infrastructure lets
extensions and core code spawn additional **server processes**
managed by the postmaster — autovacuum launcher, parallel-
query workers, logical-replication apply workers, custom
extension workers. The startup pattern has two flavors:
shared-preload registration (`RegisterBackgroundWorker`) for
permanent workers, and dynamic registration
(`RegisterDynamicBackgroundWorker`) for on-demand workers.
Both produce the same `BackgroundWorker` struct that the
postmaster turns into a forked process.

Anchors:
- `source/src/include/postmaster/bgworker.h:96-174` —
  struct + API [verified-by-code]
- `source/src/backend/postmaster/bgworker.c` —
  implementation
- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  companion skill

## The BackgroundWorker struct

```c
typedef struct BackgroundWorker
{
    char                bgw_name[96];          /* display name */
    char                bgw_type[96];          /* type for grouping */
    int                 bgw_flags;             /* shmem/conn flags */
    BgWorkerStartTime   bgw_start_time;        /* when to start */
    int                 bgw_restart_time;      /* seconds, or BGW_NEVER_RESTART */
    char                bgw_library_name[MAXPGPATH];
    char                bgw_function_name[96];
    Datum               bgw_main_arg;
    char                bgw_extra[128];        /* extension-private state */
    pid_t               bgw_notify_pid;        /* SIGUSR1 on start/stop */
} BackgroundWorker;
```

[verified-by-code `bgworker.h:96-108`]

The struct is **fully self-describing** — the postmaster
needs only this to launch the worker:
- Where to load code from: `bgw_library_name` +
  `bgw_function_name`.
- When to start: `bgw_start_time`.
- Whether to restart on crash: `bgw_restart_time`.
- What argument to pass: `bgw_main_arg` + optional 128 bytes
  of `bgw_extra`.

## The two registration paths

### Static (`shared_preload_libraries` only)

```c
void
_PG_init(void)
{
    BackgroundWorker w = { /* ... */ };
    RegisterBackgroundWorker(&w);
}
```

[verified-by-code `bgworker.h:122`]

Called during postmaster startup, before any backend forks.
Workers registered this way persist across postmaster
lifetime. ONLY valid in `_PG_init` of a
`shared_preload_libraries` module.

### Dynamic (any backend)

```c
BackgroundWorker w = { /* ... */ };
BackgroundWorkerHandle *handle;
if (!RegisterDynamicBackgroundWorker(&w, &handle))
    /* registration failed; pool full */;
WaitForBackgroundWorkerStartup(handle, &pid);
```

[verified-by-code `bgworker.h:125-131`]

Called from a regular backend at any time. Returns a handle
the caller can use to wait for startup, query status, or
terminate. Subject to `max_worker_processes` cap.

## bgw_flags — what the worker can do

| Flag | Means |
|---|---|
| `BGWORKER_SHMEM_ACCESS` | Worker can access shared memory |
| `BGWORKER_BACKEND_DATABASE_CONNECTION` | Worker can connect to a DB via `BackgroundWorkerInitializeConnection` |

A worker without `BGWORKER_BACKEND_DATABASE_CONNECTION`
runs without DB access — useful for pure background tasks
(monitoring, archiving) that don't query tables.

A worker without `BGWORKER_SHMEM_ACCESS` is rare — almost
all workers need shared memory at least to receive shutdown
signals.

## bgw_start_time — when to fire

| Value | Means |
|---|---|
| `BgWorkerStart_PostmasterStart` | Immediately at postmaster start |
| `BgWorkerStart_ConsistentState` | After recovery reaches consistency |
| `BgWorkerStart_RecoveryFinished` | After recovery completes |

The default is `RecoveryFinished` — workers won't run during
crash recovery (which makes sense; the cluster isn't ready
for application work).

## bgw_restart_time — crash policy

- **`BGW_NEVER_RESTART` (-1)** — worker exits = stay exited.
- **`BGW_DEFAULT_RESTART_INTERVAL` (60)** — wait 60s after
  crash, then re-fork.
- **Custom integer** — seconds to wait before restart.

The restart interval is the per-worker backoff. Workers that
crash repeatedly (clearly buggy) get throttled by the
interval; postmaster doesn't fork-bomb itself.

## The worker's main function

```c
void
my_worker_main(Datum main_arg)
{
    /* Initialize: */
    BackgroundWorkerUnblockSignals();
    BackgroundWorkerInitializeConnection("mydb", NULL, 0);

    /* Main loop: */
    for (;;)
    {
        do_work();
        WaitLatch(MyLatch, WL_LATCH_SET | WL_EXIT_ON_PM_DEATH,
                  0, WAIT_EVENT_MY_WORKER);
        ResetLatch(MyLatch);
    }
}
```

Conventions:
- **`BackgroundWorkerUnblockSignals`** first — the worker
  starts with all signals blocked.
- **`BackgroundWorkerInitializeConnection`** to attach to a
  DB (if flag was set).
- **Main loop** uses `WaitLatch` with `WL_EXIT_ON_PM_DEATH`
  so the worker dies cleanly if postmaster goes.

## Status querying

```c
BgwHandleStatus status = GetBackgroundWorkerPid(handle, &pid);
```

[verified-by-code `bgworker.h:128-130`]

Returns one of:
- `BGWH_STARTED` — running, `pid` populated.
- `BGWH_NOT_YET_STARTED` — postmaster hasn't gotten to it.
- `BGWH_STOPPED` — worker has exited.
- `BGWH_POSTMASTER_DIED` — postmaster is gone.

`WaitForBackgroundWorkerStartup` blocks until `BGWH_STARTED`
or terminal status.

## Termination

`TerminateBackgroundWorker(handle)` signals the worker to
exit. The worker is expected to check `MyLatch` /
`CHECK_FOR_INTERRUPTS` regularly and exit cleanly. A
non-cooperating worker can be SIGKILLed by the postmaster
after a timeout.

## bgw_notify_pid — startup notification

If `bgw_notify_pid` is non-zero, the postmaster sends
SIGUSR1 to that PID when the worker starts and stops. Used
by the parent backend to receive notification without
polling.

## Common review-time concerns

- **`RegisterBackgroundWorker` ONLY in `_PG_init`** of a
  shared-preload-libraries module. Other call sites are
  illegal.
- **Workers don't inherit `pg_hba.conf` auth.** Use
  `BGWORKER_BYPASS_ALLOWCONN` if needed.
- **`bgw_extra` is 128 bytes** — use for small private
  state. For larger state, the worker should look up shared
  memory.
- **Restart intervals are per-worker.** A crash storm spreads
  out via the per-worker backoff.
- **`bgw_library_name` MUST match a `.so` in
  `dynamic_library_path`.** Misspell = postmaster errors at
  fork time.

## Invariants

- **[INV-1]** Static registration only in `_PG_init`;
  dynamic registration any time.
- **[INV-2]** Workers respect `max_worker_processes` pool;
  static workers don't count against the pool (they're
  permanent).
- **[INV-3]** `bgw_restart_time = -1` means no restart;
  positive integer means seconds-of-backoff.
- **[INV-4]** Worker startup blocks until `BgwHandleStatus`
  transitions out of `BGWH_NOT_YET_STARTED`.
- **[INV-5]** WL_EXIT_ON_PM_DEATH in the worker's main
  wait-loop is required discipline.

## Useful greps

- All bgworker registrations:
  `grep -RIn 'RegisterBackgroundWorker\|RegisterDynamicBackgroundWorker' source/src/backend source/contrib | head -20`
- The flags:
  `grep -n 'BGWORKER_' source/src/include/postmaster/bgworker.h`
- The main-function pattern:
  `grep -RIn 'BackgroundWorkerInitializeConnection' source/src/backend source/contrib | head -10`

## Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  companion skill covering extension + bgworker design.
- `knowledge/data-structures/latch-waiteventset.md` — the
  WaitLatch primitive worker main loops use.
- `knowledge/idioms/parallel-worker-coordination.md` —
  parallel-query workers are a specialization of bgworkers.
- `knowledge/subsystems/storage-ipc.md` — postmaster
  manages bgworker IPC.
- `source/src/include/postmaster/bgworker.h` — public API.
- `source/src/backend/postmaster/bgworker.c` —
  implementation.
