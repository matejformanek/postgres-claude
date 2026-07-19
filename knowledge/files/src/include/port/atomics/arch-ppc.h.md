---
path: src/include/port/atomics/arch-ppc.h
anchor_sha: e18b0cb7344
loc: 256
depth: read
---

# arch-ppc.h

## Purpose
PowerPC / POWER atomic-ops implementation. Defines memory/read/write barriers
using PPC's `sync` / `lwsync` instructions, types for `pg_atomic_uint32`
(and `pg_atomic_uint64` on 64-bit), and load-link/store-conditional-based
inline-asm for compare-exchange and fetch-add (using `lwarx`/`stwcx.` for u32
and `ldarx`/`stdcx.` for u64). Hand-tuned to avoid the extra branches
gcc's `__atomic_compare_exchange_n` emits.

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `pg_memory_barrier_impl` | macro (gcc) | `:23` | `sync` — full barrier. |
| `pg_read_barrier_impl` | macro (gcc) | `:24` | `lwsync` — load-to-load + load-to-store. |
| `pg_write_barrier_impl` | macro (gcc) | `:25` | `lwsync` — store-to-store. |
| `PG_HAVE_ATOMIC_U32_SUPPORT` | macro | `:28` | |
| `pg_atomic_uint32` | struct typedef | `:29-32` | `volatile uint32 value;`. |
| `PG_HAVE_ATOMIC_U64_SUPPORT` | macro (`SIZEOF_VOID_P >= 8`) | `:36` | |
| `pg_atomic_uint64` | struct typedef (64-bit) | `:37-40` | `alignas(8) volatile uint64 value;`. |
| `PG_HAVE_ATOMIC_COMPARE_EXCHANGE_U32` | macro | `:78` | |
| `pg_atomic_compare_exchange_u32_impl` | static inline | `:79-122` | `lwarx`/`stwcx.` + `lwsync` + `mfcr`. |
| `PG_HAVE_ATOMIC_FETCH_ADD_U32` | macro | `:129` | |
| `pg_atomic_fetch_add_u32_impl` | static inline | `:130-163` | LL/SC + `lwsync`. |
| `PG_HAVE_ATOMIC_COMPARE_EXCHANGE_U64` | macro (64-bit) | `:167` | |
| `pg_atomic_compare_exchange_u64_impl` | static inline | `:168-214` | `ldarx`/`stdcx.`. |
| `PG_HAVE_ATOMIC_FETCH_ADD_U64` | macro (64-bit) | `:216` | |
| `pg_atomic_fetch_add_u64_impl` | static inline | `:217-251` | `ldarx`/`stdcx.` + `lwsync`. |
| `PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY` | macro | `:256` | Per PowerPC ISA: doubleword loads/stores are single-copy atomic. |

## Internal landmarks
- Header is NOT guarded by `INSIDE_ATOMICS_H` (unlike most siblings) — the inline-asm blocks are conditional on `__GNUC__` so foreign inclusion is mostly inert, but the pattern is irregular.
- 64-bit atomics gated on `SIZEOF_VOID_P >= 8` (`:35`) — pulled from `pg_config.h`; on 32-bit PPC u64 is delegated to `generic.h` + `fallback.h` (semaphore path).
- The "constant immediate" fast path is gated on `HAVE_I_CONSTRAINT__BUILTIN_CONSTANT_P` (`:87`, `:179`, `:224`); detected by configure. When the compared value or addend fits in a 16-bit signed immediate, uses `cmpwi`/`addi` (cheaper) instead of register form.
- The big block-comment at `:44-77` documents WHY the code uses raw asm instead of `__atomic_compare_exchange_n`: better codegen because we don't need to materialize the boolean in a separate register pass.
- Uses `mfcr` (move from condition register) + bit-shift to extract the eq bit of cr0 into a C bool (`:118`, `:210`) — PPC's LL/SC sets cr0 on `stwcx.`/`stdcx.`.

## Invariants & gotchas
- Always `#include`d via `atomics.h`; this one DOESN'T have the `INSIDE_ATOMICS_H` guard but should still not be included directly.
- `sync` before LL is the full-barrier prelude; `lwsync` after the SC pair gives release semantics — matches the documented `pg_atomic_*` SEQ_CST contract.
- u32 fetch-add uses constraint `"=&b"` for the result register (`:146`, `:158`) — explanatory comment at `:127` says "use constraint =&b to avoid allocating r0", because PPC instructions like `addi` interpret r0 as the literal value 0 rather than the contents of GPR 0.
- 32-bit PPC + the absence of `PG_HAVE_ATOMIC_U64_SUPPORT` here means the same fallback-semaphore-perf-cliff issue as 32-bit ARM (see `knowledge/issues/include-port.md`).

## Cross-refs
- [[knowledge/files/src/include/port/atomics/arch-x86.h.md]] — sibling.
- [[knowledge/files/src/include/port/atomics/arch-arm.h.md]] — sibling.
- [[knowledge/files/src/include/port/atomics/generic-gcc.h.md]] — picks up barrier definitions if not set here.
- [[knowledge/files/src/include/port/atomics/fallback.h.md]] — kicks in on 32-bit PPC for u64.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../subsystems/port.md)
