---
source_url: https://www.postgresql.org/docs/current/pgtrgm.html
fetched_at: 2026-07-13T20:47:00Z
anchor_sha: d92e98340fcb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.34 pg_trgm — support for similarity of text using trigram matching"
maps_to_skill: access-method-apis
---

# Docs distilled — pg_trgm (trigram similarity + index-accelerated LIKE/regex)

The canonical worked example of a **type-specific GIN _and_ GiST operator
class** that also teaches the planner to use an index for `LIKE`/`ILIKE`/`~`
pattern queries that are *not* left-anchored — something no B-tree can do.
Maps directly onto `access-method-apis` (opclass / strategy-number design).

## Non-obvious claims

- **A trigram is a group of three consecutive characters; words are padded
  "2 leading, 1 trailing" space.** `"cat"` → `" c"`, `" ca"`, `"cat"`,
  `"at "`. Non-alphanumeric characters are ignored when splitting into words.
  [from-docs] The padding constants are literal macros:
  `#define LPADDING 2` / `#define RPADDING 1` [[trgm.h:16]], and
  `trgm_regexp.c` "effectively assumes these values" (comment at trgm.h:12–14),
  so they are not freely tunable. [verified-by-code @ d92e98340fcb]
- **Three thresholds, three GUC defaults, three operator families.** The
  boolean similarity operators fire when the corresponding similarity exceeds
  a GUC:
  - `%`   ↔ `pg_trgm.similarity_threshold` = **0.3**
  - `<%` / `%>` ↔ `pg_trgm.word_similarity_threshold` = **0.6**
  - `<<%` / `%>>` ↔ `pg_trgm.strict_word_similarity_threshold` = **0.5**
  [from-docs] Defaults confirmed as C initializers
  `similarity_threshold = 0.3f` / `word_similarity_threshold = 0.6f` /
  `strict_word_similarity_threshold = 0.5f` [[trgm_op.c:27]], and registered via
  `DefineCustomRealVariable("pg_trgm.similarity_threshold", …, 0.3f, …)`
  [[trgm_op.c:148]]. [verified-by-code @ d92e98340fcb]
- **`set_limit()`/`show_limit()` are deprecated shims over the GUC.**
  `set_limit()` literally calls `SetConfigOption("pg_trgm.similarity_threshold",
  …)` and returns the GUC value [[trgm_op.c:294]] — do not use them, use `SET`.
  [verified-by-code @ d92e98340fcb]
- **`word_similarity` vs `strict_word_similarity`:** both find the best-matching
  *continuous extent* of the second string, but `strict_` forces the extent
  boundaries to coincide with word boundaries (so it never rewards a partial
  word). `word_similarity` does not pad the extent edges. [from-docs]
- **Ten strategy numbers, not the usual btree five.** The opclass strategy map
  is dense: `SimilarityStrategyNumber = 1`, `DistanceStrategyNumber = 2`,
  `LikeStrategyNumber = 3`, `ILikeStrategyNumber = 4`, `RegExpStrategyNumber = 5`,
  `RegExpICaseStrategyNumber = 6`, `WordSimilarityStrategyNumber = 7`,
  `WordDistanceStrategyNumber = 8`, `StrictWordSimilarityStrategyNumber = 9`,
  `StrictWordDistanceStrategyNumber = 10`, `EqualStrategyNumber = 11`
  [[trgm.h:36]] onward. [verified-by-code @ d92e98340fcb] This is a good study
  of how an AM's `pg_amop` rows encode a rich operator surface for one type.
- **GiST opclass `gist_trgm_ops` has a tunable `siglen`; GIN's `gin_trgm_ops`
  does not.** GiST approximates the trigram set as a fixed-length bitmap
  *signature*; default length is `SIGLEN_DEFAULT = sizeof(int) * 3` = **12
  bytes** [[trgm.h:68]], selectable per-index via the opclass-options machinery
  `CREATE INDEX … USING gist (t gist_trgm_ops(siglen=32))`. The GET_SIGLEN
  macro reads the reloption or falls back to the default
  [[trgm_gist.c:20]]; the option is registered with bounds
  `SIGLEN_DEFAULT, 1, SIGLEN_MAX` [[trgm_gist.c:972]]. Longer signature = fewer
  false positives but a larger index. [verified-by-code @ d92e98340fcb]
- **Case-insensitivity is a compile-time contract, not a runtime flag.** The
  `#define IGNORECASE` macro means trigrams are lowercased; the header warns
  that disabling it *requires removing the `~*`/`~~*` operators from the
  opclasses*, else you get "cannot handle ~*(~~*) with case-sensitive trigrams".
  [[trgm.h:19–25]] [verified-by-code @ d92e98340fcb]
- **The index-acceleration trick:** for `col LIKE '%foo%bar'` or `col ~
  '(foo|bar)'`, pg_trgm extracts the trigrams *from the pattern* and probes the
  index for rows whose trigram set is a superset. Because it works on trigram
  content, the pattern **need not be left-anchored** — the classic reason to
  reach for pg_trgm over a `text_pattern_ops` btree. If the pattern yields no
  extractable trigrams, the scan degenerates to a full-index scan. [from-docs]

## Links into corpus

- [[knowledge/subsystems/contrib-pg_trgm.md]] — the source-side companion
  (this doc is the docs-prose layer; that one walks the C).
- [[knowledge/docs-distilled/gin.md]] / [[knowledge/docs-distilled/gist.md]] —
  the two AMs whose opclass surface pg_trgm implements.
- [[knowledge/docs-distilled/xindex.md]] — how opclasses/strategy numbers/
  support functions register in `pg_amop`/`pg_amproc`.
- [[knowledge/docs-distilled/indexes-types.md]] — where GIN/GiST sit among the
  built-in index types.

## Confidence

Padding rule, threshold defaults, strategy numbers, `siglen` default, the
deprecated-shim and case-insensitivity contracts are all
[verified-by-code @ d92e98340fcb] against `contrib/pg_trgm/{trgm.h,trgm_op.c,
trgm_gist.c}`. The trigram-extraction pattern-acceleration behavior and the
`word_similarity` vs `strict_word_similarity` semantics are [from-docs].
