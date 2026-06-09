# crc32.c

## One-line summary

ltree's CRC-32 helper used to spread labels across GiST signature bits. **NOT cryptographic** and not used for collision-resistance — only as a spread function for Bloom-style signatures. Has TWO code paths controlled by the compile-time `LOWER_NODE` macro (defined everywhere except MSVC): `LOWER_NODE`-on does codepoint-by-codepoint case-fold via `pg_strfold` then traditional-CRC32 the folded bytes; `LOWER_NODE`-off does plain byte-by-byte CRC32. The choice is baked into on-disk GiST signatures, so the two builds produce incompatible indexes.

## Public API / entry points

- `unsigned int ltree_crc32_sz(const char *buf, int size)` (line 21 under `LOWER_NODE` / line 54 without) — returns CRC-32 of `size` bytes from `buf`. Definition macro `crc32(buf) = ltree_crc32_sz(buf, strlen(buf))` lives in `crc32.h`.

## Key invariants

- INV-TRADITIONAL-CRC32: uses `INIT_TRADITIONAL_CRC32` / `COMP_TRADITIONAL_CRC32` / `FIN_TRADITIONAL_CRC32` from `utils/pg_crc.h` (lines 32-48 / 60-67). NOT the slicing-by-8 hardware variant — the **traditional** one. `[verified-by-code]`
- INV-LOWER-NODE-CASE-FOLDING: under `LOWER_NODE` (`ltree.h:29-31` defines it everywhere except MSVC), `ltree_crc32_sz` folds each multibyte codepoint via `pg_strfold` (line 40) and CRCs the folded UTF-8 bytes. Without `LOWER_NODE`, each input byte is fed directly. `[verified-by-code]`
- INV-STATIC-LOCALE: the locale is cached in a static `pg_locale_t` at line 27, resolved once via `pg_database_locale()`. Same pattern as `lquery_op.c:84`. Locale captured at first call of the backend's lifetime; later `SET lc_collate` does not affect it. `[verified-by-code]`
- INV-ON-DISK-COMPATIBILITY: CRC values are stored in `lquery_variant.val` (`ltree.h:60`) and in `ITEM.val` (`ltree.h:142`) of the on-disk lquery/ltxtquery, AND drive bit positions in GiST signatures. So `LOWER_NODE` + locale choice + `pg_strfold` semantics are all **part of the on-disk format**. `[verified-by-code + from-comment at line 6-7]`

## Notable internals

- `LOWER_NODE` path (lines 19-51): `pg_mblen_range(p, end)` gets the byte length of one codepoint, `pg_strfold(foldstr, UNICODE_CASEMAP_BUFSZ, p, srclen, locale)` folds that codepoint to lowercase (locale-aware), and the folded bytes are CRC'd. `UNICODE_CASEMAP_BUFSZ` is the per-codepoint output buffer size constant (defined in `pg_locale.h`).
- Non-`LOWER_NODE` path (lines 54-71): trivial byte-by-byte CRC32. Used only on MSVC builds historically.
- The CRC algorithm itself is the standard polynomial-0xEDB88320 LSB-first traditional CRC32 (Ethernet/zip). Output is 32 bits.

## Trust boundary / Phase D surface

- **NOT cryptographic, NOT collision-resistant where it matters**: the CRC is used to spread labels across GiST signature bits via `HASHVAL(val, siglen) = val % SIGLENBIT(siglen)` (`ltree.h:253`). For a 64-bit signature, only 6 bits of the CRC matter. Collisions are EXPECTED — that's the Bloom-filter design. Two distinct labels mapping to the same bit is fine; the leaf-level recheck catches it.
- **Used in three on-disk contexts**:
  1. `lquery_variant.val` — the CRC of each label variant; stored in the lquery varlena, read at GiST consistent time (`gist_qe` in `ltree_gist.c:498` and `_ltree_gist.c:459`).
  2. `ITEM.val` — the CRC of each ltxtquery operand; stored in the ltxtquery varlena, read at GiST consistent time (`checkcondition_bit`).
  3. GiST signature bits — the OR of `HASH(sign, CRC, siglen)` over all labels of the indexed value.
  
  All three depend on `ltree_crc32_sz` producing IDENTICAL output for IDENTICAL labels across pg_dump/restore and pg_upgrade. The `LOWER_NODE` switch + locale choice are the two correctness boundaries.
- **`pg_upgrade` constraint**: the `LOWER_NODE` comment at `ltree.h:21-28` is explicit — MSVC was historically inconsistent, and the post-2010 fix preserves the old behavior to avoid breaking existing MSVC-built indexes. **Cross-platform pg_upgrade from MSVC to non-MSVC (or vice versa) silently corrupts GiST signatures** unless the indexes are REINDEXed. `[from-comment]`
- **Locale-change-at-pg_upgrade is silently broken**: an index built with `lc_ctype = C` and pg_upgrade'd into a cluster with `lc_ctype = en_US.UTF-8` will have signatures based on byte-CRC values, but new INSERTs will produce signatures based on case-folded-UTF-8-CRC values. The two are incompatible. Same risk for OS upgrades that change ICU/libc casemap tables. Mitigation: REINDEX after locale changes. **Not documented anywhere obvious.** `[inferred from code + ltree.h:21-28]`
- **No DoS surface in CRC itself**: O(N) over input bytes, no allocation in the non-LOWER_NODE path. The LOWER_NODE path allocates `foldstr[UNICODE_CASEMAP_BUFSZ]` on the stack per codepoint (line 35) — small and bounded.
- **NOT used anywhere where collision-resistance is required**: hash_ltree (`ltree_op.c:137`) uses `hash_any` (Jenkins), NOT `ltree_crc32_sz`. So the two hash universes don't overlap; CRC32's weakness doesn't propagate. `[verified-by-code]`

## Cross-references

- `source/contrib/ltree/crc32.h:7-10` — declares `ltree_crc32_sz` and the `crc32(buf)` macro.
- `source/contrib/ltree/ltree.h:29-31` — `LOWER_NODE` define.
- `source/contrib/ltree/ltree.h:60` — `lquery_variant.val` field.
- `source/contrib/ltree/ltree.h:142,253-254` — `ITEM.val` and `HASHVAL`/`HASH` macros.
- `source/contrib/ltree/ltree_gist.c:184` — call site in `hashing()`.
- `source/contrib/ltree/_ltree_gist.c:41,399` — call sites in array variant.
- `source/contrib/ltree/ltree_io.c:563` — `lrptr->val = ltree_crc32_sz(...)` in lquery parser.
- `source/contrib/ltree/ltxtquery_io.c:189` — `ltree_crc32_sz` in ltxtquery operand push.
- `source/src/include/utils/pg_crc.h` — `INIT/COMP/FIN_TRADITIONAL_CRC32`.
- `source/src/include/utils/pg_locale.h` — `pg_strfold`, `pg_database_locale`, `UNICODE_CASEMAP_BUFSZ`.

## Issues spotted

- [ISSUE-security: locale-change-at-runtime silently breaks CRC consistency. An index built under `lc_ctype = en_US.UTF-8` and queried under `C` produces different signatures for the same label values. Symptom: GiST searches return false negatives (rows that should match are missed). REINDEX is required after locale changes. **No code-side check; no documentation cross-reference; user-visible only as missing rows.** Cross-link to A12's locale findings if any. (likely — operational footgun, generic to PG locale-aware indexes)] — `source/contrib/ltree/crc32.c:27-30`.
- [ISSUE-correctness: MSVC vs non-MSVC builds produce different CRC values for identical labels. `pg_upgrade` from MSVC to Linux/macOS silently corrupts ltree GiST indexes. The defense at `ltree.h:21-28` says "we maintain the same LOWER_NODE behavior after a pg_upgrade" — but **only WITHIN the same `LOWER_NODE` setting**. Cross-platform pg_upgrade is broken. `[from-comment + verified-by-code]` (likely — see ltree.h ISSUE)] — `source/contrib/ltree/crc32.c:15`.
- [ISSUE-cost: static `pg_locale_t locale = NULL` (line 27) — same per-backend-lifetime caching pattern as `lquery_op.c:84`. SET lc_collate within a session does not invalidate it. (nit — known PG pattern)] — `source/contrib/ltree/crc32.c:27-30`.
- [ISSUE-doc: `UNICODE_CASEMAP_BUFSZ` (line 35) is the stack-buffer size for one codepoint's case-fold output. No bounds check on `pg_strfold` return — if case-folding produces > BUFSZ bytes, `pg_strfold` writes truncated. The comment at `lquery_op.c:99-103` notes that case-folding CAN grow the byte length (German ß → SS doubles). UNICODE_CASEMAP_BUFSZ is sized to accommodate the worst-case Unicode mapping (currently 18 bytes per codepoint per the Unicode 16.0 special-casing table). So OK, but worth a check that future Unicode versions don't exceed the constant. (nit — depends on PG core's Unicode tables)] — `source/contrib/ltree/crc32.c:35,40-41`.
- [ISSUE-API-shape: `ltree_crc32_sz` is the only public function. The `crc32(buf)` macro in `crc32.h` is a convenience for null-terminated input. Both paths use the SAME traditional CRC32 polynomial. (verification only)] — `source/contrib/ltree/crc32.c:21,54`.
