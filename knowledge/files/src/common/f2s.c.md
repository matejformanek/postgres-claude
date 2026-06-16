# src/common/f2s.c

## Purpose
Ryu algorithm for `float` (IEEE-754 binary32). The 32-bit analogue of
`d2s.c` — shortest decimal that roundtrips back to the same float bits.
Ported from upstream github.com/ulfjack/ryu under the Boost license.

## Role in PG
Backs `float4out` (`utils/adt/float.c`) → all text-mode emission of `real`
columns. Same path as d2s for COPY, wire protocol text mode, JSON.

## Key API (public — `shortest_dec.h`)
- `int float_to_shortest_decimal_bufn(float f, char *result)` — buffer ≥
  `FLOAT_SHORTEST_DECIMAL_LEN` (16) bytes; non-NUL-terminating.
- `int float_to_shortest_decimal_buf(float f, char *result)` —
  NUL-terminating.
- `char *float_to_shortest_decimal(float f)` — palloc'd.

## Internal structure
Mirrors d2s but on uint32 mantissas:
- `multipleOfPowerOf2` (`f2s.c:109`).
- `mulShift(uint32, uint64, int32)` (`f2s.c:120`) — 32×64 → shifted high
  bits. Simpler than d2s's mulShift because no 128-bit math is needed
  (a uint64 holds the full product).
- `mulPow5InvDivPow2`, `mulPow5divPow2` (`f2s.c:162, 168`) — wrappers
  around the precomputed power-of-5 tables (smaller than d2s's tables).
- `decimalLength(uint32 v)` (`f2s.c:174`).
- `floating_decimal_32` struct (`f2s.c:215`) — `{uint32 mantissa, int32
  exponent}`.
- `f2d(ieeeMantissa, ieeeExponent)` (`f2s.c:222`) — main Ryu mapping.
- `to_chars_f`, `to_chars` (`f2s.c:440, 563`) — ASCII emission via
  `DIGIT_TABLE[]`.
- `f2d_small_int` (`f2s.c:689`) — fast path for small exact integers.

## State / globals
None. Pure. Power-of-5 tables are inlined static constants near the top
of the file (not split into a `_full_table.h` like d2s).

## Phase D notes
Same considerations as `d2s.c`:
- Locale-independent ASCII output.
- Roundtrip-exact when paired with `strtof`.
- `STRICTLY_SHORTEST 0` diverges from upstream by design.
- No untrusted-text input — operates on in-process `float` values.

## Potential issues
- [ISSUE-undocumented-invariant: same as d2s — `STRICTLY_SHORTEST` is a
  build-time switch that would silently change output if flipped. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
