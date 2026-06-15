---
path: src/test/modules/test_parser/test_parser.c
anchor_sha: e18b0cb7344
loc: 127
depth: read
---

# src/test/modules/test_parser/test_parser.c

## Purpose

Sample **text-search parser** for the FTS extensibility API. Splits input
text into two lexeme types: `word` (lexid 3) and `blank` (lexid 12),
mirroring the default word parser's IDs so the default headline function
can be reused. The four SQL-callable functions implement the standard
parser interface (`prsstart` / `prstoken` / `prsend` / `lextype`).
`[verified-by-code]` `test_parser.c:108-127`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `testprs_start(internal, int4)` | `:47` | Returns parser state; allocates `ParserState` |
| `testprs_getlexeme(internal, internal, internal)` | `:59` | Returns next lexeme's type/lexid |
| `testprs_end(internal)` | `:99` | Frees parser state |
| `testprs_lextype(internal)` | `:108` | Returns the `LexDescr[]` describing supported lex types |

## Internal landmarks

- `ParserState` (`:24-29`) — owns the input buffer pointer (not a copy), its
  length, and the parser cursor.
- `testprs_getlexeme` (`:59`) — toggles between "swallow spaces" and
  "swallow non-spaces" branches based on the first character at `pst->pos`;
  returns `type=0` on EOF (`:91-93`).

## Invariants & gotchas

- TEST MODULE — installed by the `test_parser` extension's SQL script to
  register a parser via `CREATE TEXT SEARCH PARSER`. Not for production.
- Lexids `3` (word) and `12` (blank) are deliberately shared with the
  default parser so the standard headline function works `[from-comment]`
  `:110-113`.
- `buffer` is a borrowed pointer into the caller's text — `testprs_start`
  stores `PG_GETARG_POINTER(0)` directly, no copy.

## Cross-refs

- `knowledge/subsystems/parser-and-nodes.md` — FTS parser registration ties
  into the text-search dictionary subsystem.
- `source/src/include/tsearch/ts_public.h` — `LexDescr` and the FTS parser
  function signatures.
