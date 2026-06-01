# `src/backend/utils/adt/jsonpath_gram.y`

- **File:** `source/src/backend/utils/adt/jsonpath_gram.y` (717 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Bison grammar for the jsonpath language. Transforms the token stream
produced by `jsonpath_scan.l` into a `JsonPathParseItem` tree, which
`flattenJsonPathParseItem` (in `jsonpath.c`) then serializes into the
on-disk binary form. Exported entry is `jsonpath_yyparse`, wrapped by
`parsejsonpath` (declared `jsonpath.h:286`).

## Top of file (verbatim)

```
 * jsonpath_gram.y
 *   Grammar definitions for jsonpath datatype
 *
 * Transforms tokenized jsonpath into tree of JsonPathParseItem structs.
```
(`:1-13` [from-comment])

## Public surface

- `jsonpath_yyparse` (bison-generated; pure-parser, name-prefix
  `jsonpath_yy`, `:60`).
- `parsejsonpath(str, len, escontext)` (declared in `jsonpath.h:286`,
  defined in this file via the `yyparse` driver).

## Key invariants

- **palloc, not malloc.** `YYMALLOC = palloc`, `YYFREE = pfree`
  (`:51-52` [from-comment]) — bison allocations participate in
  PG memory contexts so parse errors via `ereport` don't leak.
- **Pure (re-entrant) parser.** `%pure-parser` (`:60`) — needed
  because jsonpath parsing can occur during query planning and must
  not share global state.
- **`%expect 0`** — grammar must be conflict-free; any shift/reduce
  is a build failure (`:61` [verified-by-code]).
- **Soft errors via escontext.** `makeItemLikeRegex` accepts a
  `Node *escontext` so a bad regex flag returns false and reports a
  soft error rather than ereport-ing (`:42-46` [verified-by-code]).

## Functions of note (constructors)

All produce `JsonPathParseItem *` and are called from grammar
actions:

- `makeItemType` (`:27`), `makeItemString` (`:28`),
  `makeItemVariable` (`:29`), `makeItemKey` (`:30`),
  `makeItemNumeric` (`:31`), `makeItemBool` (`:32`).
- `makeItemBinary` / `makeItemUnary` (`:33, 36`) — wrap two-arg /
  one-arg operators.
- `makeItemList` (`:38`) — chains items via the `next` field for
  path chains like `$.a[*].b`.
- `makeIndexArray` (`:39`) / `makeAny` (`:40`) — array subscript
  list and `.**{n,m}` window.
- `makeItemLikeRegex` (`:41`) — also validates and converts XQuery
  flag string to internal bits via `jspConvertRegexFlags`.

## Cross-references

- `source/src/backend/utils/adt/jsonpath_scan.l` — lexer producing
  `jsonpath_yy` tokens.
- `source/src/backend/utils/adt/jsonpath_internal.h` — token names
  and `JsonPathString` shared between scanner and grammar.
- `source/src/backend/utils/adt/jsonpath.c` — flattener consumes the
  tree this produces.

## Open questions

- Generated `jsonpath_gram.c` / `.h` are produced into the build
  dir; line numbers cited here will not match generated artifacts.
  `[inferred]`

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 2
- `[inferred]` × 1
