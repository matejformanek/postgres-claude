---
path: src/interfaces/ecpg/pgtypeslib/numeric.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 1588
depth: deep
---

# `numeric.c` — client-side arbitrary-precision numeric for ecpg (`PGtypesnumeric`)

## Purpose
Self-contained, malloc-based reimplementation of PostgreSQL's `NUMERIC` for the
ecpg `pgtypes` client library. Defines the `numeric`/`decimal` variable types
and the full `PGTYPESnumeric_*` API: allocate/free, parse from ASCII / int /
long / double / decimal, format to ASCII, the four arithmetic ops
(add/sub/mul/div) plus compare, and conversion back to int/long/double/decimal.
Unlike the backend's base-`NBASE` (10000) packed representation, this version
stores **one decimal digit per `NumericDigit` byte** (`var->digits[i]` holds
0–9) [verified-by-code numeric.c:146,930], which keeps the schoolbook
arithmetic simple at the cost of density. Errors are signalled by returning
`-1` (or `INT_MAX`/`NULL`) and setting `errno` to a `PGTYPES_NUM_*` code
[verified-by-code numeric.c:1081,1304].

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `numeric *PGTYPESnumeric_new(void)` | numeric.c:41 | allocs `numeric` + 0-digit buf; NULL on OOM |
| `decimal *PGTYPESdecimal_new(void)` | numeric.c:58 | zeroed `decimal` (fixed-size, no buf) |
| `void PGTYPESnumeric_free(numeric *)` | numeric.c:384 | frees `var->buf` then `var` |
| `void PGTYPESdecimal_free(decimal *)` | numeric.c:391 | frees the struct only |
| `numeric *PGTYPESnumeric_from_asc(char *, char **endptr)` | numeric.c:320 | parse; frees value on parse error |
| `char *PGTYPESnumeric_to_asc(numeric *, int dscale)` | numeric.c:342 | works on a copy (rounding mutates) |
| `int PGTYPESnumeric_add(v1,v2,result)` | numeric.c:636 | sign dispatch over `add_abs`/`sub_abs` |
| `int PGTYPESnumeric_sub(v1,v2,result)` | numeric.c:764 | mirror of add |
| `int PGTYPESnumeric_mul(v1,v2,result)` | numeric.c:895 | schoolbook; `global_rscale = r1+r2` |
| `int PGTYPESnumeric_div(v1,v2,result)` | numeric.c:1052 | long division; div-by-zero → errno |
| `int PGTYPESnumeric_cmp(v1,v2)` | numeric.c:1280 | returns `INT_MAX`+errno on bad sign |
| `int PGTYPESnumeric_from_int(int,var)` | numeric.c:1308 | delegates to from_long |
| `int PGTYPESnumeric_from_long(long,var)` | numeric.c:1317 | hand-rolled digit extraction |
| `int PGTYPESnumeric_copy(src,dst)` | numeric.c:1387 | deep copy of digit buffer |
| `int PGTYPESnumeric_from_double(double,dst)` | numeric.c:1410 | via `%.*g` (DBL_DIG) → from_asc |
| `int PGTYPESnumeric_to_double(nv,*dp)` | numeric.c:1482 | wraps `numericvar_to_double` |
| `int PGTYPESnumeric_to_int(nv,*ip)` | numeric.c:1493 | via to_long + INT range check |
| `int PGTYPESnumeric_to_long(nv,*lp)` | numeric.c:1517 | to_asc(scale 0) + strtol |
| `int PGTYPESnumeric_to_decimal(src,dst)` | numeric.c:1546 | OVERFLOW if `ndigits > DECSIZE` |
| `int PGTYPESnumeric_from_decimal(src,dst)` | numeric.c:1569 | inverse of to_decimal |

## Internal landmarks
- **The `numeric` struct** (declared in `pgtypes_numeric.h`): fields used here are
  `ndigits`, `weight` (power-of-10 weight of the first digit), `rscale` (result
  scale carried through arithmetic), `dscale` (display scale), `sign`
  (`NUMERIC_POS`/`NUMERIC_NEG`/`NUMERIC_NAN`), `buf` (owned allocation), and
  `digits` (= `buf + 1`, leaving a spare leading slot for round-up carry)
  [verified-by-code numeric.c:36].
- **`alloc_var()`** numeric.c:28 — frees any old `buf`, allocs `ndigits+1`, zeroes
  the spare slot, sets `digits = buf+1`. The `+1` spare is what lets `weight++`
  round-up (e.g. numeric.c:259-264, 1248) borrow a digit to the left.
- **`set_var_from_str()`** numeric.c:77 — the parser. Handles leading spaces,
  `NaN`, optional sign, one decimal point, digits (one per `digits[]` byte),
  optional `e`/`E` exponent (clamped to `±INT_MAX/2`), trailing spaces, then
  strips leading zeros. Sets `errno = PGTYPES_NUM_BAD_NUMERIC` on any malformity.
- **`get_str_from_var()`** numeric.c:225 — `numeric_out` guts. **Mutates its
  argument** by rounding (banker-less, round-half-up at numeric.c:248); callers
  always pass a copy.
- **`cmp_abs`/`add_abs`/`sub_abs`** numeric.c:406/464/552 — magnitude primitives.
  `sub_abs` requires `ABS(var1) >= ABS(var2)` (caller-enforced via `cmp_abs`).
- **The long-division loop** numeric.c:1168-1230 — classic guess-and-subtract.
  `divisor[1]` is var2 with a leading zero; `divisor[2..9]` are lazily-built
  multiples of the divisor (numeric.c:1181-1197). `guess` is estimated from the
  two leading "have" digits over the leading divisor digits (numeric.c:1175),
  capped at 9, then decremented until `cmp_abs(dividend, divisor[guess]) >= 0`.
  A single `goto done` cleanup path frees `dividend.buf` and all `divisor[i].buf`.
- **`numericvar_to_double()`** numeric.c:1431 — copy → `get_str_from_var` →
  `strtod`, mapping `ERANGE` to UNDERFLOW (val==0) or OVERFLOW.

## Invariants & gotchas
- **`digits = buf + 1` ownership.** Only `buf` is freed; `digits` is an interior
  pointer. After leading-zero stripping the `digits`/`weight`/`ndigits` triple is
  advanced *but `buf` is unchanged* (numeric.c:204-209, 518-523) — so always free
  `buf`, never `digits`. `zero_var` frees `buf` and NULLs both (numeric.c:373).
- **Round-up needs the spare slot.** `get_str_from_var` may do `var->digits--;
  var->weight++` (numeric.c:261-263) — only safe because `digits` started at
  `buf+1`. Same trick in div (numeric.c:1248).
- **Sign handling.** `NUMERIC_NAN` short-circuits parsing/printing; arithmetic
  does **not** special-case NaN inputs — `add_abs`/`mul`/`div` will treat a NaN
  operand as if its (zero) digit buffer were a real number. A zero result forces
  `sign = NUMERIC_POS` (numeric.c:962, 1257) to avoid "-0".
- **`rscale` vs `dscale`.** `rscale` is the working precision propagated through
  add/sub (`Max` of inputs) and mul (`r1+r2`); `dscale` is the display scale.
  `select_div_scale` (numeric.c:986) picks `dscale` for ≥`NUMERIC_MIN_SIG_DIGITS`
  significant digits and sets working `rscale = dscale + 4`.
- **Division by zero** → `errno = PGTYPES_NUM_DIVIDE_ZERO`, return −1
  (numeric.c:1078-1083). The check is `var2->ndigits + 1 == 1`, i.e. var2 has
  zero digits; a var2 whose digits are all literal `0` but `ndigits>0` would
  *not* be caught here (but parser strips leading zeros, and an all-zero value
  normalizes to `ndigits==0`).
- **`PGTYPESnumeric_div` allocates result into a temp buffer first**
  (numeric.c:1145) so `result->buf` is only freed once a replacement is secured —
  result is left intact on OOM. But see Potential issues for the partial-init case.
- **Free contract on error paths.** `from_asc` frees its value on parse failure
  (numeric.c:335); `to_asc`/`numericvar_to_double` free the working copy; the
  div `done:` label frees all scratch. `to_long`/`numericvar_to_double` are
  careful to free the `strtod`/`strtol` source string *after* `endptr` use.

## Cross-refs
- [[common.c]] — `pgtypes_alloc` (the malloc+errno wrapper) and sibling pgtypes helpers.
- [[dt_common.c]] — companion date/time client type using the same error idiom.
- [[decimal.h]] / `pgtypes_numeric.h` — declares the `numeric`/`decimal` structs,
  `NumericDigit`, `DECSIZE`, `NUMERIC_POS/NEG/NAN`, and the `NUMERIC_*_SCALE` /
  `NUMERIC_MIN_SIG_DIGITS` constants this file depends on.

## Potential issues
- **[ISSUE-CORRECTNESS: signed-char digit multiply in mul]** `numeric.c:930` —
  `var1->digits[i1] * var2->digits[i2]` multiplies two `NumericDigit`s. If
  `NumericDigit` is a signed `char` (it is `char`-width here), each digit is 0–9
  so the product (≤81) fits, but the expression is computed in `int`; the running
  `sum` is `long`. Low severity — values are bounded by the one-digit-per-byte
  invariant, so no overflow in practice. Flagging only because the same pattern
  in the packed backend uses wider types. Severity: low / informational.
- **[ISSUE-OVERFLOW: alloc sizing from parsed weight/exponent]**
  `numeric.c:484-491, 575-577, 1092-1095` — `res_ndigits` is derived from
  `rscale + weight (+1)`, and `weight` can be inflated by a parsed exponent up to
  `±INT_MAX/2` (numeric.c:181-186). A crafted input like `1e1073741000` yields a
  huge `weight`; subsequent `add_abs`/`sub_abs`/`div` compute `res_ndigits` from
  it and call `digitbuf_alloc(res_ndigits)` (= `pgtypes_alloc`, an `int`-sized
  malloc). The arithmetic `res_rscale + res_weight + 1` can overflow `int` to a
  small/negative value (clamped to 1) or request a multi-GB allocation; the
  `+ 4`/`+ 2` paddings (numeric.c:272, 1145) can also overflow. No explicit
  guard against pathological weights before allocation. Severity: medium —
  client-side, but an attacker-controlled numeric literal fed to ecpg arithmetic
  could OOM or, on `int` overflow, under-allocate. Worth a bounds check on
  `weight`/`res_ndigits`. Severity: medium.
- **[ISSUE-LEAK: div scratch on early `goto done` before full result wiring]**
  `numeric.c:1145-1156` — once `tmp_buf` replaces `result->buf`, success path is
  fine; but `divisor[guess].buf` allocations inside the loop (numeric.c:1187) on
  a later OOM `goto done` are correctly freed by the `for (i=1;i<10;i++)` sweep
  (numeric.c:1270). This is actually handled — noting it only to confirm the
  cleanup is complete. No leak. (informational)
- **[ISSUE-CORRECTNESS: `from_long` of `LONG_MIN`]** `numeric.c:1334-1336` —
  `if (abs_long_val < 0) abs_long_val *= -1;` negates `LONG_MIN`, which is
  signed-overflow UB and leaves `abs_long_val` negative on two's-complement. The
  subsequent size/extract loops then misbehave for the single value `LONG_MIN`.
  Severity: low (one input value) but a real correctness/UB bug. Severity: low.
