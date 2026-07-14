---
source_url: https://www.postgresql.org/docs/current/fuzzystrmatch.html
fetched_at: 2026-07-14T20:58:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.17 fuzzystrmatch — determine string similarities and distance"
maps_to_skill: [type-cache, fmgr-and-spi]
---

# Docs distilled — fuzzystrmatch (edit-distance + phonetic matching functions)

A pure-SQL-function contrib (no type, no opclass): Levenshtein, Soundex,
Metaphone, Double Metaphone, Daitch-Mokotoff. The companion to `pg_trgm` and
`citext` in a fuzzy-search toolbox — SQL-callable C functions, no indexing of
its own, so a useful `fmgr-and-spi` example of scalar C functions with cost
parameters and early-exit optimizations.

## Non-obvious claims

- **`levenshtein(src, tgt [, ins_cost, del_cost, sub_cost]) → int`** — edit
  distance with per-operation costs (all default 1). **Both strings are capped
  at 255 characters.** [from-docs]
- **`levenshtein_less_equal(src, tgt [, ins,del,sub,] max_d) → int`** is the
  accelerated variant: it **stops early once the distance is known to exceed
  `max_d`**, returning some value `> max_d`. Use it whenever you only care
  "is the distance ≤ k?" — much cheaper than full `levenshtein` for a threshold
  filter. [from-docs]
- **Phonetic functions are effectively ASCII-only.** The docs caution that
  `soundex`, `metaphone`, `dmetaphone`, `dmetaphone_alt` **do not work well with
  multibyte encodings (e.g. UTF-8)**; for such data use `daitch_mokotoff` or
  `levenshtein`. [from-docs]
- **`soundex(text) → text`** = 4-char code; **`difference(a,b) → int`** compares
  the two Soundex codes and returns a 0–4 match score (4 = strongest). [from-docs]
- **`daitch_mokotoff(text) → text[]`** returns an *array* of 6-digit codes —
  multiple entries when a name has several plausible pronunciations (the
  multibyte-safe phonetic option). [from-docs]
- **`metaphone(src, max_output_length int) → text`** truncates to
  `max_output_length` (input capped at 255); `dmetaphone`/`dmetaphone_alt` give
  the primary and alternate "sounds-like" codes with no length limit. [from-docs]
- **No index support of its own** — these are scalar functions. Practical use is
  as a `WHERE` predicate or a `lower()`-style expression; for scale, pre-compute
  the phonetic code into a column and B-tree it, or pair with `pg_trgm`'s
  index-accelerated similarity for candidate generation. [inferred] (the docs do
  *not* document a pg_trgm pairing.)

## Links into corpus

- `[[docs-distilled/pgtrgm.md]]` — the *indexed* fuzzy-search half; fuzzystrmatch
  supplies phonetic/edit-distance scoring, pg_trgm supplies the GIN/GiST
  candidate index. Common pattern: pg_trgm narrows, fuzzystrmatch ranks.
- `[[docs-distilled/citext.md]]` — sibling case-insensitivity tool; both live in
  the "fuzzy text" toolbox.
- `fmgr-and-spi` skill — clean example of SQL-callable C scalar functions with
  optional cost args and a `_less_equal` early-exit fast path (a good template
  for a threshold-bounded distance function).
