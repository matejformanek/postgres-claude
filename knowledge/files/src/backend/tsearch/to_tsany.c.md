# `src/backend/tsearch/to_tsany.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~660
- **Source:** `source/src/backend/tsearch/to_tsany.c`

SQL surface for `to_tsvector(config, text|json|jsonb)` and
`to_tsquery(config, text)` / `phraseto_tsquery` / `websearch_to_tsquery`
/ `plainto_tsquery`. Drives the **parser → dictionary chain →
tsvector** assembly pipeline: tokenize via configured parser
(`pg_ts_config_map`), for each token type walk the configured
dictionary list until one accepts the token, gather resulting lexemes
into a sorted+deduplicated `TSVector` with per-lexeme position arrays.

JSON variants walk only string fields (skipping keys/numbers/booleans
by default — `to_tsvector(jsonb)` has settings to change this).
[from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
