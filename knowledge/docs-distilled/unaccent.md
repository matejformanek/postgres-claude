---
source_url: https://www.postgresql.org/docs/current/unaccent.html
fetched_at: 2026-07-15T20:50:00Z
anchor_sha: 8f71f64deee6
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.48 unaccent — a text search dictionary which removes diacritics"
maps_to_skill: [extension-development, collation-provider]
---

# Docs distilled — unaccent (accent-removing *filtering* text-search dictionary)

The reference implementation of a **filtering dictionary** — the one text-search
dictionary shape that does *not* terminate token processing but rewrites the
lexeme and hands it to the next dictionary in the chain. Strips diacritics
(`Hôtel` → `Hotel`) so an accent-insensitive full-text search works, and doubles
as a plain `unaccent(text)` scalar function.

## Non-obvious claims

- **It is a *filtering* dictionary, not a terminal one.** Its output is always
  passed to the next dictionary in the mapping rather than stopping the token;
  in `source/contrib/unaccent/unaccent.c` the lexize builds a two-slot
  `TSLexeme` result (`unaccent.c:425`, `palloc0_array(TSLexeme, 2)`) — the
  rewritten lexeme plus a terminator — which is the filtering-dictionary
  contract (emit a replacement, don't stop). [verified-by-code] It therefore
  **cannot** be used as the normalizing dictionary of a `thesaurus`. [from-docs]
- **`unaccent([dictionary regdictionary,] string text) → text`.** Called with
  one arg it uses the `unaccent` dictionary in the *same schema as the
  function*; the two-arg form names an explicit `regdictionary`. So
  `unaccent('Hôtel')` and `unaccent('unaccent','Hôtel')` are equivalent.
  [from-docs]
- **Rules live in `$SHAREDIR/tsearch_data/unaccent.rules`**, whitespace-separated
  `source target` pairs: one char → one char (`À  A`), one char → many
  (`Æ  AE`), or a **lone source with no target = delete the character**. Quoted
  strings carry specials/spaces (`¼  " 1/4"`). File must be UTF-8; untranslatable
  lines are silently skipped — the parser sets a `skip` flag and continues
  (`unaccent.c:102`, `:118`, reset `:276`, loop `:297`). [verified-by-code]
- **Chained in a config via `ALTER MAPPING … WITH unaccent, french_stem`** —
  unaccent de-accents, then the stemmer normalizes. You `CREATE TEXT SEARCH
  DICTIONARY unaccent (TEMPLATE unaccent)` and can point it at a custom rules
  file with `ALTER … (RULES='my_rules')`. [from-docs]
- **Indexing caveat (implicit).** Because a full-text index stores the *output*
  lexemes, changing the rules file (or the dictionary chain) requires reindexing
  affected `tsvector` columns to stay consistent — the docs show the config
  wiring but do not spell out the reindex obligation. [inferred]
- **Trusted extension** — installable by a non-superuser with `CREATE` on the
  database. [from-docs]

## Links into corpus

- `[[docs-distilled/dict-int.md]]` — the *terminal* dictionary-template sibling;
  dict_int emits-or-stops, unaccent rewrites-and-passes. The two smallest
  complete `ts_lexize` examples, one per dictionary shape.
- `[[docs-distilled/textsearch-dictionaries.md]]` — filtering vs. normal
  dictionaries, the chaining rule this module exercises.
- `[[docs-distilled/fuzzystrmatch.md]]` + `[[docs-distilled/citext.md]]` —
  neighboring "make text comparison tolerant" tools; unaccent is the
  diacritic-folding member.
- `collation-provider` skill — accent-folding overlaps conceptually with
  nondeterministic ICU collations that ignore diacritics; unaccent is the
  index-time (rewrite-the-lexeme) approach vs. the collation (compare-time) one.
