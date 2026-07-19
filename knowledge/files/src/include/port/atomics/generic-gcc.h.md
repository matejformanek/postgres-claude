---
path: src/include/port/atomics/generic-gcc.h
anchor_sha: e18b0cb7344
loc: 326
depth: read
---

# generic-gcc.h

## Purpose
Atomic-ops implementation for gcc (or any compiler that exposes the gcc atomic
intrinsics — clang, icc). Prefers the modern `__atomic_*` family (memory-model
aware) but falls through to the legacy `__sync_*` family on older toolchains.
Defines barrier macros, the `pg_atomic_flag` / `pg_atomic_uint32` /
`pg_atomic_uint64` types when no arch-specific header beat it to it, and the
core primitives (CAS, exchange, fetch-add/sub/and/or for both widths).

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `pg_compiler_barrier_impl` | macro | `:30` | `__asm__ __volatile__("" ::: "memory")`. |
| `pg_memory_barrier_impl` | macro (fallback) | `:37-43` | `__atomic_thread_fence(SEQ_CST)` or `__sync_synchronize()`. |
| `pg_read_barrier_impl` | macro (`__atomic` only) | `:45-52` | Compiler barrier + `ACQUIRE` thread fence. |
| `pg_write_barrier_impl` | macro (`__atomic` only) | `:54-61` | Compiler barrier + `RELEASE` thread fence. |
| `PG_HAVE_ATOMIC_FLAG_SUPPORT` / `pg_atomic_flag` | macro+typedef | `:65-83` | Width = `int` or `char` depending on TAS capability. |
| `PG_HAVE_ATOMIC_U32_SUPPORT` / `pg_atomic_uint32` | macro+typedef | `:86-95` | |
| `PG_HAVE_ATOMIC_U64_SUPPORT` / `pg_atomic_uint64` | macro+typedef | `:98-108` | `alignas(8)` for portability. |
| `pg_atomic_test_set_flag_impl` | static inline | `:114-122` | `__sync_lock_test_and_set` — acquire-only barrier. |
| `pg_atomic_unlocked_test_flag_impl` | static inline | `:127-134` | Plain load. |
| `pg_atomic_clear_flag_impl` | static inline | `:136-143` | `__sync_lock_release`. |
| `pg_atomic_init_flag_impl` | static inline | `:145-152` | Just calls clear. |
| `pg_atomic_compare_exchange_u32_impl` | static inline | `:157-167` (atomic) / `:169-182` (sync) | Prefer `__atomic_compare_exchange_n` (SEQ_CST/SEQ_CST). |
| `pg_atomic_exchange_u32_impl` | static inline | `:192-199` | `__atomic_exchange_n`. |
| `pg_atomic_fetch_add_u32_impl` | static inline | `:203-210` | `__sync_fetch_and_add`. |
| `pg_atomic_fetch_sub_u32_impl` / `_and` / `_or` | static inline | `:212-237` | `__sync_fetch_and_*`. |
| u64 variants (CAS / exchange / fetch add/sub/and/or) | static inline | `:240-326` | Mirror u32 forms; gated on `!PG_DISABLE_64_BIT_ATOMICS`. |

## Internal landmarks
- Guarded by `#ifndef INSIDE_ATOMICS_H` → `#error` (`:23-25`).
- Feature macros (`HAVE_GCC__ATOMIC_INT32_CAS`, `HAVE_GCC__SYNC_INT32_CAS`, `HAVE_GCC__SYNC_CHAR_TAS`, `HAVE_GCC__SYNC_INT32_TAS`, `HAVE_GCC__ATOMIC_INT64_CAS`, `HAVE_GCC__SYNC_INT64_CAS`) are configure-detected; `pg_config.h` records what works.
- The `__atomic_*` family is checked first because it lets us be explicit about memory order; `__sync_*` is full-barrier SEQ_CST by definition.
- The 64-bit block is wrapped in `#if !defined(PG_DISABLE_64_BIT_ATOMICS)` (`:240-326`) — this honors `arch-arm.h:25` on 32-bit ARM where 64-bit atomics use slow kernel helpers.
- The flag width compromise at `:71-80`: prefer `int` (32-bit TAS more efficient on most non-x86), fall back to `char`. Comment notes that x86 takes its own path in `arch-x86.h` and bypasses this entirely.
- `__sync_lock_test_and_set` is documented as "only acquire barrier, not a full one" (`:119`) — backend code that needs full barrier on flag-set must layer one on top.

## Invariants & gotchas
- Always `#include`d via `atomics.h`; never directly.
- "FIXME: we can probably use a lower consistency model" at `:163` — the `__atomic_compare_exchange_n` calls all pass `SEQ_CST/SEQ_CST` even though some callers would tolerate weaker ordering. Performance opportunity left on the table.
- `__sync_lock_test_and_set` on some hardware only supports setting the value to 1 — the comment at `:184-191` is why `pg_atomic_exchange_u32` is gated specifically to the `__atomic_*` family.
- Compare-and-exchange uses `*expected` in/out — the `__sync_val_compare_and_swap` path manually writes back to `*expected` (`:179`) because that family doesn't have the in/out parameter; the `__atomic_compare_exchange_n` path does it natively.
- `alignas(8)` on `pg_atomic_uint64` (`:105`) — necessary because plain `uint64` on a 32-bit ABI isn't always 8-byte aligned, and most `__atomic` 64-bit ops fall back to a libatomic call (or worse) on misaligned addresses.
- AssertPointerAlignment on `expected` at `:248`, `:263` — caller bug if you pass a misaligned `uint64*`.

## Cross-refs
- [[knowledge/files/src/include/port/atomics/arch-x86.h.md]] — runs first on x86 and pre-empts most of this file.
- [[knowledge/files/src/include/port/atomics/arch-ppc.h.md]] — runs first on POWER.
- [[knowledge/files/src/include/port/atomics/arch-arm.h.md]] — sets `PG_DISABLE_64_BIT_ATOMICS` for 32-bit ARM.
- [[knowledge/files/src/include/port/atomics/generic.h.md]] — runs after, fills derived ops.
- [[knowledge/files/src/include/port/atomics/generic-msvc.h.md]] — MSVC analog.
- [[knowledge/issues/include-port.md]] — `__atomic_*` SEQ_CST overprescription.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
