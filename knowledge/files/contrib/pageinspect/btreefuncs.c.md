# btreefuncs.c

Covers `source/contrib/pageinspect/btreefuncs.c` (938 lines): B-tree
page introspection — page stats, line-pointer items, posting-list
decoding, metapage. Has both relname-based and bytea-based entry
points (the bytea variant is the only thing in pageinspect that lets
a caller decode a page they've copied somewhere else; everything
else takes a live relation).

## One-line summary

Three families: `bt_metap` reads the metapage from a live index;
`bt_page_stats(relname, blkno)` / `bt_multi_page_stats(relname,
start, count)` scan one or many pages by relation; `bt_page_items`
has two flavors — `(relname, blkno)` reads under share lock, and
`(bytea)` decodes a previously-extracted page.

## Public API / entry points

- `bt_metap(text relname)` —
  `source/contrib/pageinspect/btreefuncs.c:839`. Reads block 0 under
  share lock, decodes `BTMetaPageData`.
- `bt_page_stats(text, int4)` / `bt_page_stats_1_9(text, int8)` —
  `:329` / `:322`. Wraps `bt_page_stats_internal` (`:260`).
- `bt_multi_page_stats(text, int8, int8)` —
  `:344`. SRF; the `blk_count < 0` mode means "to end of relation",
  recomputed each iteration (`:411`).
- `bt_page_items(text, int4)` / `bt_page_items_1_9(text, int8)` —
  `:719` / `:712`. Wraps `bt_page_items_internal` (`:624`); SRF
  yielding (itemoffset, ctid, itemlen, nulls, vars, data,
  dead, htid, tids[]) per index tuple.
- `bt_page_items_bytea(bytea)` —
  `:734`. Same row shape but takes a pre-extracted bytea instead of
  re-reading from a buffer. **This is the bytea-decode path.**

## Key invariants

- INV-1: Every entry point has `superuser()` gate at `:274, :351,
  :633, :741, :853` [verified-by-code]. Error message: "must be
  superuser to use pageinspect functions" (or "raw page functions"
  for the bytea variant). Inconsistent wording but same effect.
- INV-2: Block 0 is the metapage and explicitly rejected by
  `bt_index_block_validate` (`:244-247`): "block 0 is a meta page".
  `bt_page_items_bytea` enforces this differently — it checks
  `P_ISMETA(opaque)` at `:778-781`.
- INV-3: `check_relation_block_range` (`:204-216`) bounds `blkno` to
  `[0, MaxBlockNumber]` then `< RelationGetNumberOfBlocks(rel)`.
  `bt_multi_page_stats` re-checks each iteration when in `allpages`
  mode (`:410-411`).
- INV-4: Non-local temp rejection via `RELATION_IS_OTHER_TEMP`
  (`:239, :872`) — same idiom as `rawpage.c`. [verified-by-code]
- INV-5: For the bytea-decode path, the special-space size MUST
  equal `MAXALIGN(sizeof(BTPageOpaqueData))` (`:768`). This is the
  primary "is this actually a btree page" check.
- INV-6: BTREE_NOVAC_VERSION-aware decoding of metapage fields
  (`:915-926`): pre-PG13 indexes get default values for
  `btm_last_cleanup_num_delpages`, `btm_last_cleanup_num_heap_tuples`,
  `btm_allequalimage`.

## Notable internals

**Relation-vs-bytea split.** `bt_page_items_internal` copies the
page bytes out under share lock into local memory (`:665-666`) and
releases the buffer before returning to the SRF caller — the comment
at `:656-660` explains: "to avoid holding pin on the buffer longer
than we must, and possibly failing to release it at all if the
calling query doesn't fetch all rows." Important pattern: SRFs that
hold buffers across executor returns can leak pins.

**Multi-page lock dance.** `bt_multi_page_stats` (`:344-472`) re-opens
the relation on each call via OID (`:407`) to avoid leaking a
relcache reference across an aborted SRF: "we close and re-open the
index rel each time through, using the index's OID for re-opens to
ensure we get the same rel. Keep the AccessShareLock though" —
`:394-400`. The lock is held across the whole SRF lifetime;
relcache entry is reacquired per row.

**!heapkeyspace gymnastics.** `bt_page_print_tuples` (`:480-613`)
has elaborate handling for pre-BTREE_VERSION-4 (pre-PG12) indexes
where `BTreeTupleIsPivot()` is not reliable. The comment block at
`:519-541` is the definitive explanation. For the bytea variant
there's no metapage handy to consult, so the code falls back to
"deduce pivot-tuple from leafness and offset position" (`:568`).
This is a correctness concern, not security.

**Posting-list decode.** `:542-545`: if `BTreeTupleIsPosting`, the
"data" column strips the trailing TIDs. Otherwise if pivot with
heap TID, strips MAXALIGN(sizeof(ItemPointerData)) trailing bytes.

**Metapage version detection.** `:887-899`: refuses to run if the
SQL-declared rowtype has too few columns (`tupleDesc->natts <
BT_METAP_COLS_V1_8 = 9`). Errors with hint "update the pageinspect
extension". This is the same fragility pattern as
`rawpage.c:page_header` — the C code is tied to the SQL rowtype.

## Trust boundary / Phase D surface

**Same `superuser()` gate as the rest of pageinspect.** No
`pg_stat_scan_tables` role wiring (confirmed by `grep` in
pageinspect.md). The bytea path (`bt_page_items_bytea`) is the
interesting one for adversarial analysis:

**`bt_page_items_bytea` decoder hardening.** `:768-786`:
- Special-space size must match `MAXALIGN(sizeof(BTPageOpaqueData))`.
- Refuses metapages (`P_ISMETA`).
- Refuses non-leaf with `btpo_level == 0` (corrupted level).
- Notices (not errors) deleted pages and zero-fills max_calls.

After these checks, `bt_page_print_tuples` does `PageGetItem(page,
id)` for each offset and computes `IndexTupleSize(itup)` and
`IndexInfoFindDataOffset(itup->t_info)`. The internal computation at
`:547-549` is the only post-extraction bounds check:
`if (dlen < 0 || dlen > INDEX_SIZE_MASK) elog(ERROR, "invalid tuple
length %d ...")`. A maliciously crafted bytea with bad t_info could
produce dlen that fails this check before any read-overflow happens.
`PageGetItem` itself trusts the line pointer — but the special-space
size check + the dlen sanity check combine to constrain what's
possible. **No buffer-overflow primitive identified, but the decoder
trusts `IndexTupleSize` from on-page bytes**.
**[ISSUE-correctness: `PageGetItem` is called without revalidating
`lp_off`/`lp_len` against BLCKSZ in the bytea path; relies on
upstream PageGetItem invariants holding for a fabricated page (maybe;
needs deeper read of `PageGetItem`)]** —
`source/contrib/pageinspect/btreefuncs.c:506`.

**RLS bypass via index reads.** Index pages contain (key, ctid)
pairs. The "data" column emitted is the key's on-disk bytes (`:559`),
which means a superuser-only call can surface index-key bytes for
rows that RLS would normally filter. Lower-impact than heap-page
bypass (you only get indexed columns) but still a side channel.
**[ISSUE-security: btreefuncs surfaces index-key bytes verbatim; RLS
bypass for indexed columns specifically (likely)]**.

**CONCURRENTLY index inspection.** `bt_index_block_validate` doesn't
check `indisvalid` — so `bt_page_items` works on a mid-CIC index.
Results may be garbage if the build is mid-sort, but no crash. The
"block 0 is a meta page" check fires before any !indisvalid check
could.

**Auto-vacuum interaction.** `AccessShareLock` on the index doesn't
block index VACUUM (which uses `RowExclusiveLock`-equivalent +
buffer cleanup locks). The bytea snapshot can race against VACUUM's
page deletion / split. The bytea-decode path's `P_ISDELETED` check
(`:788-789`) catches the deleted case as a NOTICE not an ERROR.

**Number-of-blocks recheck.** `bt_multi_page_stats` recomputes
`RelationGetNumberOfBlocks(rel)` each row in `allpages` mode
(`:410-411`). If a concurrent split/extension adds blocks, the SRF
keeps reading. If a concurrent truncate removes blocks, the next
iteration sees the smaller number and stops. Not exploitable but
worth knowing.

**Crash on `ItemIdIsValid` (good).** `:503-504` `elog(ERROR, "invalid
ItemId")` — defensive against malicious-but-shape-correct bytea. Same
at `:548-549` for tuple length.

## Cross-references

- `source/src/include/access/nbtree.h` — `BTMetaPageData`,
  `BTPageOpaqueData`, `BTREE_NOVAC_VERSION`, `P_ISDELETED` /
  `P_IGNORE` / `P_ISLEAF` / `P_ISROOT` macros.
- `source/src/backend/access/nbtree/nbtpage.c` — `_bt_metaversion`,
  the function this file's metapage decode mirrors.
- `knowledge/files/contrib/pageinspect/pageinspect.md` —
  `get_page_from_raw` and the bytea convention.
- `knowledge/files/contrib/amcheck/` — amcheck's btree verification
  (`bt_check_index_internal`) does the inverse: verifying invariants
  instead of exposing bytes.

<!-- issues:auto:begin -->
- [Issue register — `pageinspect`](../../../issues/pageinspect.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-security: btreefuncs surfaces index-key on-disk bytes;
  effective RLS bypass for indexed columns (likely; bounded by
  `superuser()`)]** — `source/contrib/pageinspect/btreefuncs.c:559`.
- **[ISSUE-correctness: bytea-decode `PageGetItem` calls don't
  revalidate `lp_off/lp_len` against BLCKSZ; relies on macro
  invariants from `PageGetItemId` holding for a fabricated page
  (maybe)]** — `:506`.
- **[ISSUE-correctness: `bt_index_block_validate` doesn't check
  `indisvalid`; mid-CIC index inspection produces uncertain output
  (nit)]** — `:226-249`.
- **[ISSUE-api-shape: `bt_metap` refuses to run when SQL rowtype is
  too narrow but pre-1.8 silently misinterpreted columns; only newer
  installs get the clean error (nit, documented behavior)]** —
  `:895-899`.
- **[ISSUE-defense-in-depth: error wording inconsistent — "must be
  superuser to use pageinspect functions" vs "raw page functions"
  in the same file (nit)]** — compare `:277` and `:744`.
- **[ISSUE-correctness: !heapkeyspace heuristic at `:568` may
  mis-classify pivot vs non-pivot tuples; comment at `:519-541`
  acknowledges (nit, pre-PG12 only)]**.
