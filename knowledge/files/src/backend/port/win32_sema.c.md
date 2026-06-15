---
path: src/backend/port/win32_sema.c
anchor_sha: e18b0cb7344
loc: 235
depth: read
---

# src/backend/port/win32_sema.c

## Purpose

Backs `PGSemaphore` using **Win32 anonymous semaphores** (`CreateSemaphore` /
`WaitForMultipleObjectsEx` / `ReleaseSemaphore`). Selected automatically when
building for Windows (no configure flag — the platform decides). The
fundamental shape mirrors `sysv_sema.c` and `posix_sema.c` but the
implementation must integrate with PG's Win32 signal-emulation layer
(`win32/signal.c`), since Windows has no native POSIX signals.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void PGSemaphoreShmemRequest(int maxSemas)` | `win32_sema.c:31` | No-op — no shmem needed on Windows |
| `void PGSemaphoreInit(int maxSemas)` | `win32_sema.c:46` | Allocates the postmaster-local `HANDLE` array |
| `PGSemaphore PGSemaphoreCreate(void)` | `win32_sema.c:78` | `CreateSemaphore` with initial 1, max 32767 |
| `void PGSemaphoreReset(PGSemaphore)` | `win32_sema.c:115` | Drains via repeated `PGSemaphoreTryLock` |
| `void PGSemaphoreLock(PGSemaphore)` | `win32_sema.c:131` | Multi-object wait on sema + signal event |
| `void PGSemaphoreUnlock(PGSemaphore)` | `win32_sema.c:195` | `ReleaseSemaphore(sema, 1, NULL)` |
| `bool PGSemaphoreTryLock(PGSemaphore)` | `win32_sema.c:209` | `WaitForSingleObject(sema, 0)` |

## Internal landmarks

- **`mySemSet[]` postmaster-local registry** (`win32_sema.c:20`) — array of
  raw `HANDLE`s populated as `PGSemaphoreCreate` is called. Released by
  `ReleaseSemaphores` (`:63`) as an `on_shmem_exit` callback. Anonymous
  semas are auto-freed by Windows when the last referencing process exits,
  so no kernel-level cleanup beyond `CloseHandle` is required.
- **`PGSemaphoreLock` dual-event wait** (`:131-187`) — the heart of the
  Windows integration. `WaitForMultipleObjectsEx(2, {pgwin32_signal_event,
  sema}, FALSE, INFINITE, TRUE)`:
  - **`WAIT_OBJECT_0`** = signal event fired → call
    `pgwin32_dispatch_queued_signals()` and re-loop. `[verified-by-code]`
  - **`WAIT_OBJECT_0 + 1`** = sema acquired → done.
  - **`WAIT_IO_COMPLETION`** = APC fired (e.g. some loaded DLL) → resume
    waiting; PG itself never queues APCs (`:170-175`).
  - **`WAIT_FAILED`** = FATAL.
- **`CHECK_FOR_INTERRUPTS` at top of loop** (`:154`) — must be called each
  iteration. Comment at `:145-149` explains: unlike POSIX, where signal
  delivery happens magically during the syscall, on Windows PG must
  service interrupts explicitly. The signal event in the wait array is
  what wakes us; the CHECK is what then does cancel/die processing.
- **Signal event ordering matters** (`:137-141`) — `pgwin32_signal_event`
  is `wh[0]`, sema is `wh[1]`. `WaitForMultipleObjects` reports the
  lowest-indexed signaled object when several are ready, so we are
  guaranteed to drain signals before consuming the sema.

## Invariants & gotchas

- **Anonymous, inheritable HANDLEs** (`:81-95`). `bInheritHandle = TRUE` is
  what lets forked-and-exec'd children inherit the same sema (Windows
  always uses fork+exec — see `EXEC_BACKEND`). `lpSecurityDescriptor =
  NULL` means default ACL.
- **Max count = 32767** (`:95`) — the `lMaximumCount` parameter to
  `CreateSemaphore`. PGSemaphore is binary-ish in practice (latches and
  proc-sleeps use values 0/1), so the high cap is just defensive.
- **No `PGSemaphoreReset` API.** Like POSIX, Win32 has no "set count"
  primitive. PG ratchets the count down by looping `WaitForSingleObject(s,
  0)` until it returns `WAIT_TIMEOUT` (`:121-122`). Same pattern as
  `posix_sema.c::PGSemaphoreReset`.
- **PGSemaphoreCreate is postmaster-only.** Assertion `!IsUnderPostmaster`
  at `:84`. `mySemSet` lives in the postmaster's address space and is
  copied to children via `EXEC_BACKEND` parameter passing.
- **No EINTR loop.** Unlike POSIX where `sem_wait` can return early on
  signal, Win32's `WaitForMultipleObjectsEx` cleanly reports
  `WAIT_OBJECT_0` (signal event) vs `WAIT_OBJECT_0 + 1` (sema). The
  multi-object semantics replace the EINTR retry pattern.
- **`PGSemaphoreShmemRequest` is a no-op.** Windows semaphores are kernel
  objects identified by HANDLE, not shared memory structures, so no shmem
  allocation is needed (contrast `sysv_sema.c:307` which allocates
  `sharedSemas[]`). `[verified-by-code at :31]`

## Cross-refs

- `knowledge/subsystems/storage-ipc.md` — IPC layer overview.
- `knowledge/files/src/include/storage/pg_sema.h.md` — the abstract
  interface.
- `knowledge/files/src/backend/port/win32/signal.c.md` —
  `pgwin32_signal_event` and `pgwin32_dispatch_queued_signals` referenced
  in the wait loop.
- `knowledge/files/src/backend/port/sysv_sema.c.md` /
  `knowledge/files/src/backend/port/posix_sema.c.md` — Unix counterparts.
- `knowledge/idioms/locking.md` — PGSemaphore in the lock taxonomy.
