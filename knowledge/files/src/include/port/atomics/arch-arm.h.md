---
path: src/include/port/atomics/arch-arm.h
anchor_sha: e18b0cb7344
loc: 32
depth: read
---

# arch-arm.h

## Purpose
ARM/AArch64-specific atomic-ops considerations. Doesn't define any operations
itself — it only sets feature-detection macros that downstream
`generic-gcc.h` / `generic.h` headers key off. The split is: on 32-bit ARM
disable 64-bit atomics entirely (kernel-helper fallback is too slow); on
AArch64 advertise single-copy 8-byte atomicity so the generic header can use
the fast aligned-load path.

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `PG_DISABLE_64_BIT_ATOMICS` | macro (32-bit ARM only) | `:25` | Set when not `__aarch64__`; suppresses 64-bit atomic codegen in `generic-gcc.h:99`. |
| `PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY` | macro (AArch64 only) | `:31` | Allows `generic.h:270` to skip the CAS-on-read trick for aligned u64. |

## Internal landmarks
- Guarded by `#ifndef INSIDE_ATOMICS_H` → `#error` (`:16-18`).
- Branch on `__aarch64__` (`:24-32`).
- The "use kernel helpers for ARM32 64-bit atomics" rationale is the comment at `:21-23` — they'd work but would be unacceptably slow.

## Invariants & gotchas
- Always `#include`d via `atomics.h` (NOT directly).
- On 32-bit ARM, the absence of 64-bit native atomics combined with `PG_DISABLE_64_BIT_ATOMICS` causes `fallback.h` to take over for u64 (semaphore-backed). Same perf cliff as documented in `fallback.h`.
- AArch64 single-copy 8-byte atomicity is a quote from the ARMv8 ARM (Architecture Reference Manual); this is the same property x86-64 advertises.

## Cross-refs
- [[knowledge/files/src/include/port/atomics/arch-x86.h.md]] — same pattern, different arch.
- [[knowledge/files/src/include/port/atomics/arch-ppc.h.md]] — same pattern.
- [[knowledge/files/src/include/port/atomics/fallback.h.md]] — kicks in for 32-bit ARM u64.
- [[knowledge/files/src/include/port/atomics/generic-gcc.h.md]] — consumes `PG_DISABLE_64_BIT_ATOMICS`.
