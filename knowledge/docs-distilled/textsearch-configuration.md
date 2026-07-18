---
source_url: https://www.postgresql.org/docs/current/textsearch-configuration.html
fetched_at: 2026-07-17T20:59:00Z
anchor_sha: 5174d157a038
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "12.7 Configuration Example"
maps_to_skill: [catalog-conventions, gucs-config, type-cache]
---

# Docs distilled — textsearch-configuration (assembling a config: pg_ts_config_map DDL)

How a text-search *configuration* is built out of a parser plus per-token-type
**dictionary chains**. This is the catalog-DDL layer (`pg_ts_config` +
`pg_ts_config_map`) that `[[docs-distilled/textsearch-debugging.md]]`'s
`ts_debug` reads back — completing the "how the pipeline is wired" story.

## Non-obvious claims

- **A configuration is best created by COPY, then edited** [from-docs]:
  `CREATE TEXT SEARCH CONFIGURATION public.pg ( COPY = pg_catalog.english );`
  duplicates every token-type→dictionary mapping of the source config, so you
  only adjust the deltas rather than map all ~23 token types from scratch.
- **The `WITH` list is an ordered dictionary CHAIN per token type** [from-docs]:
  `ALTER TEXT SEARCH CONFIGURATION pg ALTER MAPPING FOR asciiword, word, hword,
  ... WITH pg_dict, english_ispell, english_stem;` runs each token of those
  types through `pg_dict` → `english_ispell` → `english_stem` in order. The
  **first dictionary that returns a non-`NULL` result wins** and stops the
  chain — this is exactly the `ts_lexize` `NULL`-vs-`{}` contract from
  `[[docs-distilled/textsearch-debugging.md]]`: `NULL` = pass to next, `{}` =
  consume as stop word (chain stops, lexeme dropped).
- **Chain design idiom: specific → general** [inferred from example]: put a
  synonym/thesaurus dictionary first (narrow, mostly passes through), an Ispell
  morphological dictionary next, and the Snowball stemmer (`english_stem`) last
  as the catch-all — the stemmer never returns `NULL`, so it must be terminal.
- **`ALTER MAPPING REPLACE old WITH new`** swaps a dictionary in place across
  the token types that used it; **`DROP MAPPING FOR email, url, sfloat, ...`**
  makes those token types produce no lexemes at all (they are then neither
  indexed nor searchable). [from-docs]
- **Dictionaries are catalog objects created independently** [from-docs] via
  `CREATE TEXT SEARCH DICTIONARY name (TEMPLATE = synonym|ispell|snowball|...,
  <template-params>)` before they can be named in a mapping — e.g.
  `TEMPLATE = synonym, SYNONYMS = pg_dict` or `TEMPLATE = ispell, DictFile=...,
  AffFile=..., StopWords=...`.
- **Active config selection is a GUC** [from-docs]: `to_tsvector`/`to_tsquery`
  without an explicit `regconfig` argument use `default_text_search_config`
  (settable in `postgresql.conf` or per-session `SET`). The C-level resolver is
  `get_current_ts_config()`, which is exactly what the one-arg `ts_debug`
  overload calls (see `[[docs-distilled/textsearch-debugging.md]]`,
  `system_functions.sql:356`). [from-docs + cross-verified]
- **Two catalogs back all of this** [from-docs]: `pg_ts_config` (the config
  row: name, namespace, parser) and `pg_ts_config_map` (one row per
  (config, token-type, sequence-position) → dictionary — the chain, materialized
  as ordered rows). `\dF` in psql renders them.

## Links into corpus

- `[[docs-distilled/textsearch-debugging.md]]` — `ts_debug` prints the
  `pg_ts_config_map` chain per token; this doc is how that chain got there.
- `[[docs-distilled/textsearch-parsers.md]]` — the parser (fixed at config
  creation) supplies the token types the `ALTER MAPPING FOR ...` list names.
- `[[docs-distilled/textsearch-dictionaries.md]]` — the dictionary templates
  (`synonym`/`ispell`/`snowball`/`thesaurus`) named in the `WITH` chain.
- `catalog-conventions` skill — `pg_ts_config` / `pg_ts_config_map` /
  `pg_ts_dict` / `pg_ts_parser` are the FTS catalog family; the config-map is an
  ordered many-rows-per-config table (sequence column orders the chain).
- `gucs-config` skill — `default_text_search_config` is the `PGC_USERSET` string
  GUC that selects the config; `get_current_ts_config()` is its C resolver.

## Code-vs-docs / verification notes

- The DDL and chain semantics are `[from-docs]`; the `get_current_ts_config()`
  linkage to the one-arg `ts_debug` overload is cross-verified against
  `system_functions.sql:356` at anchor `5174d157a038` (see textsearch-debugging).
  No new numeric constants introduced.
