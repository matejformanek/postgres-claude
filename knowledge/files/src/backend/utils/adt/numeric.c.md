# `src/backend/utils/adt/numeric.c`

- **File:** `source/src/backend/utils/adt/numeric.c` (12163 lines — by
  far the largest single file in `utils/adt/`)
- **Header:** `source/src/include/utils/numeric.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The arbitrary-precision exact decimal `NUMERIC` data type. Implements
its own multi-precision arithmetic (no libgmp dependency), with separate
representations for **on-disk storage** (compact, varlena) and
**arithmetic** (digit buffer with carry headroom). Borrowed
algorithmic ideas from David Smith's "FM" multi-precision library
(`numeric.c:7-12` [from-comment]). Original code 1998 Jan Wieck, heavily
revised 2003 Tom Lane.

## The two representations (load-bearing distinction)

### On-disk: `NumericData` (`:157-161`)

A varlena. The first uint16 (`n_header`) encodes which of three sub-formats
to use, via high-bit flags (`:168-172`):
- `NUMERIC_POS = 0x0000`, `NUMERIC_NEG = 0x4000` — **NumericLong**
  format (4-byte header): `n_sign_dscale` (sign + 14-bit display scale)
  + `int16 n_weight` + `n_data[]`.
- `NUMERIC_SHORT = 0x8000` — **NumericShort** (2-byte header):
  1-bit sign + 6-bit dscale + 7-bit weight packed into the
  header. Covers most "everyday" values.
- `NUMERIC_SPECIAL = 0xC000` — NaN / +∞ / −∞, stored as just the
  2-byte header. Sub-codes: `NUMERIC_NAN = 0xC000`, `NUMERIC_PINF =
  0xD000`, `NUMERIC_NINF = 0xF000` (`:200-204`).

> "We currently always store SPECIAL values using just two bytes, but
> previous releases used only the NumericLong format, so we might find
> 4-byte NaNs (though not infinities) on disk if a database has been
> migrated using pg_upgrade." (`:115-119` [from-comment]).

### In-memory arithmetic: `NumericVar` (`:314-322`)

```c
struct NumericVar {
    int ndigits;            /* digits in digits[]; can be 0! */
    int weight;             /* weight of first digit, in base NBASE */
    int sign;               /* NUMERIC_POS/NEG/NAN/PINF/NINF */
    int dscale;             /* display scale (in decimal digits) */
    NumericDigit *buf;      /* start of palloc'd buffer; NULL = const */
    NumericDigit *digits;   /* first digit in use */
};
```

The `digits` pointer is offset from `buf` by 1-2 unused leading digits
(preset to 0) — so carry-out can be absorbed by decrementing `digits`
and incrementing `weight`, without reallocating (`:277-283`
[from-comment]).

By convention, **packed (on-disk) values have leading and trailing zero
digits stripped**. A zero numeric has `ndigits == 0` and arbitrary
weight (`:131-134` [from-comment]).

## NBASE and digit width

**`NBASE = 10000`, `DEC_DIGITS = 4`, `NumericDigit = int16`** (`:96-103`
[verified-by-code]). Each NumericDigit stores 4 decimal digits.

> "Values of NBASE other than 10000 are considered of historical
> interest only and are no longer supported in any sense; no mechanism
> exists for the client to discover the base, so every client supporting
> binary mode expects the base-10000 format. If you plan to change this,
> also note the numeric abbreviation code, which assumes NBASE=10000."
> (`:68-72` [from-comment])

Headroom: `NBASE * NBASE = 10^8` fits in int32 with margin — `mul_var`
and `div_var` postpone carry propagation to amortize cost (`:60-66`
[from-comment]).

## Limits

- `NUMERIC_WEIGHT_MAX = PG_INT16_MAX` (`:261`) — bounded by the int16
  `n_weight` field of NumericLong on disk. NumericVar can hold larger
  intermediate weights.
- `NUMERIC_DSCALE_MAX = 0x3FFF` (`:238`) — 14-bit dscale.
- Short format: dscale ≤ 0x3F (`NUMERIC_SHORT_DSCALE_MAX`, `:220-221`),
  weight ∈ [-64, 63] (`:224-225`).
- Public-facing precision limit `NUMERIC_MAX_PRECISION = 1000` (decl in
  `numeric.h` [unverified]).

## Public type entry points

I/O: `numeric_in` (`:626`), `numeric_out` (`:799`), `numeric_out_sci`
(`:975` — scientific notation), `numeric_recv` (`:1061`), `numeric_send`
(`:1146`).

Comparison: `numeric_cmp(PG_FUNCTION_ARGS)` (`:2417`) and the internal
`cmp_numerics(num1, num2)` (`:2523`). Hashing: `hash_numeric` (`:2715`),
`hash_numeric_extended` (`:2795`).

Sort support (the abbreviated-key implementation): **`numeric_sortsupport`**
(`:2110`) — the `BTSORTSUPPORT_PROC`. Sets up:
- `numeric_cmp_abbrev` (`:2302`) — the cheap abbreviated comparator.
- `numeric_abbrev_convert` (`:2151`) — converts a packed Numeric Datum
  to an int64 abbreviated proxy.
- `numeric_abbrev_abort` (`:2213`) — uses HyperLogLog (the
  `hyperLogLogState abbr_card` field of `NumericSortSupport`) to track
  abbreviation cardinality; if proxies aren't distinguishing values
  effectively, return true to abort.

Abbreviation encoding (`:393-410` [from-comment]):
```c
NUMERIC_ABBREV_NAN  = PG_INT64_MIN
NUMERIC_ABBREV_NINF = PG_INT64_MAX  (yes, positive — see comment)
NUMERIC_ABBREV_PINF = -PG_INT64_MAX
/* Finite values: from +PG_INT64_MAX to -PG_INT64_MAX */
```
And the leading sort comparator is `ssup_datum_signed_cmp` (one of the
radix-sort-eligible comparators — see `tuplesort.c:3011-3021`), so
NUMERIC gets **both abbreviated keys AND radix sort** automatically.

## Arithmetic kernels

Public PG_FUNCTION wrappers: `numeric_add` (`:2866`), `numeric_sub`
(`:2941`), `numeric_mul` (`:3017`), `numeric_div` (`:3139`),
`numeric_div_trunc` (`:3253`), `numeric_mod`, `numeric_power`,
`numeric_sqrt`, `numeric_exp`, `numeric_ln`, `numeric_log`, ...
Each has a `_safe` variant taking a `Node *escontext` for
soft-error (non-throwing) paths used by `pg_input_is_valid` etc.

Internal `*_var` helpers (operate on NumericVar, idempotent w.r.t. dest
== src):
- `add_var`, `sub_var`, `mul_var`, `div_var`, `mod_var`, `power_var`,
  `sqrt_var`, `exp_var`, `ln_var`, `log_var`, `cmp_var`, `cmp_var_common`.
- Conversion: `set_var_from_str` (parser), `set_var_from_num`,
  `make_result` / `make_result_opt_error` (NumericVar → packed Numeric).
- Buffer mgmt: `alloc_var`, `free_var`, `zero_var`, `init_var`,
  `digitbuf_alloc`, `digitbuf_free` (`:478-486`).

> "All the variable-level functions are written in a style that makes it
> possible to give one and the same variable as argument and destination.
> This is feasible because the digit buffer is separate from the
> variable." (`:309-312` [from-comment])

## `NumericSumAccum` (`:381-390`)

A fast accumulator for `SUM()`-style aggregates that avoids carry
propagation on every add. Stores digits as **int32** instead of int16, so
up to `NBASE - 1 = 9999` values can be added without overflow (`:354-360`
[from-comment]). Positive and negative values are accumulated in
**separate** `pos_digits[]` / `neg_digits[]` buffers and combined only in
`accum_sum_final()` — this avoids the branching cost of "do I add or
subtract from current?" per value (`:361-366` [from-comment]). **Cannot
handle NaN** (`:378` [from-comment]).

## Special values (NaN / Inf) semantics

> "We don't trouble to ensure that dscale and weight read as zero for an
> infinity; however, that doesn't matter since we never convert
> 'special' numerics to NumericVar form. Only the constants defined
> below (const_nan, etc) ever represent a non-finite value as a
> NumericVar." (`:231-234` [from-comment])

So all paths that produce a NumericVar with a special sign do so by
copying one of `const_nan`, `const_pinf`, `const_ninf` (`:451-458`); the
arithmetic kernels short-circuit on special inputs.

## Functions of note

1. **`numeric_in` (`:626-…`)** — string parser. Handles leading sign,
   optional decimal point, `e`/`E` scientific notation, and the literal
   strings `NaN`, `Infinity`/`Inf`, `-Infinity`/`-Inf` (case-insensitive,
   I believe — [unverified]).
2. **`make_result` (in the `static` block; transcoded to packed
   Numeric)** — chooses NumericShort if `NUMERIC_CAN_BE_SHORT(scale,
   weight)` (`:492-495`), else NumericLong.
3. **`cmp_numerics` (`:2523-…`)** — the canonical 3-way compare on packed
   Numeric values; handles NaN/Inf ordering (NaN > everything, equal to
   itself; +Inf > all finite; -Inf < all finite).
4. **`numeric_abbrev_convert_var` (`:2361-…`)** — the heart of
   abbreviation: maps a NumericVar to an int64 such that lexicographic
   order on int64 matches numeric order (modulo abbreviation-tie cases).

## Cross-references

- `source/src/include/utils/numeric.h` — public type API
  (`NumericVar`/`Numeric` opaque), function decls, constants.
- `source/src/backend/utils/sort/sortsupport.c` /
  `source/src/include/utils/sortsupport.h` — provides `SortSupport`
  framework; `ssup_datum_signed_cmp` is one of the radix-sort
  comparators numeric_sortsupport installs.
- `source/src/backend/utils/adt/numeric.c` is also where statistical
  aggregates (avg, stddev, variance) live for the numeric and integer
  types — they use `NumericSumAccum`.
- `common/int128.h` — int128 helpers used by some kernels.

## Open questions

- The precise threshold at which `mul_var` switches from schoolbook to
  fast-multiplication (split / Karatsuba?) — not chased.
- Behavior of `numeric_div` w.r.t. `division_round_mode` — only skimmed.
- Whether `set_var_from_str` ever returns errors via escontext path on
  malformed input vs ereporting — [unverified].

## Confidence tag tally

- `[verified-by-code]` × ~12
- `[from-comment]` × ~12
- `[unverified]` × 4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
