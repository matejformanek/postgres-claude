# nbtree.h

- **Source path:** `source/src/include/access/nbtree.h` (1334 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The AM-internal header for nbtree. Public-facing AM entry points are declared at the bottom (`btbuild`, `btinsert`, scan lifecycle, vacuum, `btvalidate`, etc.), but the bulk of the file is the **type system and inline helpers** that the AM uses internally: page layout (`BTPageOpaqueData`, `BTMetaPageData`, `BTDeletedPageData`), tuple-format bit-twiddling (the dual interpretation of `t_tid` for pivot/posting/normal tuples — *the most subtle part of the file*), scan state (`BTScanOpaqueData`, `BTScanPosData`, `BTArrayKeyInfo`), insert state (`BTScanInsertData`, `BTInsertStateData`), dedup state (`BTDedupStateData`), and VACUUM state (`BTVacState`, `BTPendingFSM`). [from-comment, nbtree.h:1-12; verified-by-code]

## Sections (with line offsets)

### Page layout

- `BTPageOpaqueData` (63-72): the fixed-size special area at the end of every btree page. Five fields: `btpo_prev`, `btpo_next`, `btpo_level` (0 = leaf), `btpo_flags` (`BTP_*` bits), `btpo_cycleid` (16-bit VACUUM cycle ID). Plus `BTP_HAS_FULLXID` (=0x100) which signals that the page is *deleted* and the special area is followed by a `BTDeletedPageData` in the tuple area. [verified-by-code]
- Flag bits `BTP_*` (76-85): LEAF, ROOT, DELETED, META, HALF_DEAD, SPLIT_END, HAS_GARBAGE (deprecated), INCOMPLETE_SPLIT, HAS_FULLXID.
- `MAX_BT_CYCLE_ID = 0xFF7F` (94): reserves top 8 bits of the 2-byte slot for pg_filedump's index-type marker.
- `BTMetaPageData` (104-120): metapage layout, version 4. `btm_root`/`btm_level` vs `btm_fastroot`/`btm_fastlevel` (Lanin & Shasha fast-root optimisation). `btm_allequalimage` (deduplication safety).
- `BTREE_VERSION = 4`, `BTREE_MIN_VERSION = 2` (151-152): on-disk versions still supported for read.
- `BTMaxItemSize`/`BTMaxItemSizeNoHeapTid` (165-173): 1/3-page upper bound on tuple size.
- `BTPageIsRecyclable(page, heaprel)` static-inline (291-319): the canonical recycle-safety test. Reads `safexid` from `BTDeletedPageData` and calls `GlobalVisCheckRemovableFullXid(heaprel, safexid)`. **This is the test that gates FSM placement and is mirrored on the standby by the `XLOG_BTREE_REUSE_PAGE`-driven snapshot-conflict resolution.** [verified-by-code]
- `BTDeletedPageData` (234-237): a single `FullTransactionId safexid`. Written into the *tuple area* (not the opaque area) by `BTPageSetDeleted` (239-258).
- Page-position constants `P_NONE`, `P_HIKEY`, `P_FIRSTKEY`, `P_FIRSTDATAKEY`, and the `P_*` predicates `P_LEFTMOST`/`P_RIGHTMOST`/`P_ISLEAF`/`P_ISROOT`/`P_ISDELETED`/`P_ISHALFDEAD`/`P_IGNORE`/`P_INCOMPLETE_SPLIT`/`P_HAS_FULLXID` (213-229, 368-370).

### Tuple format — the most subtle section (372-549)

Three tuple shapes, distinguished by status bits in `t_info` (`INDEX_ALT_TID_MASK = INDEX_AM_RESERVED_BIT`) and the top nibble of `t_tid.ip_posid` (`BT_STATUS_OFFSET_MASK = 0xF000`):

1. **Non-pivot plain (leaf data tuple)**: `INDEX_ALT_TID_MASK` clear. `t_tid` is a real heap TID. Number of attributes implicit (= index nkeyatts + ninclude).
2. **Pivot tuple** (internal pages + leaf high keys): `INDEX_ALT_TID_MASK` set, `BT_IS_POSTING` clear. `t_tid.ip_blkid` is the downlink (for internal pages) or topparent (for half-dead leaves), and `t_tid.ip_posid` low 12 bits store the number of key attributes; bit `BT_PIVOT_HEAP_TID_ATTR` (`0x1000`) signals that a tiebreaker heap TID is appended at the end of the tuple body.
3. **Posting-list tuple** (leaf data tuple representing a deduplicated group): `INDEX_ALT_TID_MASK` set, `BT_IS_POSTING` (`0x2000`) set. `t_tid.ip_blkid` is the byte offset within the tuple to the start of the posting list (an `ItemPointerData[]`), and `t_tid.ip_posid` low 12 bits store the count of TIDs.

The 12-bit attribute-count field is `StaticAssertDecl`'d to fit `INDEX_MAX_KEYS` (line 473-474).

Inline accessors `BTreeTupleIsPivot`, `BTreeTupleIsPosting`, `BTreeTupleSetPosting`, `BTreeTupleGetNPosting`, `BTreeTupleGetPostingOffset`, `BTreeTupleGet/SetDownLink`, `BTreeTupleGet/SetTopParent`, `BTreeTupleGet/SetNAtts`, `BTreeTupleGetHeapTID`, `BTreeTupleGetMaxHeapTID` (480-677). Several explicitly note "cannot assert pivot" because !heapkeyspace v2/v3 indexes have false-negative detection.

### Scan/insert/dedup state structs

- `BTStackData` (743-750): the descent stack (block + offset of each pivot tuple visited), used to find the parent during a split or page-delete.
- `BTScanInsertData` (795-805): the "insertion scankey" — `heapkeyspace`/`allequalimage`/`anynullkeys`/`nextkey`/`backward`/`scantid`/`keysz`/`scankeys[INDEX_MAX_KEYS]` (flexible-array-like, sized exactly so stack allocations work).
- `BTInsertStateData` (820-844): per-insert working area. Includes `bounds_valid`/`low`/`stricthigh` for the `_bt_binsrch_insert` bounds cache, and `postingoff` (-1 for "overlaps an LP_DEAD posting").
- `BTDedupStateData` (876-902): dedup pass state, including a `BTDedupInterval intervals[MaxIndexTuplesPerPage]` flexible-like array for the merge plan.
- `BTVacuumPostingData` (914-923): partial-delete plan for a posting-list tuple during VACUUM/delete. Flexible `deletetids[]` array.
- `BTScanPosData` (962-1000): the per-page item cache built by `_bt_readpage`. Holds `currPage`/`prevPage`/`nextPage`/`lsn` (the page's LSN snapshot, only when `dropPin`), `dir`, `moreLeft`/`moreRight`, `firstItem`/`lastItem`/`itemIndex` cursors, and `items[MaxTIDsPerBTreePage]`. Flexible-array-like tail (`MUST BE LAST`).
- `BTArrayKeyInfo` (1034-1051): one per SAOP/skip array. SAOP arrays store `elem_values[num_elems]`; skip arrays store `attlen`/`attbyval`/`null_elem`/`sksup`/`low_compare`/`high_compare`.
- `BTScanOpaqueData` (1053-1095): per-scan opaque state. `qual_ok`/`numberOfKeys`/`keyData[]` from preprocessing; `numArrayKeys`/`skipScan`/`needPrimScan`/`scanBehind`/`oppositeDirCheck`/`arrayKeys[]`/`orderProcs[]`/`arrayContext`; `killedItems[]`/`numKilled`/`dropPin`; `currTuples`/`markTuples` workspaces (BLCKSZ * 2 packed alloc); `markItemIndex`; `currPos`/`markPos` (last in struct because of trailing flex array in each).

### Private scan-key flag bits (1101-1117)

`SK_BT_REQFWD` / `SK_BT_REQBKWD` / `SK_BT_SKIP` / `SK_BT_MINVAL` / `SK_BT_MAXVAL` / `SK_BT_NEXT` / `SK_BT_PRIOR` — set during preprocessing and during array advancement. Upper byte (`<< SK_BT_INDOPTION_SHIFT = 24`) duplicates the index's per-column `indoption` (DESC, NULLS FIRST) for fast access.

### VACUUM state

- `BTVacState` (331-347): the per-VACUUM-pass state passed through `btvacuumpage` → `_bt_pagedel` → `_bt_pendingfsm_*`. Includes the `pagedelcontext` AllocSet (to throw away deletion-time allocations) and the pending-FSM buffer (`pendingpages[]`).
- `BTPendingFSM` (325-329): a `(target, safexid)` pair recorded at deletion time so `_bt_pendingfsm_finalize` can later test recyclability without re-reading the page.

### AM constants and reloptions

- Strategy numbers: imported via `access/stratnum.h`. `BTCommuteStrategyNumber(strat) = BTMaxStrategyNumber + 1 - strat` (686) for swapping `<` ↔ `>`.
- Support function slots `BTORDER_PROC`/`BTSORTSUPPORT_PROC`/`BTINRANGE_PROC`/`BTEQUALIMAGE_PROC`/`BTOPTIONS_PROC`/`BTSKIPSUPPORT_PROC` = 1..6 (717-723).
- `BT_READ = BUFFER_LOCK_SHARE`, `BT_WRITE = BUFFER_LOCK_EXCLUSIVE` (730-731).
- `BTOptions` (1119-1125) + `BTGetFillFactor`/`BTGetTargetPageFreeSpace`/`BTGetDeduplicateItems` macros.

## Highest-risk invariants encoded here

- `BTPageIsRecyclable` (291) is the single source of truth for safe-to-recycle. Any change to nbtree page-deletion semantics MUST update this function and the comment at lines 280-290 in lock-step with `_bt_pendingfsm_finalize` (which "duplicates some of the same logic"). [from-comment]
- The tuple-shape encoding (`INDEX_ALT_TID_MASK` + `BT_IS_POSTING`) is a load-bearing convention shared with `_bt_swap_posting`, `_bt_form_posting`, `btree_xlog_insert(... posting=true)`, and amcheck. Changing it is a hard upgrade event.
- `BTPageSetDeleted(page, safexid)` (239-258): the inline that performs the entire "now it's a tombstone" mutation — sets flags, rewrites `pd_lower` to just past the `BTDeletedPageData`, sets `pd_upper = pd_special` (no tuples). Called from both the primary (`_bt_unlink_halfdead_page`) and the REDO routine (`btree_xlog_unlink_page`); the two paths must produce identical pages.

## Cross-references

- Included by every `*.c` in `access/nbtree/`, by `amcheck`, by `pg_visibility`, by `pageinspect`, and by extensions that build btree pages directly (e.g. some FDWs in tests).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-nbtree.md](../../../../subsystems/access-nbtree.md)
