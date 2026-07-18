# utils/numeric.h — NUMERIC exact-decimal varlena type

Source: `source/src/include/utils/numeric.h` (108 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Opaque NUMERIC handle (`Numeric` = `struct NumericData *`), display-precision limits, and the soft-error / random-numeric / int conversion API. Actual on-disk layout (sign+dscale+weight+digits[]) is private to `numeric.c`.

## Public API

- Conversion: `int64_to_numeric` (`numeric.h:94`), `int64_div_fast_to_numeric` (`numeric.h:95`).
- Soft-error arithmetic: `numeric_add_safe` / `_sub_safe` / `_mul_safe` / `_div_safe` / `_mod_safe` (`numeric.h:97-101`) and `numeric_int4_safe`/`numeric_int8_safe` (`numeric.h:102-103`).
- Hard-error legacy ops live in fmgrprotos.h.
- `random_numeric(state, rmin, rmax)` (`numeric.h:105-106`).
- Predicates: `numeric_is_nan` / `numeric_is_inf` (`numeric.h:88-89`); yes, NUMERIC supports both Inf and NaN since v14.

## Invariants

- **INV-numeric-precision-max=1000** [verified-by-code, `numeric.h:35`]: `NUMERIC_MAX_PRECISION = 1000` is the *typmod* cap, NOT the implementation cap. Comment line 32-34 explicitly warns: "the implementation limits on the precision and display scale of a numeric value are much larger --- beware of what you use these for!"
- **INV-numeric-scale-range** [verified-by-code, `numeric.h:37-38`]: typmod scale ∈ `[-1000, +1000]`. Negative scale = round before the decimal point.
- **INV-numeric-result-scale-2x** [verified-by-code, `numeric.h:46`]: `NUMERIC_MAX_RESULT_SCALE = 2 * NUMERIC_MAX_PRECISION = 2000`.
- **INV-numeric-min-sig-digits=16** [verified-by-code, `numeric.h:53`]: division and sqrt aim for ≥16 sig digits (float8-comparable).
- **INV-numeric-NumericData-private** [verified-by-code, `numeric.h:55-57`]: layout is intentionally opaque. The (sign, dscale, weight, digit[]) format is documented in `numeric.c` only.

## Notable internals

- `DatumGetNumeric` / `DatumGetNumericCopy` (`numeric.h:63-73`) detoast via `PG_DETOAST_DATUM[_COPY]`.

## Trust-boundary / Phase-D surface

- **numeric_recv (binary input)** [inferred — header silent]: the on-wire format is sign + dscale + weight + ndigits + digits[ndigits]. CVE-2014-0064 (integer overflow in numeric binary input) is the historical Phase-D anchor in this family. The header gives no visibility into validation; lives in `numeric.c`.
- **Implementation-level numeric values can exceed typmod limits** (`numeric.h:32-34`): code paths that assume typmod bounds = actual value bounds will be wrong. Any allocation sizing based on precision must use the *internal* limit, not `NUMERIC_MAX_PRECISION`.

## Cross-refs

- `source/src/backend/utils/adt/numeric.c` — implementation and `numeric_recv`.
- `common/pg_prng.h` — random source for `random_numeric`.
- A11/A14 NaN/Inf cluster — NUMERIC NaN/Inf join the same family as float NaN/Inf, but with different sort semantics (NaN > Inf > everything else for NUMERIC; same as float per `float.h`).

## Issues

- `[ISSUE-DOC: NumericData on-disk format undocumented at header (low)]` — Cross-link to `source/src/backend/utils/adt/numeric.c` header comment would help; CVE-2014-0064 lessons are invisible from the header.
- `[ISSUE-INVARIANT: typmod vs implementation cap easy to confuse (medium)]` — `numeric.h:32-34` warning is informal text; an explicit `NUMERIC_IMPL_MAX_PRECISION` constant would prevent miscoding.

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/numeric-type.md](../../../../data-structures/numeric-type.md)
