# `src/backend/tsearch/wparser.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~440
- **Source:** `source/src/backend/tsearch/wparser.c`

SQL-level glue for text-search parsers (`pg_ts_parser` catalog rows).
Exports `ts_parse(parser_name, text)`, `ts_token_type(parser_name)`,
`ts_headline(...)` adapters. Looks up the parser's start/getlexeme/end
function pointers via `pg_ts_parser`, calls them in sequence: `start
→ repeated getlexeme → end`, yielding (token_type, lexeme) tuples.
[from-comment]
