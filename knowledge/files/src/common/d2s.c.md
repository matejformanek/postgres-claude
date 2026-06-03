# src/common/d2s.c

## Purpose
Ryu algorithm (Adams 2018) for shortest-decimal-roundtrip formatting of
`double`. Given any IEEE-754 binary64, emit the shortest decimal string
that parses back to the same bit pattern. Ported from upstream
github.com/ulfjack/ryu under the Boost license (file header `d2s.c:10-32`).

## Role in PG
- Backs `float8out` (`utils/adt/float.c`) → user-visible representation of
  `double precision`, used by every COPY, every text-mode wire protocol,
  every JSON serialization of a float.
- Also used by `extra_float_digits` GUC machinery — when set to "use
  shortest roundtrip" (the default since PG 12), this is the path.
- Replaces the old printf("%.17g") approach: shorter output, exact
  roundtrip guaranteed, faster.

## Key API (public — `shortest_dec.h`)
- `int double_to_shortest_decimal_bufn(double f, char *result)` — write
  into caller-provided buffer of at least `DOUBLE_SHORTEST_DECIMAL_LEN`
  (25) bytes; returns length, **does not NUL-terminate**.
- `int double_to_shortest_decimal_buf(double f, char *result)` — same but
  NUL-terminates.
- `char *double_to_shortest_decimal(double f)` — palloc'd result.

## Internal structure (just the spine — algorithm is dense)
- `pow5Factor`, `multipleOfPowerOf5`, `multipleOfPowerOf2` (`d2s.c:74,95,106`)
  — number-theoretic divisibility helpers.
- `mulShift`, `mulShiftAll` (`d2s.c:161,170,182,208,220`) — 64×128 →
  high-bits-of-shifted multiplication. Three implementations gated by
  `HAVE_INT128`, `HAS_64_BIT_INTRINSICS` (MSVC x64), and the slow
  generic path. The interesting math.
- `decimalLength(uint64 v)` (`d2s.c:264`) — number of decimal digits in v.
- `floating_decimal_64` struct (`d2s.c:339`) — `{uint64 mantissa, int32
  exponent}` — Ryu's internal short form.
- `d2d(ieeeMantissa, ieeeExponent)` (`d2s.c:346`) — **the heart**: take
  IEEE bit fields, return shortest `(mantissa, exponent)`. ~280 lines.
- `to_chars_df`, `to_chars` (`d2s.c:631, 787`) — convert
  `floating_decimal_64` to ASCII. Uses `DIGIT_TABLE[]` for pair-at-a-time
  digit emission.
- Special-case handling at top of public entry points: NaN, ±Infinity,
  ±0 → fall through `copy_special_str` (in `ryu_common.h`).

## State / globals
None. Pure leaf functions. Reads tables in `d2s_full_table.h` (43 KB of
precomputed 5^k mantissas — Ryu's space-time tradeoff).

## Phase D notes
- **Locale-independent.** No `setlocale` interaction; always emits ASCII
  `.` and `e`. Important for COPY output stability across locales.
  [verified-by-code: no `_l` variants, no `localeconv` calls]
- **Roundtrip exactness.** This is the security-relevant invariant for
  Phase D's "data-leak hardening" lens: the on-disk binary representation
  must equal the parsed-back representation. Ryu guarantees this; the old
  `printf("%.17g")` approach had documented edge cases where 17 digits
  weren't enough on some platforms. So Ryu is *stronger* for data
  integrity, not weaker.
- **PG's `STRICTLY_SHORTEST = 0`** (`ryu_common.h:46`) — PG diverges from
  upstream Ryu by *not* emitting the exact midpoint between two
  representable floats. The comment at ryu_common.h:38-45 explains:
  midpoint reliance on reader's round-to-even is the common failure mode
  across language stdlibs. PG opts for slightly-longer-but-unambiguous.
  [from-comment]
- **No untrusted input.** Input is an in-process `double` value; no
  parsing-from-text here.

## Potential issues
- [ISSUE-undocumented-invariant: `STRICTLY_SHORTEST 0` diverges from
  upstream Ryu by design; any future patch that flips it to 1 would
  change wire-protocol output for some floats, breaking pg_dump round-trip
  for clusters mixing versions. (low — it's a #define that requires
  conscious change)]
- [ISSUE-dead-code: many `RYU_*` MSVC-intrinsics paths in `d2s_intrinsics.h`
  are only exercised on Windows x64 builds without HAVE_INT128. Linux CI
  doesn't cover them. (low)]
