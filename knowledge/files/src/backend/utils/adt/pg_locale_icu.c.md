# `src/backend/utils/adt/pg_locale_icu.c`

- **File:** `source/src/backend/utils/adt/pg_locale_icu.c` (1379 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

The **ICU locale provider** — binds Postgres collations to ICU's
`UCollator` and ctype methods via `<unicode/ucol.h>`. Compiled in only
when `USE_ICU` is set; otherwise `create_pg_locale_icu` errors at
runtime with "ICU is not supported in this build" (`pg_locale_icu.c:411-
416` [verified-by-code]).

## Entry points

- `create_pg_locale_icu(collid, context)` (`:322`):
  1. Read `colllocale` and optional `collicurules` from
     pg_collation (or pg_database for default OID).
  2. For single-byte DB encodings, also create a libc `locale_t` via
     `make_libc_ctype_locale` (`:361`) — ICU's ctype is UTF-16-based,
     so single-byte ctype falls back to libc.
  3. Call `make_icu_collator(iculocstr, icurules)` (`:557`).
  4. Allocate `pg_locale_struct` with collate/ctype methods.
- `pg_ucol_open(loc_str)` (`:482`) — wraps `ucol_open` with version
  handling. Errors on ICU failure with the original locale string.
- `make_icu_collator(iculocstr, icurules)` (`:557`) — if custom rules,
  extracts standard rules, concatenates, builds a new collator.
- `fix_icu_locale_str(loc_str)` (`:431`) — for ICU < 55, rewrites
  `und*` prefix to `root*` (older ICU didn't recognize "und").
- `icu_set_collation_attributes` (`:1273`) — applies BCP-47 keyword
  attributes (`ks=primary`, etc.) by parsing the locale-string suffix.
  Used only on ICU < 54 since newer ICU handles them natively.

## Operations exposed

- `strncoll_icu` (`:1119`), `strcoll_icu` (`:1126`) — collation
  comparison via `ucol_strcollUTF8` (UTF-8 path) or with conversion
  to UTF-16 (`icu_to_uchar`, `:912`) for other encodings.
- `strnxfrm_icu` (`:826`), `strxfrm_icu` (`:833`) — produce a binary
  blob whose `memcmp` order matches the collation order. Used by
  varlena's abbreviated-key sortsupport.
- `strnxfrm_prefix_icu` (`:1177`) — prefix transform.
- Case ops: `strlower_icu` (`:622`), `strtitle_icu`, `strupper_icu`,
  `strfold_icu` (`:643`).
- `downcase_ident_icu` (`:712`) — used by the parser for unquoted
  identifier downcase.
- Ctype wcs: `wc_isdigit_icu` (`:189`) etc., `toupper_icu` (`:152`),
  `tolower_icu` (`:158`).

## Phase D notes — locale-string injection

- **The locale string is end-user-controlled** at CREATE COLLATION
  time (`CREATE COLLATION foo (provider=icu, locale='en-US-u-ka-shifted');`).
- `pg_ucol_open` (`:482`) passes the string directly to ICU's
  `ucol_open`. ICU itself parses BCP-47 syntax; malformed input
  triggers `U_FAILURE(status)`, which becomes an `ereport(ERROR)` here
  (`:492-497`). Echoes the original string in the message
  (`"could not open collator for locale \"%s\"..."`) — by design.
- `fix_icu_locale_str` does **string manipulation** on the
  user-supplied locale (`:464-466`: `strcpy(fixed_str, "root");
  strcat(fixed_str, remainder)`) — but only after `uloc_getLanguage`
  validates that the first component is "und". Safe.
- `make_icu_collator` with custom rules (`:557+`) takes
  user-supplied `collicurules` and `ucol_getRules` from the standard
  collator, concatenates as UChar arrays, then `ucol_openRules`. ICU
  does the parsing; an attacker-supplied rule string can't escape
  to native code, but can:
  - Trigger ICU memory allocation up to the rule string size.
  - Trigger ICU error codes (handled via `U_FAILURE` checks).
- **GUC `icu_validation_level`** (declared in pg_locale.c, defaults
  WARNING) controls strictness of attribute warnings.

## Resource cleanup

Multiple comments stress: **"Ensure that no path leaks a UCollator"**
(`:479, :554, :829`). `make_icu_collator` and `pg_ucol_open` are
paranoid about `ucol_close` on every error path.

## Potential issues

- [ISSUE-injection: locale strings supplied to CREATE COLLATION are
  passed nearly verbatim to ICU. ICU itself is the parser; any past
  CVEs in ICU's BCP-47 parser would expose the backend. Mitigation:
  string is only processable by privileged roles (CREATE COLLATION is
  per-schema; depends on schema ACL). (medium)]
- [ISSUE-dos: custom collation rules can be arbitrary length; ICU
  parses them into a UCollator that may consume significant memory
  per backend that uses this collation. No PG-side cap. (low)]
- [ISSUE-info-disclosure: error messages echo user-supplied locale
  strings (`:496, :513, :543`). Accepts; DBA-controlled. (low)]
- [ISSUE-undocumented-invariant: for ICU < 55, `fix_icu_locale_str`
  rewrites `und` → `root`. If a user creates a collation under old
  ICU with "und-..." and the DB is later upgraded to ICU ≥ 55, the
  raw "und-..." string is used unchanged — version-skew with the
  pre-fix path. The stored collversion check at create-time should
  catch this on REFRESH. (low)]

## Cross-references

- `source/src/backend/utils/adt/pg_locale.c` — dispatcher.
- `source/src/backend/commands/collationcmds.c` — CREATE COLLATION
  entry; calls into ICU validation.
- `source/src/include/utils/pg_locale_c.h` — `pg_locale_struct`,
  collate/ctype method tables.
- `<unicode/ucol.h>` (system) — ICU public API.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 8
- `[from-comment]` × 4
- `[inferred]` × 1
