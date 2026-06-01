# `src/backend/utils/adt/float.c`

- **File:** `source/src/backend/utils/adt/float.c` (4321 lines)
- **Header:** `source/src/include/utils/float.h` (inline helpers)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Fmgr-callable surface for `real` (`float4`) and `double precision`
(`float8`): I/O (with shortest-decimal round-trip), arithmetic
(checked for over/underflow/zero-div via the central
`float_overflow_error` family), comparison/sort support, sqrt /
exp / log / trig / hyperbolic / inverse trig / degree-based trig,
`width_bucket`, and the aggregate machinery (`avg`, `variance`,
`stddev`, regression aggregates) — all the float computational
infrastructure.

## Top of file (verbatim)

```
 * float.c
 *    Functions for the built-in floating-point types.
 *
 * Reject building with gcc's -ffast-math switch. It breaks our handling of
 * float Infinity and NaN values ...
```
(`:1-50` [from-comment])

## Public surface (selected)

- **I/O:** `float4in/_out/_recv/_send` (`:205, ~`),
  `float8in/_out/_recv/_send`. `float4in_internal` (`:223`) and
  `float8in_internal` (extern) are reused by every place that has
  to parse a float (geometric types, hstore, json).
- **Constants & error helpers (extern):** `float_overflow_error`
  (`:103`), `float_underflow_error` (`:111`),
  `float_zero_divide_error` (`:119`), plus `_ext` variants taking
  `escontext` (`:127, 135, 143`). `is_infinite` (`:159`).
- **Arithmetic:** `float4pl/mi/mul/div/abs/um/up/larger/smaller`,
  `float8pl/mi/mul/div/abs/um/up/larger/smaller`. All overflow-
  checked via inline helpers in `float.h`.
- **Comparison + sort:** `float4eq/.../ge`, `float8eq/.../ge`,
  `btfloat4cmp`, `btfloat8cmp`, `btfloat4sortsupport`,
  `btfloat8sortsupport` (`:1033`) — the sortsupport variants
  enable nbtree's abbreviated key path.
- **Casts:** `i4tod/dtoi4/i2tod/dtoi2/i4tof/ftoi4/...` and
  float↔numeric.
- **Math:** `dsqrt`, `dcbrt`, `dpow`, `dexp`, `dlog1`, `dlog10`,
  `dsin/dcos/dtan/dasin/dacos/datan/datan2`,
  degree-based `dsind/dcosd/dtand/dcotd/dasind/dacosd/datand/datan2d`,
  hyperbolic `dsinh/dcosh/dtanh/dasinh/dacosh/datanh`,
  `dceil`, `dfloor`, `dround`, `dtrunc`, `dsign`, `width_bucket_float8`.
- **Aggregates:** `float8_accum` (`:3090`), `float8_combine` (`:2998`),
  `float8_var_pop` (`:3274`), `float8_var_samp`, `float8_stddev_*`,
  `float8_avg`, `float4_accum`, `float8_regr_*` (regression
  aggregates: count, sxx, syy, sxy, slope, intercept).

## Key invariants

- **`-ffast-math` is a compile error.** `#ifdef __FAST_MATH__` →
  `#error` (`:30-46` [from-comment]) — breaks infinity/NaN handling
  and silently makes errno-based error detection unreliable.
- **Shortest-decimal output by default.** `extra_float_digits` GUC
  defaults to 1, which triggers `float_to_shortest_decimal_buf`
  (`:368`) producing round-trip-accurate text in minimum digits.
  Setting to ≤0 reverts to FLT_DIG/DBL_DIG fixed-precision
  (`:362-370, 581-589` [verified-by-code]).
- **NaN compares as larger than infinity for ordering.** Required
  so btree can store NaN values; `float4_cmp_internal` /
  `float8_cmp_internal` enforce this with explicit NaN checks
  (`[inferred]` from standard PG pattern, applies here).
- **Errors go through out-of-line helpers.** `pg_noinline` markers
  on `float_overflow_error` etc. (`:102, 110, 118`) — keeps the
  hot path tight by moving the cold ereport out of line.
- **Degree-trig uses anchored exact values.** `init_degree_constants`
  (`:92`) computes `sin(30°)` etc. at runtime once, deliberately
  through globals the compiler can't precompute, ensuring
  `sind(30) == 0.5` exactly across platforms (`:69-87`
  [from-comment]).

## Functions of note

- **`float4in_internal`** (`:223`) — uses `strtof` (not `strtod` then
  cast) to avoid the double-rounding bug documented at length in
  the function header (`:175-203` [from-comment]). Concrete example
  given: `7.038531e-26` rounds to a different float depending on
  whether you go through double first.
- **`float8in_internal`** — exported and widely used; same
  errno/endptr discipline; accepts `"NaN"`, `"Infinity"`,
  `"-Infinity"` case-insensitively.
- **`float8_accum`** (`:3090`) — classical Welford-Knuth running
  Sx / Sxx accumulator, stored as a float8[3] array (`{N, Sx, Sxx}`)
  via `check_float8_array` (`:3015`). The 3-element shape is
  the implicit ABI between `_accum`, `_combine`, `_var_*`,
  `_stddev_*` finalfns.
- **`float8_combine`** (`:2998`) — used by parallel aggregation.
  Merges two `{N, Sx, Sxx}` triples with the numerically-stable
  parallel formula attributed to Chan/Golub/LeVeque.
- **`btfloat8sortsupport`** (`:1033`) — installs the comparator
  and an abbreviated-key function: encodes a float8 in a uint64
  preserving order (sign-flip the negative half), which lets
  the tuplesort compare by integer instead of float.
- **`width_bucket_float8`** — the SQL-spec histogram-bucket
  function; rejects infinity bounds.

## Cross-references

- `source/src/common/shortest_dec.c` — Ryu algorithm
  implementation (`float_to_shortest_decimal_buf`).
- `source/src/include/utils/float.h` — inline overflow-check
  helpers (`float8_pl`, `float8_mul`, ...).
- `source/src/backend/utils/adt/numeric.c` — float↔numeric casts.
- `source/src/backend/access/nbtree/` — consumer of sort support.

## Open questions

- The degree-constants anti-optimization trick relies on the
  externs hiding the constant values from the compiler. With LTO
  enabled, could the optimizer still inline these? `[unverified]`
- `float8_accum`'s array-of-3 representation predates the
  internal-type aggregate pattern; modernization to a struct
  passed via internal pseudo-type was considered? `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 1
- `[from-comment]` × 3
- `[inferred]` × 1
- `[unverified]` × 2
