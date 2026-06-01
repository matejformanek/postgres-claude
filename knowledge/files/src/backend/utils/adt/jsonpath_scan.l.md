# `src/backend/utils/adt/jsonpath_scan.l`

- **File:** `source/src/backend/utils/adt/jsonpath_scan.l` (749 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Flex lexer for the jsonpath language. Splits a jsonpath C-string into
tokens for `jsonpath_gram.y`, accumulating string/key bodies in a
re-entrant `JsonPathString` buffer (defined in
`jsonpath_internal.h`). Decodes unicode (`\uXXXX`, `\u{XXXX}`) and hex
escapes, recognizes the SQL/JSON keyword set (`true`, `false`, `null`,
`strict`, `lax`, `is`, `unknown`, `to`, `last`, `starts`, `with`,
`like_regex`, item-method names).

## Top of file (verbatim)

```
 * jsonpath_scan.l
 * Lexical parser for jsonpath datatype
 *
 * Splits jsonpath string into tokens represented as JsonPathString structs.
 * Decodes unicode and hex escaped strings.
```
(`:1-14` [from-comment])

## Public surface

- `jsonpath_yylex` (flex-generated; `%option reentrant`).
- `jsonpath_yyalloc` / `_realloc` / `_free` overrides exist for
  reentrancy.
- Internal helpers: `addstring` / `addchar` (`:37-38`) — append into
  `scanstring`; `checkKeyword` (`:39`); `parseUnicode` / `parseHexChar`
  (`:40-41`).

## Key invariants

- **Reentrant lexer.** `%option reentrant` (`:60+`) + per-call
  `jsonpath_yy_extra_type` (`:32-35`) — required because jsonpath
  parsing can occur during planning of a query that itself contains
  nested parsing (`[inferred]`).
- **Fatal-error redirect.** `yy_fatal_error` is suppressed and any
  flex `fprintf(stderr, …)` is rerouted through
  `fprintf_to_ereport` (`:46-52` [verified-by-code]). Without this
  override flex would `exit(1)` inside the backend.
- **Escapes report soft errors.** `parseUnicode` / `parseHexChar`
  take a `struct Node *escontext` so invalid escapes can be
  surfaced via `ereturn` instead of throwing.
- **LCOV exclusion.** `/* LCOV_EXCL_START */` (`:54`) — generated
  scanner code is excluded from coverage; only the hand-written
  helpers count.

## Cross-references

- `source/src/backend/utils/adt/jsonpath_gram.y` — consumer.
- `source/src/backend/utils/adt/jsonpath_internal.h` —
  `JsonPathString`.

## Open questions

- Keyword table is checked post-IDENT match via `checkKeyword`; does
  it support case-insensitive matching for keywords like `LAX`?
  `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 1
- `[from-comment]` × 1
- `[inferred]` × 1
- `[unverified]` × 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
