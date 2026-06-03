# pthread-win32.c

- **Source path:** `source/src/interfaces/libpq/pthread-win32.c`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 67 lines

## Purpose

"Partial pthread implementation for win32." [line 4, from-comment] A thin shim providing just enough POSIX thread API for libpq's internal locking on Windows. Paired with `src/interfaces/libpq/pthread-win32.h` (not in this doc set) which declares the `pthread_mutex_t`/`pthread_key_t` types.

## Coverage

Implemented:

- `pthread_self()` — wraps `GetCurrentThreadId()`. Returns `DWORD`, not the POSIX `pthread_t` — works because callers only compare for equality. [verified-by-code]
- `pthread_mutex_init(mp, attr)` — zeros `initstate`. Always returns 0. **Ignores `attr`.** [verified-by-code]
- `pthread_mutex_lock(mp)` — lazy initialization of the underlying Windows `CRITICAL_SECTION` via a 3-state initstate (0 unset, 2 initializing, 1 ready) using `InterlockedExchange`. Spin-yields with `Sleep(0)` while another thread is initializing. Then `EnterCriticalSection`.
- `pthread_mutex_unlock(mp)` — returns `EINVAL` if mutex was never initialized; else `LeaveCriticalSection`.

Stubbed (do nothing):

- `pthread_setspecific(key, val)` — empty body, no storage. [verified-by-code]
- `pthread_getspecific(key)` — always returns NULL.

[ISSUE-pthread-win32-001 — maybe] **Thread-local storage is a silent no-op on Windows.** Any libpq code that relies on `pthread_setspecific`/`pthread_getspecific` for per-thread state will see no state preserved. Whether any libpq code path actually uses these on Windows is unverified by this file alone; if yes, that path is silently broken on Win32 builds. Grep `src/interfaces/libpq` for `pthread_setspecific` callers and check the `WIN32` branches.

[ISSUE-pthread-win32-002 — maybe] The lazy-init race in `pthread_mutex_lock` uses `Sleep(0)` to yield. On a single-CPU machine under high contention, `Sleep(0)` only yields to threads of equal-or-higher priority; lower-priority initializing threads could starve. Modern Windows almost always has multiple cores so this is academic.

[ISSUE-pthread-win32-003 — maybe] `pthread_mutex_destroy` is **not provided**. The underlying `CRITICAL_SECTION` is initialized lazily but never destroyed — leaks per-mutex Windows kernel resources if a long-lived process churns through mutexes. libpq creates very few mutexes (typically one global) so this is bounded.

## Tally

`[verified-by-code]=3 [from-comment]=1 [maybe]=3`
