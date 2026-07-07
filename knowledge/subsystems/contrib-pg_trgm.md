# contrib-pg_trgm (trigram-based text similarity + indexing)

- **Source path:** `source/contrib/pg_trgm/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.6` (per `pg_trgm.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

Text similarity measurement based on **trigrams** (3-character
substrings). Provides:

- **Similarity functions** — `similarity(text, text)`,
  `word_similarity`, `strict_word_similarity`.
- **Similarity operators** (`%`, `<%`, `<<%`) for WHERE
  clauses.
- **Distance operators** (`<->`, `<<->`, `<<<->`) for
  KNN-style ORDER BY.
- **GIN + GiST index support** for indexed similarity search.
- **Regex acceleration** — index-supports trigram-extractable
  regexes via `trgm_regexp.c`.

A workhorse text-search extension. Heavily used in
production for autocomplete, typo-tolerant search, fuzzy
matching.

## 2. The 4 C files

| File | LOC | What it does |
|---|---|---|
| `trgm_op.c` | 1538 | similarity + word_similarity functions |
| `trgm_regexp.c` | 2357 | extract trigrams from a regex |
| `trgm_gist.c` | 976 | GiST opclass (signature-based) |
| `trgm_gin.c` | 362 | GIN opclass (trigram inverted index) |

[verified-by-code `wc -l source/contrib/pg_trgm/*.c`]

The largest is `trgm_regexp.c` — extracting trigrams from a
regex is non-trivial (need to handle alternation, char classes,
quantifiers correctly).

## 3. The trigram model

Each string is split into overlapping 3-character substrings
(trigrams):

```
"hello" → " h", " he", "hel", "ell", "llo", "lo "
```

The string is padded with spaces at start + end so prefix/
suffix matches work. Similarity between two strings is:

```
similarity(a, b) = |T(a) ∩ T(b)| / |T(a) ∪ T(b)|
```

(Jaccard index on the trigram sets.)

## 4. The similarity flavors

[verified-by-code `trgm_op.c:31-44`]

| Function | Behavior |
|---|---|
| `similarity(a, b)` | Pure Jaccard on whole strings |
| `word_similarity(a, b)` | Best-matching contiguous word-aligned window |
| `strict_word_similarity(a, b)` | Like word_similarity but strict boundaries |

`word_similarity` and `strict_word_similarity` are useful for
matching a **search term against a longer document** — pure
similarity would be dragged down by the document length.

## 5. The threshold GUCs

```c
double word_similarity_threshold        = 0.6f;
double strict_word_similarity_threshold = 0.5f;
```

[verified-by-code `trgm_op.c:28-29`]

`pg_trgm.similarity_threshold` (the original; default 0.3)
controls the `%` operator. The two `word_*` thresholds gate
the corresponding operators. `set_limit(float)` adjusts at
runtime; `show_limit()` reads.

A lower threshold = more matches but more false positives.

## 6. The GIN opclass

[verified-by-code `trgm_gin.c:12-16`]

- `gin_extract_value_trgm` — extract trigrams from a
  to-be-indexed value.
- `gin_extract_query_trgm` — extract trigrams from a query
  value, distinguishing equality / substring / regex / similarity.
- `gin_trgm_consistent` — given a query and the trigrams
  found in an index entry, decide if the entry might match.
- `gin_trgm_triconsistent` — three-valued (TRUE / FALSE /
  MAYBE) version; lets GIN prune more aggressively.

GIN-trigram is the **default choice for similarity indexing**.
Performant on large tables; supports ILIKE, regex, and
similarity operators.

## 7. The GiST opclass

Trigram GiST uses **signature-based compression** — each
internal node stores a signature (bit array) representing
trigrams below. Faster on small tables; supports the
distance operators directly for KNN-search:

```sql
SELECT name FROM contacts
ORDER BY name <-> 'Smyth' LIMIT 10;
```

`<->` is the distance operator (1 - similarity); GiST visits
internal nodes in best-distance order, finding the top 10
closest matches without scanning the whole table.

## 8. The regex-trigram trick

`trgm_regexp.c` examines a regex and extracts **trigrams
guaranteed to appear** in any matching string. Example:

- Regex: `hello.*world` → must contain trigrams from "hello"
  AND from "world".
- Regex: `hel(lo|p)` → must contain "hel" plus trigrams from
  either "lo" or "p".

The extracted set drives the GIN/GiST index lookup. If the
regex can't be cracked (e.g., `.*` alone), the lookup falls
back to a sequential scan.

## 9. The operators

| Operator | Meaning |
|---|---|
| `a % b` | a similarity-matches b (above threshold) |
| `a <% b` | word_similarity(b, a) above threshold |
| `a <<% b` | strict_word_similarity(b, a) above threshold |
| `a <-> b` | 1 - similarity(a, b) |
| `a <<-> b` | 1 - word_similarity(b, a) |
| `a <<<-> b` | 1 - strict_word_similarity(b, a) |

The distance operators are KNN-friendly — `ORDER BY ... <-> X
LIMIT N` becomes an index scan with the GiST opclass.

## 10. Production-use guidance

- **For "search box with typos"**, use the GIN opclass + `%`
  operator.
- **For "find me the 10 closest matches"**, use the GiST
  opclass + `<->` distance + `ORDER BY ... LIMIT 10`.
- **Tune the threshold** based on your data — a corpus with
  long words may want a lower threshold.
- **For ILIKE acceleration**, the GIN opclass supports it
  natively without any extra work.

## 11. Invariants

- **[INV-1]** Trigrams include surrounding spaces; prefix /
  suffix matches work.
- **[INV-2]** Similarity = Jaccard on trigram sets.
- **[INV-3]** GIN faster for "find rows containing similar
  text"; GiST faster for KNN-search.
- **[INV-4]** Regex acceleration extracts mandatory trigrams;
  falls back to seq scan if regex is too loose.
- **[INV-5]** Trusted extension; CREATE EXTENSION pg_trgm
  without superuser.

## 12. Useful greps

- All entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/pg_trgm/trgm_op.c | head -20`
- Trigram extraction:
  `grep -n 'generate_trgm\|generate_wildcard_trgm' source/contrib/pg_trgm/trgm_op.c | head -5`
- GIN consistent function:
  `grep -n 'gin_trgm_consistent\|gin_trgm_triconsistent' source/contrib/pg_trgm/trgm_gin.c`

## 13. Cross-references

- `knowledge/subsystems/access-nbtree.md` — companion AM
  (but pg_trgm uses GIN/GiST).
- `knowledge/subsystems/contrib-btree_gist.md` — sibling
  contrib; GiST opclasses for scalar types.
- `knowledge/subsystems/contrib-intarray.md` — sibling
  contrib; similar GIN/GiST split for int4[].
- `.claude/skills/access-method-apis/SKILL.md` — index AM
  contracts.
- `source/contrib/pg_trgm/` — implementation directory.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**5 files.**

| File |
|---|
| [`contrib/pg_trgm/trgm.h`](../files/contrib/pg_trgm/trgm.h.md) |
| [`contrib/pg_trgm/trgm_gin.c`](../files/contrib/pg_trgm/trgm_gin.c.md) |
| [`contrib/pg_trgm/trgm_gist.c`](../files/contrib/pg_trgm/trgm_gist.c.md) |
| [`contrib/pg_trgm/trgm_op.c`](../files/contrib/pg_trgm/trgm_op.c.md) |
| [`contrib/pg_trgm/trgm_regexp.c`](../files/contrib/pg_trgm/trgm_regexp.c.md) |

<!-- /files-owned:auto -->
