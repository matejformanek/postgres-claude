---
path: src/include/port/atomics/generic-msvc.h
anchor_sha: e18b0cb7344
loc: 115
depth: read
---

# generic-msvc.h

## Purpose
Atomic-ops implementation for MSVC. Defines the `pg_atomic_uint32` /
`pg_atomic_uint64` types and uses `InterlockedCompareExchange*` /
`InterlockedExchange*` / `InterlockedExchangeAdd*` intrinsics for the
primitives. Also wires `_ReadWriteBarrier()` as the compiler barrier and
`MemoryBarrier()` as the runtime full memory barrier.

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `pg_compiler_barrier_impl` | macro | `:27` | `_ReadWriteBarrier()` MSVC intrinsic. |
| `pg_memory_barrier_impl` | macro | `:30` | `MemoryBarrier()` from `<windows.h>`. |
| `PG_HAVE_ATOMIC_U32_SUPPORT` / `pg_atomic_uint32` | macro+typedef | `:33-37` | |
| `PG_HAVE_ATOMIC_U64_SUPPORT` / `pg_atomic_uint64` | macro+typedef | `:39-43` | `alignas(8)`. |
| `pg_atomic_compare_exchange_u32_impl` | static inline | `:47-57` | `InterlockedCompareExchange`. |
| `pg_atomic_exchange_u32_impl` | static inline | `:60-64` | `InterlockedExchange`. |
| `pg_atomic_fetch_add_u32_impl` | static inline | `:67-71` | `InterlockedExchangeAdd`. |
| `pg_atomic_compare_exchange_u64_impl` | static inline | `:82-92` | `_InterlockedCompareExchange64`. |
| `pg_atomic_exchange_u64_impl` | static inline (`_WIN64`) | `:99-104` | `_InterlockedExchange64`. |
| `pg_atomic_fetch_add_u64_impl` | static inline (`_WIN64`) | `:108-113` | `_InterlockedExchangeAdd64`. |

## Internal landmarks
- Guarded by `#ifndef INSIDE_ATOMICS_H` → `#error` (`:22-24`).
- `#include <intrin.h>` at `:19` — pulls in MSVC's intrinsic declarations.
- `#pragma intrinsic(_ReadWriteBarrier)` (`:26`), and similarly for the 64-bit interlocked functions (`:79`, `:97`, `:106`) — forces MSVC to use the intrinsic rather than the library entry point.
- 64-bit CAS is unconditionally available because PG's MSVC baseline is XP+ which always has `_InterlockedCompareExchange64` (`:74-78`).
- 32-bit MSVC build (`!_WIN64`) intentionally omits `_InterlockedExchange64` and `_InterlockedExchangeAdd64` (`:95-115`) — `generic.h` will then synthesize them from the CAS primitive.

## Invariants & gotchas
- Always `#include`d via `atomics.h`; never directly.
- The Interlocked* family takes `LONG*` (32-bit) and `LONGLONG*` (64-bit) — relies on `volatile uint32`/`volatile uint64` being layout-compatible on MSVC. Casts via void pointer arithmetic.
- Argument order for `InterlockedCompareExchange` is `(dest, newval, expected)` — note this is DIFFERENT from gcc `__sync_val_compare_and_swap(dest, expected, newval)` and from the inline-asm `cmpxchg` operand order. Confusing during code archaeology.
- 32-bit MSVC has u64 CAS but no u64 exchange or fetch_add — silently picks up `generic.h`'s CAS-loop synthesis (slower than the native call on 64-bit builds, but correct).
- No `pg_atomic_flag` type defined here — relies on `generic.h:38-41` to alias to `pg_atomic_uint32`. No `pg_atomic_test_set_flag_impl` — uses the CAS-based fallback in `generic.h:112-141`.
- No barriers for read/write — `generic.h:24-29` upgrades them to the full `MemoryBarrier()`.
- No `pg_spin_delay_impl` here — `arch-x86.h:113-126` provides one via `_mm_pause` / inline asm for MSVC, and on ARM64 MSVC the `generic.h` no-op kicks in.

## Cross-refs
- [[knowledge/files/src/include/port/atomics/generic-gcc.h.md]] — sibling for gcc/clang.
- [[knowledge/files/src/include/port/atomics/arch-x86.h.md]] — provides PAUSE for MSVC.
- [[knowledge/files/src/include/port/atomics/generic.h.md]] — fills in flag ops + u32 derived ops.
- [[knowledge/files/src/include/port/atomics.h.md]] — umbrella.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
