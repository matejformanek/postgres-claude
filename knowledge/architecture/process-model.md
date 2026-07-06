# PostgreSQL Process Model

How a running PG cluster is organized as a tree of OS processes, what each one
does, who spawns whom, and what they share.

## The big picture

```
                    postmaster (PostmasterMain)
                          │  forks everything
   ┌──────────────────────┼──────────────────────────────────────────┐
   │                      │                                          │
 startup           aux singletons                           one per client / replica
  (recovery        ┌─────┴───────┐                          ┌────────┴──────────┐
   then exits)     │  checkpointer  bgwriter  walwriter      backend (B_BACKEND)
                   │  archiver      walreceiver              walsender (B_WAL_SENDER)
                   │  walsummarizer io_workers (N)           parallel workers (bgworker)
                   │  logger (no shmem)
                   └─ special workers ─ autovac launcher → autovac workers
                                       logical-rep launcher → apply workers (bgworker)
                                       slotsync worker
                                       checksum worker launcher → workers
                   └─ user bgworkers (extensions)
```
[from-wiki](https://wiki.postgresql.org/wiki/Backend_flowchart)
[verified-by-code] `source/src/include/miscadmin.h:340-381` (`BackendType`)

## The postmaster

- Single supervisor process; runs `PostmasterMain` → `ServerLoop`.
  [verified-by-code] `postmaster.c:1415` (`status = ServerLoop()`), `:1678` (definition).
- **Allocates shared memory and semaphores at startup, then deliberately stays
  out of them** — it is not in the `PGPROC` array, holds no lwlocks, and so
  can survive a backend crashing inside shared memory.
  [from-comment] `postmaster.c:14-23`
- Accepts TCP/unix-socket connections; for each, calls `BackendStartup` which
  forks. The child performs authentication (so blocking SSL/PAM cannot DoS the
  postmaster).
  [from-comment] `postmaster.c:25-32`
  [verified-by-code] `postmaster.c:3568-3580` (`BackendStartup`).
- On any backend crash, postmaster signals all children to terminate, resets
  shared memory, and re-launches the auxiliary set. This is the "crash-restart"
  cycle.
  [from-comment] `postmaster.c:54-57` (garbage collection)
- All children go through `postmaster_child_launch` in `launch_backend.c`,
  which switches on `BackendType` via the `child_process_kinds[]` table to find
  the right `main_fn`.
  [verified-by-code] `postmaster/launch_backend.c:179-184, 204-272`

## BackendType enum — every process kind in one place

From `source/src/include/miscadmin.h:340-381`:

| Symbol | Category | Singleton? | Notes |
|---|---|---|---|
| `B_BACKEND` | client-serving | per connection | regular SQL backend |
| `B_DEAD_END_BACKEND` | client-serving | transient | rejects a conn that arrived too late/early |
| `B_AUTOVAC_LAUNCHER` | special worker | yes | schedules autovac workers per DB |
| `B_AUTOVAC_WORKER` | special worker | up to `autovacuum_max_workers` | runs `VACUUM`/`ANALYZE` |
| `B_BG_WORKER` | generic | many | parallel-query workers, logical apply workers, extension workers |
| `B_WAL_SENDER` | client-serving | per replica | streams WAL to physical/logical replica |
| `B_SLOTSYNC_WORKER` | special worker | yes | syncs logical slots on standby |
| `B_STANDALONE_BACKEND` | — | n/a | single-user mode (no postmaster) |
| `B_ARCHIVER` | aux | yes | runs `archive_command` / archive module |
| `B_BG_WRITER` | aux | yes | trickles dirty buffers to disk |
| `B_CHECKPOINTER` | aux | yes | runs checkpoints; also handles fsync requests forwarded by backends |
| `B_IO_WORKER` | aux | many | async/direct IO workers (PG 17+ AIO subsystem) |
| `B_STARTUP` | aux | yes, then exits | runs crash/archive recovery before normal operation |
| `B_WAL_RECEIVER` | aux | yes (on standby) | pulls WAL from primary |
| `B_WAL_SUMMARIZER` | aux | yes | builds WAL summaries for incremental backup |
| `B_WAL_WRITER` | aux | yes | flushes WAL buffers periodically |
| `B_DATACHECKSUMSWORKER_*` | special worker | yes/many | online enable/disable of data checksums |
| `B_LOGGER` | aux | yes | syslogger; *not* attached to shared memory |

[verified-by-code] `miscadmin.h:340-381`, with comment `:376-379` confirming
logger has no shmem and no `PGPROC`.

## Lifetimes & who starts whom

- **Postmaster** — started by `pg_ctl` / `postgres`; lives for the cluster's
  lifetime. Crashes are fatal to the cluster.
- **Startup process** — first child the postmaster launches. Performs WAL
  replay (recovery or archive recovery). On a primary it reaches the
  consistent point and exits; on a hot standby it stays alive and keeps
  replaying. [from-docs](https://www.postgresql.org/docs/current/wal-internals.html)
- **Aux singletons (checkpointer, bgwriter, walwriter, archiver, walsummarizer,
  logger, io workers)** — launched by postmaster as soon as startup recovery
  reaches the right phase. Postmaster respawns them on crash.
- **Autovac launcher** — postmaster child. Spawns autovac workers (which are
  *also* postmaster children, not launcher children — the launcher just asks
  the postmaster). [from-docs](https://www.postgresql.org/docs/current/runtime-config-autovacuum.html)
- **Logical replication launcher** — postmaster child; manages apply workers
  (bgworkers).
- **Regular backends** — postmaster forks one per accepted connection.
- **Walsenders** — backend that the postmaster forked for a replication
  connection. Same fork path, different `BackendType`.
  [verified-by-code] `miscadmin.h:414-415` `IsExternalConnectionBackend`
  includes both `B_BACKEND` and `B_WAL_SENDER`.
- **Parallel query workers** — launched on demand via the bgworker API by the
  *leader* backend; postmaster does the actual fork.
  [from-docs](https://www.postgresql.org/docs/current/parallel-query.html)
- **Custom bgworkers** — registered by extensions in `shared_preload_libraries`
  or dynamically via `RegisterDynamicBackgroundWorker`. Postmaster forks them.
  [from-docs](https://www.postgresql.org/docs/current/bgworker.html)

## What they share

### Shared memory (allocated by postmaster, attached by every child whose
`shmem_attach == true`)

The canonical inventory of what lives in shared memory — and the *order* in
which each subsystem is initialized — is `subsystemlist.h`, an X-macro list
of `PG_SHMEM_SUBSYSTEM(x)` entries expanded once by
`RegisterBuiltinShmemCallbacks` (`ipci.c:167`). Ordering is encoded as
comments at the top of the header: LWLocks first (so other init callbacks may
safely `LWLockAcquire`), then DSM/DSMRegistry, then xlog/clog/buffers, then
lock manager, then proc/sinval, etc. The historic giant `XXXShmemInit()`
chain in `ipci.c` has been replaced by this callback-table mechanism; new
subsystems register via `ShmemCallbacks` rather than editing a central list.
[verified-by-code] `source/src/include/storage/subsystemlist.h:18-90`,
`source/src/backend/storage/ipc/ipci.c:119-167`.
[from-comment] `subsystemlist.h:18-26` (ordering rationale).

Major shmem residents (per `subsystemlist.h` order):

- `shared_buffers` — the page cache (buffer manager).
- WAL buffers.
- `PGPROC` array — one slot per backend/aux process; carries xid, vxid, latch,
  wait info.
- Lock tables (heavyweight, predicate, lwlocks' tranches).
- ProcArray (snapshot computation).
- Shared inval message queue (catalog cache invalidation).
- **Cumulative statistics system** (PG 15+) — replaced the old stats collector
  process; backends write stats directly into shared memory now.
  [from-docs](https://www.postgresql.org/docs/current/monitoring-stats.html)
- Replication slot array, sync rep state, AIO state, etc.

The logger (and only the logger) skips shmem attach:
[from-comment] `miscadmin.h:376-379`.
[verified-by-code] `launch_backend.c:243-248` (the `dsm_detach_all()` /
`PGSharedMemoryDetach()` for non-attaching children).

#### Startup process and sinval

The startup process is registered on the sinval queue with the `sendOnly`
flag set: during recovery it *ships* catalog invalidations to hot-standby
readers but has no catalog cache of its own (it isn't running queries), so
it never *receives* messages and `SICleanupQueue` ignores its slot when
computing `minMsgNum`. [verified-by-code] `sinvaladt.c:148-154` (ProcState
`sendOnly` field), `:596-612` (`SICleanupQueue` ignores `sendOnly` slots —
comment at `:596-599`, the `if (... || stateP->sendOnly) continue;` skip at
`:612`).

### Latches and signals

- Each `PGPROC` carries a `Latch`. Waking a process = `SetLatch` on its proc's
  latch.
- **Latch wakes use `SIGURG`, *not* `SIGUSR1`.** SIGURG is otherwise unused by
  PG and carries no procsignal payload — it's a pure wake-only signal.
  `WakeupOtherProc(pid)` ultimately calls `kill(pid, SIGURG)`.
  [verified-by-code] `latch.c:289-330` (`SetLatch` + `WakeupOtherProc`),
  `waiteventset.c:30-33` (epoll path docs).
- On Linux (`WAIT_USE_EPOLL`) there is **no SIGURG signal handler** installed;
  SIGURG stays blocked and a `signalfd` is added to the `WaitEventSet`, so the
  kernel delivers wakes directly into the wait loop.
  [verified-by-code] `waiteventset.c:30-33`.
- `SIGUSR1` is the **`ProcSignal` multiplex** signal — backend ↔ backend
  asks-target-to-do-N-things mechanism. The handler walks
  `pss_signalFlags[]` and dispatches (catchup, recovery conflict,
  parallel-message, barriers, log memory context, log backtrace, …).
  [verified-by-code] `procsignal.c:295-313` (`SendProcSignal`),
  `procsignal.c:696` (`procsignal_sigusr1_handler`, registered via
  `pqsignal(SIGUSR1, ...)` at `tcop/postgres.c:4427`).
- Other signals: `SIGHUP` for config reload, `SIGTERM`/`SIGINT` for
  terminate/cancel, `SIGCHLD` to the postmaster.

### ProcSignalBarrier — cluster-wide quiesce-and-confirm

When a global state change needs every backend to *observe* it before
proceeding (online checksum toggling, dropping a database, smgr release on
tablespace removal, etc.), `EmitProcSignalBarrier(type)` is used:

1. The initiator sets a bit in every backend's `pss_barrierCheckMask` and
   bumps the global `psh_barrierGeneration` counter.
2. It then raises `PROCSIG_BARRIER` (a `SendProcSignal` reason) on every
   active slot.
3. Each backend, on its next `CHECK_FOR_INTERRUPTS` →
   `ProcessProcSignalBarrier`, atomically swaps its mask, runs the
   `Process*Barrier` handler for each set bit, then bumps its own
   `pss_barrierGeneration` to the shared value and broadcasts a CV.
4. The initiator calls `WaitForProcSignalBarrier(generation)` which sleeps
   on each slot's CV until every `pss_barrierGeneration >= generation` —
   at which point every backend has definitely absorbed every bit-handler.

[verified-by-code] `procsignal.c:368` (`EmitProcSignalBarrier`),
`:439-490` (`WaitForProcSignalBarrier` ordering — checks generation only,
not mask).
[from-comment] `procsignal.c:451-455` (the
"mask-cleared-before-absorb / generation-bumped-after-absorb" ordering rule).

### On-disk channels

- WAL (`pg_wal/`) — durability + replication transport.
- Archive (`archive_command` output) — for PITR and standby catch-up.
- Postmaster pid file (`postmaster.pid`).
- `pg_stat_tmp` / shared-memory stats files (varies by version).

## EXEC_BACKEND vs fork

On Unix, children inherit shared memory via plain `fork()`. On Windows (and
when `EXEC_BACKEND` is defined for testing on Unix), the child re-execs the
postgres binary and has to re-attach to shared memory and reload state. Most
of `launch_backend.c` is the abstraction over those two paths.
[verified-by-code] `postmaster/launch_backend.c:217-271` (the
`#ifdef EXEC_BACKEND` split inside `postmaster_child_launch`).

## Single-user mode

`postgres --single` runs without a postmaster — one process that does init +
PostgresMain. Used by initdb and emergency recovery. `B_STANDALONE_BACKEND`.
[verified-by-code] `miscadmin.h:353`.

## Open Questions / Unverified

- Exact list of aux processes started during recovery vs after consistent point
  is version-dependent; the walwriter and autovac launcher do not run during
  recovery on a primary. [inferred] — verify against `postmaster.c` state
  machine when working on the recovery subsystem.
- Whether `B_IO_WORKER` is enabled by default in the version `source/` points
  at (the new async-IO subsystem landed in PG 17/18). [unverified]
- Whether `wal_summarizer` is enabled by default (depends on
  `summarize_wal` GUC). [unverified]

## Pointers for going deeper

- `postmaster/postmaster.c` top comment (lines 1-63) — the design constraints.
- `postmaster/launch_backend.c:179-272` — the fork/exec dispatch.
- `postmaster/proctypelist.h` — the table that registers each process kind's
  main function and shmem-attach flag.
- `storage/lmgr/proc.c` — `PGPROC` lifecycle.
- `bgworker.c` — generic background-worker registration.
