# source/contrib/pg_trgm/trgm.h

**Source pin:** master @ 4b0bf07. 131 LOC.

## Role

Module-wide header for `pg_trgm`: trigram type, signature/array key
layout, strategy numbers, similarity macros, and the public
`generate_trgm` / `cnt_sml` / `createTrgmNFA` API surface shared by
`trgm_op.c`, `trgm_gin.c`, `trgm_gist.c`, `trgm_regexp.c`.

## Public API and macros

- `typedef char trgm[3]` — a trigram is **always exactly three bytes**
  [verified-by-code source/contrib/pg_trgm/trgm.h:41]. Multibyte
  characters get hashed down to 3 bytes via `compact_trigram` in
  `trgm_op.c:374`.
- `LPADDING 2`, `RPADDING 1` — word padding for trigram extraction
  [from-comment source/contrib/pg_trgm/trgm.h:13-17]. Header comment
  explicitly warns `trgm_regexp.c` assumes these values.
- `IGNORECASE` defined → trigrams are case-insensitive
  [verified-by-code source/contrib/pg_trgm/trgm.h:25]; turning it off
  forces `~*` / `~~*` operators to be dropped from opclass.
- `SIGLEN_DEFAULT (sizeof(int) * 3)` = **12 bytes = 96 bits**
  [verified-by-code source/contrib/pg_trgm/trgm.h:68]. This is the
  GiST signature length default; configurable per-index via
  `siglen` reloption up to `SIGLEN_MAX = GISTMaxIndexKeySize`.
- `HASHVAL(val, siglen) ((unsigned int)(val)) % SIGLENBIT(siglen))`
  [verified-by-code source/contrib/pg_trgm/trgm.h:85] — **the
  trigram-to-bit hash is a simple modulo of the 24-bit trigram
  integer over (siglen*8 - 1)**. No CRC, no permutation, no salt.
- `CALCSML` — Jaccard-style similarity:
  `count / (len1 + len2 - count)` when `DIVUNION` defined
  [verified-by-code source/contrib/pg_trgm/trgm.h:108].
- 11 strategy numbers covering similarity (1), distance (2),
  like (3,4), regex (5,6), word similarity (7-10), equal (11)
  [verified-by-code source/contrib/pg_trgm/trgm.h:29-39].
- Flag bits on `TRGM`: `ARRKEY` (sorted unique array of trigrams),
  `SIGNKEY` (bitmap signature), `ALLISTRUE` (signature saturated)
  [verified-by-code source/contrib/pg_trgm/trgm.h:88-94].

## Invariants

- INV: a trigram is exactly 3 bytes; UTF-8 multibyte characters are
  hashed via legacy CRC32 in `compact_trigram` [verified-by-code
  source/contrib/pg_trgm/trgm_op.c:374-393].
- INV: `SETBIT(sign, SIGLENBIT(siglen))` always sets the last unused
  bit in `makesign` (see `trgm_gist.c:106`) — this is a sentinel that
  the empty signature is non-zero.
- INV: GiST signature collisions are intentional — `HASHVAL` is mod
  over fewer bits than the trigram value space (24 bits → 95 bits
  default), so an adversary CAN engineer trigram→bit collisions.
  False-positives are caught by recheck on heap tuples.

## Notable internals

- `CMPTRGM` is a function pointer (`trgm_op.c:49`) chosen at first
  call based on `GetDefaultCharSignedness()` — handles
  signed-vs-unsigned char comparison portability across platforms.
- `BITVECP` is just `char*`; no alignment guarantees.

## Trust-boundary / Phase-D surface

1. **Signature hash is mod-based, not cryptographic.** `HASHVAL` is
   `int % (siglen*8 - 1)`. Default `siglen*8 - 1 = 95`. An attacker
   who can submit text values to a GiST `gist_trgm_ops` index can
   craft inputs whose trigrams all collide on the same handful of
   signature bits, defeating the leaf-vs-internal pruning and
   forcing the index to behave like a sequential scan + recheck.
   Echo of A13 intarray HASHVAL mod-collisions and A13 hstore CRC32
   gistbits.
2. **`siglen` GUC-like reloption is user-controlled.** Larger
   `siglen` means more bits → fewer collisions but bigger index
   pages. Range is 1..GISTMaxIndexKeySize. A confused-deputy
   admin could create an index with `siglen=1` (8 bits!) which
   makes the signature trivially saturated.
3. **`LPADDING/RPADDING` constants leak word boundaries into
   trigrams.** The two-space left padding means " a" matches any
   word starting with 'a', allowing prefix-match queries to behave
   surprisingly when the input contains literal leading spaces.
4. **`IGNORECASE` semantics depend on `DEFAULT_COLLATION_OID`** for
   `str_tolower` (see `trgm_op.c:545, 1121`). Collation drift between
   index build and query can yield false negatives.

## Cross-refs

- `source/contrib/pg_trgm/trgm_op.c` — implementation
- `source/contrib/pg_trgm/trgm_gist.c` — GiST opclass + siglen
- `source/contrib/pg_trgm/trgm_gin.c` — GIN opclass
- `source/contrib/pg_trgm/trgm_regexp.c` — regex-to-NFA bridge

## Issues

- [ISSUE-Phase-D: mod-based signature hash (med)] —
  source/contrib/pg_trgm/trgm.h:85 — `HASHVAL` is plain modulo;
  adversary trigram-set can target a small subset of bits.
- [ISSUE-Phase-D: siglen=1 reloption (low)] —
  source/contrib/pg_trgm/trgm_gist.c:970-973 — reloption range
  allows siglen=1, trivially-saturated signatures.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_trgm.md](../../../subsystems/contrib-pg_trgm.md)
