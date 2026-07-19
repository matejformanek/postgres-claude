# ltree_gist.c

## One-line summary

The `gist_ltree_ops` GiST opclass for the scalar `ltree` type — a hybrid B-tree + signature-tree key. Inner nodes carry both a `[left, right]` `ltree` range (for B-tree-style B-tree comparison strategies 1-5 and 10-11 isparent/isancestor) AND a CRC32-bit signature (for `~`, `?`, `@` strategies 12-17 lquery/ltxtquery/array). The picksplit is a midpoint cut over a sorted RIX array; union computes left=min, right=max, sign=OR-of-signs; consistent dispatches per strategy.

## Public API / entry points

GiST opclass support functions (registered via SQL in `ltree--1.x.sql`):

- `Datum ltree_compress(PG_FUNCTION_ARGS)` (line 94) — wraps `ltree` leaf values into `ltree_gist` with `LTG_ONENODE` flag.
- `Datum ltree_decompress(PG_FUNCTION_ARGS)` (line 113) — detoasts the key.
- `Datum ltree_same(PG_FUNCTION_ARGS)` (line 131) — exact equality of two `ltree_gist` keys.
- `Datum ltree_union(PG_FUNCTION_ARGS)` (line 192) — computes a covering key for a set; tracks min `left`, max `right`, and OR-of-signatures, with `ALLTRUE` shortcut when bitvec saturates.
- `Datum ltree_penalty(PG_FUNCTION_ARGS)` (line 261) — penalty = `Max(cmpl, 0) + Max(cmpr, 0)` (line 273) where `cmpl`/`cmpr` are **`ltree_compare_distance`** (float) on the boundary nodes (lines 270-271). Switched from the int `ltree_compare` to the float `ltree_compare_distance` by `3f328049` — the penalty genuinely needs the divergence *magnitude*, and that magnitude is precisely what was overflowing int32 before the fix split it into a float helper.
- `Datum ltree_picksplit(PG_FUNCTION_ARGS)` (line 294) — sorts entries by `LTG_GETLNODE` ltree value, splits at midpoint.
- `Datum ltree_consistent(PG_FUNCTION_ARGS)` (line 617) — main dispatch for 11 strategy numbers (1-5 B-tree-style, 10-17 ltree-specific).
- `Datum ltree_gist_options(PG_FUNCTION_ARGS)` (line 735) — registers the `siglen` reloption (default 8 bytes, max `GISTMaxIndexKeySize`).
- `Datum ltree_gist_in/out(PG_FUNCTION_ARGS)` (lines 22, 32) — internal type, always errors `cannot accept / display`.

Exported (cross-file):

- `ltree_gist *ltree_gist_alloc(bool isalltrue, BITVECP sign, int siglen, ltree *left, ltree *right)` (line 42) — single allocator for the three on-page shapes.

Internal:

- `static void hashing(BITVECP sign, ltree *t, int siglen)` (line 175) — CRCs each level and ORs the bit into `sign`.
- `static bool gist_isparent(ltree_gist *key, ltree *query, int siglen)` (line 423) — for strategy 10, tests if `query` could be a parent of any value in the [left,right] range.
- `static bool gist_ischild(ltree_gist *key, ltree *query, int siglen)` (line 453) — for strategy 11, tests if `query` could be a descendant.
- `static bool gist_qe(ltree_gist *key, lquery *query, int siglen)` (line 478) — lquery-vs-signature filter using `LQL_CANLOOKSIGN`.
- `static int gist_tqcmp(ltree *t, lquery *q)` (line 517) — partial compare against `q->firstgood` leading simple-match levels.
- `static bool gist_between(ltree_gist *key, lquery *query, int siglen)` (line 546) — uses `gist_tqcmp` to check the `[left,right]` range contains a possible match.
- `static bool gist_qtxt(...)` (line 575) — runs `ltree_execute` with `checkcondition_bit` (signature lookup) callback.
- `static bool arrq_cons(...)` (line 591) — OR-fold over an `lquery[]` array.

## Key invariants

- INV-LTG-ONENODE-LEAF-ONLY: `ltree_compress` (line 99-108) sets `LTG_ONENODE` only when `entry->leafkey` is true — i.e. leaves carry the literal ltree value, inner nodes carry signature + range. `[verified-by-code]`
- INV-SIGLEN-FROM-OPTION-OR-DEFAULT: every consistent-fn entry reads `LTREE_GET_SIGLEN()` (e.g. line 625) — returns 8 bytes default or the reloption value. `siglen` MUST be `INTALIGN`'d (line 729 validator). `[verified-by-code]`
- INV-ALLTRUE-SHORTCUT: `ltree_union` (line 240-251) checks if all bytes of the OR'd signature are `0xff` AFTER the loop; if so, sets `LTG_ALLTRUE` flag and drops the bitvec. Saves space + makes `gist_qe`/`gist_qtxt` return `true` quickly (lines 485, 580).
- INV-RECHECK-FALSE-FOR-EXACT-OPS: `ltree_consistent` sets `*recheck = false` at line 631. The B-tree-style strategies and `<@`/`@>` are EXACT — no rescan needed. **Note: this is suspicious for inner-node strategy 12-17 (lquery/ltxtquery/array) where the signature filter is FALSE-POSITIVE-prone**, but the leaf case (strategy 12-17 calls `ltq_regex`/`ltxtq_exec` on the full ltree, exact) and the inner case (gist_qe is a CONSERVATIVE filter, may return true when actual leaf is false, but never returns false when leaf is true). Recheck=false is correct because GiST guarantees that consistent=true at inner nodes leads to a descent and a re-call of consistent at leaves — and the leaf call IS exact. `[verified-by-code]`
- INV-LEAF-STRATEGY-USES-LTG_NODE: strategies 10-17 at leaves call `LTG_NODE(key)` (lines 669, 676, 685, 697, 708) — the literal ltree from the `LTG_ONENODE` form. The full operator function (`ltq_regex`, `ltxtq_exec`, etc.) is then dispatched via `DirectFunctionCall2`. `[verified-by-code]`
- INV-INNER-STRATEGY-USES-LTG_GETLNODE/GETRNODE: at inner nodes, strategies 1-5 / 10-11 do the B-tree-style boundary test against `LTG_GETLNODE` / `LTG_GETRNODE`; strategies 12-17 use `gist_qe + gist_between` for lquery, `gist_qtxt` for ltxtquery, `arrq_cons` for array. `[verified-by-code]`

## Notable internals

- **The hybrid B-tree+signature key** is the central design: inner nodes store both a [min, max] ltree range AND a Bloom-like CRC32 signature. The range supports prefix/range queries; the signature supports lquery's per-label-existence pruning. Two filters AND'd at inner-node level (`gist_qe(key, q) && gist_between(key, q)` at line 689).
- `LTG_NORIGHT` (line 66-68 in `ltree_gist_alloc`): when left == right (or ISEQ), the right node is aliased to the left to save space. `LTG_RNODE` (`ltree.h:286`) then returns the left.
- `gist_isparent` (line 423) is clever: it tries shorter prefixes of `query` (loop from `i = numlevel down to 0`) and checks if ANY prefix falls within [left, right]. If so, query's ancestors could appear in this subtree.
- `gist_qe` (line 478): for each query level, IF the level is "simple" (single variant, no flag bits in `LQL_CANLOOKSIGN` excluded set) AND the CRC bit for that variant is NOT set in the signature, fail. Otherwise pass. **A false-positive filter**: bit set ≠ value exists (it could be a CRC collision); bit unset = value definitely absent. `[verified-by-code]`
- `gist_tqcmp` (line 517) uses the `firstgood` count from lquery (set by parser at `ltree_io.c:535`) to do a prefix-bounded comparison. If the lquery starts with N simple levels, those levels can be lexicographically compared against the [left,right] ltree boundaries.
- `ltree_penalty` (line 261): penalty is the sum of how far the new key "stretches" the original key bounds. `Max(cmpl, 0) + Max(cmpr, 0)` — zero penalty if the new key falls inside [left, right], positive if it forces an expansion. **Signature stretching is NOT counted** — only the boundary stretching. So packing densely on the lexicographic axis is preferred over signature collision-avoidance.
- `ltree_picksplit` (line 294) sorts entries by `LTG_GETLNODE(...)` (their left-boundary ltree) and splits at the midpoint. Half the entries go left, half right. **Pure lexicographic split**; signature density is recomputed for both halves but doesn't influence the split point.

## Trust boundary / Phase D surface

- **Signature false-positive rate vs siglen**: with `LTREE_SIGLEN_DEFAULT = 8 bytes = 64 bits`, the signature has 64 buckets. By the Bloom-filter formula, with k=1 hash function and n labels indexed, false-positive probability is `1 - (1 - 1/64)^n`. For n=10 labels per entry, fpr ≈ 14.5%. For n=44 (signature half-full), fpr = 50%. **`gist_qe` calls `LTG_ISALLTRUE(key) → return true` (line 485)** — once any inner key saturates to ALLTRUE, lquery searches through that subtree are forced to recheck every leaf. Critical operational tuning knob.
- **No collision attacks on signature for security**: the signature is a performance index, not an authorization gate. False positives degrade index efficiency but cannot leak data — `ltq_regex` (in `lquery_op.c`) recomputes the match at the leaf with full precision. `[inferred from GiST architecture + verified-by-code]`
- **CRC32 used here is `ltree_crc32_sz`** — NOT a cryptographic hash, but also not used for any collision-resistance property. Used purely for spreading labels across signature bits. See `crc32.c.md`.
- **GiST inner-node format is on-disk**: every change to `ltree_gist` layout / `LTG_ALLTRUE` semantics / `siglen` defaults is a pg_upgrade concern. `LOWER_NODE` (`ltree.h:29`) is explicitly defined to preserve on-disk CRC compatibility.
- **No interrupt checks in opclass functions**: `ltree_union`, `ltree_picksplit`, `ltree_consistent` all loop without `CHECK_FOR_INTERRUPTS`. Loops are bounded by `entryvec->n` which is page-size limited (~120 entries typical for an 8KB GiST page). Not a DoS concern individually, but a long-running index build COULD benefit from interrupt checks at the per-tuple level. The caller (`gistbuild.c`) does have them.
- **`gist_isparent` modifies `query->numlevel` in-place** (line 431) — it later restores via `query->numlevel = numlevel` at line 435/440. The query was acquired via `PG_GETARG_LTREE_P_COPY` at line 667 (strategy 10), so the mutation is on a private copy. Safe but fragile if the strategy dispatch order changes. `[verified-by-code]`
- **`copy_ltree` in `gist_ischild` (line 444)** does palloc + memcpy on every inner-node consistency check for strategy 11. With a large index walk, that's a palloc per page per query. Bounded but allocator pressure.
- **`ltree_gist_relopts_validator`** rejects non-`INTALIGN(siglen)` values at line 730. So a user can pass `siglen = 5` and get an error at index-create time. `siglen = 4` is the minimum INTALIGN'd value. `siglen = LTREE_SIGLEN_MAX = GISTMaxIndexKeySize` ≈ 8K-ish allowed (depends on platform's MAXALIGN-tweaked GIST limit; commonly ~2700 bytes per current `gist.h`).

## Cross-references

- `source/contrib/ltree/ltree.h:256-313` — `ltree_gist`, `LTG_*` flags, `LtreeGistOptions`.
- `source/contrib/ltree/lquery_op.c:263,287` — `ltq_regex`, `lt_q_regex` called at leaves.
- `source/contrib/ltree/ltxtquery_op.c:82` — `ltxtq_exec` called at leaves.
- `source/contrib/ltree/ltree_op.c:250,49,83` — `inner_isparent`, `ltree_compare`, `ltree_compare_distance` (the last added by 3f328049, now used in `ltree_penalty`).
- `source/contrib/ltree/crc32.c` — `ltree_crc32_sz` used by `hashing` and `gist_te`/`gist_qe`.
- `source/contrib/ltree/_ltree_gist.c` — parallel implementation for `ltree[]`.
- `source/src/include/access/gist.h` — `GISTMaxIndexKeySize`, `GIST_LEAF`, `GISTENTRY`.
- `source/src/include/access/reloptions.h` — `init_local_reloptions`, `add_local_int_reloption`, `register_reloptions_validator`.
- `source/src/include/access/stratnum.h` — `BTLessStrategyNumber` etc.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-cost: default `siglen = 8 bytes = 64 bits` is far too small for realistic ltree workloads (anything > 10 labels saturates). The reloption raises it, but the default chosen pre-v13 was never revisited. **A new index with 1000-row data and default siglen typically has ALL inner nodes flipped to ALLTRUE within a few page splits**, after which lquery/ltxtquery searches scan every leaf. Cross-link: `ltree.h:236` for the constant. (likely — perf foot-gun, well-known in the ltree user community)] — `source/contrib/ltree/ltree_gist.c:736-746`.
- [ISSUE-correctness: `ltree_penalty` (line 273) ignores signature-stretch cost. Two entries with identical boundary ltrees but DIFFERENT signature bits get penalty=0 — `picksplit` then groups them by lexicographic boundary, not by signature density. **Subtrees can develop very heterogeneous signatures, defeating the signature filter entirely.** (likely — algorithmic)] — `source/contrib/ltree/ltree_gist.c:265-275`.
- [ISSUE-cost: `ltree_picksplit` (line 294) does `qsort` over up to ~120 entries per page (line 331). With many index inserts, this is `O(n log n)` per split; acceptable. (verification only)] — `source/contrib/ltree/ltree_gist.c:331-332`.
- [ISSUE-correctness: `gist_isparent` mutates `query->numlevel` in-place (line 431), restoring at lines 435/440. If the strategy 10 dispatch ever changes to not use `PG_GETARG_LTREE_P_COPY` (line 667), this would corrupt the caller's varlena. Fragile. A defensive `query = copy_ltree(query)` would be safer. (nit)] — `source/contrib/ltree/ltree_gist.c:429-441`.
- [ISSUE-API-shape: `ltree_consistent` strategies 10-17 use bare integer literals (lines 666, 673, 680, 692, 703). The `stratnum.h` defines `BTLessStrategyNumber` etc. for 1-5 but the ltree-specific strategies (10-17) have no symbolic names. Hard to grep for. (nit)] — `source/contrib/ltree/ltree_gist.c:666-714`.
- [ISSUE-doc: `LTG_NORIGHT` (line 65-68 in `ltree_gist_alloc`) saves space when left == right. Not documented at the struct definition in `ltree.h` beyond the macro name. The aliasing implication for callers is non-obvious. (nit)] — `source/contrib/ltree/ltree_gist.c:62-70`.
- [ISSUE-correctness: `ltree_same` (line 131) compares signatures byte-by-byte (lines 161-168) only if `!LTG_ISALLTRUE(a)`. If both keys are ALLTRUE, they're considered equal (line 158 returns `*result = true`) WITHOUT comparing boundaries. **Two ALLTRUE keys with DIFFERENT [left, right] boundaries would be considered "same"**. This is OK for picksplit logic but potentially incorrect for index maintenance — though in practice ALLTRUE means "any value possible", and the boundaries are still tracked in `LTG_LNODE`/`LTG_RNODE` which ARE compared at lines 153, 155. So actually NO: lines 153/155 do compare LNODE/RNODE even in the ALLTRUE branch. Re-reading: the ISEQ check at 153/155 runs unconditionally before the byte-by-byte signature compare. Confirmed correct. (verification only)] — `source/contrib/ltree/ltree_gist.c:131-173`.
- [ISSUE-cost: `arrq_cons` (line 606-613) iterates the lquery array calling `gist_qe + gist_between` for each. Short-circuit on first match. With a long `lquery[]` and ALLTRUE keys, this returns true on the first lquery → fast. With non-ALLTRUE keys, each `gist_qe` is O(numlevel × numvar). (nit)] — `source/contrib/ltree/ltree_gist.c:591-614`.
- [ISSUE-doc: line 666 strategy 10 uses `PG_GETARG_LTREE_P_COPY` while line 674 strategy 11 uses `PG_GETARG_LTREE_P` (no copy). Asymmetric because strategy 10 calls `gist_isparent` which mutates; strategy 11 calls `gist_ischild` which does its own copies internally. The asymmetry is correct but warrants a comment. (nit)] — `source/contrib/ltree/ltree_gist.c:667,674`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-ltree.md](../../../subsystems/contrib-ltree.md)
