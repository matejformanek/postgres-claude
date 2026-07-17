---
source_url: https://www.postgresql.org/docs/current/textsearch-controls.html
fetched_at: 2026-07-17T20:55:00Z
anchor_sha: 5174d157a038
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "12.3 Controlling Text Search"
maps_to_skill: [type-cache, gin, jsonpath-and-jsonb]
---

# Docs distilled — textsearch-controls (query parsing + weights + ranking cover-density)

The user-facing control surface over `tsvector`/`tsquery`: the four query-parser
functions (`to_tsquery` family), the A/B/C/D weight system, and the two ranking
functions `ts_rank` (frequency) vs `ts_rank_cd` (cover density). This is where
the FTS *ranking algorithm* — the one genuine piece of backend math in the
chapter — lives, in `src/backend/utils/adt/tsrank.c`.

## Non-obvious claims

- **Four query parsers, differing only in the operator they inject and what
  syntax they honor** [from-docs]:
  - `to_tsquery([cfg,] text)` — the ONLY one that parses `tsquery` operator
    syntax (`&` `|` `!` `<->`), weight labels (`'rat':AB`), and prefix match
    (`'supern':*`). Discards stop words.
  - `plainto_tsquery` — normalizes like `to_tsvector`, joins survivors with
    `&`. Ignores all operators/weights/prefix.
  - `phraseto_tsquery` — like `plainto` but injects `<->` (FOLLOWED BY);
    crucially, **stop words are NOT dropped** — they become `<N>` gap operators
    so phrase distance stays correct. `'The Fat Rats'` → `'fat' <-> 'rat'`.
  - `websearch_to_tsquery` — web-engine syntax (`"quoted"`→phrase, `OR`→`|`,
    `-`→`!`); **never raises a syntax error**, so it is the safe choice for raw
    untrusted user input.
- **Weights are labels A/B/C/D applied to positions, not lexemes** [from-docs];
  `D` is the default and is not displayed. `setweight()` relabels; see
  `[[docs-distilled/textsearch-features.md]]`.
- **Default weight array is `{0.1, 0.2, 0.4, 1.0}`** ordered **{D, C, B, A}** —
  verified in code: `static const float default_weights[NUM_WEIGHTS] =
  {0.1f, 0.2f, 0.4f, 1.0f};` [[tsrank.c:25]]. A caller-supplied `weights float4[]`
  overrides per-slot only where the array value is `>= 0`, else the default is
  substituted: `ws[i] = (arrdata[i] >= 0) ? arrdata[i] : default_weights[i]`
  [[tsrank.c:453]]. [verified-by-code @ 5174d157a038]
- **`ts_rank` vs `ts_rank_cd`** [from-docs + code]:
  - `ts_rank(...)` ranks by weighted **frequency** of matching lexemes —
    `calc_rank` → `calc_rank_and`/`calc_rank_or` [[tsrank.c:381]].
  - `ts_rank_cd(...)` computes **cover density** (Clarke/Cormack/Tudhope 1999):
    it finds the shortest "covers" (extents containing all query terms) and
    scores by their density — `calc_rank_cd` [[tsrank.c:878]], cover search at
    [[tsrank.c:692]]/[[tsrank.c:719]]. **Requires positions**: it silently
    ignores stripped lexemes and returns 0 if the vector has no position data.
  [verified-by-code @ 5174d157a038]
- **The `normalization` argument is a bitmask, applied in listed order**
  [from-docs]; default is `0` = ignore document length, i.e.
  `DEF_NORM_METHOD = RANK_NO_NORM` [[tsrank.c:36]] [verified-by-code]:
  | bit | effect |
  |----|--------|
  | 0 | (default) ignore length |
  | 1 | divide by `1 + ln(length)` |
  | 2 | divide by length |
  | 4 | divide by mean harmonic distance between extents (**ts_rank_cd only**) |
  | 8 | divide by number of unique words |
  | 16 | divide by `1 + ln(unique words)` |
  | 32 | `rank/(rank+1)` — scales into 0..1 |
- **Ranking is I/O-bound and un-indexable** [from-docs]: it must fetch every
  matching document's `tsvector`, so the docs explicitly warn there is no way
  to avoid the cost for high-match queries. Practical pattern: `ORDER BY rank
  DESC LIMIT n` after the `@@` filter has cut the candidate set.
- **`ts_headline([cfg,] document text, query, [opts])`** works on the **original
  document text, not the `tsvector`** — so it re-parses and can be slow; keep it
  off the hot path (apply after LIMIT). Options (string of `opt=val` pairs):
  `MaxWords=35`, `MinWords=15`, `ShortWord=3`, `HighlightAll=false`,
  `MaxFragments=0` (0 = single-best-passage mode; >0 = fragment mode),
  `StartSel=<b>`, `StopSel=</b>`, `FragmentDelimiter=" ... "`. [from-docs]
- **`ts_headline` output is NOT XSS-safe** [from-docs]: with `HighlightAll=false`
  it strips *some* simple XML tags but does not sanitize HTML. Sanitize the
  input document or the output before rendering untrusted text to a web page.

## Links into corpus

- `[[docs-distilled/textsearch-features.md]]` — the `setweight`/`strip`/`||`
  operators that produce the weighted, positional vectors ranking consumes;
  `strip()` is exactly what makes `ts_rank_cd` return 0.
- `[[docs-distilled/textsearch-indexes.md]]` — GIN vs GiST for the `@@` filter
  that ranking runs *after*; note GIN is lossy for phrase (`<->`) queries, so
  ranking/recheck still reads the heap tuple's vector.
- `[[docs-distilled/textsearch-limitations.md]]` — the `MAXENTRYPOS`/position
  ceiling that bounds how far `<->` and cover-density extents can reach.
- `type-cache` skill — `tsvector`/`tsquery` are ordinary varlena types; the
  parser functions are `fmgr` entry points in `tsrank.c`/`tsquery.c`.

## Code-vs-docs / verification notes

- All numeric defaults above (weight array, default norm method, the `>=0`
  override rule) are **code-verified** at anchor `5174d157a038` via
  `raw.githubusercontent.com`. The bitmask semantics and I/O-cost/XSS warnings
  are `[from-docs]` (prose-only, not a single constant).
