# Issues — `contrib/pg_trgm`

Trigram-based similarity index extension (GIN + GiST opclasses). 5 source files / ~5364 LOC.

**Parent docs:** `knowledge/files/contrib/pg_trgm/*` (5 docs: trgm.h, trgm_gin.c, trgm_gist.c, trgm_op.c, trgm_regexp.c).

**Source:** 14 entries surfaced 2026-06-09 by A14-4.

## Headlines

1. **`trgm_regexp.c` has ZERO `CHECK_FOR_INTERRUPTS()` calls** — the entire regex-to-NFA pipeline relies on static `MAX_EXPANDED_STATES=128 / MAX_EXPANDED_ARCS=1024 / MAX_TRGM_COUNT=256` constants. Bounds are tight in practice but adversarial stage-3 merge combinatorics have no yield point. Confirmed by grep.
2. **Signature-tree hash is plain modulo** (`HASHVAL = trgm % 95` at default siglen=12) — adversary text can engineer trigram→bit collisions that saturate internal GiST nodes to ALLISTRUE, degrading the index to a leaf scan. Direct echo of A13 intarray, A13 hstore, A14 bloom.
3. **`pg_regcomp` is unbounded at trgm boundary** — catastrophic-backtracker regex spent in `pg_regcomp` BEFORE the bounded NFA conversion. Echoes A13 ltree `checkCond`.
4. **`show_trgm` + similarity = SELECT-grantable text-content oracle** — accelerates cracking hashed/encrypted text columns vs direct equality.
5. **`siglen=1` reloption effectively disables the index** (~7 usable bits) — confused-deputy / misconfig makes index useless without warning.
6. Multiple missing-CFI sites in word-similarity / make-trigrams loops.

## Entries

- [ISSUE-resource: mod-based signature hash (likely)] — `source/contrib/pg_trgm/trgm.h:85` — adversary text values craft collisions saturating internal-node bitmaps to ALLISTRUE.
- [ISSUE-defense-in-depth: `siglen=1` reloption effectively disables index (nit)] — `source/contrib/pg_trgm/trgm_gist.c:970-973`
- [ISSUE-resource: no `CHECK_FOR_INTERRUPTS` in `createTrgmNFA` pipeline (maybe)] — `source/contrib/pg_trgm/trgm_regexp.c` — relies entirely on `MAX_EXPANDED_STATES=128 / MAX_EXPANDED_ARCS=1024 / MAX_TRGM_COUNT=256 / COLOR_COUNT_LIMIT=256`.
- [ISSUE-resource: `pg_regcomp` complexity not bounded at trgm boundary (nit)] — `source/contrib/pg_trgm/trgm_regexp.c:737-741`
- [ISSUE-correctness: case-fold assumption shaky for non-ASCII (nit)] — `source/contrib/pg_trgm/trgm_regexp.c:854-859` (XXX comment in source)
- [ISSUE-defense-in-depth: legacy CRC32 multibyte trigram hash (nit)] — `source/contrib/pg_trgm/trgm_op.c:382-392`
- [ISSUE-correctness: case-folding pinned to `DEFAULT_COLLATION_OID` (nit)] — `source/contrib/pg_trgm/trgm_op.c:545,1121`
- [ISSUE-security: `show_trgm` + similarity as text-content oracle (maybe)] — `source/contrib/pg_trgm/trgm_op.c:1171,1339` — both SELECT-grantable; accelerate cracking of hashed/encrypted text columns.
- [ISSUE-resource: missing CFI in inner word_similarity loop (nit)] — `source/contrib/pg_trgm/trgm_op.c:774-813`
- [ISSUE-resource: missing CFI in `make_trigrams` multibyte loop (nit)] — `source/contrib/pg_trgm/trgm_op.c:399-483`
- [ISSUE-resource: full-index-scan fallback on empty trigrams (nit)] — `source/contrib/pg_trgm/trgm_gin.c:135-138,165-167`
- [ISSUE-memory: regex graph leak across rescans (nit, acknowledged in source)] — `source/contrib/pg_trgm/trgm_gist.c:225-226,299`
- [ISSUE-api-shape: `MAX_*` regex bounds are static constants, not GUCs (nit)] — `source/contrib/pg_trgm/trgm_regexp.c:221-225`
- [ISSUE-api-shape: triple StrategyNumber switch maintenance hazard (nit)] — `source/contrib/pg_trgm/trgm_gin.c:90-144,190-258,286-356`

## Cross-sweep references

- A13 hstore (CRC32) + A13 ltree (CRC32) + A13 intarray (mod-hash) + A14 pg_trgm (mod-hash) + A14 bloom (deterministic LCG) = **5-module signature-collision cluster**.
- A13 ltree `checkCond` catastrophic backtracker — A14 pg_trgm `pg_regcomp` echo.
- A11 pg_stat_statements, A12 amcheck/pageinspect — "monitoring/similarity-as-extraction" cluster.
- A13 citext, A5 collation — `DEFAULT_COLLATION_OID` cluster.
