---
path: src/backend/port/posix_sema.c
anchor_sha: e18b0cb7344
loc: 382
depth: read
---

# src/backend/port/posix_sema.c

## Purpose

Backs `PGSemaphore` using **POSIX semaphores** (`sem_init` / `sem_open` /
`sem_wait` / `sem_post`). Selected at configure time when
`USE_NAMED_POSIX_SEMAPHORES` or `USE_UNNAMED_POSIX_SEMAPHORES` is defined
(`[from-comment]`, see `pg_config.h.in`). Alternative to `sysv_sema.c`;
preferred on systems where SysV IPC limits are restrictive or POSIX is
considered the modern path (macOS, some Linux distros).

The file actually implements two flavors driven by the same configure
selection:

- **Unnamed** (preferred, `sem_init`): `sem_t` structs live in PG shared
  memory; sharing is automatic by pointer.
- **Named** (`sem_open` + `sem_unlink`): `sem_t` structs live in the
  postmaster's private heap and are inherited via `fork()`. **Does NOT
  support `EXEC_BACKEND`** — explicitly `#error`'d at `posix_sema.c:41-43`.

`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void PGSemaphoreShmemRequest(int maxSemas)` | `posix_sema.c:165` | No shmem for named; sizes `sharedSemas[]` for unnamed |
| `void PGSemaphoreInit(int maxSemas)` | `posix_sema.c:198` | Seeds `nextSemKey` from data-dir inode |
| `PGSemaphore PGSemaphoreCreate(void)` | `posix_sema.c:255` | Postmaster-only |
| `void PGSemaphoreReset(PGSemaphore)` | `posix_sema.c:288` | Drains via repeated `sem_trywait` |
| `void PGSemaphoreLock(PGSemaphore)` | `posix_sema.c:313` | EINTR-retry loop around `sem_wait` |
| `void PGSemaphoreUnlock(PGSemaphore)` | `posix_sema.c:333` | EINTR-retry around `sem_post` |
| `bool PGSemaphoreTryLock(PGSemaphore)` | `posix_sema.c:358` | EINTR-retry around `sem_trywait` |

## Internal landmarks

- **`SemTPadded` union** (`posix_sema.c:45-49`) — pads each `sem_t` out to
  `PG_CACHE_LINE_SIZE` to avoid false sharing between adjacent
  PGSemaphoreData entries in the shmem array. Critical for high-concurrency
  workloads where neighboring backends touch neighboring semas.
- **`PosixSemaphoreCreate` — named** (`:85-126`) — loops with
  `sem_open(/pgsql-<n>, O_CREAT|O_EXCL)`, retrying on collision (`EEXIST`,
  `EACCES`, `EINTR`). **Immediately `sem_unlink`s** after successful create
  (`:123`) — the sema persists by virtue of the open fd in this process,
  but no other process can find it by name, and a crash leaves no kernel
  named-semaphore leak.
- **`PosixSemaphoreCreate` — unnamed** (`:134-139`) — single `sem_init(sem,
  1, 1)` call. The `pshared = 1` arg is what makes it work across `fork()`.
- **`PosixSemaphoreKill`** (`:146-158`) — branches on configure flag:
  `sem_close` for named, `sem_destroy` for unnamed. Both LOG-level on
  failure; never FATAL — shutdown path must press on.

## Invariants & gotchas

- **Named flavor is incompatible with EXEC_BACKEND.** The `#error` at
  `:41-43` catches this at compile time. The reason: `sem_open` allocates
  `sem_t` in the postmaster's anonymous heap, which is preserved by `fork`
  but NOT by `fork+exec`. Backends would be unable to access semas they
  ostensibly inherited. `[from-comment at :10-15]`
- **No kernel resource leak from named semas.** Because of the immediate
  `sem_unlink` (`:123`), even a `kill -9 postmaster` does NOT leave
  visible named semaphores on disk (Linux: `/dev/shm/sem.pgsql-*`). The
  sem is reaped when the last fd referencing it closes.
- **`sem_trywait` errno is platform-dependent.** Linux returns `EAGAIN`;
  some others return `EDEADLK`. Both are handled at `:298` and `:374`.
- **EINTR loop on every blocking op.** Same pattern as `sysv_sema.c`: PG
  retries `sem_wait` / `sem_post` / `sem_trywait` on `EINTR` without
  servicing the signal. Signal delivery is the layer above's job.
  `[from-comment at :337-342]`
- **`PGSemaphoreReset` drains.** POSIX has no "set count" — only
  `sem_post` / `sem_wait`. To force count to 0, the code loops
  `sem_trywait` until it returns `EAGAIN`/`EDEADLK` (`:294-304`). Same
  pattern as `win32_sema.c::PGSemaphoreReset`.
- **`PGSemaphoreCreate` is postmaster-only.** Assertion `!IsUnderPostmaster`
  at `:261`. Static counters populated pre-fork.
- **Key seeding from data-dir inode** (`:222`) — same trick as
  `sysv_sema.c`, minimizes collision between independent clusters' named
  semaphores.

## Cross-refs

- `knowledge/subsystems/storage-ipc.md` — overall IPC layer.
- `knowledge/files/src/include/storage/pg_sema.h.md` — abstract interface.
- `knowledge/files/src/backend/port/sysv_sema.c.md` — sister
  implementation, selected by `USE_SYSV_SEMAPHORES`.
- `knowledge/files/src/backend/port/win32_sema.c.md` — Windows
  implementation.
- `knowledge/idioms/locking.md` — PGSemaphore's role in PG's six-layer
  lock taxonomy.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
