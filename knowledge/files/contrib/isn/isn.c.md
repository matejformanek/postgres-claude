# contrib/isn/isn.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 1143
**Verification depth:** scan + targeted deep-reads (input parser, GUC,
exported API, check-digit routines, error paths)

## Role

The full data-type implementation for `ean13`, `isbn`, `ismn`, `issn`,
`upc`: input/output parsers with optional hyphen tolerance, check-digit
validation (Mod-10 weighted for ISBN/ISSN, plain Mod-10 for EAN13/UPC),
inter-type casts, the `isn.weak` GUC for accepting bad check digits,
SQL-callable `is_valid`/`make_valid` predicates, and `accept_weak_input`
session-mutator helpers.

## Public API

- SQL-callable functions (each `PG_FUNCTION_INFO_V1`):
  - Input: `ean13_in`, `isbn_in`, `ismn_in`, `issn_in`, `upc_in`.
  - Output: `ean13_out`, `isn_out` (variant covers ISBN/ISMN/ISSN/UPC).
  - Casts: `isbn_cast_from_ean13`, `ismn_cast_from_ean13`,
    `issn_cast_from_ean13`, `upc_cast_from_ean13`.
  - Predicates: `is_valid`, `make_valid`.
  - GUC helpers: `accept_weak_input`, `weak_input_status`.
  [verified-by-code] `source/contrib/isn/isn.c:939-1143`
- Internal:
  - `ean2isn` — derive isn type from EAN13 prefix, cast or error.
    [verified-by-code] `source/contrib/isn/isn.c:344-431`
  - `string2ean` (escontext-aware) — the unified parser; switches over
    `type` (EAN13/ISBN/ISSN/ISMN/UPC/ANY) and dispatches.
    [verified-by-code] `source/contrib/isn/isn.c:520-898`
  - `checkdig(buf, len)` — Mod-10 check digit (used for EAN13/UPC/ISMN).
    [verified-by-code] `source/contrib/isn/isn.c:314-335`
  - `weight_checkdig` — weighted Mod-11 (used for ISBN-10 / ISSN).
    [referenced] `source/contrib/isn/isn.c:829, 835`
- GUC: `isn.weak` (PGC_USERSET, bool, default false). Marks
  `isn.*` prefix as reserved.
  [verified-by-code] `source/contrib/isn/isn.c:922-934`

## Invariants

- INV-1: Internal representation is `uint64` with the LOW bit
  reserved as "invalid-check-digit" flag. `(val & 1) == 0` means
  valid; `val | 1` means valid-format-but-bad-check-digit (only
  achievable when `g_weak=true` at input time, or via `make_valid`'s
  inverse `accept_weak_input` workflow).
  [verified-by-code] `source/contrib/isn/isn.c:850-855, 1100-1120`
- INV-2: `g_weak` (the `isn.weak` GUC) is per-session (PGC_USERSET),
  globally affects acceptance of bad check digits. Default OFF.
  [verified-by-code] `source/contrib/isn/isn.c:47, 922-931`
- INV-3: Soft-error mode is supported via `ereturn(escontext, ...)`
  in parser error paths — used by the `*_input` family when the
  caller passed a Node*. (Allows `pg_input_is_valid` and the JSONB
  cast-on-error to short-circuit instead of throwing.)
  [verified-by-code] `source/contrib/isn/isn.c:867-897`
- INV-4: All textual output goes through `hyphenate()` with the
  appropriate per-type prefix table. Output buffer is fixed
  `MAXEAN13LEN+1 = 19` (13 digits + up to 4 hyphens + NUL).
  [verified-by-code] `source/contrib/isn/isn.c:37, 144-300` (caller
  side at lines 939-1043).
- INV-5: `_PG_init` calls `check_table` on each prefix table ONLY in
  ASSERT builds; production startup is a no-op for table integrity.
  [verified-by-code] `source/contrib/isn/isn.c:904-933`

## Notable internals

- **`g_weak` flips parser behavior globally**: when ON, a number with
  a bad check digit is accepted but the low bit of the result is set.
  When OFF (default), the parser throws an
  `ERRCODE_INVALID_TEXT_REPRESENTATION` error.
  [verified-by-code] `source/contrib/isn/isn.c:857-864`
- **"!" suffix in input means "I know the check digit is wrong, accept
  anyway"** — a per-input override that works regardless of `g_weak`.
  Sets the `magic` local to true.
  [verified-by-code] `source/contrib/isn/isn.c:737-743`
- **Type discrimination from prefix** (in `ean2isn` and `string2ean`):
  `978/979` → ISBN, `977` → ISSN, `9790` → ISMN, `0..` → UPC,
  else generic EAN13.
  [verified-by-code] `source/contrib/isn/isn.c:374-397, 807-820`
- **`accept_weak_input(bool)` uses `set_config_option(... PGC_S_SESSION
  ... is_local=true)`** — mutates the GUC for the current session
  (transient if is_local) and returns the new value.
  [verified-by-code] `source/contrib/isn/isn.c:1126-1136`

## Trust-boundary / Phase-D surface

### `isn.weak` GUC — central concern

- **PGC_USERSET, per-session, ANY logged-in role can flip it**
  [verified-by-code:927]. So an untrusted client can opt into
  "accept bad ISBNs". The intent of the module is to let admins
  bulk-load legacy data with known-bad check digits; per-session
  scope is appropriate.
- **No cross-session leak**: GUC mutation in one session does not
  affect another.
- **What can an attacker do with `isn.weak=on`?** Insert ISBN-like
  values whose check digits are wrong. The low-bit of the stored
  uint64 is set; later readers can call `is_valid()` to filter. So
  the only impact is downstream applications that didn't expect
  flagged values. Acceptable.

### Input parser robustness

- **Buffer bounds**: parser reads from caller-supplied `str` (a C
  string), writes into a fixed `buf[17]`. Bound check at line 750-752:
  `if (++length > 13) goto eantoobig;` — actively enforced.
  [verified-by-code] `source/contrib/isn/isn.c:748-752`
- **`atooid`-style overflow**: no — the parser builds digit-by-digit,
  not via `atoi`/`atol`. Check-digit math is bounded.
- **Locale/charset injection**: input uses `isdigit((unsigned char)
  *p)` and `pg_ascii_toupper((unsigned char) *p)` — locale-safe
  variants. No locale-dependent surprises with non-ASCII.
  [verified-by-code] `source/contrib/isn/isn.c:90-99, 711-721`
- **No format-string injection in errmsg** — all `errmsg(...)` use
  `%s` for the (caller-supplied) input string. The string is logged
  but never `printf`'d as a format.
  [verified-by-code] `source/contrib/isn/isn.c:870-897`

### `ean2isn` cast routine

- **No overflow check on `ean > UINT64CONST(9999999999999)`** — guard
  at line 357 covers the "too large" case explicitly. Anything above
  the EAN13 numeric range errors out before further processing.
  [verified-by-code] `source/contrib/isn/isn.c:355-358`

### Unknown registration-group handling (silent acceptance)

- **ISSUE-D1 (info, "weak input by design")**: a value with a valid
  check digit but unknown registration prefix is accepted and stored.
  This is by design — the module validates *check digits*, not
  *registration-group existence*. See `isn_data_headers.md` for the
  static table side.

### Other observations

- **`check_table` debug output goes to elog(DEBUG1, ...)** at lines
  133, 138 — wouldn't normally be visible. Fine.
- **`PG_FUNCTION_INFO_V1(weak_input_status)` returns g_weak unchanged**
  — pure read. The function `accept_weak_input(bool)` is a side-effecting
  mutator. **ISSUE-D2 (info)**: `accept_weak_input` *changes the
  session's `isn.weak` GUC*. Documented behavior; but a casual reader
  might expect it to be functionally-pure given the SQL function shape.
  [verified-by-code] `source/contrib/isn/isn.c:1122-1143`

## Cross-refs

- `source/contrib/isn/isn.h` — public type macros.
- `source/contrib/isn/{EAN13,ISBN,ISMN,ISSN,UPC}.h` — static lookup
  tables (see `isn_data_headers.md`).
- `source/src/backend/utils/misc/guc.c` — `set_config_option`,
  `MarkGUCPrefixReserved`.

## Issues raised

- **ISSUE-D1 (info)** — unknown registration prefix is silently
  accepted (only check digit is validated). By module design.
- **ISSUE-D2 (info)** — `accept_weak_input(bool)` is a side-effecting
  SQL function; mutates the session's `isn.weak` GUC. Worth
  documenting.
- **ISSUE-D3 (info, hygiene)** — `extern void initialize(void);` in
  isn.h has no definition (also raised in `isn.h.md`).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-isn.md](../../../subsystems/contrib-isn.md)
