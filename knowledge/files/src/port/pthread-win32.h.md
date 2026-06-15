---
path: src/port/pthread-win32.h
anchor_sha: e18b0cb7344
loc: 31
depth: read
---

# src/port/pthread-win32.h

## Purpose

Tiny shim header that lets PG code `#include "pthread.h"`-style on
Windows where the real `pthread.h` doesn't exist. Provides a minimal
subset — `pthread_key_t`, `pthread_mutex_t`, `pthread_once_t`, plus
prototypes for `pthread_self`, `pthread_setspecific`,
`pthread_getspecific`, and the `pthread_mutex_*` lock/unlock trio. The
mutex is implemented on top of Win32 `CRITICAL_SECTION` with a small
init state machine. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `typedef ULONG pthread_key_t` | `pthread-win32.h:7` | TLS key, maps to `TlsAlloc` slot |
| `struct pthread_mutex_t` | `pthread-win32.h:9-14` | `{ LONG initstate; CRITICAL_SECTION csection; }` |
| `PTHREAD_MUTEX_INITIALIZER` | `pthread-win32.h:16` | `{ 0 }` — lazy-initialized at first lock |
| `typedef int pthread_once_t` | `pthread-win32.h:18` | |
| `DWORD pthread_self(void)` | `pthread-win32.h:20` | Returns Win32 thread id |
| `void pthread_setspecific(pthread_key_t, void *)` | `pthread-win32.h:22` | |
| `void *pthread_getspecific(pthread_key_t)` | `pthread-win32.h:23` | |
| `int pthread_mutex_init/lock/unlock(pthread_mutex_t *, ...)` | `pthread-win32.h:25-29` | |

## Internal landmarks

- `initstate` is a tri-state: `0` = not initialized, `1` = init done,
  `2` = init in progress (`pthread-win32.h:11`). The implementation
  (in libpq's `pthread-win32.c`, not in `src/port/`) uses an
  `InterlockedCompareExchange` spin to safely race the first lockers
  through `InitializeCriticalSection`.

## Invariants & gotchas

- This is **not** a general pthread emulation — it covers exactly what
  libpq needs for its own thread-safety on Windows. There is no
  `pthread_create`, no `pthread_cond_*`, no `pthread_join`.
- `pthread_barrier_wait.c` in this same directory uses a *different*
  `pthread.h` (via `port/pg_pthread.h`) and is the cross-platform
  barrier shim, not Windows-specific.
- The `pthread_mutex_t` here is the **address-stable** variant: the
  embedded `CRITICAL_SECTION` is initialized in-place. Callers must
  not memcpy or relocate a live mutex.

## Cross-refs

- `knowledge/files/src/port/pthread_barrier_wait.c.md` — cross-platform
  barrier shim, unrelated to this Windows-specific pthread subset.
- `source/src/interfaces/libpq/pthread-win32.c` — the matching
  implementation file.
