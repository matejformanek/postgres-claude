# _ltree_gist.c

## One-line summary

The `gist__ltree_ops` GiST opclass for `ltree[]` (arrays of ltree). Uses a **pure signature-tree** key (no left/right boundaries — unlike scalar `gist_ltree_ops`), with `LTREE_ASIGLEN_DEFAULT = 28 bytes = 224 bits` signature. Picksplit is the classic GiST "two-seeds, sort-by-cost, greedy-assign" Hamming-distance algorithm; union is OR-of-signatures; consistent is signature-bit-existence checks for each strategy. **All searches set `recheck = true`** because the signature filter is approximate.

## Public API / entry points

GiST opclass support functions:

- `Datum _ltree_compress(PG_FUNCTION_ARGS)` (line 49) — converts `ltree[]` leaf array into a signature by hashing every level of every element. Also handles the "saturated" optimization (lines 85-102): if a non-leaf signature is all `0xff` already, replace with `LTG_ALLTRUE` flag-only.
- `Datum _ltree_same(PG_FUNCTION_ARGS)` (line 107) — byte-equal signature compare; both ALLTRUE → true; one ALLTRUE → false.
- `Datum _ltree_union(PG_FUNCTION_ARGS)` (line 154) — OR-reduces signatures; flips to ALLTRUE on first ALLTRUE input.
- `Datum _ltree_penalty(PG_FUNCTION_ARGS)` (line 218) — penalty = Hamming distance between signatures.
- `Datum _ltree_picksplit(PG_FUNCTION_ARGS)` (line 242) — classic two-seed algorithm: find the most-distant pair, then greedily assign each remaining entry to the closer seed (with tie-breaking via `WISH_F`).
- `Datum _ltree_consistent(PG_FUNCTION_ARGS)` (line 504) — strategy dispatch (10-17). **`*recheck = true`** at line 518.
- `Datum _ltree_gist_options(PG_FUNCTION_ARGS)` (line 547) — `siglen` reloption default 28 bytes, max `GISTMaxIndexKeySize`. **Min is `1` here** (line 553) vs `INTALIGN(1)` in scalar variant (`ltree_gist.c:744`).

Internal:

- `static void hashing(BITVECP sign, ltree *t, int siglen)` (line 33) — CRCs each level of one ltree into the signature.
- `static int32 unionkey(BITVECP sbase, ltree_gist *add, int siglen)` (line 140) — OR-in one key.
- `static int32 sizebitvec(...)` (line 179) — `pg_popcount`.
- `static int hemdistsign/hemdist(...)` (lines 185, 200) — Hamming distance between two signatures (handles ALLTRUE).
- `static bool gist_te(ltree_gist *key, ltree *query, int siglen)` (line 387) — for strategy 10/11, checks every level of `query` has its CRC bit set in `key`'s signature.
- `static bool gist_qe(ltree_gist *key, lquery *query, int siglen)` (line 440) — same as scalar but using `AHASHVAL`.
- `static bool gist_qtxt(...)` (line 424) — runs `ltree_execute` with signature-bit callback.
- `static bool _arrq_cons(...)` (line 479) — OR over lquery[] array.

## Key invariants

- INV-NO-BOUNDARIES: unlike `ltree_gist.c`, keys here do NOT carry left/right ltree boundaries. `_ltree_compress` allocates with `left=NULL, right=NULL` (line 71), `ltree_gist_alloc` skips the ONENODE branch and only writes the signature. So `LTG_ONENODE`, `LTG_LNODE`, `LTG_RNODE` are never used in this opclass. `[verified-by-code]`
- INV-RECHECK-TRUE-ALWAYS: `_ltree_consistent` sets `*recheck = true` at line 518 unconditionally. Every signature match is rechecked at the leaf via the underlying scalar operator. `[verified-by-code]`
- INV-ASIGLEN-DEFAULT-28: `LTREE_ASIGLEN_DEFAULT = 7 * sizeof(int32) = 28 bytes = 224 bits` (`ltree.h:296`). The scalar opclass uses 8 bytes. Larger because arrays cover more labels per row.
- INV-ASIGLEN-MIN-1: `add_local_int_reloption` at line 553 passes `1` as min vs `INTALIGN(1)=4` in the scalar opclass (`ltree_gist.c:744`). **Asymmetry** — array opclass allows non-aligned siglens. Also no `register_reloptions_validator` call in `_ltree_gist_options` (compare line 747 in `ltree_gist.c`). `[verified-by-code]`
- INV-SATURATION-IN-COMPRESS: `_ltree_compress` (line 85-102) checks AFTER any inner-node operation whether the signature is fully saturated (`(sign[i] & 0xff) != 0xff` for all bytes → fully saturated). If so, converts to ALLTRUE. This is a post-hoc optimization; `_ltree_union` (line 167-170) does the same check inline. `[verified-by-code]`

## Notable internals

- `_ltree_compress` is more complex than the scalar variant: at LEAF level, it iterates the `ltree[]` array elements (line 73-78) and hashes each one's levels into a single shared signature. **No per-element separation** — the index loses the multiplicity. A row with `ARRAY['a.b', 'c.d']` produces the same signature as `ARRAY['a.b', 'c.d', 'a.b', 'a.b']`.
- The `ARR_NDIM > 1` and `array_contains_nulls` checks at lines 62-69 reject multi-dim and NULL-bearing arrays with hard `ereport(ERROR)`.
- `hemdist` (line 200) is the Hamming distance with three cases: both ALLTRUE → 0; one ALLTRUE → `total_bits - popcount(other)`; otherwise byte-by-byte XOR + popcount.
- `_ltree_picksplit` (line 242) is the classic Guttman quadratic algorithm: O(n²) pair-comparison to find the two most-distant seeds (lines 274-287), then a sorted-by-cost greedy assignment (lines 311-376). `WISH_F` (line 29) is a balance-encouraging term that adds a small bias against very lopsided splits.
- The cost vector at line 311-319 is `abs(hemdist(left_seed, candidate) - hemdist(right_seed, candidate))` — entries whose closeness to one seed is much greater than to the other are placed first (clearer assignment).
- `gist_te` (line 387) is unique to this opclass: tests if EVERY level of `query` exists in the signature. For `<@` strategy 10/11 on `ltree[]`, this is the inner-node filter — "all of the query's labels must be in some element of the indexed array".

## Trust boundary / Phase D surface — `ltree[]` array-element-count caps

- **`ltree[]` array element count is `ArrayGetNItems(...)`** at line 59. This is bounded by the array varlena structure — `MaxAllocSize / sizeof(min-ltree)`. With min ltree size ~12 bytes (header + one 1-char level), max ~85 million elements per array. **A single index entry could thus hash 85M ltrees in a tight loop.** Per-hash cost: O(per-element levels × per-level len). For a single large `ltree[]`, compress could take significant CPU. `[inferred + verified-by-code]`
- **`_ltree_compress` is O(total_levels_across_all_array_elements)**: with 85M elements × 65K levels each = 5.5 trillion `ltree_crc32_sz` calls per compress. Far worse than the scalar variant. No `CHECK_FOR_INTERRUPTS()` in the loop (lines 73-78). **Per-insert DoS class on pathological `ltree[]` arrays.**
- **No per-element count cap**: nothing in this file (or `array.c`) caps the per-row `ltree[]` element count. Only `MaxAllocSize` of the array varlena. **A 1-GB `ltree[]` with millions of paths is legal input.** `[verified-by-code]`
- **Signature saturation forces full scans**: with `LTREE_ASIGLEN_DEFAULT = 224 bits`, fpr at saturation ~50% requires ~155 distinct labels per row's array contents (birthday paradox). A row with an `ltree[]` containing 100 paths of ~5 levels each → 500 hash insertions → very likely saturated. **Default index is unusable on realistic `ltree[]` data.** Mitigation: raise `siglen` via reloption.
- **Approximation always rechecked at leaf** (`recheck=true` at line 518): no correctness risk from collisions. Pure performance.
- **`pg_popcount` is fast** but is called inside `hemdist` for every penalty/picksplit comparison. With 224-bit signature and ~120 entries per page, picksplit's O(n²) pair search does ~14400 popcounts per split. Tolerable.
- **No interrupt checks in `_ltree_picksplit`**: the O(n²) loop (lines 274-287) is not interruptible. With page-bounded entryvec size (~120 entries) this is fine; only matters during index BUILD which has its own interrupt checks at the per-tuple level in `gistbuild.c`.
- **The reloption validator is missing**: compare `ltree_gist_options` at `ltree_gist.c:747` which calls `register_reloptions_validator(relopts, ltree_gist_relopts_validator)`. The array variant does NOT (line 547-557). So a user could in principle pass `siglen = 3` (non-INTALIGN'd) — the macros assume INTALIGN'd signature storage, behavior would be silently wrong on platforms where alignment matters. `[verified-by-code]`

## Cross-references

- `source/contrib/ltree/ltree.h:294-307` — `LTREE_ASIGLEN_*`, `AHASH`, `AHASHVAL`.
- `source/contrib/ltree/ltree_gist.c` — sibling scalar opclass.
- `source/contrib/ltree/_ltree_op.c` — the SQL operator suite for `ltree[]`.
- `source/contrib/ltree/lquery_op.c:263,287` — `ltq_regex`, `lt_q_regex` called for leaf recheck.
- `source/contrib/ltree/ltxtquery_op.c:82` — `ltxtq_exec`.
- `source/contrib/ltree/crc32.c` — `ltree_crc32_sz`.
- `source/src/include/port/pg_bitutils.h` — `pg_popcount`, `pg_number_of_ones[256]`.
- `source/src/include/utils/array.h` — `ARR_NDIM`, `ARR_DIMS`, `ArrayGetNItems`, `array_contains_nulls`.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `_ltree_compress` (lines 73-78) hashes every level of every element of an `ltree[]` array per insert/update. With a 1-GB `ltree[]` argument (allowed by `MaxAllocSize`), this is hours of CPU. **No `CHECK_FOR_INTERRUPTS()` in the loop.** A single INSERT could pin the backend uncancellably. (likely — per-call DoS, requires malicious large `ltree[]` input)] — `source/contrib/ltree/_ltree_gist.c:73-78`.
- [ISSUE-security: no per-row cap on `ltree[]` element count for indexing. `MaxAllocSize / sizeof(min-ltree) ≈ 85M` elements per row. Each contributes O(levels) hash ops. Even with `siglen` at max, the work is O(N × levels) and unbounded. (likely — pairs with the previous)] — `source/contrib/ltree/_ltree_gist.c:59`.
- [ISSUE-correctness: `_ltree_gist_options` (line 547) is missing `register_reloptions_validator`. A user passing `siglen = 3` would silently get a non-INTALIGN'd signature. The macros (`AHASH`, `AHASHVAL`) assume word-aligned access. Compare `ltree_gist_options` at `ltree_gist.c:747`. (likely — minor robustness)] — `source/contrib/ltree/_ltree_gist.c:547-557`.
- [ISSUE-correctness: `_ltree_gist_options` (line 553) uses `1` as siglen min vs `INTALIGN(1)=4` in scalar `ltree_gist.c:744`. Asymmetric. With a `siglen=1` 8-bit signature, the index becomes nearly useless but does not crash. (nit)] — `source/contrib/ltree/_ltree_gist.c:553`.
- [ISSUE-cost: default `siglen = 28 bytes = 224 bits` is too small for typical `ltree[]` data (rows with 50+ paths saturate). Raising to 1 KB (8000 bits) would handle ~5000-label rows with fpr ~30%. **No DBA-facing guidance**; the only mention is the reloption. (likely — perf foot-gun, same flavor as scalar opclass)] — `source/contrib/ltree/_ltree_gist.c:553`.
- [ISSUE-correctness: signatures are aggregated WITHOUT distinguishing array element boundaries — two arrays `['a.b.c']` and `['a','b','c']` produce IDENTICAL signatures (all three labels are CRC'd in either case). The signature filter cannot distinguish them. Leaf recheck IS correct (uses full lquery match against each array element). (verification only — known approximation)] — `source/contrib/ltree/_ltree_gist.c:73-78`.
- [ISSUE-API-shape: strategies 10-17 use bare integers (lines 522-537); no symbolic names. Parallel issue to `ltree_gist.c:666`. (nit)] — `source/contrib/ltree/_ltree_gist.c:522-537`.
- [ISSUE-correctness: `_arrq_cons` (line 493-500) on `ltree[]` queries against `ltree[]` index entries iterates the query array and applies `gist_qe`. Each `gist_qe` is the conservative "all simple-match levels' bits are set" check. If the indexed `ltree[]` has a saturated signature (very likely under defaults), `_arrq_cons` returns true → recheck at leaf. So saturation collapses the filter to a full scan plus recheck cost. (likely — see signature saturation ISSUE above)] — `source/contrib/ltree/_ltree_gist.c:479-501`.
- [ISSUE-correctness: line 80, `_ltree_compress` builds the signature with `ltree_gist_alloc(false, NULL, siglen, NULL, NULL)` — the result has `left=NULL, right=NULL`. Look at `ltree_gist_alloc` in `ltree_gist.c:42-80`: this branch (siglen != 0, left == NULL) leaves the result with siglen bytes of zeroed signature and the (non-ONENODE) flag. Then `hashing()` ORs bits into it. Correct, but the API is double-purpose: `ltree_gist_alloc` is used for both single-node and signature-only allocation. (nit — API surface duplicated)] — `source/contrib/ltree/_ltree_gist.c:71-78`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-ltree.md](../../../subsystems/contrib-ltree.md)
