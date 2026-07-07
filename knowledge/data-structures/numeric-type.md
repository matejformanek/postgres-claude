# Numeric — arbitrary-precision decimal

`Numeric` is PG's arbitrary-precision exact-decimal type.
Distinct from `float8` (IEEE 754, binary, lossy) or `int8`
(64-bit). Backs the SQL `NUMERIC` / `DECIMAL` types. Used
for financial / scientific / catalog data where exact
decimal arithmetic matters. The internal representation is a
**variable-length array of base-10000 digits** plus a sign,
weight, and display-scale header.

Anchors:
- `source/src/backend/utils/adt/numeric.c:111-180` — format
  + header constants [verified-by-code]
- `source/src/include/utils/numeric.h` — public API
- `knowledge/data-structures/datum-nullabledatum.md` —
  Numeric is pass-by-ref
- `.claude/skills/fmgr-and-spi/SKILL.md` — `PG_GETARG_NUMERIC`

## Three on-disk formats

[from-comment `numeric.c:111-118`]

```c
union NumericChoice
{
    uint16    n_header;       /* short header detector */
    NumericShort n_short;
    NumericLong  n_long;
};
```

The header word's high bits determine format:

| Header high bits | Format | Description |
|---|---|---|
| `NUMERIC_POS` (0x0000) | Long | Positive, signed long format |
| `NUMERIC_NEG` (0x4000) | Long | Negative, signed long format |
| `NUMERIC_SHORT` (0x8000-0xBFFF) | Short | Short format (2-byte header) |
| `NUMERIC_SPECIAL` (0xC000) | Special | NaN, +Inf, -Inf |

[verified-by-code `numeric.c:169-175`]

The short format saves 2 bytes vs long; chosen when the
value fits its range. Modern code uses short for the
overwhelming majority of values.

## NumericShort layout

```c
typedef struct NumericShort
{
    uint16    n_header;     /* sign + scale + weight, all packed */
    NumericDigit n_data[]; /* base-10000 digits */
} NumericShort;
```

16-bit header packs:
- 1 bit sign.
- 6 bits dscale (display scale, 0..63).
- 1 bit weight sign.
- 6 bits weight magnitude.
- Bit pattern at high bits = `NUMERIC_SHORT`.

The 6-bit ranges limit short to: dscale ≤ 63, weight ∈
[-64, 63]. Most decimal values fit (each weight unit = 4
decimal digits in base-10000).

## NumericLong layout

```c
typedef struct NumericLong
{
    uint16    n_sign_dscale;   /* sign + dscale */
    int16     n_weight;        /* signed weight */
    NumericDigit n_data[];     /* base-10000 digits */
} NumericLong;
```

When short doesn't fit (huge values, lots of scale), long
format. 4-byte header instead of 2.

## The base-10000 digits

[from-comment context]

```c
typedef int16 NumericDigit;
```

Each digit represents 4 decimal digits (0..9999). So
`12345.678` in base-10000:
- Decimal: `1, 2345, 6780`
- weight: `+0` (one whole-number unit)
- digits: `[1, 2345, 6780]`

Base-10000 was chosen because it fits 16-bit digits and
keeps mul/div implementations simple (multiplying two
NumericDigits fits in int32).

## Special values

[verified-by-code via `NUMERIC_SPECIAL`]

Beyond ordinary decimals:
- **NaN** — propagates through arithmetic.
- **+Infinity / -Infinity** — IEEE 754-like behavior.
- **Negative zero** — distinct from positive zero in some
  contexts but compare equal.

Special values use 2-byte header only; no digit array.

## SQL semantics — NUMERIC(precision, scale)

```sql
CREATE TABLE financial (
    amount NUMERIC(10, 2)   -- 10 digits, 2 after decimal
);
```

The `(precision, scale)` constrains:
- `precision` = total significant digits.
- `scale` = digits after decimal point.

PG stores everything as variable-length Numeric internally.
The type modifier (`atttypmod` for the column) enforces the
constraint on INSERT/UPDATE.

## Performance characteristics

- **All arithmetic O(N)** in digit count. For typical
  financial precision (10-20 digits), that's 2-4 digits;
  fast.
- **For very high precision** (1000+ digits, e.g.
  cryptographic-grade), arithmetic gets slow. Use specialized
  libraries instead.
- **Comparison** is O(N) but heavily optimized — equal-
  weight comparison is one memcmp.
- **Conversion to/from text** is O(N²) in the worst case
  (long divisions). Cached for repeated conversions.

## The fmgr conversion macros

```c
Numeric n = PG_GETARG_NUMERIC(0);
PG_RETURN_NUMERIC(result);
```

Convention: `numeric_*` family of operators
(`numeric_add`, `numeric_sub`, `numeric_mul`,
`numeric_div`, etc.) for arithmetic. Each
detoasts the input, computes, returns a fresh Numeric.

For temporary working copies, `init_var_from_num` /
`free_var` convert between on-disk Numeric and in-memory
NumericVar (mutable).

## NumericVar — the in-memory mutable form

```c
typedef struct NumericVar
{
    int         ndigits;       /* digit count */
    int         weight;        /* base-10000 weight */
    int         sign;
    int         dscale;        /* display scale */
    NumericDigit *buf;         /* pointer to digit buffer */
    NumericDigit *digits;      /* digits within buf */
} NumericVar;
```

Used internally by arithmetic functions. The
`buf` vs `digits` split lets arithmetic operations write
into a pre-allocated buffer without copying.

Conversion to/from on-disk Numeric is fast:
`make_result` / `numeric_to_var`.

## Common review-time concerns

- **`Numeric` is varlena** — use `PG_GETARG_NUMERIC` (which
  detoasts) for arguments.
- **Don't assume binary representation.** The format choice
  (short vs long vs special) depends on value.
- **Conversions to `float8` lose precision.** Avoid in
  financial paths; use only for sorting / approximate ops.
- **NaN comparisons** follow PG conventions (NaN = NaN, not
  IEEE NaN ≠ NaN).
- **Performance** matters for hot paths — consider
  `int8` if you can guarantee value range.

## Invariants

- **[INV-1]** Three formats: Short / Long / Special;
  detected from header high bits.
- **[INV-2]** Digits are base-10000 (each = 0..9999).
- **[INV-3]** Special values (NaN, ±Inf) have 2-byte
  header only.
- **[INV-4]** Arithmetic is O(N digits); exact, no float
  approximation.
- **[INV-5]** PG NaN equals PG NaN (unlike IEEE 754).

## Useful greps

- The format definitions:
  `grep -n 'NUMERIC_POS\|NUMERIC_NEG\|NUMERIC_SHORT\|NUMERIC_SPECIAL' source/src/backend/utils/adt/numeric.c | head -10`
- The arithmetic functions:
  `grep -n 'numeric_add\|numeric_sub\|numeric_mul\|numeric_div' source/src/include/utils/numeric.h | head -10`
- NumericVar manipulation:
  `grep -n 'init_var\|free_var\|set_var_from_num' source/src/backend/utils/adt/numeric.c | head -10`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/adt/numeric.c`](../files/src/backend/utils/adt/numeric.c.md) | 111 | format + header constants |
| [`src/backend/utils/adt/numeric.c`](../files/src/backend/utils/adt/numeric.c.md) | — | implementation |
| [`src/include/utils/numeric.h`](../files/src/include/utils/numeric.md) | — | public API |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/datum-nullabledatum.md` —
  Numeric is pass-by-ref.
- `knowledge/data-structures/heap-tuple-layout.md` —
  Numeric stored varlena-style.
- `knowledge/idioms/heap-tuple-decompression-pattern.md` —
  Numeric values may be TOASTed.
- `.claude/skills/fmgr-and-spi/SKILL.md` —
  `PG_GETARG_NUMERIC` + arithmetic functions.
- `source/src/include/utils/numeric.h` — public API.
- `source/src/backend/utils/adt/numeric.c` —
  implementation.
