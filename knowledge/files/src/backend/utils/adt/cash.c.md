# `src/backend/utils/adt/cash.c`

- **File:** `source/src/backend/utils/adt/cash.c` (1232 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The `money` (`cash`) type — an int64 storing the value in the smallest currency
unit (e.g. cents for USD). I/O formatting and parsing are **locale-driven**
through `PGLC_localeconv()`. Max representable: `±$92,233,720,368,547,758.07`
at fpoint=2. (`cash.c:1-17` [from-comment])

## Type role

- **Input:** `cash_in` (`:175`) — accepts `[$]###[,]###[.##]`, locale-respecting
  decimal point, thousands separator, currency symbol, sign symbols, and
  parentheses for negatives (no balance check, `:241` [from-comment]).
- **Output:** `cash_out` (`:390`) — emits locale-formatted string using
  POSIX `p/n_sign_posn`, `p/n_cs_precedes`, `p/n_sep_by_space` (`:486-505`).
- **Binary I/O:** `cash_recv` / `cash_send` — raw int64.
- **Comparison/arithmetic:** all `cash_eq/ne/lt/le/gt/ge/cmp`, `cash_pl`,
  `cash_mi`, `cash_mul_*`, `cash_div_*`, `cashlarger`/`cashsmaller`.
- **Conversion:** `cash_numeric`, `numeric_cash`, `int4_cash`, `int8_cash`,
  `cash_words` (number-words English output).

## Key invariants

- All arithmetic goes through `pg_add_s64_overflow` / `pg_sub_s64_overflow` /
  `pg_mul_s64_overflow` (`:96-153`) [verified-by-code] — uses A5 common/int.h
  overflow helpers. No INT_MIN negation UB.
- `cash_in` accumulates negatively (`value` is always ≤0 during accumulation)
  to handle the `INT64_MIN` corner without UB, then flips sign at end with an
  explicit `value == PG_INT64_MIN` check (`:364-374` [verified-by-code]).
- `frac_digits` from `lconv` is **range-clamped** to `[0,10]` because some
  locales (notably C) report `CHAR_MAX`, and the file refuses to test for
  `CHAR_MAX` directly to avoid signed/unsigned-char compiler-flag confusion
  (`:193-205` [from-comment]). Same clamp applies to `mon_grouping`.
- `dsymbol` (decimal mark) is restricted to a **single byte** (`:207-212`);
  but `ssymbol` (thousands), `csymbol` (currency), `psymbol`/`nsymbol`
  (sign) may be multibyte.

## Phase D notes

- `cash_in` is the **only money-type input path** and entirely
  locale-dependent. A pathological locale where `mon_thousands_sep` ==
  `mon_decimal_point` is defended against by hard-coded fallback
  (`:215-216` [verified-by-code]).
- The `(...)` paren-negative syntax has a known caveat in the source:
  "doesn't properly check for balanced parens" (`:241`) — `cash_in("(123")`
  parses as `-123`. **[ISSUE-correctness: unbalanced "(" accepted as negative
  (low) — documented]** Not a security issue, just lax input.
- Output uses `psprintf` (`:511-585`), so no buffer-overflow surface.
- `cash_words` builds via `StringInfo`, bounded by the largest int64 (~20
  digits, fixed word count). No DoS.
- The whole file uses the standard ereport/ereturn pattern with soft-error
  context (`fcinfo->context`) where appropriate (`:292-330`).

## Potential issues

- `[ISSUE-correctness: cash_in accepts "(123" as -123 without matching ")"
  (:241,247-251). (low) — already noted in comment]`
- `[ISSUE-undocumented-invariant: dsymbol restricted to 1 byte; multibyte
  decimal marks silently fall back to '.' (:208-212). (info)]`
- `[ISSUE-info-disclosure: invalid-syntax errmsg echoes raw input verbatim
  (:294,319,329,357). (info) — standard idiom]`

## Cross-references

- `source/src/include/utils/cash.h` — `Cash` typedef (int64).
- `source/src/include/utils/pg_locale.h` — `PGLC_localeconv` shim.
- `source/src/common/int.h` — overflow helpers (A5 layer).

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 4
