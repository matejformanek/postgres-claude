# source/contrib/pg_trgm/trgm_op.c

**Source pin:** master @ 4b0bf07. 1538 LOC. Largest single file in the
pg_trgm module after `trgm_regexp.c`.

## Role

Core trigram extraction, similarity arithmetic, the SQL-visible
`similarity`/`word_similarity`/`strict_word_similarity` functions,
all `%`/`<%`/`<<%` operators, the `<->`/`<->>`/`<<->` distance
operators, and the three `pg_trgm.*_threshold` GUCs. Also defines the
sign-aware trigram comparator `CMPTRGM`.

## Public API (SQL-callable)

- `set_limit(float4)`, `show_limit()` — legacy aliases for the GUC
  [source/contrib/pg_trgm/trgm_op.c:282, 327]
- `show_trgm(text)` — return text[] of extracted trigrams
  [source/contrib/pg_trgm/trgm_op.c:1171]
- `similarity(text, text)`, `similarity_dist(text, text)`,
  `similarity_op(text, text)` [trgm_op.c:1339, 1393, 1402]
- `word_similarity` / `_dist` / `_op` / commutator variants
- `strict_word_similarity` variants
- `_PG_init` — registers three GUCs as PGC_USERSET
  [source/contrib/pg_trgm/trgm_op.c:145]

## Public C API exposed to siblings

- `generate_trgm(char*, int)` — sorted unique TRGM array
- `generate_wildcard_trgm(const char*, int)` — wildcard-aware
- `cnt_sml(TRGM*, TRGM*, bool inexact)` — sorted-merge similarity
- `trgm_contained_by(TRGM*, TRGM*)`
- `trgm_presence_map(TRGM*, TRGM*)`
- `compact_trigram(trgm*, char*, int)` — 3-byte or CRC32-hash
  fallback for multibyte
- `trgm2int(trgm*)`

## GUCs

| Name | Default | Range | Scope |
|------|---------|-------|-------|
| `pg_trgm.similarity_threshold` | 0.3 | 0..1 | PGC_USERSET |
| `pg_trgm.word_similarity_threshold` | 0.6 | 0..1 | PGC_USERSET |
| `pg_trgm.strict_word_similarity_threshold` | 0.5 | 0..1 | PGC_USERSET |

All three are session-local floats; the prefix is reserved via
`MarkGUCPrefixReserved("pg_trgm")` at `trgm_op.c:185`.

## Invariants

- INV: a trigram is exactly 3 bytes; multibyte char trigrams are
  reduced via **legacy CRC32** of all input bytes, taking the upper
  3 bytes of the 32-bit CRC
  [verified-by-code source/contrib/pg_trgm/trgm_op.c:374-393].
  Comment at 388: "hope, it's good enough hashing".
- INV: `init_trgm_array` palloc cap — guards against integer
  overflow via `init_size > MaxAllocSize / sizeof(trgm)` check
  [verified-by-code source/contrib/pg_trgm/trgm_op.c:112-115].
- INV: `enlarge_trgm_array` has the same overflow guard
  [trgm_op.c:131-134].
- INV: case-folding uses **DEFAULT_COLLATION_OID, NOT the query
  collation** [verified-by-code trgm_op.c:545, 1121]. This means
  `'STRAßE' % 'strasse'` is constant across queries regardless of
  the column collation. Comment at trgm_regexp.c:854-859 admits
  this assumption is shaky.
- INV: `similarity_op` and word variants compare against the GUC
  threshold AT QUERY TIME, after generating trigrams
  [verified-by-code trgm_op.c:1409, 1425].
- INV: `iterate_word_similarity` has one `CHECK_FOR_INTERRUPTS()`
  in the outer for-i loop [verified-by-code trgm_op.c:731]. Loop is
  O(len2 × len2_window) in the worst case.
- INV: `cnt_sml` uses sorted merge over two trigram arrays —
  linear-time in the sum of lengths [trgm_op.c:1231-1245].
- INV: `CMPTRGM` is dispatched once via function pointer based on
  `GetDefaultCharSignedness()` for portability
  [verified-by-code trgm_op.c:218-227].

## Notable internals

- `growable_trgm_array` is a TRGM* with reserved header bytes that
  caller must fill in before use [trgm_op.c:78-83]. `dst->datum`
  isn't a valid TRGM until `SET_VARSIZE` is called.
- `make_trigrams` has a fast path for purely ASCII data
  [trgm_op.c:411-419] and a slow multibyte path
  [trgm_op.c:420-478] that calls `compact_trigram` per trigram.
- `find_word` advances by `pg_mblen_range` and uses `ISWORDCHR`
  (= `t_isalnum_with_len`) — uses the database encoding, NOT the
  query collation.
- `calc_word_similarity` builds a "positional trigram" join: it
  sorts a merged pos_trgm array and then runs a sliding window
  over the haystack [trgm_op.c:858-934]. The inner
  `iterate_word_similarity` adjusts both bounds of a window
  for max similarity.

## Trust-boundary / Phase-D surface

1. **Legacy CRC32 is the multibyte trigram hash.** Same hash
   family as A13 hstore and A13 ltree — well-understood, not
   adversary-resistant. An attacker who can choose multibyte
   trigrams can collide them, but the effect is more subtle than
   GiST signature collision: in the trgm array itself, collisions
   show up as "different multibyte trigrams hashing to the same
   3-byte value", inflating `cnt_sml` count and making
   `similarity()` return a higher score than reality.
   **Phase-D pattern**: an attacker controlling text fields could
   craft adversary strings whose `similarity('admin_password', X)`
   exceeds the threshold, fooling similarity-based username
   lookups or fuzzy-deduplication batch jobs.
2. **`similarity_threshold` is PGC_USERSET** — any user can lower
   their session threshold to 0 and `SELECT username FROM users
   WHERE username % 'adm'` will return every row + recheck. This
   isn't a security bug (the user already has SELECT on the
   table) but it does turn similarity indexes into amplifiers
   for sequential-scan-style timing observation. Combined with
   the GiST adversarial-trigram pattern from `trgm_gist.c`, an
   unprivileged user with SELECT can cause indexes to
   misbehave persistently for the session.
3. **`show_trgm` requires no role** — it exposes the trigram
   decomposition of any text. If the input is, e.g., a hashed
   password column reachable via SELECT, `show_trgm` gives the
   attacker the EXACT 3-byte windows of the hash. Combined with
   `similarity()` against candidate plaintexts, this is a faster
   oracle than direct comparison. **This is a Phase-D
   "similarity-as-side-channel" pattern**: side-effect of pg_trgm
   being IMMUTABLE STRICT and SELECT-grantable means anyone with
   read on a column can use trgm functions for free.
4. **Case-folding pinned to DEFAULT_COLLATION_OID.** Cross-collation
   asymmetry: `similarity('foo', 'FOO')` is constant regardless of
   query collation, but the GIN/GiST index was built using the
   same DEFAULT_COLLATION_OID. If the database default collation
   changes (e.g., glibc upgrade reorders case maps for some
   non-ASCII chars), indexes silently desync. Echo of A13 citext
   and A5 collation handling.
5. **No CHECK_FOR_INTERRUPTS in `generate_trgm`/`make_trigrams`.**
   For a 1GB input, this can spin for seconds. The MaxAllocSize
   check at trgm_op.c:112 bounds memory but not CPU.
6. **`word_similarity` inner loops have ONE interrupt check** at
   trgm_op.c:731 — but the inner `for (tmp_lower = lower;
   tmp_lower <= upper; tmp_lower++)` at line 774 has no
   CHECK_FOR_INTERRUPTS; on a pathological string this is
   O(len² × window).

## Cross-refs

- `source/contrib/pg_trgm/trgm.h` — type and macros
- `source/backend/utils/adt/varlena.c` — `varstr_levenshtein`
  (fuzzystrmatch leverages the same family)
- A13 ltree `_ltree_op.c` — sibling fuzzy-match contrib

## Issues

- [ISSUE-Phase-D: show_trgm + similarity as text-content oracle (low)] —
  source/contrib/pg_trgm/trgm_op.c:1171,1339 — both functions are
  SELECT-grantable side-channels: any user with column SELECT can
  enumerate trigram windows and compute similarity against
  arbitrary candidates, accelerating cracking of hashed/encrypted
  columns vs direct equality.
- [ISSUE-Phase-D: legacy CRC32 multibyte trigram hash (low)] —
  source/contrib/pg_trgm/trgm_op.c:382-392 — well-understood
  legacy hash; adversary can engineer collisions, inflating
  similarity scores beyond ground truth.
- [ISSUE-Phase-D: case-folding pinned to DEFAULT_COLLATION_OID (low)] —
  source/contrib/pg_trgm/trgm_op.c:545,1121 — collation drift
  between index build and query desyncs results; cross-collation
  semantics asymmetric.
- [ISSUE-Phase-D: missing CHECK_FOR_INTERRUPTS in inner word_similarity
  loop (low)] — source/contrib/pg_trgm/trgm_op.c:774-813 — outer loop
  has one CFI but inner adjustment loop does not; pathological
  input can stall worker for seconds.
- [ISSUE-Phase-D: missing CHECK_FOR_INTERRUPTS in make_trigrams (low)] —
  source/contrib/pg_trgm/trgm_op.c:399-483 — extracting trigrams
  from a multi-MB string runs without yield.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_trgm.md](../../../subsystems/contrib-pg_trgm.md)
