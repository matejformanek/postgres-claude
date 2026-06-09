# utils/cash.h — MONEY type (int64 with locale formatting)

Source: `source/src/include/utils/cash.h` (35 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Trivial: `Cash = int64`. Storage is a pass-by-value (on 64-bit) int64; SQL formatting depends on `lc_monetary` locale.

## Public API

- `typedef int64 Cash;` (`cash.h:17`).
- `DatumGetCash`/`CashGetDatum`/`PG_GETARG_CASH`/`PG_RETURN_CASH` (`cash.h:20-33`).

## Invariants

- **INV-cash-is-int64** [verified-by-code, `cash.h:17`]: scale (decimal places) is implicit from `lc_monetary`, NOT stored in the value. Two databases with different lc_monetary may interpret the same on-disk int64 differently.
- **INV-cash-comment-from-1996** [from-comment, `cash.h:5-9`]: D'Arcy Cain's original; cash is widely considered "do not use" — NUMERIC is the modern alternative.

## Trust-boundary / Phase-D surface

- **Locale-dependent parsing in cash_in** [not in this header]: `lc_monetary` controls accepted thousands sep, currency symbol position, fraction digits. Cross-locale dump/reload is a documented foot-gun.
- **Multiplication/division overflow** [not in this header]: cash arithmetic uses int64; overflow returns silently in the legacy hard-error path. cash_mul_int8 etc. should use `pg_*_*_overflow` from common/int.h — verify in cash.c.

## Cross-refs

- `source/src/backend/utils/adt/cash.c` — locale-sensitive in/out, arithmetic.

## Issues

- `[ISSUE-INVARIANT: scale-tied-to-lc_monetary cross-database hazard (info)]` — well-known but worth documenting at header level for new readers.
