# port (backend platform layer)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Nathan Bossart (18), Peter Eisentraut (13), Tom Lane (11), John Naylor (11)
- **Top reviewers (last 24mo):** John Naylor (12), Tom Lane (8), Heikki Linnakangas (8), Nathan Bossart (7)
- **Recent landmark commits (12mo):**
  - `3e2a1496bae (Andrew Dunstan, 2026-04-14): Rework signal handler infrastructure to pass sender info as argument.`
  - `e2362eb2bd1 (Heikki Linnakangas, 2026-01-30): Move shmem allocator's fields from PGShmemHeader to its own struct`
  - `fbc57f2bc2e (John Naylor, 2026-04-04): Compute CRC32C on ARM using the Crypto Extension where available`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/port/`
- **Header path:** `source/src/include/port/` (especially `atomics.h` + `atomics/*.h`)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **README anchor:** none (top-of-file comments only)

## 1. Purpose

Backend's platform-portability layer for two things the backend can't
get from libc directly: **PGSemaphores** (the kernel-level sleep/wake
primitive that LWLocks ultimately sit on) and **shared memory** (the
main shmem segment that holds the buffer pool, locks, procarray, etc.).
Plus a tiny `atomics.c` that exists only to back the `pg_atomic_uint64`
spinlock-emulation path on archs that don't have 64-bit atomics.

Per-platform variants are selected at configure/meson time and only
one of each pair is linked in. Subdirectories `aix/`, `tas/`, `win32/`
hold platform-private helpers (mostly assembly for `tas`).

## 2. Mental model

- **One semaphore impl is chosen at build time.** `posix_sema.c` is
  preferred where it works; `sysv_sema.c` on systems without usable
  POSIX semaphores; `win32_sema.c` on Windows.
  ([from-comment] `posix_sema.c:1-16`, `sysv_sema.c:1-14`)
- **One shmem impl is chosen at build time.** `sysv_shmem.c` on Unix
  (mostly mmap-backed since 9.3, with a tiny SysV stub used only as
  an attach-count interlock — [from-comment] `sysv_shmem.c:43-68`);
  `win32_shmem.c` on Windows.
- **Atomics are header-only — except for u64 emulation.** Real impls
  live in `src/include/port/atomics/arch-{x86,arm,ppc}.h` and
  `generic-{gcc,msvc}.h`. The `.c` file only kicks in if
  `PG_HAVE_ATOMIC_U64_SIMULATION` is defined — then it emulates
  64-bit CAS/add via a spinlock embedded in the atomic
  ([verified-by-code] `atomics.c:21-73`).

## 3. Key files

- `atomics.c` — `pg_atomic_init_u64_impl`,
  `pg_atomic_compare_exchange_u64_impl`,
  `pg_atomic_fetch_add_u64_impl` — all under
  `#ifdef PG_HAVE_ATOMIC_U64_SIMULATION`. Use spinlock-per-atomic
  ([verified-by-code] `atomics.c:33-71`).
- `posix_sema.c` — POSIX `sem_t` based PGSemaphore impl. Prefers
  unnamed semaphores (`sem_init`), falls back to named (`sem_open`);
  named cannot be combined with `EXEC_BACKEND` ([from-comment]
  `posix_sema.c:7-16, 41-43`).
- `sysv_sema.c` — SysV `semget(2)`/`semop(2)` impl. Allocates sets of
  `SEMAS_PER_SET = 16` semaphores ([verified-by-code]
  `sysv_sema.c:48-58`), reserving one per set for identification.
  Uses `IPCProtection = 0600`, `PGSemaMagic = 537`.
- `sysv_shmem.c` (~32 KB) — main-shmem allocator. Since PG 9.3 the
  real shmem block is `mmap(MAP_ANONYMOUS|MAP_SHARED)` and the SysV
  segment is just a tiny interlock so PG can count attached
  processes ([from-comment] `sysv_shmem.c:43-68`). PG 12+ can choose
  full SysV via `shared_memory_type=sysv`.
- `win32_shmem.c` (~20 KB) — Win32 `CreateFileMapping` impl, with
  the dance of reserving a *protective region* immediately before
  releasing/remapping shmem on `EXEC_BACKEND` reattach to avoid
  the default-thread-pool stealing the address range
  ([from-comment] `win32_shmem.c:22-40`).
- `win32_sema.c` — Win32 `CreateSemaphore` PGSemaphore impl.
- `pg_sema.c` — *does not exist* as a standalone file; the
  declarations are in `src/include/storage/pg_sema.h`.

The platform-private subdirs `aix/`, `tas/`, `win32/` were not
opened in this pass — they're support code that only platform-specific
builds compile.

## 4. Key data structures

- **`PGSemaphore`** (`storage/pg_sema.h`). Opaque to callers. Concrete
  shapes:
  - POSIX: `union SemTPadded { sem_t pgsem; char pad[PG_CACHE_LINE_SIZE]; }`
    — padded to one cache line ([verified-by-code]
    `posix_sema.c:45-49`).
  - SysV: `struct PGSemaphoreData { int semId; int semNum; }`
    ([verified-by-code] `sysv_sema.c:30-34`).
- **`pg_atomic_uint64`** — when emulated, holds a `slock_t sema`
  spinlock plus the `uint64 value` ([verified-by-code]
  `atomics.c:26-30`).

## 5. Control flow — the common paths

This subsystem is almost all *one-shot* initialization called from
`CreateSharedMemoryAndSemaphores` and friends. The hot path for
production users is just `PGSemaphoreLock` / `PGSemaphoreUnlock`
during LWLock sleep/wake, both of which are thin wrappers around
`sem_wait`/`sem_post` (POSIX) or `semop` (SysV) — not worth a deep
trace beyond noting "it's the libc primitive".

The interesting flow is shmem creation on Unix (sketched from
`sysv_shmem.c:43-68` [from-comment]):
1. `PGSharedMemoryCreate` allocates the real region via anonymous
   `mmap`. The buffer pool, lock table, procarray etc. live here.
2. A tiny SysV shm segment is also created. Its only purpose is that
   `shmctl(IPC_STAT)` lets PG count how many processes are attached
   — anonymous mmap provides no such API. This is the interlock
   that prevents two postmasters from using one data dir.
3. On `EXEC_BACKEND` (Windows; also dev builds on Unix), child
   processes have to **re-attach** to the segment at the same virtual
   address. `sysv_shmem.c` falls back to SysV-only in this case
   because anonymous mmap can't survive `exec()`.

## 6. Locking and invariants

- Anonymous mmap shmem cannot be used with `EXEC_BACKEND` (no way to
  re-attach after exec) — `sysv_shmem.c` falls back to full SysV
  ([from-comment] `sysv_shmem.c:58-64`).
- POSIX named semaphores cannot be used with `EXEC_BACKEND`
  ([verified-by-code] `posix_sema.c:41-43` `#error`).
- `SEMAS_PER_SET` must be *less than* the kernel's `SEMMSL` ([from-comment]
  `sysv_sema.c:48-54`). Too-high values cause subtle `semget` failures
  on older Linuxes.
- The `pg_atomic_uint64` emulation uses *one* spinlock per atomic —
  this is "strong" CAS semantics (no spurious failure)
  ([from-comment] `atomics.c:39-46`).

## 7. Interactions with other subsystems

- **storage/lmgr/** — LWLocks and the proc latch ultimately sleep on
  `PGSemaphore`.
- **storage/ipc/** — `CreateSharedMemoryAndSemaphores` is the single
  entry that drives both shmem and semaphore init.
- **postmaster/** — `EXEC_BACKEND` reattach paths on Windows.
- **port/atomics/*.h** — `atomics.c` is only the fallback layer;
  the fast path is entirely inline assembly / compiler intrinsics
  from the headers.

## 8. Tests

No direct tests. Exercised implicitly by every regression run, since
every backend uses semaphores + shmem. Misbehavior shows up as
`semget` / `shmget` errors at `initdb` or postmaster start.

## 9. Open questions / unverified claims

1. Win32 detail beyond the head comments not read. `win32_sema.c`,
   `win32_shmem.c` body not deep-read.
2. `aix/`, `tas/` subdirs not inspected; `tas/` is presumably
   per-arch assembly for the test-and-set fallback spinlock impl.
3. `PG_CACHE_LINE_SIZE` value and what triggers SysV-vs-POSIX
   selection at configure time — defer.

## 10. Glossary

- **PGSemaphore** — the kernel sleep/wake primitive used by LWLocks.
- **`EXEC_BACKEND`** — build flag that exec()s instead of relying on
  fork() inheritance. Default on Windows; opt-in on Unix for testing.
- **Anonymous mmap shmem** — the standard PG ≥ 9.3 approach: shmem
  backed by `MAP_ANONYMOUS|MAP_SHARED` mmap, with a tiny SysV
  segment as an attach-count interlock.
- **`PG_HAVE_ATOMIC_U64_SIMULATION`** — set when the platform lacks
  native 64-bit atomics; `atomics.c` then emulates them with a
  per-atomic spinlock.
- **SEMMSL / SEMMNI / SEMMNS** — SysV kernel limits on semaphores;
  the canonical "you might have to tune your kernel" knobs for PG.
