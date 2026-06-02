# parser.c

- **Source:** `source/src/backend/parser/parser.c` (527 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Driver for the parser: initialize the flex scanner, prime the bison parser,
run `base_yyparse`, return the `List<RawStmt>` it built. Also hosts the
**lookahead filter** `base_yylex` that bridges flex and bison.

> "the data structures returned by the grammar are 'raw' parsetrees that
> still need to be analyzed by analyze.c and related files." `:7-10`

## Public entry points

| Line | Symbol | Role |
|---|---|---|
| 42 | `raw_parser(const char *str, RawParseMode mode)` | Top-level entry. Initializes scanner + parser, runs `base_yyparse`, returns parsetree. |
| 111 | `base_yylex(YYSTYPE *, YYLTYPE *, yyscanner)` | Token filter — collapses multi-token sequences into single tokens for LALR(1) compatibility |

## RawParseMode

`raw_parser` takes a mode that selects an injected pseudo-start token
(`MODE_TYPE_NAME`, `MODE_PLPGSQL_EXPR`, etc.). This lets PL/pgSQL re-use
the same grammar to parse a bare expression or a type name. `:53-71`

## Lookahead filter

`base_yylex` exists because parts of SQL need >1 token of lookahead but the
grammar must stay LALR(1). The filter recognizes specific 2-token sequences
(`FORMAT JSON`, `NOT BETWEEN`, `NULLS FIRST/LAST`, `WITH TIME ZONE`, …) and
emits replacement tokens. `:90-108`

It also converts `UIDENT` / `USCONST` (Unicode-escaped) sequences into the
plain `IDENT` / `SCONST` tokens once their UESCAPE clause has been read.
`:102-108`

## Why it must live separately from gram.y

Doing the lookahead in flex would re-introduce backtracking (forbidden —
see `scan.l:13-22`); doing it inside gram.y would require duplicating each
ambiguous production. The filter is the third option.

## Related

- `scan.l` / `gram.y` — the actual lexer and grammar.
- `analyze.c` — first consumer of `raw_parser`'s output, via
  `parse_analyze_*`.
- `gramparse.h` — declarations shared between flex and bison sides.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
