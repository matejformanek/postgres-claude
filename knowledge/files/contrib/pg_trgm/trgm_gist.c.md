# source/contrib/pg_trgm/trgm_gist.c

**Source pin:** master @ 4b0bf07. 976 LOC.

## Role

GiST opclass support for `gist_trgm_ops`: signature/array compression,
union, picksplit, penalty, same, consistent, distance, plus the
`siglen` reloption. Implements a signature-tree GiST index where each
internal node carries a bitmap formed by hashing trigrams into
`siglen*8 - 1` bits.

## Public API (SQL-callable)

- `gtrgm_in`, `gtrgm_out` — both raise ERROR (internal type, not
  representable as SQL text) [source/contrib/pg_trgm/trgm_gist.c:57-74]
- `gtrgm_compress` / `gtrgm_decompress` [source/contrib/pg_trgm/trgm_gist.c:115, 155]
- `gtrgm_consistent` [source/contrib/pg_trgm/trgm_gist.c:197]
- `gtrgm_distance` [source/contrib/pg_trgm/trgm_gist.c:453]
- `gtrgm_union`, `gtrgm_same`, `gtrgm_penalty`, `gtrgm_picksplit`
- `gtrgm_options` — registers `siglen` reloption
  [source/contrib/pg_trgm/trgm_gist.c:964]

## Invariants

- INV: leaf entries carry **ARRKEY** (sorted unique trigram array);
  internal entries carry **SIGNKEY** (bitmap), or `ALLISTRUE` once
  every bit is set [verified-by-code source/contrib/pg_trgm/trgm_gist.c:121-152].
- INV: `gtrgm_compress` upgrades a leaf-entry text via
  `generate_trgm` and detects ALLISTRUE on internal entries (if all
  bytes are 0xff) [verified-by-code source/contrib/pg_trgm/trgm_gist.c:139-150].
- INV: `siglen` reloption ranges from 1 to `SIGLEN_MAX` =
  `GISTMaxIndexKeySize`. Default `SIGLEN_DEFAULT = 12 bytes = 96 bits`
  [verified-by-code source/contrib/pg_trgm/trgm_gist.c:969-973].
- INV: signature bits are set via `HASH(sign, trgm_int, siglen)` =
  `SETBIT(sign, ((unsigned)val) % (siglen*8-1))`
  [verified-by-code source/contrib/pg_trgm/trgm.h:85-86, used at
  trgm_gist.c:110, 558].
- INV: `makesign` always sets the last unused bit
  `SETBIT(sign, SIGLENBIT(siglen))` so empty-but-not-allistrue
  signatures are distinguishable [verified-by-code trgm_gist.c:106].
- INV: signature-vs-signature distance is Hamming via
  `pg_popcount` [verified-by-code trgm_gist.c:651-670].
- INV: consistent function caches the extracted query trigrams +
  regex graph in `fn_extra` across calls for the same query
  [verified-by-code trgm_gist.c:228-305]. Header comment at
  225-226: "this approach can leak regex graphs across index
  rescans. Not clear if that's worth fixing."

## Notable internals

- `gtrgm_picksplit` — classic GiST seed-pair algorithm:
  1. Compute pairwise Hamming distances to find two furthest-apart
     items [trgm_gist.c:836-848] — **O(n²)** in maxoff.
  2. Sort other items by `|dist_to_seed1 - dist_to_seed2|`
     [trgm_gist.c:870-880].
  3. Assign each to closer seed with a small WISH_F bias to balance
     sizes [trgm_gist.c:924].
- `gtrgm_penalty` caches `makesign` output via `fn_extra` for
  repeated calls with the same `newval` [trgm_gist.c:714-733].
- Regex graph is allocated in `fn_mcxt`, not freed across
  index rescans (see acknowledged leak above).

## Trust-boundary / Phase-D surface

1. **Mod-based signature hashing.** Same fundamental finding as
   `trgm.h`: `HASHVAL = ((unsigned int)trgm_24bit) % 95` at
   default siglen. Carefully chosen trigram sets fall on the same
   bits → ALLISTRUE saturates quickly → `gtrgm_consistent` returns
   true for any non-leaf entry [verified-by-code trgm_gist.c:329-331,
   362-364], so internal nodes become useless and the index
   degenerates to a sequential leaf scan + recheck.
   **Adversarial pattern**: build a text column with N rows
   each containing trigrams chosen to all collide on the same
   8-10 bits, then any similarity query becomes O(table) instead
   of O(log N). Echoes A13 intarray HASHVAL, A13 hstore CRC32,
   A11 pgcrypto weak hash defaults.
2. **`siglen` reloption can be set to 1 byte (8 bits).**
   With siglen=1 the signature has effectively 7 usable bits;
   any non-trivial input saturates → ALLISTRUE is universal →
   index is useless. Not a security bug per se, but
   `add_local_int_reloption` enforces only min=1, max=SIGLEN_MAX
   with no warning [trgm_gist.c:970-973]. A confused admin or a
   privilege-escalation gadget that influences index options
   could effectively disable GiST trgm index entirely.
3. **O(n²) picksplit on attacker-controlled input.** maxoff is
   bounded by GiST page size, so this is bounded — but worth
   noting for completeness.
4. **`*recheck = true` is set for all but SimilarityStrategy** —
   plain similarity is reported as exact at leaf level
   [trgm_gist.c:319]. The `cnt_sml` at leaf compares the
   sorted-unique trigram arrays exactly, so this is correct.
5. **fn_extra cache uses `memcmp` of the raw varlena including
   header** [trgm_gist.c:231-232] — if two different queries
   could pack identically to the same byte representation
   (impossible for text but worth noting) the cache would
   return stale results.
6. **Acknowledged regex-graph leak across rescans** — comment at
   trgm_gist.c:225-226. Memory leak, not security, but if many
   regex queries run in a long-lived backend the leak
   accumulates in `fn_mcxt` (per-FmgrInfo lifetime).

## Cross-refs

- `source/contrib/pg_trgm/trgm.h` — sig macros
- `source/contrib/pg_trgm/trgm_regexp.c` — `createTrgmNFA`
- `source/contrib/pg_trgm/trgm_op.c` — `cnt_sml`, `trgm_contained_by`,
  `trgm_presence_map`
- A13 intarray `_int_gist.c` — sibling signature-tree implementation
  with the same HASHVAL mod-collision class.

## Issues

- [ISSUE-Phase-D: adversarial trigram → ALLISTRUE saturation (med)] —
  source/contrib/pg_trgm/trgm_gist.c:329-331, trgm.h:85 — mod-based
  HASHVAL admits crafted text inputs that collide on few signature
  bits, forcing internal nodes to ALLISTRUE; gtrgm_consistent then
  returns true for every page → degenerates to full leaf scan.
- [ISSUE-Phase-D: siglen=1 reloption effectively disables index (low)] —
  source/contrib/pg_trgm/trgm_gist.c:970-973 — no warning when
  siglen is set so low it makes the index useless. Defense-in-depth
  would clamp to a minimum like 4.
- [ISSUE-Resource: regex graph leak across rescans (low)] —
  source/contrib/pg_trgm/trgm_gist.c:225-226,299 — acknowledged in
  comments; memory accumulates in fn_mcxt.
- [ISSUE-Style: triple switch on StrategyNumber (low)] — same as
  `trgm_gin.c`.
