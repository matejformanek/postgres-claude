# ltree_op.c

- **Source:** `source/contrib/ltree/ltree_op.c` (689 lines)
- **Last verified commit:** `ab3023ad1e68` (re-verified 2026-06-19 by
  pg-quality-auditor AUDIT mode after anchor-bump
  `e5f94c4808fe..ab3023ad1e68`. Commit `3f328049` ("Fix int32 overflow
  in ltree_compare") **restructured the comparator**: `ltree_compare`
  is now a clean byte-wise comparator that returns small int
  differences only; the old magnitude return value was split off into a
  new `float ltree_compare_distance`. Every definition line below
  shifted ~+38–50 lines vs the prior `b78cd2bda5b1` cites; all updated.)
- **Depth:** read (re-read after the 3f328049 restructure)

## One-line summary

The ltree scalar operator suite: ordering (`<`/`<=`/`=`/`>=`/`>`, `<>` via `ltree_compare`), hash (`hash_ltree` + extended), structural predicates (`@>` / `<@` via `inner_isparent`), substring extraction (`subltree` / `subpath` / `ltree_index`), concatenation (`||` via `ltree_addltree` / `ltree_addtext` / `ltree_textadd`), longest-common-ancestor (`lca`), text round-trip (`text2ltree` / `ltree2text`), and the legacy `ltreeparentsel` selectivity stub. Also hosts the module's `PG_MODULE_MAGIC_EXT` block (line 16).

## Public API / entry points

All `PG_FUNCTION_INFO_V1` (registered at lines 22-43); each pairs with a SQL declaration in `ltree--1.x.sql`:

- `ltree_cmp` (line 125) → `int4` — three-way comparison; thin wrapper over the `ltree_compare` C helper (line 49).
- `ltree_lt/le/eq/ge/gt/ne` (lines 132, 139, 146, 153, 160, 167) — operators dispatched via `RUNCMP` macro.
- `hash_ltree` (line 175), `hash_ltree_extended` (line 205) — hash AM support; FNV-style accumulator `(h<<5)-h + level_hash`.
- `nlevel(ltree)` (line 240) — returns `numlevel`.
- `ltree_isparent` (line 274) → `bool` — `<@` / "is `p` a parent of `c`".
- `ltree_risparent` (line 286) — reverse operator.
- `subltree(ltree, start, end)` (line 338) — slice by `[start, end)` level positions.
- `subpath(ltree, start [, len])` (line 348) — slice by `[start, start+len)`, negative len/start handled (lines 356-364).
- `ltree_index(ltree haystack, ltree needle [, start])` (line 434) — first position where `needle` appears as a level-aligned substring.
- `ltree_addltree`, `ltree_addtext`, `ltree_textadd` (lines 396, 409, 494) — concat variants.
- `lca(ltree, ltree[, ltree...])` (line 600) — variadic LCA; NULL on empty result.
- `text2ltree`, `ltree2text` (lines 621, 638).
- `ltreeparentsel` (line 675) — selectivity for `<@` / `@>`; **no longer called** if the extension is at v1.2+ (comment at lines 671-672). Falls through to `generic_restriction_selectivity` (line 684) with default 0.001.

Helpers exposed via `ltree.h`:

- `int ltree_compare(const ltree *a, const ltree *b)` (line 49) — the btree-comparison function; byte-wise, returns small int differences only (post-3f328049).
- `float ltree_compare_distance(const ltree *a, const ltree *b)` (line 83) — **new in 3f328049**; carries the old "magnitude" semantics (`* 10.0 * (an + 1)`), but as a `float` so it cannot int32-overflow. Sign is consistent with `ltree_compare`.
- `bool inner_isparent(const ltree *c, const ltree *p)` (line 250).
- `ltree *lca_inner(ltree **a, int len)` (line 525).

Internal:

- `static ltree *inner_subltree(ltree *t, int32 startpos, int32 endpos)` (line 299).
- `static ltree *ltree_concat(ltree *a, ltree *b)` (line 373).

## Key invariants

- INV-COMPARE-LEXICOGRAPHIC: `ltree_compare` (line 49) compares level-by-level using `memcmp` on label bytes (line 60), breaks ties on label length (`(int) al->len - (int) bl->len`, line 64), then on level count (`a->numlevel - b->numlevel`, line 75). It returns only small int differences — **the magnitude trick was removed by 3f328049 to avoid int32 overflow.** **Comparison is BYTE-wise, not locale-aware**, so two labels that fold to the same string under a UTF-8 locale (`Foo` vs `foo`) sort distinctly. `[verified-by-code]`
- INV-COMPARE-DISTANCE-FLOAT: `ltree_compare_distance` (line 83) keeps the old "where did they diverge" magnitude (`* 10.0 * (an + 1)` at lines 98, 103, 105, 114) but computes it in `float`, so a deep tree can no longer overflow the result. Only the sign is consumed by callers; the magnitude is GiST-penalty flavour. `[verified-by-code]`
- INV-HASH-EMPTY-LTREE: empty ltree (`numlevel == 0`) returns `result = 1` (line 178, kept by the while loop never executing). `hash_ltree_extended` matches by returning `1 + seed` (line 209 init `result = 1`) — low 32 bits match, fulfilling the hash AM contract that extended-with-seed-0 == basic for low 32 bits. `[from-comment + verified-by-code]`
- INV-HASH-LEVEL-COMBINE: `result = (result << 5) - result + levelHash` (line 193) — multiplies by 31. Borrowed from `hash_array` (comment lines 186-191). `[from-comment]`
- INV-CONCAT-MAXLEVEL: `ltree_concat` rejects `a.numlevel + b.numlevel > LTREE_MAX_LEVELS` at line 378. `[verified-by-code]`
- INV-SUBLTREE-BOUNDS: `inner_subltree` rejects negative `startpos`/`endpos` and `startpos >= numlevel` and `startpos > endpos` at line 307. Clips `endpos > numlevel` silently to `numlevel` at lines 312-313. `[verified-by-code]`
- INV-INNER-ISPARENT-PREFIX: `inner_isparent(c, p)` is true iff `p`'s levels are a byte-exact prefix of `c`'s levels (lines 250-271). Quick-rejects when `p.numlevel > c.numlevel` (line 256). `[verified-by-code]`
- INV-LCA-RETURNS-NULL: `lca_inner` (line 525) returns NULL when there are no inputs (line 536), any input has `numlevel == 0` (lines 538, 548), OR the common prefix is empty. `lca` propagates NULL via `PG_RETURN_NULL` (line 617). `[verified-by-code]`

## Notable internals

- `RUNCMP` macro (line 117) is shared by the six comparison operators — `PG_GETARG_LTREE_P` both sides + call `ltree_compare` + `PG_FREE_IF_COPY` both sides.
- The "magnitude" factor `* 10 * (an + 1)` no longer lives in the sort comparator — 3f328049 moved it into `ltree_compare_distance` (line 83) and cast it to `float` precisely because, for ltrees with up to 65535 levels, `(numlevel diff) * 10 * (an + 1)` overflowed int32. Only the sign is used by sort; the distance flavour is for GiST.
- `ltree_index` (line 434) is a naive O(N×M) substring search: for each starting level position in `a` (loop at line 462), try to byte-match all of `b` (inner loop at line 468). With `numlevel` up to 65535 in each, worst case ~4 billion byte compares — but `LEVEL_NEXT` advances per level, and the inner loop breaks on first mismatch, so realistic cost is much lower.
- `ltree_addtext` (line 409) and `ltree_textadd` (line 494) both go through `ltree_in` via `DirectFunctionCall1` — i.e. text concatenation re-parses the text side. This subjects the text portion to all the parser checks (label charset, length, MAX_LEVELS).
- `lca_inner` (line 525) compares each input to `a[0]` rather than maintaining a true running prefix. Starts with `num = (*a)->numlevel - 1` (line 542) — note the `-1`: LCA excludes the last level (the node itself, in tree terminology).
- `ltreeparentsel` (line 675) is a deprecated stub kept for v1.1 extension users. Returns 0.001 default. `[from-comment]`

## Trust boundary / Phase D surface

- **No parsers, no recursion**: all operators here are iterative O(N) or O(N×M) over the ltree level array. No DoS class beyond memory allocation.
- **`ltree_addtext` re-parses text**: subject to full parser semantics including the memory-amplification class noted in `ltree_io.c.md`. A `select 'a' || '<malicious text>'::text` builds a text payload then re-parses it; the parser DoS surface is inherited.
- **`hash_ltree` uses `hash_any`** (line 184) — Jenkins hash, not crypto. No collision attacks of relevance: `hash_ltree` is only used for HASH index support and partition routing. CRC32 is reserved for GiST signatures (`crc32.c`). No overlap.
- **`ltree_compare` is byte-wise, but ltree input parsing is locale-aware**: a value that parses successfully under `lc_ctype = en_US.UTF-8` may have multibyte characters. The byte-wise compare orders them by byte sequence, NOT by locale collation. **A `WHERE ltree_col < 'café'::ltree` query returns rows by byte order, not by `lc_collate` order.** `[verified-by-code]`
- **`subpath` and `subltree` accept user int32 positions**. Negative starts handled by `start = numlevel + start` (line 357) — if `start` is extremely negative (e.g. INT_MIN), `numlevel + start` underflows. The check `startpos < 0` at line 307 catches that. `len < 0` triggers `end = numlevel + len` (line 360) which similarly checks at line 307. `[verified-by-code]`
- **`lca` with many args**: `lca` is variadic; the array variant `lca(ltree[])` is in `_ltree_op.c:292`. Each arg is detoasted and held in memory via `palloc_array(ltree *, fcinfo->nargs)` (line 606). Fine; `fcinfo->nargs` is hard-capped by FUNC_MAX_ARGS.
- **No issue with embedded NULs**: comparisons use `memcmp` with explicit lengths; concat memcpys with known length; output via `ltree_out`/`ltree2text` uses the same. NULs cannot appear in label bytes anyway because the parser rejects them (`ISLABEL` is false for 0x00).

## Cross-references

- `source/contrib/ltree/ltree_io.c:36` — `parse_ltree` reached via `ltree_in` in `ltree_addtext`.
- `source/contrib/ltree/ltree.h:33-52` — `ltree_level` / `ltree` layouts.
- `source/contrib/ltree/_ltree_op.c:292` — `_lca` array variant.
- `source/src/backend/utils/hash/hashfn.c` — `hash_any` / `hash_any_extended`.
- `source/src/backend/utils/adt/selfuncs.c` — `generic_restriction_selectivity`.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-RESOLVED: the int32 overflow in the old `ltree_compare` magnitude return (`(numlevel diff) * 10 * (an + 1)`) was **fixed upstream by `3f328049`** (anchor-bump `e5f94c4808fe..ab3023ad1e68`): the sort comparator now returns only small int differences (line 49), and the magnitude logic was split into a `float ltree_compare_distance` (line 83) that cannot overflow. The prior doc's ISSUE-doc nit about the magnitude is obsolete.] — `source/contrib/ltree/ltree_op.c:49,83`.
- [ISSUE-correctness: `lca_inner` (line 525) starts with `num = (*a)->numlevel - 1` (line 542) — i.e. excludes the LAST level. So `lca('a.b.c', 'a.b.c') = 'a.b'`. **This is intentional**: LCA in tree terminology excludes the node itself when both are equal. Documented in `doc/src/sgml/ltree.sgml`. But the `-1` is surprising; deserves a code comment. (nit)] — `source/contrib/ltree/ltree_op.c:542`.
- [ISSUE-cost: `ltree_index` (line 434) is O(N×M) naive substring search across ltree levels (loops at lines 462/468). With both at 65535 levels of 1-byte labels each, worst case ~4 billion byte-compares (though typically way less due to early break). No `CHECK_FOR_INTERRUPTS()` in the loop. (likely — bounded but not interruptible)] — `source/contrib/ltree/ltree_op.c:462-476`.
- [ISSUE-correctness: `subpath` with `start = INT32_MIN` would compute `start = numlevel + INT32_MIN` (signed overflow, UB in C). On 2's-complement the underflow gives a large positive number, which `startpos < 0` doesn't catch (it became positive). But `startpos >= t->numlevel` at line 307 catches the unreachable index. (nit — relies on UB; should use saturating arithmetic)] — `source/contrib/ltree/ltree_op.c:356-357`.
- [ISSUE-correctness: `subltree` allows `endpos > numlevel` and silently clips at lines 312-313 (`if (endpos > t->numlevel) endpos = t->numlevel;`). Inconsistent with `startpos >= numlevel → ERROR` at line 307. The asymmetry is intentional (slice-past-end is a common request) but surprising. (nit)] — `source/contrib/ltree/ltree_op.c:307-313`.
- [ISSUE-deprecation: `ltreeparentsel` (line 675) is dead code per its own comment (lines 671-672): "This function is not used anymore, if the ltree extension has been updated to 1.2 or later." Kept for older-version compatibility. (nit — known deprecation)] — `source/contrib/ltree/ltree_op.c:671-675`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-ltree.md](../../../subsystems/contrib-ltree.md)
