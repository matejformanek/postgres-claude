---
name: gucs-bgworker-parallel
description: Operational checklist for PostgreSQL backend hacking on custom GUCs, background workers, and parallel-query workers — DefineCustomBoolVariable/IntVariable/StringVariable with check/assign hooks, PGC_SIGHUP/GUC_UNIT_MS flags, RegisterBackgroundWorker vs RegisterDynamicBackgroundWorker, BackgroundWorkerInitializeConnection, BGWORKER_SHMEM_ACCESS / BGWORKER_BACKEND_DATABASE_CONNECTION, bgw_restart_time, ParallelContext + DSM segments, parallel-safe/restricted labeling. Use whenever a patch or extension adds a custom GUC, registers a bgworker, or runs code under parallel query. Skip generic tuning questions (shared_buffers, max_connections) and non-PG worker pools.
---

# GUCs, Background Workers, Parallel Query — operational skill

This is the procedural cookbook for three loosely-related extension surfaces
that share one thing: they all sit at the boundary between an extension and
the postmaster / backend lifecycle. For the conceptual model read
`knowledge/idioms/guc-variables.md` and `knowledge/idioms/bgworker-and-parallel.md`
first.

## 1. Custom GUC variables

### 1.1 Picking the right Define*Variable

Five typed entry points, all in `utils/guc.h`:
[verified-by-code `source/src/include/utils/guc.h:358-416`]

| Type | Function | Notes |
|---|---|---|
| bool | `DefineCustomBoolVariable` | |
| int | `DefineCustomIntVariable` | with `minValue` / `maxValue` |
| double | `DefineCustomRealVariable` | with `minValue` / `maxValue` |
| string | `DefineCustomStringVariable` | `valueAddr` is `char **`, see §1.5 |
| enum | `DefineCustomEnumVariable` | takes a `const struct config_enum_entry[]` |

All five take the same trailing trio of hooks: `check_hook`, `assign_hook`,
`show_hook` (any can be NULL).

### 1.2 GucContext — when the value can change

[verified-by-code `source/src/include/utils/guc.h:71-80`]

| `GucContext` | When the user can change it |
|---|---|
| `PGC_INTERNAL` | Never — display-only (e.g. `server_version`). |
| `PGC_POSTMASTER` | Only at postmaster startup (`postgresql.conf` / cmd line). |
| `PGC_SIGHUP` | Postmaster start OR config-reload (SIGHUP / `pg_reload_conf()`). |
| `PGC_SU_BACKEND` | Start of backend, superusers can pass via startup packet. |
| `PGC_BACKEND` | Start of backend (libpq `PGOPTIONS`), then fixed. |
| `PGC_SUSET` | Any time by a superuser, including `SET`. |
| `PGC_USERSET` | Any time by anyone. |

Rule of thumb: pick the loosest context that's still safe. If changing the
value mid-session would require restarting a worker or reallocating shared
memory, use `PGC_POSTMASTER`. If it just changes a runtime threshold, use
`PGC_SIGHUP` or `PGC_SUSET`.

### 1.3 Skeleton — `_PG_init` for an extension with GUCs

```c
void
_PG_init(void)
{
    DefineCustomIntVariable("my_ext.naptime",
                            "Seconds between scans.",
                            NULL,           /* long_desc */
                            &my_naptime,    /* int *valueAddr */
                            10,             /* boot_val */
                            1, INT_MAX,     /* min, max */
                            PGC_SIGHUP,
                            GUC_UNIT_S,     /* flags — UNIT_S = seconds */
                            NULL, NULL, NULL); /* check/assign/show */

    DefineCustomStringVariable("my_ext.database",
                               "DB to connect to.",
                               NULL,
                               &my_database,
                               "postgres",
                               PGC_POSTMASTER,
                               0,
                               NULL, NULL, NULL);

    /* MUST be called AFTER all DefineCustom* calls. */
    MarkGUCPrefixReserved("my_ext");
}
```

[verified-by-code `source/src/test/modules/worker_spi/worker_spi.c:303-360`]

### 1.4 `MarkGUCPrefixReserved`

Call exactly once per extension, **after** every `DefineCustom*Variable` for
your prefix. It does two things:

1. Removes any *placeholder* GUCs (`GUC_CUSTOM_PLACEHOLDER`) under that
   prefix — these get created when a config file mentions a custom variable
   before the defining extension loads. Without removal, parallel-worker
   startup later trips over them.
2. Adds the prefix to a list so future placeholders under it are refused —
   typos in `postgresql.conf` (`my_ext.napitme`) now produce a clear error
   instead of silently being accepted.

[verified-by-code `source/src/backend/utils/misc/guc.c:5178-5228`]

The old name `EmitWarningsOnPlaceholders` is still a `#define` alias —
prefer the new name in new code. [verified-by-code
`source/src/include/utils/guc.h:421`]

### 1.5 String GUCs and `guc_malloc`

For string GUCs, `valueAddr` is a `char **`. The pointed-to storage is
owned by guc.c and must be allocated with `guc_malloc` / `guc_strdup` —
never `palloc`. If a check_hook wants to replace the proposed value it
must `guc_malloc` the new value and `guc_free` the old one.
[from-README `source/src/backend/utils/misc/README:51-60`]

### 1.6 The hook trio

`check_hook(newval *, void **extra, GucSource source) → bool`
- Validate the proposed value; return false on reject.
- May modify `*newval` to canonicalize (round, lowercase, ...).
- May allocate an `extra` struct with `guc_malloc` and return it through
  `*extra` to pass derived data to the assign hook.
- For error detail: `GUC_check_errdetail(...)`, `GUC_check_errhint(...)`,
  `GUC_check_errcode(...)`, `GUC_check_errmsg(...)` — never `ereport(ERROR)`
  directly except on OOM.
- May run **outside any transaction** (bootstrap, postmaster startup,
  config reload). Guard catalog lookups with `IsTransactionState()`.
- May also be called just to validate without assigning — must not have
  side effects.

[from-README `source/src/backend/utils/misc/README:25-109`]

`assign_hook(newval, void *extra) → void`
- Cannot fail (no return). Do all fallible work in the check hook.
- May be called during transaction rollback → no catalog lookups.

`show_hook(void) → const char *`
- Customise what SHOW displays. Static buffer is fine; not reentrant.

### 1.7 Useful `flags` bits

[verified-by-code `source/src/include/utils/guc.h:214-242`]

| Flag | Effect |
|---|---|
| `GUC_LIST_INPUT` | Value is a comma-separated list — needed to use lists at all. |
| `GUC_LIST_QUOTE` | Each list element is double-quoted on serialization. Required for lists of identifiers (e.g. `search_path`). |
| `GUC_UNIT_KB` / `_MB` / `_BYTE` / `_BLOCKS` | Int GUC understands `'128MB'`. |
| `GUC_UNIT_MS` / `_S` / `_MIN` | Time units. |
| `GUC_NOT_IN_SAMPLE` | Don't include in generated `postgresql.conf.sample`. |
| `GUC_SUPERUSER_ONLY` | Hide value from non-superusers in `pg_settings`. |
| `GUC_DISALLOW_IN_FILE` | Cannot appear in config file (set only at runtime). |
| `GUC_DISALLOW_IN_AUTO_FILE` | Cannot be set by `ALTER SYSTEM`. |
| `GUC_REPORT` | Auto-send `ParameterStatus` to client on change. |
| `GUC_EXPLAIN` | Include in `EXPLAIN (SETTINGS)` output. |
| `GUC_ALLOW_IN_PARALLEL` | OK to set inside a parallel-mode block. |

### 1.8 Checklist

- [ ] `_PG_init` defines every custom GUC.
- [ ] `MarkGUCPrefixReserved(prefix)` is called *after* all definitions.
- [ ] String storage uses `guc_malloc` / `guc_strdup`, never `palloc`.
- [ ] `check_hook` is side-effect-free and uses `GUC_check_errdetail` (not
      `ereport(ERROR)`) for validation failures.
- [ ] `check_hook` guards catalog lookups with `IsTransactionState()`.
- [ ] Right `GucContext` chosen (don't use `PGC_USERSET` if the change
      would require restarting workers).
- [ ] Unit flag set on int GUCs that represent size or time.
- [ ] List GUCs have `GUC_LIST_INPUT`, and `GUC_LIST_QUOTE` if elements
      are identifiers.

## 2. Background workers

### 2.1 Static vs dynamic registration

| API | Where to call | Restart? |
|---|---|---|
| `RegisterBackgroundWorker(&w)` | `_PG_init`, only when `process_shared_preload_libraries_in_progress` | Yes per `bgw_restart_time` |
| `RegisterDynamicBackgroundWorker(&w, &handle)` | Any backend at runtime | Yes per `bgw_restart_time`, but worker is forgotten once `handle` goes away unless re-registered |

[verified-by-code `source/src/include/postmaster/bgworker.h:122-133`]

`RegisterBackgroundWorker` errors out unless called from `_PG_init` during
shared-library preload (i.e. `process_shared_preload_libraries_in_progress`
is true). From any other site — including a regular backend at runtime —
use `RegisterDynamicBackgroundWorker` instead.

### 2.2 Filling the `BackgroundWorker` struct

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

### 2.3 Flag cheatsheet

[verified-by-code `source/src/include/postmaster/bgworker.h:50-75`]

| Flag | Meaning |
|---|---|
| `BGWORKER_SHMEM_ACCESS` | Required for any worker that touches shared buffers / LWLocks. |
| `BGWORKER_BACKEND_DATABASE_CONNECTION` | Worker may call `BackgroundWorkerInitializeConnection*`. Requires `SHMEM_ACCESS`. |
| `BGWORKER_INTERRUPTIBLE` | Worker exits if its DB is CREATE/ALTER/DROP'd. Requires the two above. |
| `BGWORKER_CLASS_PARALLEL` | **Don't set** — internal, counts against `max_parallel_workers`. |

### 2.4 Start times

[verified-by-code `source/src/include/postmaster/bgworker.h:84-89`]

- `BgWorkerStart_PostmasterStart` — earliest. No DB access yet; replication / archive only.
- `BgWorkerStart_ConsistentState` — DB is consistent (during recovery, after WAL apply reached a consistent point). Hot-standby readers can run here.
- `BgWorkerStart_RecoveryFinished` — primary mode only, or standby promotion. This is what you usually want.

### 2.5 Restart policy

Two knobs decide restart; both must allow it.

| `bgw_restart_time` | Worker exit | Restarted? |
|---|---|---|
| `BGW_NEVER_RESTART` (`-1`) | any | No — slot is freed. |
| N seconds | `proc_exit(0)` (return 0) | No — clean exit retires the slot regardless of `bgw_restart_time`. |
| N seconds | `proc_exit(1)` (return 1) | Yes, after N seconds. |
| N seconds | crash / signal | Yes, after N seconds. |

[from-comment `source/src/include/postmaster/bgworker.h:14-27`]

### 2.6 Worker main function skeleton

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

Hard rules inside a worker:
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

### 2.7 Querying / terminating dynamic workers

`RegisterDynamicBackgroundWorker` returns a `BackgroundWorkerHandle*`.
With it the launcher backend can:

- `GetBackgroundWorkerPid(handle, &pid)` — non-blocking status.
- `WaitForBackgroundWorkerStartup(handle, &pid)` — block until started.
- `WaitForBackgroundWorkerShutdown(handle)` — block until exit.
- `TerminateBackgroundWorker(handle)` — SIGTERM, no restart.

If `bgw_notify_pid` is set to the launcher's PID, the launcher gets
`SIGUSR1` on worker start/stop transitions — useful with the wait calls.
[verified-by-code `source/src/include/postmaster/bgworker.h:128-137`]

### 2.8 Checklist

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

## 3. Parallel query infrastructure

### 3.1 Two layers — pick the right one

| Goal | Use |
|---|---|
| Build a parallel-aware **executor node** | Plumb into `execParallel.c` (override `ExecXXXInitializeDSM` / `ExecXXXInitializeWorker`). |
| Run arbitrary parallel C code from an extension | Use the `ParallelContext` API directly (`access/parallel.h`). |
| Just expose a function to a query that may run in parallel | Mark it `PARALLEL SAFE` and that's it. |

### 3.2 Function parallel-safety markings

Catalog column `pg_proc.proparallel`. [verified-by-code
`source/src/include/catalog/pg_proc.h:79`]

| Value | SQL keyword | Meaning |
|---|---|---|
| `s` (default) | `PARALLEL SAFE` | Function may run in a worker. |
| `r` | `PARALLEL RESTRICTED` | Function may run in the leader only when plan is parallel. |
| `u` | `PARALLEL UNSAFE` | Plan must not be parallelised at all. |

Use **UNSAFE** if the function: writes to the DB, uses SQL that reads
sequences, touches session state (temp tables, prepared statements,
client connection), holds non-table relation locks across calls, calls
PL functions that aren't themselves safe.

Use **RESTRICTED** if the function: reads non-temp tables but needs the
leader's snapshot guarantees, or has costly setup that workers can't
replicate.

### 3.3 ParallelContext lifecycle (extension-author view)

[verified-by-code `source/src/include/access/parallel.h:64-72`]

```c
EnterParallelMode();

/* Library and function must be PGDLLEXPORT and resolvable in workers. */
pcxt = CreateParallelContext("my_ext", "my_parallel_main", nworkers);

/* Estimate DSM size — call shm_toc_estimate_chunk / _keys for every
 * piece of shared state you'll insert later. */
shm_toc_estimate_chunk(&pcxt->estimator, my_state_size);
shm_toc_estimate_keys (&pcxt->estimator, 1);

InitializeParallelDSM(pcxt);    /* allocates the DSM, sets up TOC */

/* Populate shared state. Pick a key value > the PARALLEL_KEY_* range
 * reserved by parallel.c (use small unsigned ints — they're disjoint
 * from the 0xFFFFFFFFFFFF000x range). */
my_state = shm_toc_allocate(pcxt->toc, my_state_size);
init_my_state(my_state);
shm_toc_insert(pcxt->toc, MY_KEY_STATE, my_state);

LaunchParallelWorkers(pcxt);
/* pcxt->nworkers_launched is the actual count; may be < requested. */

/* Optionally do leader work in parallel with workers. */

WaitForParallelWorkersToFinish(pcxt);
DestroyParallelContext(pcxt);

ExitParallelMode();
```

Reserved TOC magic-number range used internally (don't collide):
`0xFFFFFFFFFFFF0001` .. `0xFFFFFFFFFFFF000F`. Use small integers like
`0x0001`, `0x0002`, ... for your own keys.
[verified-by-code `source/src/backend/access/transam/parallel.c:67-81`]

### 3.4 Worker entry point

The function name passed to `CreateParallelContext` must be a
`PGDLLEXPORT` symbol with signature:

```c
void my_parallel_main(dsm_segment *seg, shm_toc *toc);
```

[verified-by-code `source/src/include/access/parallel.h:25`]

Inside the worker:
- `ParallelWorkerNumber` is set to the worker index (`>= 0`).
  `IsParallelWorker()` is true. [verified-by-code
  `source/src/include/access/parallel.h:59-62`]
- Look up your shared state with `shm_toc_lookup(toc, MY_KEY_STATE, false)`.
- Transaction, snapshot, GUC state, combo CIDs, etc. are restored by
  `ParallelWorkerMain` *before* your function runs — you start with
  the leader's view of the world.
- Errors are propagated back to the leader via the per-worker error
  message queue; just `ereport(ERROR, ...)` as usual.

### 3.5 What workers can't do

A parallel worker must not:
- Acquire locks not already held by the leader (other than buffer locks).
- Modify the database (no INSERT/UPDATE/DELETE, no DDL).
- Use temp tables or sequences.
- Change persistent backend state (prepared statements, listening on
  notify channels, etc.).
- Call any `PARALLEL UNSAFE` function.

This is why function marking matters: the planner uses `proparallel`
to decide whether a path is allowed to contain parallelism at all
(`UNSAFE`), or allowed only in the leader's part of the plan
(`RESTRICTED`).

### 3.6 Checklist

- [ ] `EnterParallelMode()` before `CreateParallelContext`, matching
      `ExitParallelMode()` after `DestroyParallelContext`.
- [ ] Every chunk in the DSM has matching `shm_toc_estimate_chunk` +
      `shm_toc_estimate_keys` calls *before* `InitializeParallelDSM`.
- [ ] TOC keys do not collide with `PARALLEL_KEY_*` (use small ints).
- [ ] Worker function is `PGDLLEXPORT` and findable by
      `load_external_function(library_name, function_name, ...)`.
- [ ] Worker reads shared state with `shm_toc_lookup`, not from globals.
- [ ] Worker never writes the DB, doesn't touch temp tables, doesn't
      acquire non-buffer locks unilaterally.
- [ ] Functions exposed via SQL have explicit `PARALLEL { SAFE |
      RESTRICTED | UNSAFE }` in CREATE FUNCTION — don't rely on the
      default `s`.
- [ ] `pcxt->nworkers_launched` is checked — postmaster may launch fewer
      workers than requested under load.

## 4. Cross-cutting: GUCs inside workers

GUC state is serialized by the leader and restored in each worker by
`ParallelWorkerMain` before your code runs — workers see exactly the
leader's GUC values at launch time. If your custom GUC is `PGC_USERSET`
and a worker is mid-flight when the user `SET`s it, the worker does
*not* see the change.

For background workers (non-parallel), GUC state is whatever
`postgresql.conf` says at start. To honour SIGHUP, install
`SignalHandlerForConfigReload` and call `ProcessConfigFile(PGC_SIGHUP)`
when `ConfigReloadPending` is set.

## 5. Useful greps

- All custom GUC definitions: `grep -RIn 'DefineCustom\(Bool\|Int\|Real\|String\|Enum\)Variable' source/src`
- All bgworker registrations: `grep -RIn 'RegisterBackgroundWorker\|RegisterDynamicBackgroundWorker' source/src source/contrib`
- All `ParallelContext` callers: `grep -RIn 'CreateParallelContext' source/src source/contrib`
- Parallel-safety markings in catalog data: `grep -RIn 'proparallel' source/src/include/catalog`

## 6. Open questions / [unverified]

- `[unverified]` Whether `BGWORKER_INTERRUPTIBLE` is recommended for
  long-running general-purpose workers — most contrib examples don't
  set it.
- `[unverified]` Exact behaviour of `bgw_notify_pid` when the notify-target
  backend exits before the worker starts (likely: silently ignored).
- `[unverified]` Maximum number of TOC keys per DSM segment (likely
  bounded only by available DSM size).
