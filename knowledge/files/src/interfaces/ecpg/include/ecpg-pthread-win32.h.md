---
path: src/interfaces/ecpg/include/ecpg-pthread-win32.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 49
depth: read
---

# `ecpg-pthread-win32.h` — pthread→Win32 thread shim for ecpglib

## Purpose
Lets ecpglib's thread-safety code (per-thread `sqlca`, the mutex-guarded
connection/statement-cache state) be written once against the pthreads API. On
non-Windows it just `#include <pthread.h>`; on Windows it maps the small pthreads
subset ecpglib needs onto Win32 primitives (CRITICAL_SECTION, TLS, one-time
init). [verified-by-code]

## Public symbols (WIN32 branch only)
| Symbol | Site | Notes |
|---|---|---|
| `pthread_mutex_t` | ecpg-pthread-win32.h:13 | `LONG initstate` + `CRITICAL_SECTION` [verified-by-code] |
| `pthread_key_t` / `pthread_once_t` | ecpg-pthread-win32.h:20-21 | `DWORD` / `bool` [verified-by-code] |
| `PTHREAD_MUTEX_INITIALIZER` / `PTHREAD_ONCE_INIT` | ecpg-pthread-win32.h:23-24 | static initializers [verified-by-code] |
| `pthread_mutex_init/_lock/_unlock` | ecpg-pthread-win32.h:26-28 | real fns (in `misc.c`) [verified-by-code] |
| `win32_pthread_once` | ecpg-pthread-win32.h:30 | one-time init helper [verified-by-code] |
| `pthread_getspecific/_setspecific/_key_create/_once` | ecpg-pthread-win32.h:32-46 | macros over TLS / `win32_pthread_once` [verified-by-code] |

## Internal landmarks
- `pthread_mutex_t.initstate` is a 3-state lazy-init flag (0 not-init / 1 done /
  2 in-progress, ecpg-pthread-win32.h:15) so a statically-initialized mutex
  (`PTHREAD_MUTEX_INITIALIZER = {0}`) can defer `InitializeCriticalSection`
  until first lock. [verified-by-code]
- `pthread_once` is a macro that fast-paths the already-done case without calling
  the helper (ecpg-pthread-win32.h:42-46). [verified-by-code]

## Invariants & gotchas
- **Documented FIXME: TLS destructors are never called on Win32**
  (ecpg-pthread-win32.h:38-40) — `pthread_key_create` discards the `destructor`
  argument. Any per-thread cleanup ecpglib registers via a key destructor
  silently does not run on Windows, so thread-local allocations can leak at
  thread exit on that platform. [verified-by-code] See `knowledge/issues/ecpg.md`.
- The Win32 mutex shim is non-recursive (CRITICAL_SECTION is actually recursive,
  but the 3-state init is not reentrancy-safe during the init window). [inferred]

## Cross-refs
- `knowledge/files/src/interfaces/ecpg/ecpglib/misc.c.md` — implements
  `pthread_mutex_*`, `win32_pthread_once`, and the per-thread sqlca.

## Potential issues
- **[ISSUE-leak: Win32 pthread_key destructor never runs]**
  `ecpg-pthread-win32.h:38` — `pthread_key_create` drops its destructor on
  Windows (long-standing FIXME); per-thread cleanup is skipped → potential
  per-thread leak on thread exit. Mirrored to `knowledge/issues/ecpg.md`.
