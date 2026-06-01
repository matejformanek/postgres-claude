# gramparse.h

- **Source:** `source/src/backend/parser/gramparse.h` (75 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Private shared definitions for the raw-parser core (flex + bison). The
header explicitly restricts its audience:

> "NOTE: this file is only meant to be included in the core parsing files,
> i.e., parser.c, gram.y, and scan.l. Definitions that are needed
> outside the core parser should be in parser.h." [from-comment] `:6-9`

That's why it lives in `src/backend/parser/`, not in `src/include/parser/`.

## Contents

- `base_yy_extra_type` `:35-56` — the per-parse scratch struct flex stores
  via `yyextra`. Holds the core scanner state, the one-token lookahead
  used by `base_yylex`, and the final `parsetree` list.
- `pg_yyget_extra` macro `:64` — fast path that exploits flex's guarantee
  that `yyextra` is the first field, avoiding the slower `yyget_extra()`
  call.
- Prototypes: `base_yylex` (from `parser.c`), `parser_init` and
  `base_yyparse` (from `gram.y`).

## Note

Includes `gram.h` (generated from `gram.y`) AFTER `scanner.h`, because
`scanner.h` provides `YYLTYPE`. `:26-29`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
