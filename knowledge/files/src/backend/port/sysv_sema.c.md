---
path: src/backend/port/sysv_sema.c
anchor_sha: e18b0cb7344
loc: 531
depth: read
---

# src/backend/port/sysv_sema.c

## Purpose

Backs `PGSemaphore` (the abstract semaphore type used by `proc.c`, `lwlock.c`,
and any sleeping primitive in the backend) using **System V semaphore sets**
(`semget` / `semop` / `semctl`). Selected at configure time when
`USE_SYSV_SEMAPHORES` is defined (`[from-comment]`, see `pg_config.h.in`).
This is the historical default on Linux/BSD; the alternative is
`posix_sema.c`.

`PGSemaphore` is the binary-blocking primitive sitting just above the kernel
in PG's six-layer locking taxonomy: ProcArray slots, latches, and the
LWLock semaphore array all bottom out in `PGSemaphoreLock` /
`PGSemaphoreUnlock`. Without these, `LWLockAcquire`'s slow path could not
sleep. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void PGSemaphoreShmemRequest(int maxSemas)` | `sysv_sema.c:307` | Reserves shmem space for `maxSemas` `PGSemaphoreData` slots |
| `void PGSemaphoreInit(int maxSemas)` | `sysv_sema.c:334` | Postmaster startup; seeds key search from data-dir inode |
| `PGSemaphore PGSemaphoreCreate(void)` | `sysv_sema.c:386` | Returns next free sema slot; postmaster-only |
| `void PGSemaphoreReset(PGSemaphore)` | `sysv_sema.c:421` | Force count to 0 |
| `void PGSemaphoreLock(PGSemaphore)` | `sysv_sema.c:432` | Decrement / block; loops on EINTR |
| `void PGSemaphoreUnlock(PGSemaphore)` | `sysv_sema.c:465` | Increment |
| `bool PGSemaphoreTryLock(PGSemaphore)` | `sysv_sema.c:495` | Non-blocking via `IPC_NOWAIT` |

## Internal landmarks

- **`SEMAS_PER_SET = 16`** (`sysv_sema.c:54`) — PG packs 16 semaphores into
  one SysV "sema set" plus one extra "identification" semaphore (=17 total
  per `semget` call). Must stay below the kernel's `SEMMSL` (typical 25);
  raising it past that produces unhelpful `EINVAL` from `semget`.
  `[from-comment]`
- **`PGSemaMagic = 537`** (`sysv_sema.c:58`) — the magic value PG writes
  into the per-set identification semaphore via `IpcSemaphoreInitialize`
  (`:294`) and reads back during crash-recovery key search (`:248`).
  Lets PG distinguish "abandoned PG sema set" from "some other app's sema
  set" before it dares zap one.
- **`IpcSemaphoreCreate` at `:222`** — the dead-postmaster recycling loop.
  For each candidate key it:
  1. Tries `semget(IPC_CREAT|IPC_EXCL)` (`:239`).
  2. If collision, opens the existing set and reads the magic + GETPID
     of the creator (`:248-255`).
  3. If `creatorPID != getpid()`, sends signal 0 (`kill(pid, 0)`) to test
     liveness (`:260`). `ESRCH` means dead → safe to `IPC_RMID` and reuse.
  4. Else loop to next key.
- **Key seed = data-dir inode** (`sysv_sema.c:359`) — minimizes collisions
  between independent clusters on the same host and maximizes collision
  with our own crashed postmaster's leftover sema sets (so we can detect
  and clean them up).
- **`ReleaseSemaphores` on_shmem_exit hook** (`:370-378`) — `IPC_RMID`s
  every sema set we own. The postmaster-local `mySemaSets` array (NOT in
  shmem) drives the loop so that a backend that scribbled over shmem
  cannot prevent cleanup. `[from-comment at :329]`

## Invariants & gotchas

- **PGSemaphoreCreate is postmaster-only.** Assertion `!IsUnderPostmaster`
  at `:391`. The static counters `numSharedSemas`, `numSemaSets`, and
  `nextSemaNumber` are populated before fork; child backends inherit by
  copy.
- **`semget` errno taxonomy** is intricate (`:107-128`): `EEXIST`,
  `EACCES`, `EINVAL`, and `EIDRM` all mean "collision, try another key"
  and are silently retried up to 1000 times. `ENOSPC` produces a verbose
  hint about `SEMMNI` / `SEMMNS` kernel limits (`:139-147`).
- **EINTR loop on `semop`** (`:450-453`, `:480-483`, `:509-512`) — SysV
  `semop` can return with `errno == EINTR` if a signal was delivered.
  PG's policy is to retry immediately rather than service interrupts from
  signal context. `CHECK_FOR_INTERRUPTS` happens at the latch / WaitEventSet
  layer above, not here. `[from-comment at :441-449]`
- **Kernel resource leakage.** A `kill -9 postgres` (or postmaster crash
  followed by a system reboot before cleanup) can leave SysV semaphore
  sets in the kernel's IPC namespace. They are detected and recycled on
  next startup via the dead-postmaster scan, but until then they show up
  in `ipcs -s` and count against `SEMMNI`. The recycling logic depends on
  the magic value (`:248`) and PID-liveness check (`:260`) — both required.
- **No autosizing.** `maxSemas` passed to `PGSemaphoreInit` is set in
  `CalculateShmemSize` based on `max_connections` etc. Reaching it triggers
  `elog(PANIC, "too many semaphores created")` (`:397, :404`). This is
  fundamentally a postmaster-startup limit.
- **`union semun` is conditional** (`:36-43`) — some platforms declare it
  in `<sys/sem.h>`, others require us to define it. The `HAVE_UNION_SEMUN`
  configure probe picks.

## Cross-refs

- `knowledge/subsystems/storage-ipc.md` — overall IPC layer overview.
- `knowledge/files/src/include/storage/pg_sema.h.md` — the abstract
  interface this file implements.
- `knowledge/files/src/backend/port/posix_sema.c.md` — alternative
  implementation; selected by `USE_NAMED_POSIX_SEMAPHORES` or
  `USE_UNNAMED_POSIX_SEMAPHORES`.
- `knowledge/files/src/backend/port/sysv_shmem.c.md` — companion file
  that uses the same data-dir-inode key-seeding trick and the same
  dead-postmaster recycling pattern.
- `knowledge/idioms/locking.md` — where PGSemaphore sits in the six-layer
  taxonomy.
