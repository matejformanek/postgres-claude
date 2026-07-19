# `src/include/port/simd.h`

## Role

Portable SIMD vector primitives — `Vector8` (16-byte register of 8-bit
lanes) and `Vector32` (16-byte register of 32-bit lanes). Three
implementation backends, picked by preprocessor:

- `USE_SSE2` → `__m128i` via `<emmintrin.h>` (x86)
- `USE_NEON` → `uint8x16_t` / `uint32x4_t` via `<arm_neon.h>` (ARM/AArch64)
- `USE_NO_SIMD` → soft-emulation via `uint64` (Vector32 unavailable)

The emmintrin.h-only include (line 28) is deliberate: PG explicitly
excludes AVX/AVX2 paths in this header because MSVC will silently allow
post-SSE2 intrinsics if they're transitively visible, breaking the
"baseline-only" promise `[from-comment]`
`source/src/include/port/simd.h:21-28`.

## Public API

All `static inline` `[verified-by-code]` `source/src/include/port/simd.h:50-89`:

- **Load/store**: `vector8_load`, `vector8_store`, `vector32_load`.
- **Broadcast**: `vector8_broadcast(c)` → all-lanes-c, same for v32.
- **Scalar predicates**: `vector8_has(v,c)`, `vector8_has_zero(v)`,
  `vector8_has_le(v,c)`, `vector8_has_ge(v,c)`,
  `vector8_is_highbit_set(v)`, `vector32_is_highbit_set(v)`,
  `vector8_highbit_mask(v)`.
- **Vector ops**: `vector8_or`, `vector8_and`, `vector8_add`,
  `vector8_issub` (signed saturating sub), `vector8_eq`, `vector32_eq`,
  `vector8_gt`, `vector8_min`,
  `vector8_interleave_{low,high}`, `vector8_pack_16`,
  `vector8_shift_{left,right}`, `vector32_or`.

## Invariants

1. **`sizeof(VectorN)` is platform-dependent.** Always 16 on SSE2/NEON,
   8 on USE_NO_SIMD `[from-comment]`
   `source/src/include/port/simd.h:11-14`. Callers must use
   `sizeof(Vector8)` for stride math (see `pg_lfind8`).
2. **Vector32 has no soft-SIMD fallback.** Under `USE_NO_SIMD`,
   `Vector32`-touching functions are not defined and using them is a
   compile error `[verified-by-code]`
   `source/src/include/port/simd.h:38-48,52-54`.
3. **`vector8_shift_left/right` accept only literal integer shifts**
   on NEON, not runtime values. Implementation is a `switch (i)` over
   the *expected* callsites; new callers must extend the switch.
   `[verified-by-code]` `source/src/include/port/simd.h:556-572,582-601`.
   Currently `case 4` for shift-left, `case 4, case 8` for shift-right.
4. **`vector8_pack_16` requires upper 8 bits of each 16-bit element to
   be zero.** Asserted under `USE_ASSERT_CHECKING`. The result is
   architecture-dependent if violated `[verified-by-code]`
   `source/src/include/port/simd.h:529-547`.
5. **Assert-checked correctness.** Many functions (e.g. `vector8_has`,
   `vector8_has_le`) compute the result both with the SIMD path and
   with a byte-by-byte loop under `USE_ASSERT_CHECKING`, then
   `Assert(assert_result == result)` `[verified-by-code]`
   `source/src/include/port/simd.h:168-189,222-267`. This catches
   intrinsic-mishandling at debug-build time.
6. **`vector8_has_le` USE_NO_SIMD path has a precondition.** The
   bithack works only if highest bit of v is clear AND c<128; otherwise
   it falls back to a byte-by-byte loop `[verified-by-code]`
   `source/src/include/port/simd.h:236-257`.

## Notable internals

The `_has_le` algorithm under USE_NO_SIMD is the bit-hack from
[Stanford bithacks](https://graphics.stanford.edu/~seander/bithacks.html#HasLessInWord):
`(v - broadcast(c+1)) & ~v & broadcast(0x80)`. Source-cited in
comments `source/src/include/port/simd.h:241-244`.

`vector8_highbit_mask` on NEON is non-trivial: NEON lacks a direct
`movemask` equivalent of SSE's `_mm_movemask_epi8`. The implementation
uses a per-lane mask LUT, `vshrq_n_s8(v, 7)` to broadcast the sign bit,
`vandq_u8` with the mask, `vextq_u8` + `vzip1q_u8` + `vaddvq_u16` to
horizontally sum into a single u32 `[verified-by-code]`
`source/src/include/port/simd.h:340-352`. The comment notes there's a
faster `vget_lane_u64`/`vshrn_n_u16` path that was rejected because it
returns u64 and is awkward to combine with other masks.

## Trust-boundary / Phase D surface

- **No bounds-checking semantics.** Every load/store is unaligned
  (`_mm_loadu_si128`, `vld1q_u8`). The caller is responsible for not
  reading past the buffer end. `pg_lfind8` handles this with a
  `tail_idx = nelem & ~(sizeof(Vector8)-1)` round-down + scalar tail,
  but any new caller that does the math wrong reads up to 15 bytes
  past the buffer. ASAN/MSAN should catch but production won't.
- **Compile-time-only NEON shift dispatch.** If a future contributor
  adds a `vector8_shift_left(v, 7)` callsite on AArch64, the `default:
  Assert(false); return broadcast(0)` returns *zero* in release builds
  rather than the intended shift. Silent miscompute. A debug build
  would catch via the Assert. **Phase-D-review-pattern:** any new
  caller of `vector8_shift_*` requires a NEON case-statement update
  AND a USE_ASSERT_CHECKING regression run.
- **USE_NO_SIMD platforms** are second-class — Vector32 ops just
  don't exist, so any code path that uses Vector32 implicitly requires
  SSE2 or NEON. That's fine for x86_64 and AArch64 (both baseline) but
  any new niche arch (RISC-V, LoongArch, MIPS) silently degrades all
  Vector32 consumers to non-SIMD or doesn't build them at all.
  Document this when introducing a platform.
- **Endianness/lane-order assumptions.** The header assumes "lane 0 is
  byte 0 of the buffer", which is true on both x86 (LE) and ARM (LE)
  but would need scrutiny on a big-endian SIMD target (PowerPC altivec
  in BE mode isn't supported by this header).
- **`vector8_pack_16`** has a documented "results differ between
  architectures if precondition violated" footgun
  `source/src/include/port/simd.h:528-531`. Only currently used by
  numeric/escape JSON paths; new callers must respect the upper-byte-
  zero invariant.

## Cross-refs

- `source/src/include/port/pg_lfind.h` — primary consumer (linear find).
- `source/src/backend/utils/adt/varlena.c`, `numeric.c`, `jsonpath_scan.l`
  — production callsites of `pg_lfind` and direct Vector8 use.
- `source/src/common/wchar.c` — multibyte UTF-8 validation uses Vector8.
- A7 (record_recv stack-depth) — JSON parsing fast path lands here.
- A13/A14 collision cluster — Vector8 is the substrate for the
  hash-prefix scan in radix tree key search.

## Issues / unresolved

- **ISSUE-doc**: `sizeof(Vector8)` differs by platform — no constant
  for "the max stride to expect" published from the header. Callers
  reinvent the round-down each time. (severity: low)
- **ISSUE-correctness**: NEON `vector8_shift_*` returns 0 + Assert in
  release build for unknown shift amounts — silent wrong-answer.
  (severity: medium on the "unknown caller adds shift amount, ships
  release-build" path)
- **ISSUE-portability**: only SSE2/NEON/none; no AVX2 in this header
  by design (gated to specialized files like `pg_popcount_avx512.c`).
  Documented but worth surfacing to "why isn't this faster on
  Skylake?" questions. (severity: doc-only)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
