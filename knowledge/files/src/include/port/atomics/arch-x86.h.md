---
path: src/include/port/atomics/arch-x86.h
anchor_sha: e18b0cb7344
loc: 243
depth: read
---

# arch-x86.h

## Purpose
x86 / x86-64-specific atomic-ops implementation: defines `pg_atomic_flag`,
`pg_atomic_uint32` (and `pg_atomic_uint64` on x86-64), inline assembly for
memory/read/write barriers, the spin-loop `pause` hint, compare-and-exchange
via `cmpxchg`, and fetch-add via `xadd`. Lives above `generic-gcc.h` in the
include chain so the chip-specific inline asm wins over the gcc-builtin
fallbacks — generally faster than `__sync_*`/`__atomic_*` on x86.

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `pg_memory_barrier_impl` | macro | `:36-41` | `lock; addl $0,0(%rsp)` — faster than `mfence`. i386 uses `%esp`, x86-64 uses `%rsp`. |
| `pg_read_barrier_impl` | macro | `:44` | Aliases to compiler barrier — TSO. |
| `pg_write_barrier_impl` | macro | `:45` | Aliases to compiler barrier — TSO. |
| `PG_HAVE_ATOMIC_FLAG_SUPPORT` | macro | `:54` | Gates flag struct definition. |
| `pg_atomic_flag` | struct typedef | `:55-58` | `volatile char value;`. |
| `PG_HAVE_ATOMIC_U32_SUPPORT` | macro | `:60` | |
| `pg_atomic_uint32` | struct typedef | `:61-64` | `volatile uint32 value;`. |
| `PG_HAVE_ATOMIC_U64_SUPPORT` | macro (x86-64 only) | `:71` | |
| `pg_atomic_uint64` | struct typedef (x86-64 only) | `:72-76` | 8-byte alignment guaranteed by ABI. |
| `PG_HAVE_SPIN_DELAY` | macro | `:106 / :113 / :120` | gcc inline asm `rep; nop`, MSVC `_mm_pause`. |
| `pg_spin_delay_impl` | static inline | `:107-111 / :114-118 / :121-126` | PAUSE hint for hyperthreaded cores. |
| `PG_HAVE_ATOMIC_TEST_SET_FLAG` | macro | `:133` | |
| `pg_atomic_test_set_flag_impl` | static inline | `:134-146` | `lock; xchgb`. |
| `PG_HAVE_ATOMIC_CLEAR_FLAG` | macro | `:148` | |
| `pg_atomic_clear_flag_impl` | static inline | `:149-158` | Compiler barrier + plain store — TSO. |
| `PG_HAVE_ATOMIC_COMPARE_EXCHANGE_U32` | macro | `:160` | |
| `pg_atomic_compare_exchange_u32_impl` | static inline | `:161-179` | `lock; cmpxchgl` + setz. |
| `PG_HAVE_ATOMIC_FETCH_ADD_U32` | macro | `:181` | |
| `pg_atomic_fetch_add_u32_impl` | static inline | `:182-193` | `lock; xaddl`. |
| `PG_HAVE_ATOMIC_COMPARE_EXCHANGE_U64` | macro (x86-64) | `:197` | |
| `pg_atomic_compare_exchange_u64_impl` | static inline (x86-64) | `:198-218` | `lock; cmpxchgq`. |
| `PG_HAVE_ATOMIC_FETCH_ADD_U64` | macro (x86-64) | `:220` | |
| `pg_atomic_fetch_add_u64_impl` | static inline (x86-64) | `:221-232` | `lock; xaddq`. |
| `PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY` | macro (x86-64) | `:242` | |

## Internal landmarks
- Memory model is TSO — read/write barriers degrade to a pure compiler barrier (`:20-32`).
- Inline asm is gated on `__GNUC__ || __INTEL_COMPILER`. On MSVC, only the PAUSE intrinsic is provided here; everything else comes from `generic-msvc.h`.
- 32-bit x86 has NO 64-bit native atomics here — the comment at `:67-69` explicitly punts to whatever generic fallback runs after. (Combined with 32-bit gcc this typically means cmpxchg8b via `__sync_*`, NOT the semaphore fallback.)
- `cmpxchg` returns the old value in `%eax`/`%rax`; the macro reads that back into `*expected` (`:175`, `:214`), and uses `setz` to materialize the success boolean (`:174`, `:213`).
- NOT a header guard — relies on `#pragma once`-equivalent ordering via `atomics.h`.

## Invariants & gotchas
- 386 not supported (no `xadd`/`cmpxchg`); 486+ required (`:6-8`).
- `lock; addl $0,0(%rsp)` is a no-op data-wise but its `lock` prefix flushes the store buffer — works because rsp is always touchable. Some kernels (KASAN) have complained historically but it remains the upstream choice.
- `pg_atomic_clear_flag_impl` uses a compiler barrier, NOT a memory barrier — relies on x86 TSO. Porting this sequence to a weakly-ordered arch would be a correctness bug.
- Per-arch `pg_atomic_uint64` here does NOT carry the `alignas(8)` spec used by `arch-ppc.h:39` and `generic-gcc.h:105` — comment at `:74` says "alignment guaranteed due to being on a 64bit platform" — i.e. natural alignment from `uint64` is good enough on the x86-64 ABI.

## Cross-refs
- [[knowledge/files/src/include/port/atomics/arch-arm.h.md]] — sibling.
- [[knowledge/files/src/include/port/atomics/arch-ppc.h.md]] — sibling.
- [[knowledge/files/src/include/port/atomics/generic-gcc.h.md]] — runs after, fills in 32-bit u64 via `__sync_*`.
- [[knowledge/files/src/include/port/atomics/generic-msvc.h.md]] — MSVC analog.
- [[knowledge/files/src/include/port/atomics.h.md]] — umbrella.
- [[knowledge/issues/include-port.md]] — barrier-asymmetry notes.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
