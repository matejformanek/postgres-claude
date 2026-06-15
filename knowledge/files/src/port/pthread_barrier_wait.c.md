---
path: src/port/pthread_barrier_wait.c
anchor_sha: e18b0cb7344
loc: 77
depth: read
---

# src/port/pthread_barrier_wait.c

## Purpose

In-tree `pthread_barrier_t` implementation for platforms whose pthread
library doesn't include POSIX barriers (notably macOS, which ships
pthreads but not `pthread_barrier_*`). Provides `init`, `wait`, and
`destroy`. Compiled into `libpgport` when `configure`/meson detects the
absence of the system barrier symbols. `[verified-by-code]`

A barrier holds `count` threads at `pthread_barrier_wait()` until all
`count` have arrived, then releases them all simultaneously. PG uses
barriers in test harnesses and (sparingly) in parallel-worker
synchronization patterns where every worker must reach a common point
before any may proceed.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pthread_barrier_init(pthread_barrier_t *barrier, const void *attr, int count)` | `pthread_barrier_wait.c:18` | `attr` ignored; returns errno on `pthread_cond_init`/`pthread_mutex_init` failure |
| `int pthread_barrier_wait(pthread_barrier_t *barrier)` | `pthread_barrier_wait.c:38` | Returns `PTHREAD_BARRIER_SERIAL_THREAD` to exactly one waiter, `0` to the rest |
| `int pthread_barrier_destroy(pthread_barrier_t *barrier)` | `pthread_barrier_wait.c:72` | Tears down the embedded cond + mutex |

## Internal landmarks

- The barrier struct (defined in `port/pg_pthread.h`, not shown here)
  holds: `bool sense`, `int count`, `int arrived`, `pthread_cond_t
  cond`, `pthread_mutex_t mutex` — used at `pthread_barrier_wait.c:23-25`.
- **Sense-reversal idiom** (`pthread_barrier_wait.c:60-64`): instead of
  resetting an `arrived` counter to 0 after release (which races with
  late-arriving threads from the next cycle), the barrier flips a
  `sense` bool. Waiters loop on `barrier->sense == initial_sense`. The
  last arriver flips `sense` and broadcasts.
- The last arriver returns `PTHREAD_BARRIER_SERIAL_THREAD`
  (`pthread_barrier_wait.c:56`) — POSIX-mandated to designate one
  thread for post-barrier cleanup.

## Invariants & gotchas

- `arrived` is asserted `<= count` (`pthread_barrier_wait.c:46`). Over-
  arrival means a caller invoked `wait()` from more than `count`
  threads — usually a logic bug.
- Mutex is released *before* `pthread_cond_broadcast`
  (`pthread_barrier_wait.c:53-54`). The broadcast doesn't need the mutex
  held, and releasing first avoids a thundering-herd contention spike.
- Sense-reversal means **the same barrier struct can be reused** across
  cycles without re-init. Don't `destroy` + `init` between cycles.
- `attr` arg is ignored — barrier attributes (process-shared etc.) are
  not implementable here without dragging in more pthread API surface.

## Cross-refs

- `source/src/include/port/pg_pthread.h` — struct definition + the
  fallback prototypes.
- `knowledge/files/src/port/pthread-win32.h.md` — *different* shim,
  Windows-only minimal pthread subset.
