# src/include/common/unicode_category.h

## Purpose

Defines `pg_unicode_category` (the 30 Unicode general categories Lu,
Ll, …) and declares per-codepoint property predicates
(`pg_u_isalpha`, `pg_u_isspace`, etc.) plus the POSIX-flavoured
character class predicates used by regex and the `ctype` builtin
provider.

## Role in PG

Shared **frontend + backend**. The category values are deliberately
numeric-equal to ICU's `UCharCategory` so that swapping between
builtin and ICU providers does not change category semantics.

## Key declarations

- `enum pg_unicode_category` — 30 values (`PG_U_UNASSIGNED=0` …
  `PG_U_FINAL_PUNCTUATION=29`). The header notes the Unicode
  stability policy guarantees no new values will ever be added.
  (`unicode_category.h:28-60`)
- `unicode_category(char32_t)`, `unicode_category_string()`,
  `unicode_category_abbrev()` — lookup and pretty-printers.
  (`unicode_category.h:62-64`)
- Property predicates (`pg_u_prop_*`) — alphabetic, lowercase,
  uppercase, cased, case_ignorable, white_space, hex_digit,
  join_control. (`unicode_category.h:66-73`)
- POSIX classifiers (`pg_u_is*`) — isdigit/isalpha/isalnum/isword/
  isupper/islower/isblank/iscntrl/isgraph/isprint/ispunct/isspace/
  isxdigit. Several take a `bool posix` flag distinguishing
  POSIX-bracket semantics from the looser Unicode interpretation.
  (`unicode_category.h:75-87`)

## Phase D notes

`char32_t` is the codepoint type — these predicates do NOT take
bytes, so misuse from a multi-byte-encoded buffer would just look
like wrong-category results, not OOB. Conversion to codepoint is the
caller's responsibility (typically `utf8_to_unicode`).

## Potential issues

None at the header level.
