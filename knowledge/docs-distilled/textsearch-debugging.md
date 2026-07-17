---
source_url: https://www.postgresql.org/docs/current/textsearch-debugging.html
fetched_at: 2026-07-17T20:57:00Z
anchor_sha: 5174d157a038
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "12.8 Testing and Debugging Text Search"
maps_to_skill: [type-cache, catalog-conventions, fmgr-and-spi]
---

# Docs distilled — textsearch-debugging (ts_debug / ts_lexize / ts_parse / ts_token_type)

The four introspection functions that expose each stage of the FTS pipeline
independently: the parser (`ts_parse`, `ts_token_type`), a single dictionary
(`ts_lexize`), and the whole config end-to-end (`ts_debug`). Useful precisely
because they let you diagnose *which* stage dropped or mangled a lexeme.

## Non-obvious claims

- **`ts_debug` is a SQL-language function, not C** [verified-by-code] — defined
  in `system_functions.sql`: `CREATE OR REPLACE FUNCTION ts_debug(config
  regconfig, document text, OUT alias, OUT description, OUT token, OUT
  dictionaries regdictionary[], OUT dictionary regdictionary, OUT lexemes
  text[])` [[system_functions.sql:315]], with a one-arg wrapper that defaults to
  `get_current_ts_config()` [[system_functions.sql:356]]. It joins the parser
  output against `pg_ts_config_map` to show the configured dictionary chain per
  token type — so it is the readable reference for how a config is wired.
  [verified-by-code @ 5174d157a038]
- **`ts_debug` return columns** [from-docs], one row per parser token:
  `alias` (token-type short name, e.g. `asciiword`), `description` (human text,
  e.g. "Word, all ASCII"), `token` (raw text), `dictionaries` (the whole chain
  configured for this token type), `dictionary` (the one that actually matched,
  `NULL` if none), `lexemes` (result: `{lexeme}` normal, **`{}` = recognized
  stop word**, **`NULL` = no dictionary matched**).
- **`ts_lexize(dict regdictionary, token text) → text[]`** has a three-way
  return that mirrors `ts_debug.lexemes` [from-docs]:
  `{star}` = normalized, `{}` = stop word, `NULL` = unrecognized. This
  tri-state (`NULL` vs empty array) is the load-bearing distinction — a
  dictionary returning `{}` *consumed* the token (chain stops); returning `NULL`
  *passed* it to the next dictionary in the chain.
- **`ts_lexize` does NOT tokenize** [from-docs]: it takes exactly one token, so
  it cannot test multi-word thesaurus/phrase entries —
  `ts_lexize('thesaurus_astro', 'supernovae stars')` returns `NULL` because it
  treats the whole string as one token. Use `plainto_tsquery`/`to_tsvector`
  (which run the parser first) to exercise phrase dictionaries.
- **`ts_parse(parser, document) → (tokid int, token text)`** shows the raw
  parser output *before* any dictionary runs — one row per token, `tokid` the
  parser's numeric type. Accepts the parser by name or OID. [from-docs]
- **`ts_token_type(parser) → (tokid int, alias text, description text)`** is the
  parser's static catalog of token types it can emit (`asciiword`=1, `word`=2,
  `numword`=3, `email`=4, `url`=5, `blank`=12, `tag`=13, `uint`=22, ...). The
  `tokid` values here are what `ts_parse` labels tokens with, and the `alias`
  values are what `pg_ts_config_map` keys the dictionary chain on. [from-docs]
- **Pipeline mental model** [inferred from the four signatures]:
  `ts_parse` (text→tokens) → per-token dictionary chain from `pg_ts_config_map`,
  each tested by `ts_lexize` → assembled lexemes = `to_tsvector`; `ts_debug`
  runs the whole thing and prints the intermediate state at each token.

## Links into corpus

- `[[docs-distilled/textsearch-parsers.md]]` — `ts_parse`/`ts_token_type` are
  the SQL windows onto the parser API documented there (the token-type IDs are
  the parser's `lextype` output).
- `[[docs-distilled/textsearch-dictionaries.md]]` — `ts_lexize` is the direct
  test harness for the `lexize` dictionary method; the `{}` vs `NULL` return is
  the stop-word-vs-passthrough contract of that method.
- `[[docs-distilled/dict-int.md]]` / `[[docs-distilled/unaccent.md]]` — the two
  smallest complete `ts_lexize`-testable dictionaries (terminal emit vs
  filtering passthrough).
- `catalog-conventions` skill — `ts_debug` reads `pg_ts_config` /
  `pg_ts_config_map` / `pg_ts_dict` / `pg_ts_parser`; `regconfig`/`regdictionary`
  are the OID-alias input types.

## Code-vs-docs / verification notes

- `ts_debug` being SQL-defined (both overloads) is **code-verified** at
  `5174d157a038` (`system_functions.sql:315`/`:356`). The column/return
  semantics and token-type table are `[from-docs]`; the pipeline synthesis is
  `[inferred]`.
