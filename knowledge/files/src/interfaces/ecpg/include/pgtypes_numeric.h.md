---
path: src/interfaces/ecpg/include/pgtypes_numeric.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 69
depth: read
---

# `pgtypes_numeric.h` — client-side arbitrary-precision numeric API

## Purpose
Defines the two client-visible decimal structs and the `PGTYPESnumeric_*` /
`PGTYPESdecimal_*` arithmetic/conversion API for the standalone pgtypes library.
`numeric` stores digits in a malloc'd `buf`/`digits` pair; `decimal` stores them
in a **fixed `digits[DECSIZE]` array** (DECSIZE = 30) for stack/embedded use.
[verified-by-code] This is a client-side fork of the backend's NUMERIC type.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `struct numeric` | pgtypes_numeric.h:18 | malloc'd-digit variant; `buf` is alloc base, `digits` points within it [verified-by-code] |
| `struct decimal` | pgtypes_numeric.h:29 | fixed `digits[DECSIZE]` (30) variant [verified-by-code] |
| `NumericDigit` | pgtypes_numeric.h:17 | `unsigned char` — one base-?? digit-group [verified-by-code] |
| `PGTYPESnumeric_new/_free/_from_asc/_to_asc` | pgtypes_numeric.h:44-49 | lifecycle + text I/O [verified-by-code] |
| `PGTYPESnumeric_add/_sub/_mul/_div/_cmp` | pgtypes_numeric.h:50-54 | arithmetic [verified-by-code] |
| `PGTYPESnumeric_to_decimal` / `_from_decimal` | pgtypes_numeric.h:62-63 | convert between the two structs [verified-by-code] |
| `NUMERIC_POS/_NEG/_NAN/_NULL` | pgtypes_numeric.h:6-9 | sign flags [verified-by-code] |

## Internal landmarks
- The `numeric.sign` field holds `NUMERIC_POS/_NEG/_NAN` — note `NUMERIC_NULL`
  (0xF000) exists as a flag but the struct comment only lists the first three
  (pgtypes_numeric.h:24). [verified-by-code]
- `NUMERIC_MAX_PRECISION = 1000`, `NUMERIC_MIN_SIG_DIGITS = 16`
  (pgtypes_numeric.h:10-13) mirror the backend's caps — a fork point. [verified-by-code]

## Invariants & gotchas
- `decimal` is capped at `DECSIZE = 30` digit-groups (pgtypes_numeric.h:15,36).
  `PGTYPESnumeric_to_decimal` must reject / overflow-signal a `numeric` whose
  `ndigits > DECSIZE`; the fixed array cannot grow. Callers converting a
  high-precision `numeric` into a `decimal` are at the mercy of that guard. [verified-by-code]
- Strings from `PGTYPESnumeric_to_asc` must be freed with `PGTYPESchar_free`
  (see [[pgtypes.h]]), not `free`. [inferred]
- These structs are a **client fork** of `src/backend/utils/adt/numeric.c`
  internals — backend numeric hardening does not auto-propagate. See the
  cross-cutting theme in `knowledge/issues/ecpg.md`. [inferred]

## Cross-refs
- [[pgtypes.h]] — `PGTYPESchar_free`.
- [[ecpgtype.h]] — `ECPGt_numeric` (malloc) vs `ECPGt_decimal` (fixed) mirror
  this struct split.
- `knowledge/files/src/interfaces/ecpg/pgtypeslib/numeric.c.md` — implementation
  (carries the `numeric.c:181` exponent-sizing issue).
