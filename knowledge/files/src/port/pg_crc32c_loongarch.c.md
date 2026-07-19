---
path: src/port/pg_crc32c_loongarch.c
anchor_sha: e18b0cb7344
loc: 73
depth: read
---

# src/port/pg_crc32c_loongarch.c

## Purpose

CRC32C implementation using LoongArch's native CRC-C instructions
(`crcc.w.{b,h,w,d}.w`), exposed via GCC builtins
`__builtin_loongarch_crcc_w_*_w`. LoongArch is the Chinese ISA whose modern
cores ship with hardware CRC-C support; this file produces the
LoongArch-native arm of the corpus-wide `pg_comp_crc32c` dispatcher. Unlike
the x86 and ARM SSE4.2/ARMv8 paths, there is no runtime CPU-feature check
here — if the build targets LoongArch with the CRC extension, the function
is always callable. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `pg_crc32c pg_comp_crc32c_loongarch(pg_crc32c crc, const void *data, size_t len)` | `pg_crc32c_loongarch.c:20` | LoongArch hardware CRC32C |

## Internal landmarks

- Alignment preamble (`:30-47`) — three sequential checks bring `p` to a
  uint64-aligned address, processing 1 byte (`crcc_w_b_w`), then 2
  (`crcc_w_h_w`), then 4 (`crcc_w_w_w`). LoongArch tolerates unaligned
  access but performs better aligned. `[from-comment]`
- Main loop (`:50-54`) — `crcc_w_d_w` consumes 8 bytes per instruction.
- Trailing residue (`:57-70`) — symmetric to the preamble: 4, 2, 1 bytes
  if those remain.

## Invariants & gotchas

- **No runtime feature check.** The build system decides at compile time
  whether to include this file; the assumption is that any binary built
  for LoongArch CRC includes the necessary ISA. The choose-dispatcher
  (in the LoongArch case) is simpler than x86/ARM — there is no software
  fallback path within this file.
- The four builtins use the `_w_w` suffix meaning "32-bit CRC out". Don't
  confuse with `crc.w.*` (without the second `c`), which would compute the
  zlib-style CRC32 with a different polynomial.
- `PointerIsAligned` macro comes from `c.h`; it's `((uintptr_t)(p) % sizeof(t) == 0)`.

## Cross-refs

- `knowledge/files/src/port/pg_crc32c_sb8.c.md` — software fallback.
- `knowledge/files/src/port/pg_crc32c_sse42.c.md` — x86 sibling with the
  same alignment-then-eight-byte-loop shape.
- `knowledge/files/src/port/pg_crc32c_armv8.c.md` — ARM sibling, near-identical
  structure (this file appears to be modelled on it).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
