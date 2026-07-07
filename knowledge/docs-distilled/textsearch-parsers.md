---
source_url: https://www.postgresql.org/docs/current/textsearch-parsers.html
fetched_at: 2026-07-06T00:00:00Z
anchor_sha: a8c2547eaac7
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18, §12.5)
primary: false
---

# Docs distilled — §12.5: Full-Text-Search Parsers

The parser splits raw text into typed tokens **without modifying it** — it
only finds word boundaries and classifies. The token *type* is what a
configuration keys its dictionary mapping on, so the parser sits upstream of
every dictionary decision.

## The default parser and its token types

- One built-in parser: `pg_catalog.default`, recognizing **23 token types**.
  The parser "does not modify the text at all — it simply identifies
  plausible word boundaries." `[from-docs]`
- Token-type families (the alias names, which appear in `ts_debug` /
  `ALTER … MAPPING FOR`):
  - words: `asciiword` (`elephant`), `word` (`mañana`, non-ASCII),
    `numword` (`beta1`, letters+digits); `[from-docs]`
  - hyphenated compounds: `asciihword`/`hword`/`numhword` plus the *parts*
    `hword_asciipart`/`hword_part`/`hword_numpart`; `[from-docs]`
  - URLs/hosts: `protocol`, `url`, `host`, `url_path`; `[from-docs]`
  - `email`, `file` (path), numbers `int`/`uint`/`float`/`sfloat`/`version`;
    `[from-docs]`
  - markup `tag`/`entity`; catch-all `blank` (whitespace / unrecognized
    punctuation). `[from-docs]`
- Letter classification depends on `lc_ctype` (§24.1), so what counts as a
  `word` char is locale-sensitive. `email`/`tag` have restricted char sets
  (email: only `. - _` as non-alnum; tag: ASCII letter/underscore/colon
  start). `[from-docs]`

## Overlapping tokens (why compounds match both ways)

- Hyphenated compounds emit **overlapping** tokens: `foo-bar-beta1` yields
  the whole `numhword` *and* each part (`hword_asciipart: foo`, `…: bar`,
  `hword_numpart: beta1`) — so searches hit either the compound or a
  component. Inspect via `ts_debug('foo-bar-beta1')`. `[from-docs]`

## Custom parser API (four C methods)

- `CREATE TEXT SEARCH PARSER name (START=…, GETTOKEN=…, END=…,
  LEXTYPES=…)`, stored in **`pg_ts_parser`**. `[from-docs]`
- The four required C functions:
  - **start(text, len)** → internal parse state; `[from-docs]`
  - **gettoken(state, &token, &type)** → next token + its type id, 0 at end;
    `[from-docs]`
  - **end(state)** → free state; `[from-docs]`
  - **lextypes(state)** → the array of `{type-id, alias, description}` this
    parser can emit (drives `ts_token_type`). `[from-docs]`
- Inspection SQL: `ts_parse(parser, text)`, `ts_token_type(parser)`,
  `ts_debug(config, text)`. `[from-docs]`

## Links into corpus

- The dictionaries these token types map to:
  [docs-distilled/textsearch-dictionaries.md](./textsearch-dictionaries.md)
- Indexing the resulting tsvector:
  [docs-distilled/textsearch-indexes.md](./textsearch-indexes.md)
- Parser code lives under source/src/backend/tsearch/ (wparser*.c);
  the default parser is `prsd_*` in ts_parse.c.
- Relevant skills: `fmgr-and-spi` (the four callbacks are `internal`-typed C
  functions), `catalog-conventions` (pg_ts_parser).
