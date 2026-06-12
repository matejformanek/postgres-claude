---
path: src/include/port/atomics/generic.h
anchor_sha: e18b0cb7344
loc: 436
depth: read
---

# generic.h

## Purpose
The "build everything else from compare-exchange" layer of the atomics stack.
Arch- and compiler-specific headers (arch-x86.h, arch-ppc.h, generic-gcc.h,
generic-msvc.h, fallback.h) define a minimum set of primitives — typically
`pg_atomic_compare_exchange_*` and `pg_atomic_fetch_add_*` — and this file
synthesizes everything else (read, write, exchange, fetch-sub/and/or,
add-fetch/sub-fetch, read/write-with-membarrier) by chaining CAS loops or by
delegating to the existing primitives.

## Public symbols
All `static inline` `*_impl` functions; the public `pg_atomic_*` names are
defined by `atomics.h` and dispatch here. The macros indicate which
primitives this file synthesizes when the preceding layer left them blank.

| Synthesized op | File:line | Strategy |
|---|---|---|
| `pg_read_barrier_impl`, `pg_write_barrier_impl` (fallback to full mb) | `:24-29` | Upgrade undefined read/write barriers to full memory barrier. |
| `pg_spin_delay_impl` (no-op) | `:31-34` | Defined as `((void)0)` if arch didn't provide one. |
| `pg_atomic_flag` (alias to u32) | `:38-41` | When arch has u32 but not separate flag type. |
| `pg_atomic_read_u32_impl` | `:43-50` | Plain load. |
| `pg_atomic_write_u32_impl` | `:52-59` | Plain store. |
| `pg_atomic_unlocked_write_u32_impl` | `:61-68` | Same — caller asserts no contention. |
| `pg_atomic_init_flag_impl` / `pg_atomic_test_set_flag_impl` / `_clear_flag_impl` / `_unlocked_test_flag_impl` | `:75-104` (exchange variant) `:112-141` (CAS variant) | Two variants: implement via `pg_atomic_exchange_u32` or via CAS. |
| `pg_atomic_init_u32_impl` | `:148-155` | Plain store; same restriction as `pg_atomic_init` in `atomics.h`. |
| `pg_atomic_exchange_u32_impl` | `:158-167` | CAS loop. |
| `pg_atomic_fetch_add_u32_impl` | `:171-180` | CAS loop. |
| `pg_atomic_fetch_sub_u32_impl` | `:184-189` | Calls fetch_add with `-sub_`. |
| `pg_atomic_fetch_and_u32_impl` / `_fetch_or_u32_impl` | `:194-202`, `:206-215` | CAS loops. |
| `pg_atomic_add_fetch_u32_impl` / `_sub_fetch_u32_impl` | `:219-224`, `:228-233` | Derived from fetch-add. |
| `pg_atomic_read_membarrier_u32_impl` | `:236-242` | `fetch_add(0)` — emulates seq-cst read. |
| `pg_atomic_write_membarrier_u32_impl` | `:245-251` | `(void) exchange(val)` — emulates seq-cst write. |
| `pg_atomic_exchange_u64_impl` | `:254-264` | CAS loop. |
| `pg_atomic_write_u64_impl` | `:267-297` | Plain store if 8-byte single-copy + no simulation, else exchange. |
| `pg_atomic_unlocked_write_u64_impl` | `:300-306` | Plain store. |
| `pg_atomic_read_u64_impl` | `:309-343` | Aligned load if single-copy, else `compare_exchange(0)` trick. |
| `pg_atomic_init_u64_impl` | `:345-352` | Plain store. |
| `pg_atomic_fetch_add_u64_impl` / `_sub` / `_and` / `_or` / `_add_fetch` / `_sub_fetch` | `:354-418` | All CAS-loop or derived. |
| `pg_atomic_read_membarrier_u64_impl` / `_write_membarrier_u64_impl` | `:420-436` | Same pattern as u32. |

## Internal landmarks
- Guarded by `#ifndef INSIDE_ATOMICS_H` → `#error` (`:16-18`).
- The flag emulation has THREE forks: exchange-based (`:73`), CAS-based (`:110`), and `#error` (`:143-145`) if neither exists — i.e. we refuse to build a platform with no usable test-and-set primitive.
- The "compare_exchange(0)" read trick at `:327-341` reads u64 atomically on platforms without 8-byte single-copy atomicity — the comment notes it might spuriously store a 0 *only when the existing value was already 0* (harmless).
- The split between `PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY` and `PG_HAVE_ATOMIC_U64_SIMULATION` at `:270-283` / `:312-322` is subtle: the fallback semaphore path can't guarantee 8-byte alignment of the value field (it's prefixed by an `int sema`), so even on arches that *would* support single-copy aligned u64, we go through the spinlock path.
- "XXX: release semantics suffice?" comment at `:101` and `:138` — open question whether the full memory barrier on flag clear is overkill.

## Invariants & gotchas
- Always `#include`d via `atomics.h` AFTER all arch/compiler/fallback headers — that's how `#ifndef PG_HAVE_ATOMIC_X` correctly fills the gaps.
- `pg_atomic_init_u32_impl` deliberately omits any barrier — `pg_atomic_init` in `atomics.h` is documented as not safe for concurrent use against other accessors. Same for u64.
- `pg_atomic_unlocked_*` variants intentionally skip the locked-instruction overhead; correctness depends on the caller proving no other thread is touching the value (typical at backend startup before publishing the pointer).
- The CAS-loop synthesizers all use `old = ptr->value` as the initial read — explicit comment "ok if read is not atomic" (`:163`, `:176`, etc.): a torn read just gets corrected on the first CAS failure.
- `pg_atomic_read_membarrier_u32_impl` via `fetch_add(0)` does a R-M-W and thus a write to the cache line; on a hot read-mostly counter this can bounce cache lines among CPUs even though semantically read-only. Caller should prefer plain `pg_atomic_read_u32` unless they need seq-cst ordering.

## Cross-refs
- [[knowledge/files/src/include/port/atomics.h.md]] — the umbrella header that defines the public `pg_atomic_*` names atop these `_impl` symbols.
- [[knowledge/files/src/include/port/atomics/generic-gcc.h.md]] — sibling, supplies primitives via gcc intrinsics.
- [[knowledge/files/src/include/port/atomics/fallback.h.md]] — when 64-bit support is missing entirely.
- [[knowledge/issues/include-port.md]] — `pg_atomic_read_membarrier_*` perf cost; barrier-asymmetry observations.
