---
path: src/port/pg_popcount_aarch64.c
anchor_sha: e18b0cb7344
loc: 472
depth: read
---

# src/port/pg_popcount_aarch64.c

## Purpose

AArch64 (ARM64) SIMD popcount implementations, the ARM sibling of
`pg_popcount_x86.c`. Two SIMD arms: Neon (`vcntq_u8` over 16-byte vectors,
always compiled when `USE_NEON`) and SVE (scalable-vector predicate-based,
behind `USE_SVE_POPCNT_WITH_RUNTIME_CHECK`). When SVE runtime check is
enabled, function pointers dispatch between Neon and SVE based on
`HWCAP_SVE`; when not, the Neon code is inlined directly through external
function definitions of `pg_popcount_optimized` (no indirect call overhead).
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `uint64 (*pg_popcount_optimized)(const char *buf, int bytes)` | `pg_popcount_aarch64.c:56` (when SVE check enabled) | Function pointer dispatched between Neon and SVE |
| `uint64 pg_popcount_optimized(const char *buf, int bytes)` | `:281` (when SVE check disabled) | Direct external function returning Neon result |
| `uint64 (*pg_popcount_masked_optimized)(...)` / matching external | sibling | Masked variants |

## Internal landmarks

- HWCAP probe (`:59-72`) — `pg_popcount_sve_available()` uses
  `elf_aux_info(AT_HWCAP)` on FreeBSD or `getauxval(AT_HWCAP)` on Linux,
  checking the `HWCAP_SVE` bit. macOS has neither, so returns false.
  `[verified-by-code]`
- SVE arms (`:109`, `:193`) — carry
  `pg_attribute_target("arch=armv8-a+sve")`. The main loops are 4-way
  unrolled (`accum1..4`) for instruction-level parallelism, then a 2-way
  block for residual data, with the final tail using `svwhilelt_b8_s32` to
  build a predicate covering exactly the remaining bytes. `svcntb()` returns
  the SVE vector length in bytes at runtime — code is vector-length-agnostic.
- Neon arms (`:309`, `:389`) — same 4-way unrolled structure but with
  fixed-width `uint8x16_t` (16-byte) chunks. Tail processes 8-byte uint64
  blocks via `pg_popcount64_neon`, then per-byte using `pg_number_of_ones`
  table.
- Mask materialization (`:203`, `:399`): `mask64 = ~UINT64CONST(0) / 0xFF *
  mask` is the broadcast-byte-to-64-bit trick (replicates the mask byte
  across all eight lanes of a uint64). `[verified-by-code]`

## Invariants & gotchas

- **SVE register length is runtime-determined.** Unlike Neon's fixed 128-bit
  vectors, SVE vectors are 128 to 2048 bits depending on the silicon (Fujitsu
  A64FX = 512-bit, Graviton3 = 256-bit, Apple Silicon = no SVE at all).
  `svcntb()` queries the actual length each call; loops use that value to
  compute stride, so the same binary runs on any SVE width. `[verified-by-code]`
- **Compile-without-runtime-check optimization.** When SVE runtime check is
  off, the file emits Neon code as a plain external function rather than
  through a function pointer (`:280-290`), saving one indirect call per
  invocation. The compiler "should be able to inline the Neon versions
  here" per the comment. `[from-comment]`
- The bottom-of-file empty-module guard (`:469-472`) protects platforms
  where `USE_NEON` is undefined.

## Cross-refs

- `knowledge/files/src/port/pg_popcount_x86.c.md` — x86 sibling, same
  dispatch pattern.
- `knowledge/files/src/port/pg_bitutils.c.md` — portable fallback and
  `pg_number_of_ones` table.
- `knowledge/files/src/port/pg_crc32c_armv8.c.md` — sibling ARM SIMD file
  using same HWCAP probe pattern.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
