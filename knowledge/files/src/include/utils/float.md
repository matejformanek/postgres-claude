# utils/float.h — float4/float8 NaN-aware ops + overflow-checked arithmetic

Source: `source/src/include/utils/float.h` (339 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Inline arithmetic + comparison helpers for built-in float4 (REAL) and float8 (DOUBLE PRECISION). Wraps IEEE-754 operations with overflow/underflow/divide-by-zero detection and a uniform NaN sort order.

## Public API

- `M_PI`, `RADIANS_PER_DEGREE` (`float.h:21-26`).
- `extra_float_digits` GUC declaration (`float.h:28`).
- Error helpers: `float_overflow_error`, `float_underflow_error`, `float_zero_divide_error` (hard) + `*_ext(escontext)` soft variants (`float.h:33-38`).
- `is_infinite` (`float.h:39`), `float[48]in_internal`, `float8out_internal`, `float[48]_cmp_internal` (`float.h:40-48`).
- `get_float4_infinity` / `get_float8_infinity` / `_nan` (`float.h:60-91`).
- Overflow-checked arithmetic: `float4_pl/mi/mul/div`, `float8_pl/mi/mul/div` + `_safe` variants (`float.h:103-233`).
- NaN-aware comparisons: `float[48]_eq/ne/lt/le/gt/ge/min/max` (`float.h:243-337`).

## Invariants

- **INV-IEEE-754-required** [verified-by-code, `float.h:51-58, 74-77`]: "Postgres requires IEEE-standard float arithmetic, including infinities and NaNs." `#error "Postgres requires support for IEEE quiet NaNs"` if NAN is undefined.
- **INV-NaN-sort-order** [from-comment, `float.h:236-241`]: "We consider all NaNs to be equal and larger than any non-NaN." Arbitrary but consistent — required so sort/btree/hash agree.
- **INV-no-underflow-detect-for-add-sub** [from-comment, `float.h:96-101`]: "There isn't any way to check for underflow of addition/subtraction." E.g. `'1e-45'::float4 == '2e-45'::float4 == 1.4013e-45` on x86. Only mul/div have underflow checks.
- **INV-overflow-detected-via-isinf** [verified-by-code, `float.h:107-110, 137-140, 167-170, ...`]: pattern is `result = op(a, b); if (isinf(result) && !isinf(a) && !isinf(b)) overflow`. Skips reporting when input was already Inf.
- **INV-underflow-detected-via-zero-from-nonzero** [verified-by-code, `float.h:171-172, 185-186, 207-208, 222-223`]: `if (result == 0 && a != 0 && b != 0) underflow`.
- **INV-div-by-zero-respects-NaN** [verified-by-code, `float.h:202-203, 218-219`]: zero-divide error only fires if numerator is NOT NaN; `NaN / 0` returns NaN per IEEE.
- **INV-float4-no-safe-variant** [verified-by-code]: the float4_pl/mi/mul/div family doesn't have `_safe(escontext)` overloads, only float8 does. New float4 callers needing soft-error must check `escontext`-aware float8 versions first or upgrade precision.
- **INV-ecpg-data-c-keeps-parallel-copy** [from-comment, `float.h:57`]: "If you change these functions, see copies in interfaces/ecpg/ecpglib/data.c." Drift is a real risk.

## Notable internals

- `float8_pl(a, b)` is implemented as `float8_pl_safe(a, b, NULL)` (`float.h:128-131`): hard variants are thin shells over safe variants.
- `float[48]_eq` puts NaN==NaN as TRUE (`float.h:243-253`): conflicts with IEEE-754 where NaN != NaN. This is the PG sort convention, NOT IEEE.

## Trust-boundary / Phase-D surface

- **A13 btree_gist + A14 seg/cube NaN family** [from-corpus]: float.h is the API anchor. Every extension that handles floats SHOULD use these helpers (not raw `==`, `<`, etc.) so sort order matches btree opclass.
- **float4 has no soft-error path** — new code on user input that's float4 must convert to float8 first or accept hard ereport.
- **`is_infinite` is NOT `isinf`** (`float.h:39`): the header declares an exported function; it differs from the libc `isinf` — verify in float.c. (`is_infinite` returns -1/0/+1 vs `isinf` returning bool.)

## Cross-refs

- `source/src/backend/utils/adt/float.c` — `is_infinite`, `float8in_internal`, etc.
- `source/src/interfaces/ecpg/ecpglib/data.c` — parallel copies (drift hazard per comment).
- A13/A14 NaN cluster: `cube_in`, `seg_in`, `btree_gist` float type ops.

## Issues

- `[ISSUE-DRIFT-RISK: ecpglib/data.c parallel copies (medium)]` — `float.h:57` notes this; without a build-time crosscheck, drift can silently change ecpg vs backend semantics.
- `[ISSUE-COMPLETENESS: float4 lacks _safe variants (low)]` — newer soft-error code paths get only float8; consider adding `float4_pl_safe` etc. for parity.
- `[ISSUE-INVARIANT: NaN==NaN is PG-only (medium)]` — comment at line 236-241 is the contract; new extensions doing float compares often forget this and use raw `==` (A13/A14 finding family).
