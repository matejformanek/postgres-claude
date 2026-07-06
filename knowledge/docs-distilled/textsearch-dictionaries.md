---
source_url: https://www.postgresql.org/docs/current/textsearch-dictionaries.html
fetched_at: 2026-07-06T00:00:00Z
anchor_sha: a8c2547eaac7
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18, §12.6)
primary: false
---

# Docs distilled — §12.6: Full-Text-Search Dictionaries

The dictionary contract (token → lexemes), the template mechanism, the five
built-in templates, and — the non-obvious part — the *dictionary chain*
inside a configuration (first non-NULL wins) and filtering vs terminal
dictionaries.

## The lexize contract (the whole interface)

A dictionary is a function taking one token and returning exactly one of:

- an **array of lexemes** — recognized word(s) (one token may yield several
  normal forms); `[from-docs]`
- an **empty array `{}`** — token is a **stop word**, dropped from
  vector/query (but its *position* is still consumed, affecting ranking);
  `[from-docs]`
- a lexeme flagged **`TSL_FILTER`** — a *filtering* dictionary that rewrites
  the token and hands the result to the *next* dictionary (e.g. `unaccent`);
  `[from-docs]`
- **`NULL`** — token not recognized; pass it to the next dictionary in the
  chain. `[from-docs]`

Test with `ts_lexize('dictname', 'token') → text[]`; whole-pipeline debug
with `ts_debug(config, text)`. `[from-docs]`

## Templates and the catalog trio

- A **template** (`pg_ts_template`) supplies the C `init` + `lexize`
  functions; a **dictionary** (`pg_ts_dict`) is a template + parameters; a
  **configuration** (`pg_ts_config`) maps token types to dictionary lists.
  `CREATE TEXT SEARCH TEMPLATE / DICTIONARY / CONFIGURATION`. `[from-docs]`
- Config/data files (`.stop`, `.syn`, `.ths`, `.dict`, `.affix`) must be
  UTF-8 and live in `$SHAREDIR/tsearch_data/` (`pg_config --sharedir`);
  they're loaded once per session, so an `ALTER TEXT SEARCH DICTIONARY` is
  needed to force a reload. `[from-docs]`

## The five built-in templates

- **simple** (`pg_catalog.simple`) — lowercase + stopword check. `Accept=true`
  (default) → returns the lowercased word or `{}` (terminal, recognizes
  everything); `Accept=false` → returns `NULL` for non-stopwords (acts as a
  stopword filter that passes the rest along). `[from-docs]`
- **synonym** — flat word→synonym replacement from a `.syn` file; trailing
  `*` enables prefix matching (`index*` → `'index':*` marker in the query).
  `[from-docs]`
- **thesaurus** — *phrase*-level replacement (matches the longest phrase,
  ties→last definition); `?` marks a stop-word slot; requires a subdictionary
  to normalize first. **Changing the thesaurus needs a REINDEX** (positions
  bake in). `[from-docs]`
- **ispell** — morphological (`.dict` + `.affix`), handles inflections and
  optional `compoundwords controlled` splitting; normalizes *then* checks
  stopwords. `[from-docs]`
- **snowball** — Porter-family stemmer; recognizes everything, so it is
  **always the terminal dictionary** in a chain. Checks stopwords *first*.
  `[from-docs]`

## The dictionary chain (the load-bearing behavior)

- A configuration maps each token type to an ordered dictionary list:
  `ALTER TEXT SEARCH CONFIGURATION c ADD MAPPING FOR asciiword WITH astrosyn,
  english_ispell, english_stem`. `[from-docs]`
- Execution: consult dictionaries left-to-right; **first non-`NULL` result
  wins** and stops the chain; `{}` = stop-word (discarded); `NULL` = fall
  through. `[from-docs]`
- **Ordering rule of thumb**: narrow/specific dicts first (synonym, domain),
  general (ispell) next, terminal stemmer (snowball/simple) last. A
  **filtering** dict (`TSL_FILTER`) must *not* be last (nothing to hand off
  to). `[from-docs]`

## Links into corpus

- The parser that produces the token types these dicts map from:
  [docs-distilled/textsearch-parsers.md](./textsearch-parsers.md)
- Timely contrib synonym-group example (dict_xsyn):
  [docs-distilled/dict-xsyn.md](./dict-xsyn.md)
- GIN/GiST indexing of the resulting tsvector:
  [docs-distilled/textsearch-indexes.md](./textsearch-indexes.md)
- Relevant skills: `catalog-conventions` (pg_ts_dict/template/config),
  `extension-development` (a template's init/lexize are C functions).
