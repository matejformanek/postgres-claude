---
path: src/backend/utils/adt/cash.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1232
depth: deep
---

# cash.c

- **Source path:** `source/src/backend/utils/adt/cash.c`
- **Lines:** 1232
- **Depth:** deep
- **Companion files:** `src/include/utils/cash.h` (`Cash` typedef, `PG_GETARG_CASH`/`PG_RETURN_CASH`), `src/include/common/int.h` (`pg_add/sub/mul_s64_overflow`, `pg_abs_s64`), `src/include/utils/pg_locale.h` (`PGLC_localeconv`), `src/include/utils/numeric.h` (`int64_to_numeric`, `numeric_mul_safe`, `numeric_int8_safe`), `src/include/utils/float.h` (`float8_mul/div`, `FLOAT8_FITS_IN_INT64`).
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose
Implements the `money` type. `[from-comment]` "Functions to allow input and output of money normally but store and handle it as 64 bit ints" `cash.c:7-8`. The on-disk value is an `int64` count of the smallest currency unit (cents at 2 frac_digits); the decimal point and grouping are purely a formatting artifact driven by the `lc_monetary` locale via `PGLC_localeconv()`. Covers I/O (`cash_in`/`cash_out`/`cash_recv`/`cash_send`), the full comparison family, arithmetic (add/sub/mul/div against cash, int2/4/8, float4/8), and conversions to/from `numeric` and the int types, plus the en-US word renderer `cash_words`. `[verified-by-code]`

## Public symbols
| Symbol | file:line | Role |
| --- | --- | --- |
| `cash_in` | `cash.c:174` | SQL input: locale-aware parse `[$]###[,]###[.##]`; soft-error capable. |
| `cash_out` | `cash.c:389` | SQL output: locale-driven formatting (sign position, grouping, currency symbol). |
| `cash_recv` | `cash.c:594` | Binary input: raw int64. |
| `cash_send` | `cash.c:605` | Binary output: raw int64. |
| `cash_eq`/`cash_ne`/`cash_lt`/`cash_le`/`cash_gt`/`cash_ge` | `cash.c:620,629,638,647,656,665` | Comparisons (plain int64 compare). |
| `cash_cmp` | `cash.c:674` | B-tree support: -1/0/1. |
| `cash_pl`/`cash_mi` | `cash.c:693,707` | Add / subtract, overflow-checked. |
| `cash_div_cash` | `cash.c:721` | money / money -> float8. |
| `cash_mul_flt8`/`flt8_mul_cash`/`cash_div_flt8` | `cash.c:742,756,770` | money <-> float8. |
| `cash_mul_flt4`/`flt4_mul_cash`/`cash_div_flt4` | `cash.c:784,798,813` | money <-> float4 (widened to float8). |
| `cash_mul_int8`/`int8_mul_cash`/`cash_div_int8` | `cash.c:827,841,854` | money <-> int8. |
| `cash_mul_int4`/`int4_mul_cash`/`cash_div_int4` | `cash.c:868,882,897` | money <-> int4. |
| `cash_mul_int2`/`int2_mul_cash`/`cash_div_int2` | `cash.c:911,924,938` | money <-> int2. |
| `cashlarger`/`cashsmaller` | `cash.c:951,967` | max/min support. |
| `cash_words` | `cash.c:984` | int64 cents -> English words ("... dollars and NN cents"). |
| `cash_numeric`/`numeric_cash` | `cash.c:1075,1132` | money <-> numeric (scale by frac_digits). |
| `int4_cash`/`int8_cash` | `cash.c:1172,1205` | int -> money (multiply by scale). |
| `append_num_word` (static) | `cash.c:39` | Word renderer for a 0..999 group. |
| `cash_pl_cash`/`cash_mi_cash`/`cash_mul_float8`/`cash_div_float8`/`cash_mul_int64`/`cash_div_int64` (static inline) | `cash.c:91,104,117,130,143,156` | Overflow/zero-checked arithmetic primitives behind the fmgr wrappers. |

## Internal landmarks
- **Locale handling (the high-value part):** every I/O and conversion path calls `PGLC_localeconv()` and reads `struct lconv` `cash.c:191,407,1081,1141,1180,1213`. Fields used: `frac_digits` (decimal places), `mon_decimal_point` (`dsymbol`), `mon_thousands_sep` (`ssymbol`), `currency_symbol`, `positive_sign`/`negative_sign`, plus in `cash_out` the POSIX sign-placement quartet `p/n_sign_posn`, `p/n_cs_precedes`, `p/n_sep_by_space`, and `mon_grouping`.
- **frac_digits range guard (recurring idiom):** `frac_digits` can be `CHAR_MAX` in the C locale and the signedness of `char` is compiler-dependent, so the code never tests `== CHAR_MAX`; instead it range-checks `< 0 || > 10` and falls back to 2 `cash.c:193-205` (repeated verbatim at `:409-412,1083-1086,1143-1146,1182-1185,1215-1218`). `mon_grouping` gets the analogous `<= 0 || > 6` guard in `cash_out` `cash.c:414-420`.
- **dsymbol restricted to one byte:** the decimal point must be a single byte else it defaults to `'.'` `cash.c:207-212,422-427`; the thousands sep may be multibyte and is chosen so it never equals `dsymbol` `cash.c:213-216,428-431`.
- **cash_in accumulation in the negative:** to capture the most-negative int64, the absolute value is built as a *negative* running total (`pg_mul_s64_overflow(value,10)` then `pg_sub_s64_overflow(value,digit)`) `cash.c:286-299`, with the sign flipped at the end and `value == PG_INT64_MIN` caught when the result should be positive `cash.c:364-372`. `[from-comment]` `cash.c:271-278`.
- **cash_in rounding:** a single extra digit `>= '5'` rounds the (negative) accumulator by subtracting 1 `cash.c:312-321`; remaining digits past frac_digits are consumed and discarded `cash.c:337-338`.
- **cash_out right-to-left buffer build:** digits, decimal point, and thousands separators are emitted backwards into a 128-byte `buf[]` `cash.c:453-481`, then the currency/sign decoration is applied by the `sign_posn` switch (cases 0-4) honoring `cs_precedes` and `sep_by_space` `cash.c:507-586`.
- **cash_words grouping:** splits the unsigned cents into cents + six 3-digit groups (hundreds..quadrillions) `cash.c:1010-1019` and renders each via `append_num_word`; the `small[]`/`big` word tables live at `cash.c:42-48`.
- **numeric_cash uses the safe numeric API:** `numeric_mul_safe`/`numeric_int8_safe` with `fcinfo->context` and `SOFT_ERROR_OCCURRED` checks `cash.c:1156-1163`; `numeric_int8` rounds to nearest for the final cents value.

## Invariants & gotchas
- **money is locale-dependent on input AND output.** The same stored int64 formats differently under different `lc_monetary`, and a value dumped under one locale may not re-parse under another. This is a long-standing money caveat, visible from the per-call `PGLC_localeconv()` `cash.c:191,407`. `[verified-by-code]`
- **All arithmetic that can overflow is checked and hard-throws.** `cash_pl_cash`/`cash_mi_cash`/`cash_mul_int64` use `pg_*_s64_overflow` -> `ereport(ERROR)` "money out of range" `cash.c:96-99,109-112,148-151`; float paths check `isnan || !FLOAT8_FITS_IN_INT64` after `rint` `cash.c:122-125,135-138`; `cash_div_int64`/`cash_div_cash` reject zero divisor with `ERRCODE_DIVISION_BY_ZERO` `cash.c:159-162,728-731`. These are hard `ereport`, NOT soft errors, even though they run under fmgr. `[verified-by-code]`
- **cash_in / int4_cash / int8_cash / numeric_cash are the soft-error-aware paths.** `cash_in` uses `ereturn(escontext, ...)` for overflow and bad syntax `cash.c:292,317,327,354,367`; `int4_cash`/`int8_cash` use `ereturn(fcinfo->context, ...)` `cash.c:1194,1227`; `numeric_cash` checks `SOFT_ERROR_OCCURRED` and `PG_RETURN_NULL` `cash.c:1157-1163`. Mixing these up (treating the hard arithmetic helpers as soft) would break `pg_input_is_valid`-style callers.
- **Rounding is to nearest, half-up (away from zero), at frac_digits precision.** `cash_in` rounds via the `>= '5'` extra-digit rule `cash.c:312-321`; float multiply/divide round via `rint` `cash.c:120,133`; `numeric_cash` rounds via `numeric_int8` `cash.c:1160-1161`. Different code paths, same intended semantics — changing one without the others would make conversions inconsistent.
- **cash_div_cash returns float8, not money** `cash.c:721-735`: money/money is a dimensionless ratio. Other `*_div_*` keep money.
- **cash_words treats the value as unsigned after sign extraction** `cash.c:1003-1010` ("Now treat as unsigned, to avoid trouble at INT_MIN"); negating INT64_MIN as signed would be UB.
- **cash_out buffer is fixed 128 bytes** `cash.c:395`; sufficient for max int64 cents plus grouping/decoration, but any change widening the value or grouping density must re-check this.
- **The `(` paren as negative sign is heuristic** `cash.c:247-251`; the comment flags it does not check for balanced parens `cash.c:241`.
- **cash_numeric guards against scale loss** `cash.c:1105-1122`: near INT64_MAX, `select_div_scale` could pick scale 0, so it forces dscale via `numeric_round` before dividing and rounds again after.

## Cross-references
- [[knowledge/files/src/backend/utils/adt/numutils.c]] — shares the `common/int.h` s64-overflow helpers; numutils is the general integer parser, cash hand-rolls its own locale-aware parser.
- [[knowledge/files/src/backend/utils/adt/enum.c]] — sibling adt fmgr I/O file.
- [[knowledge/idioms/fmgr-and-spi]] — `PG_GETARG_CASH`/`PG_RETURN_CASH`, `DirectFunctionCall2` to numeric_round/numeric_div, `fcinfo->context` soft-error wiring.
- [[knowledge/idioms/error-handling]] — `ereport(ERROR)` hard arithmetic vs `ereturn`/`SOFT_ERROR_OCCURRED` soft conversion paths.
- `source/src/backend/utils/adt/pg_locale.c` — `PGLC_localeconv` source of every formatting decision here.
- `source/src/backend/utils/adt/numeric.c` — `numeric_mul_safe`/`numeric_int8_safe`/`int64_to_numeric` used by the numeric conversions.

## Potential issues
- **[ISSUE-undocumented-invariant: money round-trip is not locale-stable]** `cash.c:191,407` — because both `cash_in` and `cash_out` re-read `lc_monetary` at call time, a `money` value output under one `lc_monetary` can fail to re-parse (or parse to a different int64) under another locale, e.g. when `mon_thousands_sep`/`mon_decimal_point` swap roles. Not a code defect (it is the documented nature of the type) but the invariant is implicit in the source; surfaced for corpus completeness. Severity: nit.
- **[ISSUE-stale-todo: unbalanced-paren and "needs more checking" comments in cash_in]** `cash.c:226,240-241` — the parser carries long-standing `XXX`/"better heuristics needed"/"doesn't properly check for balanced parens - djmc" comments. These are accurate descriptions of known looseness in money input parsing, not regressions. Severity: nit.

## Confidence tag tally
- [verified-by-code]: 5
- [from-comment]: 3
- [from-README]: 0
- [inferred]: 0
- [unverified]: 0
