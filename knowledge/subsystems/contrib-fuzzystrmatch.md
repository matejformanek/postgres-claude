# contrib-fuzzystrmatch (Levenshtein + Soundex + Metaphone + Daitch-Mokotoff)

- **Source path:** `source/contrib/fuzzystrmatch/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `fuzzystrmatch.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

Algorithmic string-similarity functions for the common
fuzzy-match toolkit: edit distance (Levenshtein), phonetic
hashing (Soundex, Metaphone, Daitch-Mokotoff), and helpers
for proper-noun matching. Unindexed in the contrib form —
typically combined with pg_trgm or a CHECK-pre-filter for
production performance.

## 2. The 3 C files

| File | LOC | What it provides |
|---|---|---|
| `fuzzystrmatch.c` | 805 | Levenshtein, Soundex, Metaphone |
| `dmetaphone.c` | 1443 | Double Metaphone |
| `daitch_mokotoff.c` | 571 | Daitch-Mokotoff Soundex (German + Slavic names) |

[verified-by-code `wc -l source/contrib/fuzzystrmatch/*.c`]

## 3. SQL surface

| Function | Returns |
|---|---|
| `levenshtein(source, target)` | Edit distance (int) |
| `levenshtein(source, target, ins_cost, del_cost, sub_cost)` | Weighted edit distance |
| `levenshtein_less_equal(source, target, max)` | Faster when only "less than N edits" matters |
| `soundex(text)` | 4-char Soundex code |
| `difference(a, b)` | 0..4 Soundex-similarity score |
| `metaphone(text, max_len)` | English-phoneme encoding |
| `dmetaphone(text)` | Double Metaphone — primary code |
| `dmetaphone_alt(text)` | Double Metaphone — alternate code |
| `daitch_mokotoff(text)` | Daitch-Mokotoff Soundex array |

[verified-by-code `fuzzystrmatch.c`: PG_FUNCTION_INFO_V1 entries]

## 4. Levenshtein details

Standard dynamic-programming O(M×N) algorithm. The
weighted variant lets you charge different costs for
insertions, deletions, and substitutions — useful when
matching against a stable index where insertions are more
expensive than substitutions.

`levenshtein_less_equal(a, b, max)` is the early-exit
optimization: as soon as the partial DP table exceeds the
max threshold, return `max + 1` without finishing. Useful
when you only care whether the strings are "close enough" —
not the exact distance.

## 5. Soundex (English)

[verified-by-code `fuzzystrmatch.c:55-68`]

A 4-character phonetic code:

```
soundex('Smith')  = 'S530'
soundex('Smyth')  = 'S530'   -- match
soundex('Schmidt') = 'S530'  -- match
```

Based on the 1918 Russell Soundex algorithm. Mostly useful
for English surnames; fails on:
- Non-English names (Schwartz, Müller, Чехов).
- Names with silent letters.
- Same name in different spellings (Catherine vs Katherine =
  C365 vs K365 — no match).

## 6. Metaphone (improved English)

[verified-by-code `fuzzystrmatch.c:84-114`]

```
metaphone('Smith', 6) = 'SM0'   -- '0' = TH phoneme
metaphone('Smyth', 6) = 'SM0'
```

More phonetically-accurate than Soundex for English. Handles
"Knight" → "NT" (silent K), "Catherine"/"Katherine" → "K0RN"
(both match). Variable-length output (max set by 2nd
argument).

## 7. Double Metaphone (modern; international)

[`dmetaphone.c` — 1443 LOC, the largest file]

Returns TWO codes per word — primary + alternate. Designed
for slavic / spanish / italian / english surnames. The
"Smith" vs "Schmidt" case:

```
dmetaphone('Smith')     = 'SM0'
dmetaphone_alt('Smith') = 'XMT'
dmetaphone('Schmidt')   = 'XMT'   -- matches the alt!
```

Use both codes for matching: any-of-two = either form of
either name. Trade-off: more false positives, fewer false
negatives.

## 8. Daitch-Mokotoff Soundex

[`daitch_mokotoff.c` — 571 LOC]

The 1985 Jewish-genealogical Soundex — handles Germanic and
Slavic surnames much better than English Soundex. Returns
an **array** of codes (because some names have multiple
valid phonetic interpretations):

```
daitch_mokotoff('Müller') = ['658000']
daitch_mokotoff('Schmidt') = ['463000']
daitch_mokotoff('Mueller') = ['658000', '650000']
```

Match on any-element-overlap.

## 9. Production-use guidance

- **For typo-tolerant search**, prefer pg_trgm
  (`%` operator + GIN index) — indexed, fast.
- **For phonetic matching**, fuzzystrmatch shines. Combine
  with pg_trgm: pre-filter with trigram similarity, then
  re-rank by Levenshtein.
- **Index expressions**:
  ```sql
  CREATE INDEX ON users (soundex(last_name));
  -- Then: SELECT * FROM users WHERE soundex(last_name) = soundex('Smith');
  ```
- **For long strings**, `levenshtein_less_equal(a, b, N)` is
  much faster than `levenshtein(a, b) <= N`.

## 10. Invariants

- **[INV-1]** Levenshtein is O(M×N); use less_equal variant
  for early exit.
- **[INV-2]** Soundex / Metaphone return fixed-length codes;
  index-friendly.
- **[INV-3]** Double Metaphone returns 2 codes — use both for
  matching.
- **[INV-4]** Daitch-Mokotoff returns ARRAY (multiple codes);
  use ARRAY-overlap operators.
- **[INV-5]** Trusted extension; CREATE EXTENSION without
  superuser.

## 11. Useful greps

- All entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/fuzzystrmatch/*.c | head -15`
- Soundex implementation:
  `grep -n '_soundex\|soundex_table' source/contrib/fuzzystrmatch/fuzzystrmatch.c | head -5`
- Levenshtein:
  `grep -n 'levenshtein' source/contrib/fuzzystrmatch/fuzzystrmatch.c | head -5`

## 12. Cross-references

- `knowledge/subsystems/contrib-pg_trgm.md` — companion
  text-similarity; pair pg_trgm pre-filter + fuzzystrmatch
  rank.
- `knowledge/subsystems/contrib-citext.md` — sibling text-
  matching contrib (case-insensitive equality).
- `knowledge/subsystems/contrib-dict_int.md` — text-search
  dictionary template.
- `.claude/skills/fmgr-and-spi/SKILL.md` — SQL-callable C
  functions (the model fuzzystrmatch follows).
- `source/contrib/fuzzystrmatch/` — implementation directory.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**3 files.**

| File |
|---|
| [`contrib/fuzzystrmatch/daitch_mokotoff.c`](../files/contrib/fuzzystrmatch/daitch_mokotoff.c.md) |
| [`contrib/fuzzystrmatch/dmetaphone.c`](../files/contrib/fuzzystrmatch/dmetaphone.c.md) |
| [`contrib/fuzzystrmatch/fuzzystrmatch.c`](../files/contrib/fuzzystrmatch/fuzzystrmatch.c.md) |

<!-- /files-owned:auto -->
