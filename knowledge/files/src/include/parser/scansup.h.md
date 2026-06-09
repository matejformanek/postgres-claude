# src/include/parser/scansup.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 27 [verified-by-code]

## Role

Scanner support — identifier downcasing/truncation and an
`isspace` variant tuned for the scanner. These are the
catalog-facing identifier-normalization choices.

## Public API

- `downcase_truncate_identifier(const char *ident, int len, bool
  warn) -> char *` (`:17-18`) — combo: downcase + truncate to
  NAMEDATALEN-1.
- `downcase_identifier(const char *ident, int len, bool warn,
  bool truncate) -> char *` (`:20-21`) — downcase, optional
  truncate.
- `truncate_identifier(char *ident, int len, bool warn)`
  (`:23`) — in-place truncate.
- `scanner_isspace(char ch) -> bool` (`:25`).

## Invariants

- INV-NAMEDATALEN: max identifier length is `NAMEDATALEN - 1 =
  63` (default build). Anything longer is truncated; with
  `warn=true` a NOTICE is emitted ("identifier "..." will be
  truncated to ...").
- INV-DOWNCASE-LOCALE: ASCII downcasing only (not locale-aware,
  not Unicode-case-folding). Identifier like "Müller" lower-
  cases to "müller" by toupper-with-ASCII-tolower, NOT by
  locale rules. Quoted identifiers ("Müller") are never
  downcased.
- INV-TRUNCATE-BYTE-NOT-CHAR: truncation is by BYTE, so a
  multibyte identifier may be truncated mid-character; the
  scanner subsequently validates encoding, possibly producing
  garbled output. NAMEDATALEN was sized assuming UTF-8 ~16
  chars worst case.
- INV-SCANNER-ISSPACE-SUBSET: `scanner_isspace` is NOT
  `<ctype.h>` isspace; matches only ' ', '\t', '\n', '\r',
  '\f' to avoid locale-dependent behavior in the scanner.

## Notable internals

- `downcase_*` palloc's a fresh buffer; caller frees (or lets
  context cleanup do it).
- `truncate_identifier` mutates in place; pass a writable copy.

## Trust boundary / Phase D surface

- **A11 / A13 / A14 name-truncation cluster echo.** Quoted
  identifier `"a_very_long_role_name_that_exceeds_63_chars"`
  truncates to the first 63 bytes. If an admin creates
  role `"victim_admin_role_with_long_descriptive_name_abc"`
  and an attacker creates `"victim_admin_role_with_long_descriptive_name_xyz"`,
  both downcase-truncate to the same 63-byte prefix → role
  resolution collision. This is the documented "identifier
  truncation" class of bugs.
- **Catalog name collisions.** `pg_class.relname`,
  `pg_authid.rolname`, `pg_namespace.nspname` are all 64-byte
  `name` type. Truncation here mirrors catalog limits — so
  the collision is REAL (catalog stores the truncated value)
  not just a parse-time confusion.
- **Defense: quoting required for case retention.** Bare
  identifiers get ASCII-downcased; quoted identifiers don't.
  Mixed-case role/table names work only when always quoted.
- **scanner_isspace subset is a DOS defense** (low impact) —
  prevents weird whitespace via UTF-8 NBSP from confusing
  token boundaries.

## Cross-references

- `parser/scanner.h` — wraps these in the flex scanner.
- `parser/scan.l` — direct caller.
- `catalog/namespace.h` — name resolution at relation lookup.
- `utils/snapmgr.h`, `catalog/pg_authid.h` — name columns
  are `name` type, size NAMEDATALEN.
- A11 / A13 phase-D notes on identifier-truncation collisions.

## Issues / drift

- `[ISSUE-TRUST: A11/A13/A14 cluster — identifier truncation by BYTE not CHAR allows multibyte boundary collisions; catalog-level (medium)] — source/src/include/parser/scansup.h:17-23`
- `[ISSUE-DOC: header has zero comments — invariants are folk knowledge (medium)] — source/src/include/parser/scansup.h:1-27`
- `[ISSUE-TRUST: scanner_isspace defends a narrow attack but undocumented as a security choice; reads as a perf optimization (low)] — source/src/include/parser/scansup.h:25`
