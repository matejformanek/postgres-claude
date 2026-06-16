# ltree_op.c

## One-line summary

The ltree scalar operator suite: ordering (`<`/`<=`/`=`/`>=`/`>`, `<>` via `ltree_compare`), hash (`hash_ltree` + extended), structural predicates (`@>` / `<@` via `inner_isparent`), substring extraction (`subltree` / `subpath` / `ltree_index`), concatenation (`||` via `ltree_addltree` / `ltree_addtext` / `ltree_textadd`), longest-common-ancestor (`lca`), text round-trip (`text2ltree` / `ltree2text`), and the legacy `ltreeparentsel` selectivity stub. Also hosts the module's `PG_MODULE_MAGIC_EXT` block.

## Public API / entry points

All `PG_FUNCTION_INFO_V1` (registered at lines 22-43); each pairs with a SQL declaration in `ltree--1.x.sql`:

- `ltree_compare` (line 87) → `int4` — three-way comparison.
- `ltree_lt/le/eq/ge/gt/ne` (lines 94-134) — operators dispatched via `RUNCMP` macro.
- `hash_ltree` (line 137), `hash_ltree_extended` (line 167) — hash AM support; FNV-style accumulator `(h<<5)-h + level_hash`.
- `nlevel(ltree)` (line 202) — returns `numlevel`.
- `ltree_isparent` (line 236) → `bool` — `<@` / "is `p` a parent of `c`".
- `ltree_risparent` (line 248) — reverse operator.
- `subltree(ltree, start, end)` (line 300) — slice by `[start, end)` level positions.
- `subpath(ltree, start [, len])` (line 310) — slice by `[start, start+len)`, negative len/start handled (lines 319-325).
- `ltree_index(ltree haystack, ltree needle [, start])` (line 396) — first position where `needle` appears as a level-aligned substring.
- `ltree_addltree`, `ltree_addtext`, `ltree_textadd` (lines 358, 371, 456) — concat variants.
- `lca(ltree, ltree[, ltree...])` (line 562) — variadic LCA; NULL on empty result.
- `text2ltree`, `ltree2text` (lines 583, 600).
- `ltreeparentsel` (line 637) — selectivity for `<@` / `@>`; **no longer called** if the extension is at v1.2+ (comment at line 633-636). Falls through to `generic_restriction_selectivity` with default 0.001.

Helpers exposed via `ltree.h`:

- `int ltree_compare(const ltree *a, const ltree *b)` (line 46).
- `bool inner_isparent(const ltree *c, const ltree *p)` (line 213).
- `ltree *lca_inner(ltree **a, int len)` (line 487).

Internal:

- `static ltree *inner_subltree(ltree *t, int32 startpos, int32 endpos)` (line 261).
- `static ltree *ltree_concat(ltree *a, ltree *b)` (line 335).

## Key invariants

- INV-COMPARE-LEXICOGRAPHIC: `ltree_compare` (line 46) compares level-by-level using `memcmp` on label bytes, then by level count. Tie-breaking factor `* 10 * (an + 1)` (lines 60, 68, 77) returns a non-zero magnitude indicating "where" they differ — but only the sign matters for sort. **Comparison is BYTE-wise, not locale-aware**, so two labels that fold to the same string under a UTF-8 locale (`Foo` vs `foo`) sort distinctly. `[verified-by-code]`
- INV-HASH-EMPTY-LTREE: empty ltree (`numlevel == 0`) returns `result = 1` (line 141, kept by the while loop never executing). `hash_ltree_extended` matches by returning `1 + seed` (line 185) — **note that `hash_ltree(empty) = 1` but `hash_ltree_extended(empty, 0) = 1`** (low 32 bits match, fulfilling the hash AM contract that extended-with-seed-0 == basic for low 32 bits). `[from-comment + verified-by-code]`
- INV-HASH-LEVEL-COMBINE: `result = (result << 5) - result + levelHash` — multiplies by 31. Borrowed from `hash_array` (comment lines 152-155). `[from-comment]`
- INV-CONCAT-MAXLEVEL: `ltree_concat` rejects `a.numlevel + b.numlevel > LTREE_MAX_LEVELS` at line 341. `[verified-by-code]`
- INV-SUBLTREE-BOUNDS: `inner_subltree` rejects negative `startpos`/`endpos` and `startpos >= numlevel` and `startpos > endpos` at line 270. Clips `endpos > numlevel` silently to `numlevel` at line 275. `[verified-by-code]`
- INV-INNER-ISPARENT-PREFIX: `inner_isparent(c, p)` is true iff `p`'s levels are a byte-exact prefix of `c`'s levels (lines 213-234). Quick-rejects when `p.numlevel > c.numlevel`. `[verified-by-code]`
- INV-LCA-RETURNS-NULL: `lca_inner` returns NULL when there are no inputs, any input has `numlevel == 0`, OR the common prefix is empty (`num == 0` after the loop). `lca` propagates NULL via `PG_RETURN_NULL` (line 580). `[verified-by-code]`

## Notable internals

- `RUNCMP` macro (lines 80-85) is shared by the six comparison operators — `PG_GETARG_LTREE_P` both sides + call `ltree_compare` + `PG_FREE_IF_COPY` both sides.
- The "magnitude" factor `* 10 * (an + 1)` in `ltree_compare` is unusual: it makes the return value carry rough information about WHERE the strings diverged (high values = diverge early). But only the sign is used. Could just return `-1/0/1`. Historical; not load-bearing.
- `ltree_index` (line 396) is a naive O(N×M) substring search: for each starting level position in `a`, try to byte-match all of `b`. With `numlevel` up to 65535 in each, worst case ~4 billion byte compares — but `LEVEL_NEXT` advances per level, and the inner loop breaks on first mismatch, so realistic cost is much lower.
- `ltree_addtext` (line 371) and `ltree_textadd` (line 456) both go through `ltree_in` via `DirectFunctionCall1` — i.e. text concatenation re-parses the text side. This subjects the text portion to all the parser checks (label charset, length, MAX_LEVELS).
- `lca_inner` (line 487) compares each input to `a[0]` rather than maintaining a true running prefix. Starts with `num = a[0]->numlevel - 1` (line 505) — note the `-1`: LCA cannot include the LAST level (since for two equal ltrees the LCA is the prefix minus the last level — wait, actually no, see ISSUE below).
- `ltreeparentsel` (line 637) is a deprecated stub kept for v1.1 extension users. Returns 0.001 default. `[from-comment]`

## Trust boundary / Phase D surface

- **No parsers, no recursion**: all operators here are iterative O(N) or O(N×M) over the ltree level array. No DoS class beyond memory allocation.
- **`ltree_addtext` re-parses text** (line 380-385): subject to full parser semantics including the memory-amplification class noted in `ltree_io.c.md`. A `select 'a' || '<malicious text>'::text` builds a text payload then re-parses it; the parser DoS surface is inherited.
- **`hash_ltree` uses `hash_any`** (line 147) — Jenkins hash, not crypto. No collision attacks of relevance: `hash_ltree` is only used for HASH index support and partition routing. CRC32 is reserved for GiST signatures (`crc32.c`). No overlap.
- **`ltree_compare` is byte-wise, but ltree input parsing is locale-aware**: a value that parses successfully under `lc_ctype = en_US.UTF-8` may have multibyte characters. The byte-wise compare orders them by byte sequence, NOT by locale collation. Consistent with `text` storage but inconsistent with `text` collation. **A `WHERE ltree_col < 'café'::ltree` query returns rows by byte order, not by `lc_collate` order.** `[verified-by-code]`
- **`subpath` and `subltree` accept user int32 positions** (lines 311-315). Negative starts handled by `start = numlevel + start` (lines 319-321) — if `start` is extremely negative (e.g. INT_MIN), `numlevel + start` underflows to INT_MIN + numlevel. The check `startpos < 0` at line 270 catches that. `len < 0` triggers `end = numlevel + len` (line 322) which similarly checks at line 270. `[verified-by-code]`
- **`lca` with many args**: `lca` is variadic (declared in SQL with up to 8 args; `lca(ltree[])` variant is in `_ltree_op.c:292`). Each arg is detoasted and held in memory via `palloc_array(ltree *, fcinfo->nargs)` (line 569). Fine; `fcinfo->nargs` is hard-capped by FUNC_MAX_ARGS.
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

- [ISSUE-doc: lines 60, 68, 77 — the `* 10 * (an + 1)` magnitude in `ltree_compare` looks deliberate but only the SIGN is used. A new reader might assume the magnitude is meaningful. (nit — would be cleaner as `return -1/0/1`)] — `source/contrib/ltree/ltree_op.c:60`.
- [ISSUE-correctness: `lca_inner` (line 487) starts with `num = (*a)->numlevel - 1` — i.e. excludes the LAST level. But documented behavior of `lca` is "longest common ancestor", which for `{'a.b.c', 'a.b.c'}` should arguably be `a.b.c` (the values themselves). With `num = numlevel - 1`, `lca('a.b.c', 'a.b.c') = 'a.b'`. **This is intentional**: LCA in tree terminology excludes the node itself when both are equal. Documented in the user-facing manual (`doc/src/sgml/ltree.sgml`). But the `-1` is surprising; deserves a code comment. (nit)] — `source/contrib/ltree/ltree_op.c:505`.
- [ISSUE-cost: `ltree_index` (line 396) is O(N×M) naive substring search across ltree levels. With both at 65535 levels of 1-byte labels each, worst case ~4 billion byte-compares (though typically way less due to early break). No `CHECK_FOR_INTERRUPTS()` in the loop. (likely — bounded but not interruptible)] — `source/contrib/ltree/ltree_op.c:425-446`.
- [ISSUE-correctness: `subpath` with `start = INT32_MIN` and `len = INT32_MIN` would compute `start = numlevel + INT32_MIN` (signed overflow, undefined behavior in C). In practice on 2's-complement the underflow gives a large positive number, which `startpos < 0` doesn't catch (it became positive). But `startpos >= t->numlevel` at line 270 catches the unreachable index. (nit — relies on UB; should use saturating arithmetic)] — `source/contrib/ltree/ltree_op.c:319-321`.
- [ISSUE-correctness: `subltree` allows `endpos > numlevel` and silently clips at line 275-276 (`if (endpos > t->numlevel) endpos = t->numlevel;`). Inconsistent with `startpos >= numlevel → ERROR` at line 270. The asymmetry is intentional (slice-past-end is a common request) but surprising. (nit)] — `source/contrib/ltree/ltree_op.c:270-276`.
- [ISSUE-deprecation: `ltreeparentsel` (line 637) is dead code per its own comment (line 633-636): "This function is not used anymore, if the ltree extension has been updated to 1.2 or later." Kept for older-version compatibility. (nit — known deprecation)] — `source/contrib/ltree/ltree_op.c:633-651`.
- [ISSUE-correctness: `hash_ltree_extended` empty-tree path (line 182-186) returns `1 + seed` — the comment explains the low-32-bits match. But the return is `result + seed` where `result = 1`, so it's correct. Minor: the comment refers to "result + seed" but the code writes `PG_RETURN_UINT64(result + seed)`. Consistent. (verification only — code matches comment)] — `source/contrib/ltree/ltree_op.c:185`.
