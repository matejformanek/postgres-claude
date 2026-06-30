# source/contrib/pg_trgm/trgm_gin.c

**Source pin:** master @ 4b0bf07. 362 LOC.

## Role

GIN opclass support for `gin_trgm_ops`: extractor for values and
queries, plus binary and ternary consistent functions. Bridges raw
trigram extraction (in `trgm_op.c`) and NFA-based regex extraction
(in `trgm_regexp.c`) into GIN's per-entry index machinery.

## Public API (SQL-callable)

- `gin_extract_trgm` (legacy shim, dispatches by arg count)
  [source/contrib/pg_trgm/trgm_gin.c:24]
- `gin_extract_value_trgm` (3 args) — extract trigrams from a
  to-be-indexed value [source/contrib/pg_trgm/trgm_gin.c:35]
- `gin_extract_query_trgm` (7 args) — extract trigrams from a query
  by strategy number [source/contrib/pg_trgm/trgm_gin.c:70]
- `gin_trgm_consistent` (binary) [source/contrib/pg_trgm/trgm_gin.c:172]
- `gin_trgm_triconsistent` (ternary) [source/contrib/pg_trgm/trgm_gin.c:271]

## Invariants

- INV: **all answers from this opclass are inexact** — `*recheck = true`
  is set unconditionally for the binary path
  [verified-by-code source/contrib/pg_trgm/trgm_gin.c:188]. Index
  ALWAYS hands off to recheck.
- INV: similarity strategy upper-bound formula `ntrue/nkeys`
  [verified-by-code source/contrib/pg_trgm/trgm_gin.c:220] — same
  derivation for DIVUNION and non-DIVUNION (see comment lines
  205-219).
- INV: Like/Equal strategies require ALL extracted trigrams to be
  present (AND semantics) [verified-by-code source/contrib/pg_trgm/trgm_gin.c:230-239].
- INV: regex strategy stores the packed graph in `extra_data` —
  every nentries slot points to the same graph object
  [verified-by-code source/contrib/pg_trgm/trgm_gin.c:127-131].
- INV: empty extracted trigram set → `GIN_SEARCH_MODE_ALL` (full
  index scan) [verified-by-code source/contrib/pg_trgm/trgm_gin.c:135-138,
  165-167].
- INV: triconsistent uses monotonicity of `trigramsMatchGraph` to
  promote GIN_MAYBE to GIN_TRUE conservatively
  [verified-by-code source/contrib/pg_trgm/trgm_gin.c:340-347].

## Notable internals

- The same dispatch switch over `StrategyNumber` exists in three
  places (extract_query, consistent, triconsistent). Adding a new
  strategy requires updating all three. If `IGNORECASE` is undef'd
  at build, ILike/RegExpICase paths `elog(ERROR, ...)`.

## Trust-boundary / Phase-D surface

1. **Empty-trigram fallback = full index scan.** A query with no
   extractable trigrams (e.g., a regex `.+` or a 2-char LIKE)
   sets `GIN_SEARCH_MODE_ALL`. This is the standard behavior but
   an attacker with `pg_trgm.similarity_threshold` set low enough
   plus a degenerate regex can force every query to scan the
   entire index. Cost model doesn't prevent this.
2. **No CHECK_FOR_INTERRUPTS** in the per-key loops. The consistent
   function does small bounded work (nkeys ≤ MAX_TRGM_COUNT = 256)
   so this is probably fine in practice, but worth noting.
3. **`gin_extract_query_trgm` invokes `createTrgmNFA` for regex
   strategies** (line 118-119) — pushes ALL of the
   `trgm_regexp.c` regex-DoS surface into every GIN query plan.
4. **Per-row extraction (`generate_trgm`) is O(byte_length)** —
   no input length cap. A 1GB text column would extract ~1GB of
   trigrams during index build, palloc'd in one shot via
   `init_trgm_array` [source/contrib/pg_trgm/trgm_op.c:117].
   Bounded by `MaxAllocSize` check at trgm_op.c:112.

## Cross-refs

- `source/contrib/pg_trgm/trgm_op.c` — `generate_trgm`,
  `generate_wildcard_trgm`
- `source/contrib/pg_trgm/trgm_regexp.c` — `createTrgmNFA`,
  `trigramsMatchGraph`
- A13 ltree `_ltree_consistent` — analogous opclass GIN bridge

## Issues

- [ISSUE-Phase-D: full-index-scan fallback on empty trigrams (low)] —
  source/contrib/pg_trgm/trgm_gin.c:135-138,165-167 — adversary
  regex can deliberately produce empty trigram set, forcing full
  scan. Standard behavior, but no per-query cost cap.
- [ISSUE-Style: triple switch on StrategyNumber (low)] —
  source/contrib/pg_trgm/trgm_gin.c:90-144,190-258,286-356 —
  maintenance risk: adding strategies needs three coordinated
  edits.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_trgm.md](../../../subsystems/contrib-pg_trgm.md)
