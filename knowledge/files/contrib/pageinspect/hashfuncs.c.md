# hashfuncs.c

Covers `source/contrib/pageinspect/hashfuncs.c` (575 lines): hash AM
page introspection — page-type classifier, per-page stats, item
iterator (extracts hash key), bitmap-bit query, metapage decode.

## One-line summary

`hash_page_type` returns "metapage/bucket/overflow/bitmap/unused";
`hash_page_stats` and `hash_page_items` decode bucket and overflow
pages; `hash_bitmap_info(idx, blkno)` opens the index live to query
the free-bit for an overflow page; `hash_metapage_info` reads
`HashMetaPageData` (magic, version, masks, spares[], mapp[]).

## Public API / entry points

- `hash_page_type(bytea)` — `:192`.
- `hash_page_stats(bytea)` — `:237`. Wraps `verify_hash_page` with
  `LH_BUCKET_PAGE | LH_OVERFLOW_PAGE` requirement.
- `hash_page_items(bytea)` — `:300`, SRF. Each row: (offset, ctid,
  hashkey).
- `hash_bitmap_info(regclass, int8)` — `:391`. **The only live-index
  function in hashfuncs**; opens the index and reads metapage +
  bitmap page from buffer.
- `hash_metapage_info(bytea)` — `:519`.

## Key invariants

- INV-1: `superuser()` gate at `:200, :248, :313, :413, :533`
  [verified-by-code].
- INV-2: `verify_hash_page` (`:58-147`) is the central validator:
  - Special-space size == `MAXALIGN(sizeof(HashPageOpaqueData))`
    (`:69`).
  - `hasho_page_id == HASHO_PAGE_ID` magic (`:78`).
  - Page-type is one of the known LH_* constants (`:89-94`).
  - If a `flags` mask is passed, page-type must intersect (`:97-122`).
  - If metapage, `hashm_magic == HASH_MAGIC` AND `hashm_version ==
    HASH_VERSION` (`:127-143`).
- INV-3: `hash_bitmap_info` rejects metapage and bitmap-page block
  numbers via the metapage's `hashm_mapp` array (`:454-464`).

## Notable internals

**The `verify_hash_page` flags argument.** `:97-122` lets callers
require a specific page-type. Used as:
- `0` (any) by `hash_page_type` (`:205`).
- `LH_BUCKET_PAGE | LH_OVERFLOW_PAGE` by stats/items (`:253, :326`).
- `LH_META_PAGE` by metapage decoder (`:538`).

Each non-matching case has a specific error message; the `default`
arm (`:117-119`) is `elog` not `ereport` — defensive for the case
where a caller passes a mask the validator doesn't recognize.

**Magic+version both checked.** Unlike BRIN/GIN which only check
flag bits, hash AM has both `HASHO_PAGE_ID` (per-page magic at
`:78`) AND `HASH_MAGIC` + `HASH_VERSION` (metapage-only, `:131-143`).
A fabricated bytea has to lie consistently in all three fields to
pass. Strongest "is this hash?" verification in pageinspect.

**`hash_page_items` extracts hash key.** `:368`:
`_hash_get_indextuple_hashkey(itup)` reads the trailing 4 bytes of
the index tuple where the hash AM stores the hashed value. Output
is exposed as int8 (`:369`). **This is the hash of the indexed
column, not the column itself** — minor RLS bypass (you learn a
hash, not the value).

**`hash_bitmap_info` is the only live-index function.** `:447`:
`_hash_getbuf(indexRel, HASH_METAPAGE, HASH_READ, LH_META_PAGE)` —
uses the internal hash AM buffer-getter with type-verification. Then
walks `hashm_mapp[]` to find the bitmap page for the requested
overflow block, opens it, reads the bit. This is the ONLY pageinspect
function that "computes" against a live index using AM-internal
helpers; everything else is just byte-staring.

**Partitioned-index ban.** `:421-422`: uses `relation_open` not
`index_open` to bypass the index_open assertion that allows
partitioned indexes — comment at `:418-420` explains. Hash AM doesn't
support partitioned indexes, so this prevents confusion.

## Trust boundary / Phase D surface

**Strongest bytea hardening.** Magic + version + special-space size
+ page-type-mask checks make hashfuncs the most defensive
bytea-decoder in pageinspect. Buffer-overflow risk on fabricated
bytea is minimal — but `PageGetItemId` / `PageGetItem` are still
unchecked beyond what they do internally (`:357-362, :502`).
**[ISSUE-correctness: same `PageGetItem` trust as elsewhere; no
explicit `lp_off+lp_len <= BLCKSZ` defense beyond shape checks
(nit; lower-severity here because of the layered magic checks)]** —
`source/contrib/pageinspect/hashfuncs.c:362`.

**RLS bypass via hash key.** `hash_page_items` emits the
4-byte/8-byte hash of the indexed value (`:369`). For high-cardinality
columns, hash → value is hard. For low-cardinality (e.g. boolean,
enum, small int), the hash is effectively the value. Lower-impact
than B-tree key leak (the value itself), higher-impact than zero.
**[ISSUE-security: hash_page_items leaks hashed column values; for
low-cardinality columns the hash is reversible by brute-force
(maybe; depends on column cardinality)]**.

**`hash_bitmap_info` reads the live index.** `:417-440`: opens the
index under `AccessShareLock`, validates relkind/IS_HASH, validates
`ovflblkno` is in `[0, MaxBlockNumber]` AND `<
RelationGetNumberOfBlocks`, AND rejects metapage and bitmap pages.
Defense is layered. The actual page reads (`:447, :486`) use
`_hash_getbuf` with type-validation, so a corrupted metapage or
bitmap-page pointer would error inside `_hash_getbuf`, not crash.

**`_hash_ovflblkno_to_bitno` is called on user input.** `:470`. The
function (in hashovfl.c) computes the bit number from the overflow
block number using the metapage's `hashm_spares` array. Comment
says "this will error out for primary bucket pages" — defense by
expected error. **[ISSUE-correctness: `_hash_ovflblkno_to_bitno`
called for user-supplied `ovflblkno`; if a primary bucket page is
passed (which the metapage rejects don't catch), the function
errors — relying on a downstream error rather than upfront check
(nit)]** — `:470`.

**CONCURRENTLY-built hash.** No `indisvalid` check. Mid-build hash
inspection: undefined; hash CIC support exists, status unknown.

**Auto-vacuum interaction.** Hash AM uses cleanup-locks during
bucket splits. `hash_bitmap_info` acquires `HASH_READ` (share-mode
buffer lock); a concurrent split that has the cleanup lock would
wait, and vice versa. No deadlock vector identified.

**Forward-compat metapage.** `hash_metapage_info` returns
`hashm_version` as a column (`:549`). If `HASH_VERSION` bumps,
older extensions get an error in `verify_hash_page` (`:138-143`) —
they cannot decode the new format. No silent miscompare.

## Cross-references

- `source/src/include/access/hash.h` — `HashPageOpaqueData`,
  `HashMetaPageData`, `LH_*` page-type flags, `HASH_MAGIC` /
  `HASH_VERSION`, `HASHO_PAGE_ID`.
- `source/src/backend/access/hash/hashpage.c` — `_hash_getbuf`,
  `_hash_relbuf`.
- `source/src/backend/access/hash/hashovfl.c` —
  `_hash_ovflblkno_to_bitno`.
- `knowledge/files/contrib/pageinspect/pageinspect.md` — bytea source.

<!-- issues:auto:begin -->
- [Issue register — `pageinspect`](../../../issues/pageinspect.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-security: hash_page_items leaks per-row hashes;
  reversible for low-cardinality columns (maybe)]** —
  `source/contrib/pageinspect/hashfuncs.c:369`.
- **[ISSUE-correctness: `_hash_ovflblkno_to_bitno` relies on
  downstream error for primary-bucket-page input rather than
  upfront-checking (nit)]** — `:470`.
- **[ISSUE-correctness: no `indisvalid` check in `hash_bitmap_info`
  (nit; lower-impact)]** — `:424-428`.
- **[ISSUE-defense-in-depth: positive note — hashfuncs is the most
  hardened pageinspect bytea-decoder; magic + version + special-size
  + page-type-mask layered checks. Pattern worth adopting in other
  per-AM files (nit)]** — `:69-143`.
