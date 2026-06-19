# ltree.h

## One-line summary

Central header for the `ltree` / `lquery` / `ltxtquery` types plus the GiST opclass machinery: defines all three varlena layouts (`ltree` = sequence of `ltree_level`; `lquery` = sequence of `lquery_level` each carrying a list of `lquery_variant`s; `ltxtquery` = polish-notation `ITEM[]` + operand string), the `LTREE_MAX_LEVELS = PG_UINT16_MAX` and `LTREE_LABEL_MAX_CHARS = 1000` caps, the signature-bit GiST key (`ltree_gist`) with `LTG_ONENODE` / `LTG_ALLTRUE` / `LTG_NORIGHT` flag-encoded layouts, and the `LTREE_SIGLEN_DEFAULT = 8` / `LTREE_ASIGLEN_DEFAULT = 28` siglen defaults capped by `GISTMaxIndexKeySize`.

## Public API / entry points

Header-only — no functions defined. Declarations:

- `bool ltree_execute(ITEM *curitem, void *checkval, bool calcnot, bool (*chkcond)(void *, ITEM *))` (line 205) — the polish-notation walker, defined in `ltxtquery_op.c:20`.
- `int ltree_compare(const ltree *a, const ltree *b)` (line 208) — defined in `ltree_op.c:49`.
- `float ltree_compare_distance(const ltree *a, const ltree *b)` (line 209) — **added by `3f328049`** (the int32-overflow fix); carries the magnitude "distance" semantics the old `ltree_compare` returned, as a `float`. Defined in `ltree_op.c:83`.
- `bool inner_isparent(const ltree *c, const ltree *p)` (line 210) — defined in `ltree_op.c:250`.
- `bool compare_subnode(ltree_level *t, char *qn, int len, bool prefix, bool ci)` (line 211) — defined in `lquery_op.c:43`.
- `ltree *lca_inner(ltree **a, int len)` (line 212) — defined in `ltree_op.c:525`.
- `bool ltree_label_match(...)` (line 213) — defined in `lquery_op.c:80`.
- `ltree_gist *ltree_gist_alloc(...)` (line 291) — defined in `ltree_gist.c:42`.
- `PGDLLEXPORT Datum ...` declarations for the operator suite (lines 180-203).

Type-fetch macros:

- `PG_GETARG_LTREE_P(n)` / `PG_GETARG_LQUERY_P(n)` / `PG_GETARG_LTXTQUERY_P(n)` (lines 217-230) — `PG_DETOAST_DATUM` wrappers.

## Key invariants

- INV-LTREE-MAXLEVEL: `ltree.numlevel` is `uint16`; `LTREE_MAX_LEVELS = PG_UINT16_MAX = 65535` (line 52). Enforced at parse time (`ltree_io.c:64`), at concat (`ltree_op.c:378`), at lquery `low`/`high` bounds (`ltree_io.c:424,442`). `[verified-by-code]`
- INV-LQUERY-MAXLEVEL: `lquery.numlevel` is `uint16`; `LQUERY_MAX_LEVELS = PG_UINT16_MAX` (line 125). Enforced at `ltree_io.c:306`. `[verified-by-code]`
- INV-LABEL-MAX-CHARS: per-label cap is **1000 characters, not bytes** (line 18). The byte-length field is `uint16` (lines 35, 61); character cap is locale/encoding-independent, byte cap is implicit ≤ 65535. `[verified-by-code + from-comment]`
- INV-LABEL-CHARSET: `ISLABEL(x) == t_isalnum_cstr(x) || t_iseq(x,'_') || t_iseq(x,'-')` (line 130). `t_isalnum_cstr` is the encoding-aware tsearch helper — under non-C locales it accepts UTF-8 letters, not just ASCII `[A-Za-z0-9_-]`. The leading comment "alphanumerics, underscores and hyphens" is misleading w.r.t. ASCII. `[verified-by-code]`
- INV-LQUERY-LEVEL-TOTALLEN-U16: `lquery_level.totallen` is `uint16`; parser rejects levels whose serialized size would exceed `PG_UINT16_MAX` (`ltree_io.c:553`). `[verified-by-code]`
- INV-LVAR-LEN-U16 / INV-LVAR-FLAG-U8: `lquery_variant.len` is `uint16`, `flag` is `uint8` (lines 61-62); the on-disk format is **frozen for backwards compatibility** — the comment at line 67-70 explicitly forbids fixing the MAXALIGN over-estimate.
- INV-LQL-COUNT-COMPAT: a non-`*` level (i.e. `numvar > 0`) only has meaningful `low`/`high` when `LQL_COUNT` is set; otherwise zero fields mean "exactly 1 match". This is a pre-v13 on-disk compatibility hack (comment at lines 80-86), enforced in `lquery_op.c:205-208`. `[from-comment]`
- INV-LTXTQUERY-LEFT-BACKLINK: `ITEM.left` is `int16` (line 141) and stores the offset to the LEFT operand's top; `LTXTQUERY_TOO_BIG` macro (line 162) caps `state.num` so this can't overflow — but `findoprnd` in `ltxtquery_io.c:351` adds an explicit `delta > PG_INT16_MAX` check anyway.
- INV-LTG-LAYOUT: `ltree_gist` has three on-page shapes encoded by 3 flag bits (lines 256-264 comment + macros at 274-289). `LTG_ONENODE` → leaf-style `(flag)(ltree)`; non-ONENODE → `(flag)(sign)(left_ltree)(right_ltree)`; `LTG_ALLTRUE` → skips the signature; `LTG_NORIGHT` → right node aliased to left.
- INV-SIGLEN-MULTIPLE-OF-INT: `ltree_gist_options` validates `siglen` is `INTALIGN(siglen)` (`ltree_gist.c:729`); macros assume word-aligned signature storage. `LTREE_SIGLEN_MAX == GISTMaxIndexKeySize`. `[verified-by-code]`
- INV-SIGLEN-DEFAULT: `LTREE_SIGLEN_DEFAULT = 2 * sizeof(int32) = 8 bytes = 64 bits` (line 236). For `ltree[]`: `LTREE_ASIGLEN_DEFAULT = 7 * sizeof(int32) = 28 bytes = 224 bits` (line 296). The asymmetry is because `_ltree_gist` keys cover N paths, scalar `ltree` keys cover 1.

## Notable internals

- The "level" struct (`ltree_level`, line 33) is `(uint16 len)(char name[len])` MAXALIGN-padded. `LEVEL_NEXT(x)` advances by `MAXALIGN(len + LEVEL_HDRSIZE)`.
- `lquery_variant.val` (line 60) stores the CRC32 of the label string; the GiST signature looks up bits at `HASHVAL(val, siglen) = val % SIGLENBIT(siglen)` (line 253). For the default 64-bit signature: `crc % 64` — a 6-bit fingerprint per label.
- `FLG_CANLOOKSIGN(x)` (lines 107-110): GiST can use the signature ONLY when the level has no `LQL_NOT`, no `LVAR_ANYEND` (`*` prefix-match), no `LVAR_SUBLEXEME` (`%` word-wise), and **under `LOWER_NODE` ALSO no `LVAR_INCASE`** (`@`) — because CRC is computed on case-folded text under `LOWER_NODE`, so the signature already encodes the case-insensitive form. Without `LOWER_NODE` (MSVC historically), `LVAR_INCASE` also disqualifies signature use.
- `LOWER_NODE` (lines 29-31) is a compile-time switch — defined everywhere EXCEPT MSVC, for `pg_upgrade` ABI/CRC continuity. Two builds of the same Postgres produce different CRC values for identical labels. `[from-comment]`
- `ITEM` (line 138) is 12 bytes packed: `int16 type, int16 left, int32 val, uint8 flag, uint8 length, uint16 distance`. `distance` is the byte offset into the operand string for a VAL item; `val` is the CRC of the operand.

## Trust boundary / Phase D surface

- **No bounds in this file itself** — it's a layout header. But the layouts directly determine the cost model for every operator. Specifically: `lquery_level.numvar` is `uint16`, so a single level can carry up to 65535 OR'd label variants (`foo|bar|baz|...`). `lquery.numlevel` is also `uint16`, so a query can have 65535 levels. Each level's match against an ltree level is O(numvar). Each level position in the ltree is a backtracking choice point in `checkCond`. Phase D upper-bound: a 65535-level lquery with `*{0,N}` wildcards against a 65535-level ltree is the worst-case input.
- **Signature length**: default 64 bits (`LTREE_SIGLEN_DEFAULT=8`). With 64 buckets and birthday-paradox math, **~10 labels in the same signature give ~50% collision probability**. The signature is a Bloom-style false-positive filter — index searches that match the signature are rechecked at the leaf level, so collisions cause performance degradation (more pages fetched) not correctness. `LTREE_ASIGLEN_DEFAULT=28` (224 bits) for `ltree[]` makes that arm somewhat better-behaved but still very small for paths covering many labels.
- **`siglen` user-tunable up to `GISTMaxIndexKeySize`** — both opclasses accept a `siglen` reloption (`ltree_gist.c:735`, `_ltree_gist.c:546`). A DBA can raise it; nothing in core advertises this for performance hygiene.
- **`LTREE_LABEL_MAX_CHARS = 1000` is wlen (character count), not byte length**. With UTF-8, a 1000-character label can be up to 4000 bytes. The `uint16` `len` field caps bytes at 65535 — comfortably above 4×1000 = 4000.
- **`ITEM.left` is `int16`**, so a single ltxtquery's binary-tree depth has a hard cap related to `LTXTQUERY_TOO_BIG`. The cap macro is `(size) > (MaxAllocSize - HDRSIZEQT - lenofoperand) / sizeof(ITEM)` (line 162) — roughly `MaxAllocSize/12 ≈ 89 million ITEMs` before that triggers, BUT the `int16 left` field becomes the binding limit at 32767. The explicit overflow check is in `ltxtquery_io.c:351`.
- **Embedded NULs in labels** — the parser (`ltree_io.c`) uses `pg_mblen_cstr` which is null-terminated-string-based, and `ISLABEL` rejects 0x00 (it's neither alnum, '_', nor '-'). Cannot smuggle NULs through `ltree_in`. Binary recv uses `pq_getmsgtext` which decodes from client encoding, and then calls `parse_ltree` on the result — same path. `[verified-by-code]`
- **UTF-8 / multibyte labels**: `t_isalnum_cstr` is locale-aware; under `lc_ctype = en_US.UTF-8`, é/ñ/Cyrillic letters are valid. The CRC is computed on the case-folded multibyte form (`crc32.c:32-43`). So `Foo` and `foo` produce identical CRCs under `LOWER_NODE` (always on outside MSVC), and ditto for `MAYBÉ` / `maybé` under a locale that case-folds `É → é`.

## Cross-references

- `source/contrib/ltree/ltree_io.c` — parser; enforces `LTREE_MAX_LEVELS`, `LTREE_LABEL_MAX_CHARS`, level-totallen-u16.
- `source/contrib/ltree/lquery_op.c:43` — `compare_subnode`, `ltree_label_match`.
- `source/contrib/ltree/ltree_op.c:49` — `ltree_compare` (and `ltree_op.c:83` — `ltree_compare_distance`, added by 3f328049).
- `source/contrib/ltree/ltree_gist.c:42` — `ltree_gist_alloc`.
- `source/contrib/ltree/ltxtquery_op.c:20` — `ltree_execute` polish-notation walker.
- `source/contrib/ltree/crc32.c` — `ltree_crc32_sz`.
- `source/src/include/tsearch/ts_locale.h:38` — `t_iseq` / `t_isalnum_cstr`.
- `source/src/include/access/gist.h` — `GISTMaxIndexKeySize`.
- A5 finding (`knowledge/files/.../jsonapi/...`): the incremental json parser has a 6400-byte stack cap; lquery/ltxtquery parsers use `check_stack_depth()` instead, which means they fail at `max_stack_depth` (default 100 actual nesting levels deep depending on per-frame size).

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-doc: line 129 comment says "valid label chars are alphanumerics, underscores and hyphens" — implying ASCII. But `t_isalnum_cstr` is the encoding-aware tsearch helper, so under any UTF-8 locale it accepts Unicode letters. Two surprising consequences: (1) the same query string under different `lc_ctype` settings may parse differently; (2) the CRC is computed on case-folded UTF-8 bytes, so signature-bucket assignments are locale-dependent. **GiST indexes built under one locale and queried under another can silently disagree.** (likely)] — `source/contrib/ltree/ltree.h:130`.
- [ISSUE-cost: `LTREE_SIGLEN_DEFAULT=8` bytes = 64 bits is extremely small. With ~10 distinct labels in an indexed value, the signature is half-full and partial-match queries return ~half the index. The reloption to bump it has been available since v13 but **the default never moved**. The `pg_upgrade` story (line 22-28) constrains the default only for existing indexes, not for new ones; the default could be raised without ABI risk for fresh indexes. (likely — performance ergonomics)] — `source/contrib/ltree/ltree.h:236`.
- [ISSUE-correctness: `LVAR_NEXT` macro at line 72 has an explicit comment (lines 67-70) admitting "too many MAXALIGN calls and so will sometimes overestimate the space" — the bug is preserved for on-disk compatibility. Means lquery serialization wastes a few bytes per variant, no security impact. (nit — known bug, frozen)] — `source/contrib/ltree/ltree.h:67-72`.
- [ISSUE-API-shape: `LTG_RNODE` (line 286) returns `LTG_LNODE` when `LTG_NORIGHT` is set — i.e. the same pointer for both. Code that mutates through `LTG_RNODE` would corrupt the left node. All current callers treat keys read-only, but the macro is a footgun. (nit)] — `source/contrib/ltree/ltree.h:284-286`.
- [ISSUE-doc: `LQUERY_HASNOT` (line 127) is set in `parse_lquery` but never read anywhere in the source tree. Inspecting callers: only `parse_lquery` writes it. Appears to be dead flag retained for on-disk compatibility. (nit)] — `source/contrib/ltree/ltree.h:127`.
- [ISSUE-cost: `lquery_level.numvar` is `uint16`, so `a|b|c|...` levels can carry up to 65535 alternatives. `checkLevel` (`lquery_op.c:161`) iterates all of them; with a 65535-level ltree this gives a 4-billion-op worst case for a single recursive call — and `checkCond` adds backtracking on top. (likely — see `lquery_op.c.md` headline)] — `source/contrib/ltree/ltree.h:92`.
