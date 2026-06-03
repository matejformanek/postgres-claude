# src/common/unicode_category.c

## Purpose

Per-codepoint Unicode general-category lookup and the property
predicates / POSIX-style character classifiers built on top.

## Role in PG

Shared **frontend + backend**. Backend's "builtin" provider uses
these for regex character classes, `pg_u_*` functions, and the
identifier-rules table. Backed by generated
`unicode_category_table.h` (range tables) and per-property tables
in the `unicode/` subdir.

## Key functions

- `pg_unicode_category unicode_category(char32_t code)` — the main
  lookup, returns one of the 30 enum values. Backed by a binary
  search into a `pg_category_range[]` table.
  (`unicode_category.c:84-108`)
- Property predicates `pg_u_prop_*` — each is a 5-line wrapper that
  fast-paths ASCII (or returns false) and then calls
  `range_search` against a property-specific range table:
  `pg_u_prop_alphabetic`, `_lowercase`, `_uppercase`, `_cased`,
  `_case_ignorable`, `_white_space`, `_hex_digit`, `_join_control`.
  (`unicode_category.c:110-200`)
- POSIX classifiers `pg_u_is*` — most are 1-2 line wrappers that
  combine a category check with a property check. `pg_u_isdigit`,
  `isalpha`, `isalnum`, `isword`, `isupper`, `islower`, `isblank`,
  `iscntrl`, `isgraph`, `isprint`, `ispunct`, `isspace`, `isxdigit`.
  The `posix` flag (where present) tightens to ASCII-only semantics
  matching POSIX C locale. (`unicode_category.c:210-329`)
- `unicode_category_string` / `_abbrev` — pretty-print the category
  (`PG_U_UPPERCASE_LETTER` → `"Uppercase_Letter"` / `"Lu"`).
  (`unicode_category.c:331-478`)
- `range_search` static — binary search over a sorted
  `pg_unicode_range` table by codepoint, no overlap permitted.
  (`unicode_category.c:481-...`)

## State / globals

Range tables are in `unicode_category_table.h` (generated). No
mutable globals.

## Phase D notes

- **`char32_t` typed, range-bounded by Unicode.** Inputs above
  0x10FFFF would simply fall off the end of all range tables and
  return false / UNASSIGNED. No OOB risk.
- **Generated tables.** The category boundaries come from the
  Unicode UCD via `src/common/unicode/generate-unicode-category-table.pl`.
  A future Unicode release that adds new entries would require
  regenerating, but per UCD stability policy the enum values
  themselves can never change (called out at `unicode_category.h:22-25`).

## Potential issues

None — all functions are pure and bounded.
