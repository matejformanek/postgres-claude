# Background workers & parallel query — long-form

Conceptual reference for the postmaster-managed worker subsystems. For the
procedural cookbook see `.claude/skills/gucs-bgworker-parallel/SKILL.md`.

## Three kinds of "extra processes"

A Postgres cluster runs many processes; from an extension author's view
there are three you can plug into, and they have different lifecycles
and constraints.

| Kind | Started by | Lifetime | Can run SQL? | Use case |
|---|---|---|---|---|
| **Auxiliary process** (checkpointer, walwriter, ...) | postmaster, built-in | postmaster lifetime | No (limited) | Core-only; you don't add these from extensions. |
| **Background worker** (bgworker) | postmaster, via registration | configurable, optionally restarting | Yes, with `BackgroundWorkerInitializeConnection` | Long-running extension daemons (autovacuum-like, logical-replication apply, periodic maintenance). |
| **Parallel worker** | leader backend, via `ParallelContext` | one query / one parallel block | Read-only fragments of the leader's query | Parallelising one SQL operation. |

Parallel workers are *implemented as* a special class of bgworker
(`BGWORKER_CLASS_PARALLEL`) but the API surface and constraints are very
different, so we treat them as a separate concept.
[verified-by-code `source/src/include/postmaster/bgworker.h:69-75`]

## When to use which

- **Need to do periodic work in the background, possibly per-DB?**
  Background worker. Set `bgw_restart_time` if it should self-heal,
  `BGW_NEVER_RESTART` for one-shot. Examples: `worker_spi`,
  `pg_cron`-style schedulers, the logical replication apply worker.
- **Need to launch many short-lived helpers to coordinate?** Dynamic
  bgworker via `RegisterDynamicBackgroundWorker`, with `bgw_notify_pid`
  set to the launcher so it gets `SIGUSR1` on state transitions.
- **Need to parallelise one expensive computation inside a query?**
  `ParallelContext` from `access/parallel.h`. The leader backend creates
  the context, populates a DSM segment with shared state, launches N
  worker bgworkers, and waits for them. Workers inherit the leader's
  snapshot, xact, GUCs, combo CIDs, etc., so they "look like" the
  leader from the catalog's perspective — but they cannot write.
- **Need to expose a function safely to the planner's parallel paths?**
  Just set the right `PARALLEL { SAFE | RESTRICTED | UNSAFE }` in
  CREATE FUNCTION. No code work needed beyond honesty about side effects.

## Background worker lifecycle

```
_PG_init (only if process_shared_preload_libraries_in_progress)
   │  fills BackgroundWorker, calls RegisterBackgroundWorker
   ▼
postmaster (private list)
   │  forks at bgw_start_time
   ▼
worker process: BackgroundWorkerMain
   │  signal init → BackgroundWorkerUnblockSignals
   │  optional: BackgroundWorkerInitializeConnection(dbname, role)
   │  jumps to bgw_function_name in bgw_library_name
   ▼
worker_main(Datum main_arg)
   │  main loop on MyLatch w/ WL_EXIT_ON_PM_DEATH
   │  proc_exit(0)  → never restarted
   │  proc_exit(1)  → restarted after bgw_restart_time seconds
   │  crash         → restart cycle (postmaster handles)
```

`BackgroundWorkerList` in `bgworker.c` is the postmaster's private
registry. Shared memory holds a parallel `BackgroundWorkerArray` of
fixed-size slots; backends modify slot state under
`BackgroundWorkerLock`, and the postmaster reads slots lock-free via a
careful in_use / terminate / generation protocol because the postmaster
cannot take spinlocks (corrupted shared memory must not be able to wedge
it). [verified-by-code `source/src/backend/postmaster/bgworker.c:45-86`]

Practical consequence: dynamic registration from a backend writes a
slot under the lock, sets `in_use = true` with a write barrier, then
signals the postmaster, which forks the worker. There is a small but
non-zero delay between `RegisterDynamicBackgroundWorker` returning true
and the worker actually running.

### Start-time gates

`bgw_start_time` is a *gate*, not a precise schedule. The postmaster
fires the worker at the next opportunity once the gate condition holds.

- `PostmasterStart` — immediately at postmaster start. No DB access yet.
  Useful for replication/archive workers.
- `ConsistentState` — recovery has replayed enough WAL that pages are
  consistent. Standby reads can start here.
- `RecoveryFinished` — recovery is done (primary mode, or promoted
  standby). This is the safest default for general extensions.

[verified-by-code `source/src/include/postmaster/bgworker.h:84-89`]

### Restart semantics

| Worker exits with | Effect |
|---|---|
| `proc_exit(0)` | Permanent. Slot freed. |
| `proc_exit(1)` | Restart after `bgw_restart_time` seconds (unless `BGW_NEVER_RESTART`). |
| Crash / signal | Postmaster handles per global crash-restart policy. |
| `TerminateBackgroundWorker(handle)` | SIGTERM, no restart, slot freed once dead. |

The "exit code 0 = never restart" rule is important for one-shot
workers (a migration helper, say): return cleanly and you're done, no
loop needed in postmaster's recovery logic.
[from-comment `source/src/include/postmaster/bgworker.h:18-23`]

### Coordination patterns

- **Latch-based wakeups.** Workers sleep on `MyLatch`. Other backends
  wake them with `SetLatch(&worker_proc->procLatch)` (you'd need the
  worker's `PGPROC*`; usually you publish it in a shared-memory slot
  during worker startup).
- **bgw_notify_pid.** Set this to the launcher's PID and the postmaster
  signals the launcher on worker start/stop. Pair with
  `WaitForBackgroundWorkerStartup(handle, &pid)` so the launcher blocks
  until the worker is running.
- **bgw_extra.** 128 bytes of opaque payload usable however you like.
  worker_spi encodes a (database OID, role OID, flags) triple so the
  same worker function can serve both static and dynamic registrations.
  [verified-by-code `source/src/test/modules/worker_spi/worker_spi.c:151-171`]
- **Shared memory.** Workers with `BGWORKER_SHMEM_ACCESS` see the
  cluster's main shared memory and can register their own segments via
  `RequestAddinShmemSpace` / `shmem_startup_hook` (from `_PG_init` of a
  preloaded library) or via `dsm_create` at runtime.

## Parallel query — the bigger picture

The planner decides whether to parallelise a path by checking the
parallel-safety of every involved function (`pg_proc.proparallel`).
The three values:

- `'s'` (SAFE) — call site can be the leader or a worker.
- `'r'` (RESTRICTED) — call site must be the leader; workers may not run
  this function. The query can still be parallel, but the function
  itself can't appear under a `Gather`.
- `'u'` (UNSAFE) — the entire plan becomes non-parallel.

[verified-by-code `source/src/include/catalog/pg_proc.h:79`]

These markings drive `max_parallel_workers_per_gather`, the planner's
parallel-cost model, and ultimately whether `Gather` / `Gather Merge`
nodes appear in the plan.

### Executor side: ParallelContext

When the executor reaches a `Gather` node, it builds a `ParallelContext`
and uses it to spin up parallel workers. The same machinery is exposed
to extension authors directly for non-executor parallel work (e.g.
parallel `CREATE INDEX` uses it via `nbtree.c`'s parallel build).

Lifecycle (in caller terms): [verified-by-code
`source/src/include/access/parallel.h:64-72`]

1. `EnterParallelMode()` — flips a backend-wide flag that, among other
   things, makes attempts to assign new XIDs error out (the leader can't
   write while workers are running).
2. `CreateParallelContext(library_name, function_name, nworkers)` —
   allocates a `ParallelContext` in the current memory context. The
   library and function name identify the worker entry point;
   `load_external_function` will resolve them in each worker.
3. `shm_toc_estimate_chunk(&pcxt->estimator, size)` ×N and
   `shm_toc_estimate_keys(&pcxt->estimator, n)` to size the DSM.
4. `InitializeParallelDSM(pcxt)` — allocates the DSM segment, sets up
   the TOC and fixed parallel state (DB OID, user OID, snapshot, GUCs,
   transaction state, combo CIDs, etc., serialized into reserved TOC
   slots `PARALLEL_KEY_FIXED..CLIENTCONNINFO`).
5. `shm_toc_allocate` + `shm_toc_insert` to publish your shared state.
6. `LaunchParallelWorkers(pcxt)` — registers parallel bgworkers via
   the normal registration path with `BGWORKER_CLASS_PARALLEL`.
   `pcxt->nworkers_launched` is the actual count.
7. Leader may do its own portion of the work in parallel with workers.
8. `WaitForParallelWorkersToFinish(pcxt)` — blocks until all workers
   exit. Errors are re-raised in the leader via the per-worker error
   queues.
9. `DestroyParallelContext(pcxt)`, then `ExitParallelMode()`.

[verified-by-code `source/src/backend/access/transam/parallel.c:174-...`
 and the reserved keys at lines 67-81]

### Why workers can't write

The leader's snapshot is shared with workers. If a worker wrote to a
table, the leader's MVCC visibility rules would have to account for
in-progress writes by sibling backends sharing the same XID, which the
core MVCC machinery is not designed to handle. So `EnterParallelMode`
locks down XID assignment, and parallel workers cannot execute
data-modifying DML, DDL, or anything else that would need a new XID
(temp tables, sequences via `nextval`, etc.). They can read, sort,
hash, aggregate — pure functions over the leader's snapshot.

### DSM and the TOC

The shared state is one `dsm_segment`. Inside it, a `shm_toc`
("table of contents") maps `uint64` keys to byte offsets. Both
leader and workers look up shared structures by key. The PG core
reserves the high range `0xFFFFFFFFFFFF0001 ..
0xFFFFFFFFFFFF000F` for fixed parallel state; extension code uses
small integers (`0x0001`, `0x0002`, ...).
[verified-by-code `source/src/backend/access/transam/parallel.c:64-81`]

The TOC is fixed-size after `InitializeParallelDSM` — that's why every
chunk must be `shm_toc_estimate_chunk`'d *before* initialisation.
Forgetting one shows up as an assertion failure (`shm_toc_allocate`
overruns the segment) or, in release builds, as silent memory
corruption.

## GUC interaction

- Background workers read GUCs the same way regular backends do. To
  honour SIGHUP, install `SignalHandlerForConfigReload` and call
  `ProcessConfigFile(PGC_SIGHUP)` when `ConfigReloadPending` is true.
- Parallel workers inherit the leader's full GUC state — serialized
  into `PARALLEL_KEY_GUC` during `InitializeParallelDSM` and restored
  in `ParallelWorkerMain` before user code runs. Workers see exactly
  the leader's settings at launch; subsequent `SET` in the leader does
  *not* propagate.

## Files examined

| File | Depth | Produced |
|---|---|---|
| `source/src/include/postmaster/bgworker.h` | full read | this doc + SKILL.md §2 |
| `source/src/backend/postmaster/bgworker.c:1-100` | targeted (top + slot protocol) | §"Background worker lifecycle" |
| `source/src/test/modules/worker_spi/worker_spi.c:134-225, 303-385` | targeted | SKILL.md §2.2, §2.6 |
| `source/src/include/access/parallel.h` | full read | SKILL.md §3 |
| `source/src/backend/access/transam/parallel.c:1-120` | targeted (reserved keys, FixedParallelState) | §"DSM and the TOC" |
| `source/src/include/catalog/pg_proc.h:79` | targeted (proparallel default) | §"Parallel query" + SKILL.md §3.2 |
