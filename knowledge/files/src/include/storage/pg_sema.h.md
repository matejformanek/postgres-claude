# `src/include/storage/pg_sema.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 61

## Role

**Counting-semaphore platform abstraction.** Each backend's
LWLock fallback (when contended past spinlock retries) and the
PROC-wait machinery use these. Backends: POSIX
(`port/posix_sema.c`), SysV (`port/sysv_sema.c`), Windows
(`port/win32_sema.c`).

## Public API

[verified-by-code] `source/src/include/storage/pg_sema.h:30-60`

- `PGSemaphoreData` opaque struct; `PGSemaphore` pointer
- Windows special-case: `PGSemaphore = HANDLE` (line 36)
- `PGSemaphoreShmemRequest(maxSemas)` — sized at startup
- `PGSemaphoreInit(maxSemas)` — initialize the pool
- `PGSemaphoreCreate(void)` — allocates one with count=1
- `PGSemaphoreReset(sema)` — count=0
- `PGSemaphoreLock(sema)` — decrement, block if would go < 0
- `PGSemaphoreUnlock(sema)` — increment
- `PGSemaphoreTryLock(sema)` — non-blocking attempt

## Invariants

- INV-1: counting (not binary) semaphores. Multiple unlocks =
  multiple subsequent locks. [from-comment] lines 6-9.
- INV-2: opaque `PGSemaphoreData` per non-Windows port — must
  not be touched by platform-independent code. [from-comment]
  lines 24-28.
- INV-3: Lock is INTERRUPTIBLE on signal? Generally not at the
  raw level; the SysV/POSIX impls retry on EINTR. PG-level
  cancellation goes through a different path (latch).

## Trust boundary (Phase D)

- **sysctl `kernel.semmni`/`SEMMSL`** (SysV path) caps the
  number of semaphores; misconfig → postmaster startup fails.
  Sysadmin perimeter, not user-controllable.
- POSIX path uses `sem_init` in shmem — no per-segment perm
  separately; relies on shmem 0600 perms (pg_shmem.h).

## Cross-refs

- `knowledge/files/src/include/storage/pg_shmem.h.md`
- `knowledge/files/src/include/storage/lwlock.h.md` (existing)
- `knowledge/files/src/backend/port/posix_sema.c.md` (if exists)
- `knowledge/files/src/backend/port/sysv_sema.c.md` (if exists)

## Issues

None.
