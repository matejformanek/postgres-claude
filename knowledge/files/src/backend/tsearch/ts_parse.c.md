# `src/backend/tsearch/ts_parse.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~470
- **Source:** `source/src/backend/tsearch/ts_parse.c`

The text-search **driver** that wires together a parser and a config's
dictionary mappings:

- `parsetext(cfgId, *prs, buf, len)` — call the configured parser, then
  for each token (`(type, lexeme)`), walk the dictionary chain from
  `pg_ts_config_map` for that token type until a dict accepts it.
- `hlparsetext` — variant for `ts_headline` (preserves position info
  needed for highlight reconstruction).
- `generateHeadline` — assembles the highlighted snippet around
  matching lexemes using parser fragments.

Caches the configured dictionary list per token type per config in
`tsearch_cache`. [from-comment]
