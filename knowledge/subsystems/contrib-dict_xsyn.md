# contrib-dict_xsyn (extended-synonyms text-search dictionary)

- **Source path:** `source/contrib/dict_xsyn/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `dict_xsyn.control`)
- **Trusted:** no

## 1. Purpose

A text-search dictionary template that performs **extended
synonym processing** — replaces a word with a list of
related words at index/query time. Similar to the built-in
`synonym` template but with **flexible matching strategies**:
match by either side, by both, by prefix, etc.

The classic use case: a search corpus where users type
abbreviations (`pg` → `postgresql`) or vendor terms
(`pg` → `postgres`, `psql`, `postgresql`). Extended synonyms
let the dictionary do the expansion automatically.

## 2. Single 264-LOC file

```
source/contrib/dict_xsyn/dict_xsyn.c    264 LOC
```

[verified-by-code `wc -l`]

A reference implementation of a text-search dictionary
similar in shape to `dict_int.md`, but with richer matching
options.

## 3. The init + lexize callbacks

Same protocol as every text-search dictionary template:

- **`init(text[])`** — parse options, return state pointer.
- **`lexize(state, token, len, ...)`** — process a token,
  return synonyms (or pass to next dict).

(Same pattern documented in `contrib-dict_int.md`.)

## 4. The 4 matching options

`dict_xsyn` reads a **synonym file** (one rule per line)
and matches against tokens using configurable strategies:

| Option | Effect |
|---|---|
| `matchorig = true/false` | Match the original input word |
| `keeporig = true/false` | Include the original in output |
| `matchsynonyms = true/false` | Match any synonym (not just orig) |
| `keepsynonyms = true/false` | Include all synonyms in output |

Combined, these give 16 behavior combinations. The common
case: `matchorig=true, keepsynonyms=true` ("when you see X,
also produce all its synonyms").

## 5. The synonym file format

```
postgres postgresql pg psql
gimp imageeditor
firefox browser webbrowser
```

Each line: a "headword" followed by space-separated
synonyms. The headword is matched on; output includes the
headword + synonyms based on the keep* options.

Files live in `$PGDATA/share/tsearch_data/`. Configurable
via the `rules` option at dictionary CREATE time.

## 6. Configuration

```sql
CREATE TEXT SEARCH DICTIONARY my_xsyn (
    TEMPLATE = pg_catalog.xsyn_template,
    matchorig = true,
    keeporig = false,
    matchsynonyms = false,
    keepsynonyms = true,
    rules = 'my_synonyms'      -- file in share/tsearch_data/my_synonyms.rules
);
```

## 7. The asymmetric-vs-symmetric distinction

Compared to the built-in `synonym` template (which substitutes
1-to-1: every occurrence of word A becomes word B), `dict_xsyn`
does **expansion** (A → A + B + C + D). Useful for
"find documents containing any of these related terms"
patterns.

Useful where:
- Vendor names have multiple spellings.
- Languages have related-but-distinct forms.
- Acronyms are common.

## 8. The "do these get lemmatized too?" question

`dict_xsyn` operates on **raw tokens**, before stemming.
Place it earlier in the dictionary chain than `snowball` to
expand before stemming reduces words to roots.

Typical text-search config:

```sql
ALTER TEXT SEARCH CONFIGURATION my_config
    ALTER MAPPING FOR english_word
    WITH my_xsyn, english_stem;
```

Words first hit my_xsyn (synonym expansion); whatever
my_xsyn produces gets stemmed by english_stem.

## 9. Production-use guidance

- **For curated synonym lists**, dict_xsyn is the right
  tool.
- **For thesaurus-style multi-word phrases**, use the
  built-in `thesaurus` template instead (handles phrases
  natively).
- **For ML-derived semantic similarity**, the
  thesaurus + custom-trained classifier approach is
  beyond contrib; consider a dedicated vector-DB
  extension (pgvector).
- **Synonym file changes** require dictionary recreation
  via DROP + CREATE; or invalidate via init re-execution.

## 10. Invariants

- **[INV-1]** Operates on raw tokens before stemming.
- **[INV-2]** Output may include the original + synonyms
  depending on keep* options.
- **[INV-3]** Returning NULL passes the token to the next
  dictionary.
- **[INV-4]** Rules file in `share/tsearch_data/`.

## 11. Useful greps

- The matching options:
  `grep -n 'matchorig\|matchsynonyms\|keeporig\|keepsynonyms' source/contrib/dict_xsyn/dict_xsyn.c`
- The file-loading code:
  `grep -n 'read_dictionary\|t_readline' source/contrib/dict_xsyn/dict_xsyn.c | head -5`
- The lexize entry:
  `grep -n 'dxsyn_lexize\|dxsyn_init' source/contrib/dict_xsyn/dict_xsyn.c`

## 12. Cross-references

- `knowledge/subsystems/contrib-dict_int.md` — sister
  reference impl; simpler logic.
- `knowledge/subsystems/contrib-pg_trgm.md` — companion
  text-similarity (different algorithm).
- `.claude/skills/fmgr-and-spi/SKILL.md` — SQL-callable C
  patterns.
- `source/contrib/dict_xsyn/dict_xsyn.c` — 264-LOC
  implementation.
- `source/src/backend/tsearch/` — the TS subsystem.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/dict_xsyn/dict_xsyn.c`](../files/contrib/dict_xsyn/dict_xsyn.c.md) |

<!-- /files-owned:auto -->
