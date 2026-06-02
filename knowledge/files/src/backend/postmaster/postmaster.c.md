# postmaster.c

- **Source:** `source/src/backend/postmaster/postmaster.c` (4742 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (top comment, ServerLoop, BackendStartup, PostmasterStateMachine, signal plumbing)

## Purpose

The postmaster is PG's single supervisor process. It owns the listen sockets,
shared-memory and semaphore pools, and the fork-dispatch logic for every other
process in the cluster. It does *not* itself attach to or modify shared memory
under normal operation; this isolation is what lets the postmaster survive a
backend that corrupts shared state and drive the crash-restart cycle.
[from-comment] `postmaster.c:1-32` (header block on responsibilities)
[from-comment] `postmaster.c:14-23` (the "deliberately stays out of shmem" invariant — load-bearing for the whole process model)

## Mental model (load-bearing invariants)

- **No shared memory from postmaster.** Postmaster allocates shmem at startup
  but never touches it in the steady state; it is not in `PGPROC`, holds no
  lwlocks. This is why a backend crash can be recovered by resetting shmem and
  respawning. [from-comment] `:14-23, :47-52`
- **Fork-on-accept.** When a connection arrives, postmaster forks immediately;
  the child does authentication. This pre-fork avoids SSL/PAM DoS-ing the
  parent and keeps the parent single-threaded. [from-comment] `:25-32`
- **Never block on frontend messages.** [from-comment] `:48-52`
- **`PostmasterContext` is recyclable.** All postmaster palloc()s land in a
  child of `TopMemoryContext` that backends delete after they no longer need
  startup data. Anything that must survive into backends goes in
  `TopMemoryContext`. [from-comment] `:529-538`

## Key entry points

| Line | Symbol | Role |
|---|---|---|
| 497 | `PostmasterMain` | argv parsing, signal-handler install, GUC init, listen-socket setup, shmem create, then ServerLoop |
| 1678 | `ServerLoop` | the main idle loop: `WaitEventSetWait` over latch + listen sockets; on accept calls `BackendStartup`; processes pending shutdown/reload/child-exit/pmsignal flags |
| 1559 | `DetermineSleepTime` | computes next wakeup (bgworker restart, io worker schedule) |
| 1837 | `canAcceptConnections` | gate that produces `CAC_state` based on `pmState`, FatalError, recovery, etc. |
| 1958 | `InitProcessGlobals` | per-process globals (`MyStartTime`, etc.) |
| 2911 | `PostmasterStateMachine` | drives `pmState` transitions during shutdown / crash-restart |
| 3325 | `LaunchMissingBackgroundProcesses` | re-starts aux singletons when the pmstate permits |
| 3489 | `signal_child` / 3522 `SignalChildren` / 3557 `TerminateChildren` | signal delivery to children, optionally by BackendTypeMask |
| 3576 | `BackendStartup` | per-connection: assign a `PMChild` slot, call `postmaster_child_launch`, record pid |
| 4010 | `StartChildProcess` | aux-singleton launcher (calls `postmaster_child_launch`) |
| 4081 | `StartAutovacuumWorker` | special path used when launcher signals via `PMSIGNAL_START_AUTOVAC_WORKER` |
| 4173 | `StartBackgroundWorker` / 4280 `maybe_start_bgworkers` | dynamic bgworker registration → fork via `postmaster_child_launch` |
| 4473 | `maybe_start_io_workers` | PG 17+ AIO worker pool sizing |

## Control flow — connection accept (the hot path)

1. `ServerLoop` returns from `WaitEventSetWait` with `WL_SOCKET_ACCEPT`.
   `postmaster.c:1692-1727`
2. `AcceptConnection(fd, &s)` fills a `ClientSocket`.
3. `BackendStartup(&s)` (`:3576`):
   a. `canAcceptConnections(B_BACKEND)` decides CAC_OK / CAC_TOOMANY / etc.
   b. `AssignPostmasterChildSlot(B_BACKEND)` reserves a `PMChild` from
      `pmchild.c` pool; on failure → `AllocDeadEndChild`.
   c. `postmaster_child_launch(bn->bkend_type, …, &startup_data, …, client_sock)`
      forks (or fork+execs on EXEC_BACKEND) and returns the pid to parent.
      `:3627`
4. Parent records `bn->pid = pid`. Child arrives in `BackendMain`
   (`backend_startup.c:76`), which calls `BackendInitialize` (auth) then
   `PostgresMain` (`tcop/postgres.c:4274`).

## Control flow — shutdown / crash-restart

- Signal handlers (`handle_pm_*_signal`) set flags + `SetLatch`; the loop drains
  flags via `process_pm_*` routines. `:1714-1721`
- `PostmasterStateMachine` (`:2911`) advances `pmState` through
  `PM_RUN → PM_STOP_BACKENDS → PM_WAIT_BACKENDS → PM_WAIT_XLOG_SHUTDOWN →
   PM_WAIT_XLOG_ARCHIVAL → PM_WAIT_CHECKPOINTER → PM_WAIT_IO_WORKERS →
   PM_WAIT_DEAD_END → PM_NO_CHILDREN → ExitPostmaster`.
- On any backend crash, `HandleChildCrash` (`:2818`) → `HandleFatalError`
  (`:2732`) sends SIGQUIT to all children and resets shmem on the next cycle.

## Signals received by postmaster (`PostmasterMain`, `:555-563`)

- `SIGHUP` → reload config
- `SIGINT` → smart shutdown
- `SIGTERM` → fast shutdown
- `SIGQUIT` → immediate shutdown (with sigkill timeout)
- `SIGUSR1` → multiplexed pmsignal (children request actions)
- `SIGCHLD` → reap dead child

## Locking / shared-state rules

The postmaster **never takes lwlocks or spinlocks**. Communication from
children to postmaster goes through:
- `PMSignalFlags` array in shmem (lockless `sig_atomic_t`) — see `pmsignal.c`.
- `BackgroundWorkerSlot::in_use` write-barrier handshake (see `bgworker.c:43-78`).

## Interactions

- Inbound from children: `pmsignal.c` (SIGUSR1 multiplex), `pmchild.c` (slot accounting), shared `BackgroundWorkerSlot` array.
- Outbound: `launch_backend.c::postmaster_child_launch` for every fork.
- Headers: `postmaster/postmaster.h`, `postmaster/bgworker_internals.h`, `storage/pmsignal.h`.

## Open questions

- Detailed `pmState` table with every transition arrow — useful future doc.
- Exact ordering of aux-singleton startup vs `B_STARTUP` exit transition
  during recovery (cross-ref with `xlogrecovery.c`).

## Synthesized by
<!-- backlinks:auto -->
- [architecture/overview.md](../../../../architecture/overview.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
