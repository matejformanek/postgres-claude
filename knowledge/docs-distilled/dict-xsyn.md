---
source_url: https://www.postgresql.org/docs/current/dict-xsyn.html
fetched_at: 2026-07-06T00:00:00Z
anchor_sha: a8c2547eaac7
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18, contrib Appendix F)
primary: false
---

# Docs distilled — contrib `dict_xsyn`: Extended Synonym Dictionary

The canonical **worked example** of a filtering/terminal dictionary
template: given a word, emit its whole synonym group so any member matches
any other. Unlike the built-in `synonym` dictionary (flat 1→1 rename),
`dict_xsyn` maps to a *group* and exposes four independent boolean knobs for
what it matches on vs what it emits. Timely: its `dxsyn_lexize` was recently
simplified upstream.

## What it does

- Rules file (`.rules`, in `$SHAREDIR/tsearch_data/`): one synonym group per
  line — the first token is the master word, the rest are synonyms; `#`
  starts a comment. `[from-docs]`
- On a token match it can return the master and/or the synonyms, so a search
  for any group member finds documents indexed under any other. `[from-docs]`

## The four knobs (match side vs emit side)

- **`matchorig`** (default `true`) — dictionary *accepts* the original/master
  word; `[from-docs]`
- **`matchsynonyms`** (default `false`) — dictionary *accepts* the synonyms
  too (so `ts_lexize('xsyn','syn1')` fires); `[from-docs]`
- **`keeporig`** (default `true`) — include the original word in the output;
  `[from-docs]`
- **`keepsynonyms`** (default `true`) — include the synonyms in the output;
  `[from-docs]`
- **`rules`** — base name of the `.rules` file. `[from-docs]`

Verified in code: the option struct carries `matchorig`/`keeporig` (and the
synonym twins), defaulting true/true, parsed by name in the dictionary init;
the SQL entry point is `dxsyn_lexize`. `[verified-by-code]`
source/contrib/dict_xsyn/dict_xsyn.c:40-41 (`bool matchorig; bool keeporig;`),
:48 (`PG_FUNCTION_INFO_V1(dxsyn_lexize)`), :156-157 (defaults true),
:165-169 (option-name parse loop, `defGetBoolean`).

## Behavior examples

```sql
ALTER TEXT SEARCH DICTIONARY xsyn (RULES='my_rules', KEEPORIG=false);
SELECT ts_lexize('xsyn', 'word');    -- {syn1,syn2,syn3}   (master dropped)
-- KEEPORIG=true:                      {word,syn1,syn2,syn3}
-- MATCHSYNONYMS=true, lexize 'syn1':  {syn1,syn2,syn3}
```

Wire it into a config the same way as any dictionary, ahead of the stemmer:
`ALTER TEXT SEARCH CONFIGURATION english ALTER MAPPING FOR word, asciiword
WITH xsyn, english_stem;` `[from-docs]`

## vs the built-in `synonym` dictionary

- built-in `synonym` = flat single-replacement from a `.syn` file;
  `dict_xsyn` = group expansion with match/emit control — the contrib
  example that shows the template API surface (`init` parses the options,
  `lexize` = `dxsyn_lexize`). `[from-docs]` `[inferred]`

## Links into corpus

- Dictionary contract + chain this plugs into:
  [docs-distilled/textsearch-dictionaries.md](./textsearch-dictionaries.md)
- Other contrib text-search dicts follow the same template shape
  (dict_int, unaccent); source under source/contrib/dict_xsyn/.
- Relevant skills: `extension-development` (contrib module layout,
  template init/lexize C functions), `catalog-conventions` (pg_ts_template).
