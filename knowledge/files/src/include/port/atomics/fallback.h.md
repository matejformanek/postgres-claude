---
path: src/include/port/atomics/fallback.h
anchor_sha: e18b0cb7344
loc: 42
depth: read
---

# fallback.h

## Purpose
Last-resort fallback for platforms that lack native 64-bit atomic instructions.
Implements `pg_atomic_uint64` as a struct holding a `value` plus a semaphore id
(`sema`); the actual operations are emulated in `src/port/atomics.c` by taking
a process-shared spinlock keyed off `sema`. Pulled in only when no
arch-specific or compiler-generic header has set `PG_HAVE_ATOMIC_U64_SUPPORT`.

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `PG_HAVE_ATOMIC_U64_SIMULATION` | macro | `:23` | Sentinel: tells `generic.h` to treat 64-bit ops as non-atomic-aligned. |
| `pg_atomic_uint64` (sema variant) | struct typedef | `:26-30` | `int sema; volatile uint64 value;` — semaphore-backed. |
| `pg_atomic_init_u64_impl` | extern proto | `:33` | Implemented in `src/port/atomics.c`. |
| `pg_atomic_compare_exchange_u64_impl` | extern proto | `:36-37` | Spinlock-emulated CAS. |
| `pg_atomic_fetch_add_u64_impl` | extern proto | `:40` | Spinlock-emulated xadd. |

## Internal landmarks
- Guarded by `#ifndef INSIDE_ATOMICS_H` → `#error` — must be included only via `atomics.h` (`:16-18`).
- Activated only when `!defined(PG_HAVE_ATOMIC_U64_SUPPORT)` after all arch/compiler headers have run (`:21`).
- Sets both `PG_HAVE_ATOMIC_U64_SIMULATION` and `PG_HAVE_ATOMIC_U64_SUPPORT` so `generic.h` produces the slow paths and the `ptr->value = val` fast paths are turned off (see `generic.h:270-297`).

## Invariants & gotchas
- Never `#include` directly — always via `port/atomics.h`.
- The "u64 fallback is invisible at call sites" issue (logged in `knowledge/issues/include-port.md` by A16) is anchored here: a backend running on a fallback platform serializes every `pg_atomic_*_u64` through one of `NUM_ATOMICS_SEMAPHORES` spinlocks (default 64). Hot-path 64-bit counters become a contention point with no compile-time signal.
- No 32-bit fallback is provided — every supported platform must have native u32 atomics or the build fails.
- The `sema` field is initialized lazily by `pg_atomic_init_u64_impl` and must be reset across `fork()` — postmaster startup relies on `RequestAddinShmemSpace` accounting in atomics.c.

## Cross-refs
- [[knowledge/files/src/include/port/atomics.h.md]] — the umbrella header that pulls this in last.
- [[knowledge/files/src/include/port/atomics/generic.h.md]] — keys on `PG_HAVE_ATOMIC_U64_SIMULATION`.
- [[knowledge/issues/include-port.md]] — "u64 atomic fallback invisible at call sites".
