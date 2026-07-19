---
path: src/port/pg_popcount_x86.c
anchor_sha: e18b0cb7344
loc: 310
depth: read
---

# src/port/pg_popcount_x86.c

## Purpose

x86-64 SIMD implementations of the corpus-wide popcount primitive
(`pg_popcount_optimized`/`pg_popcount_masked_optimized`), dispatched from
`pg_bitutils.c`. Three arms: portable software fallback, SSE4.2 POPCNT
(scalar `popcntq`), and AVX-512 VPOPCNTDQ (vectorized 64-bit popcount over
ZMM lanes). Selection is **runtime** via `x86_feature_available()` (which
consults `pg_cpu_x86.c`'s CPUID probe), with function pointers patched on
first call so subsequent calls go straight to the chosen implementation.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `uint64 (*pg_popcount_optimized)(const char *buf, int bytes)` | `pg_popcount_x86.c:51` | Function pointer; initially `pg_popcount_choose`, patched on first call |
| `uint64 (*pg_popcount_masked_optimized)(const char *buf, int bytes, uint8 mask)` | `:52` | Masked variant |

(All other functions are file-static.)

## Internal landmarks

- `choose_popcount_functions` (`:76-97`) — runtime dispatch. Reads
  `x86_feature_available(PG_POPCNT)` first to enable SSE4.2 path; then if
  `USE_AVX512_POPCNT_WITH_RUNTIME_CHECK` is compiled in **and**
  `PG_AVX512_BW` + `PG_AVX512_VPOPCNTDQ` are present, upgrades to AVX-512.
- `pg_popcount_avx512` (`:121`) — uses `_mm512_popcnt_epi64` over 64-byte
  ZMM chunks. Alignment preamble (`:135-138`) shifts the buffer down to a
  `__m512i` boundary and computes a mask to zero out preceding bytes; the
  final iteration uses a tail mask. Carries `pg_attribute_target("avx512vpopcntdq,avx512bw")`.
- `pg_popcount_sse42` (`:257`) — calls `pg_popcount64_sse42` (which inlines
  the `popcntq` asm at `:246`) over 8-byte chunks; tail bytes use the
  precomputed `pg_number_of_ones` table from `pg_bitutils.c`. Both functions
  carry `pg_attribute_no_sanitize_alignment()`. `[verified-by-code]`
- Empty-module guard (`:304-309`) when `HAVE_X86_64_POPCNTQ` is undefined,
  preventing linker complaints on platforms where this file compiles to
  nothing.

## Invariants & gotchas

- **CPUID gating is mandatory.** Calling `popcntq` on a CPU without SSE4.2
  is `#UD`; the runtime check in `choose_popcount_functions` is the only
  safe entry. Compile-time `__POPCNT__` is **not** used because Linux
  distros ship a single binary targeting many CPU generations. `[verified-by-code]`
- AVX-512 alignment preamble assumes any read past `bytes` is safe **because
  unused lanes are zeroed by `_mm512_maskz_loadu_epi8`**, not because we
  guarantee the page is mapped. On unmapped trailing bytes this would
  segfault — callers must pass a real length covering allocated memory.
- The choose-functions arm replaces the pointer in place; first call is
  slightly slower (one indirect call into `pg_popcount_choose`, the dispatch
  logic, then the real implementation). Subsequent calls are one indirect
  call only. `[verified-by-code]`

## Cross-refs

- `knowledge/files/src/port/pg_bitutils.c.md` — portable fallback and
  `pg_number_of_ones` table.
- `knowledge/files/src/port/pg_cpu_x86.c.md` — CPUID feature probe behind
  `x86_feature_available()`.
- `knowledge/files/src/port/pg_popcount_aarch64.c.md` — Neon/SVE sibling.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
