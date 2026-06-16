# src/common/d2s_intrinsics.h

## Purpose
Ryu-internal 128-bit-math helpers for the `double`→shortest-decimal path.
Provides `umul128`, `shiftright128`, and friends — the low-level 64×64 →
128-bit multiplication used by `d2s.c`'s `mulShift`. Three implementation
strata gated on platform capability:

1. **`HAS_64_BIT_INTRINSICS`** (MSVC x64, when neither HAVE_INT128 nor
   RYU_ONLY_64_BIT_OPS) — calls `_umul128` and `__shiftright128` MSVC
   intrinsics directly. (`d2s_intrinsics.h:37-` block.)
2. **Pure-C 64-bit fallback** (when neither intrinsics nor int128 are
   available). The slowest path; only relevant on platforms without
   either, which is rare in modern PG builds.
3. **HAVE_INT128 native** — most of `d2s.c` uses `int128`/`uint128` types
   directly without going through this header.

## Role in PG
Compile-time-included by `d2s.c`. Not referenced from anywhere else.

## Key macros / inlines
- `umul128(a, b, *productHi)` — return low 64 bits, store high 64 bits.
- `shiftright128(lo, hi, dist)` — shift the 128-bit value `(hi:lo)` right
  by `dist` (asserted `< 64`), returning the low 64 bits of the result.
- Plus C fallback versions of the same when MSVC intrinsics aren't there.

## State / globals
None. Pure inline helpers.

## Phase D notes
- **Fallback correctness is fragile.** The pure-C 64-bit fallback path
  is rarely exercised in CI (Linux/Mac builds have HAVE_INT128; Windows
  x64 has the MSVC intrinsics). A subtle bug in fallback `umul128` would
  produce silently-wrong shortest-decimal output. Worth a once-over.
  [inferred]
- **No untrusted input.** Pure math.

## Potential issues
- [ISSUE-dead-code: the no-intrinsics-no-int128 fallback path may be dead
  on all PG-supported platforms today. Should confirm via meson config
  whether any buildbot exercises it. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
