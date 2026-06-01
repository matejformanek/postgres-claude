# ginxlog.c

- **Source path:** `source/src/backend/access/gin/ginxlog.c` (811 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/ginxlog.h` (record formats + `XLOG_GIN_*` info bits), every emitter file (`ginbtree.c`, `gininsert.c`, `gindatapage.c`, `ginvacuum.c`, `ginfast.c`).

## Purpose

WAL replay (`gin_redo`), masking (`gin_mask`), and the AM-private replay memory context `opCtx`. One handler per `XLOG_GIN_*` info byte. [from-comment, ginxlog.c:1-13]

## Record-to-handler table

| Info | Handler | Notes |
|---|---|---|
| `XLOG_GIN_CREATE_PTREE` | `ginRedoCreatePTree` (44) | Init a fresh posting-tree leaf with `GIN_DATA|GIN_LEAF|GIN_COMPRESSED`, memcpy in posting list |
| `XLOG_GIN_INSERT` | `ginRedoInsert` (346) | Clears `INCOMPLETE_SPLIT` on child (block 1) when inserting a downlink. Dispatches to `ginRedoInsertEntry` (entry tree) or `ginRedoInsertData` (data tree, leaf→`ginRedoRecompress` or internal→`GinDataPageAddPostingItem`) |
| `XLOG_GIN_SPLIT` | `ginRedoSplit` (400) | **Always restored from full-page images** — primary always logs `REGBUF_FORCE_IMAGE` for splits. Asserts each block restored via `BLK_RESTORED`, ERRORs otherwise. Clears child INCOMPLETE_SPLIT in block 3 if non-leaf split |
| `XLOG_GIN_VACUUM_PAGE` | `ginRedoVacuumPage` (438) | Whole-page FPI; entry-tree page vacuum |
| `XLOG_GIN_VACUUM_DATA_LEAF_PAGE` | `ginRedoVacuumDataLeafPage` (450) | Posting-tree leaf recompression — incremental via `ginRedoRecompress` |
| `XLOG_GIN_DELETE_PAGE` | `ginRedoDeletePage` (475) | Posting-tree page deletion; sets `GIN_DELETED` + `deleteXid` |
| `XLOG_GIN_UPDATE_META_PAGE` | `ginRedoUpdateMetapage` (526) | Fastupdate metapage update + tail-page tuple append OR new-tail-page link |
| `XLOG_GIN_INSERT_LISTPAGE` | `ginRedoInsertListPage` (617) | Initialize a pending-list page from scratch |
| `XLOG_GIN_DELETE_LISTPAGE` | `ginRedoDeleteListPages` (672) | Bulk-delete pending-list head pages after they were merged into entry tree |

## Recovery-correctness notes [HIGH-RISK]

### No snapshot conflicts

`gin_redo` does **not** call `ResolveRecoveryConflictWithSnapshot` for any record. Explanatory comment at line 729-733: "GIN indexes do not require any conflict processing. NB: If we ever implement a similar optimization as we have in b-tree, and remove killed tuples outside VACUUM, we'll need to handle that here." [from-comment, ginxlog.c:729-733]

This is because GIN does not use `scan->kill_prior_tuple` / `ignore_killed_tuples` (per README §"Limitations"). The deleteXid on `GIN_DELETED` pages is the gate for *recycling* the page, checked at allocation time via `ginPageRecyclable`, not a snapshot conflict.

### Split replay (`ginRedoSplit`)

Splits are always logged as **forced full-page images** on every page they touch (left, right, and root if root-split). At replay, each block is fetched via `XLogReadBufferForRedo` and the return value is asserted equal to `BLK_RESTORED`. If a split record fails to deliver an FPI, replay **PANICs**. This is the price of the "splits are rare, log fat" decision in `ginPlaceToPage`. [verified-by-code, ginxlog.c:417-426; comment, ginbtree.c:601-605]

Lock-order at replay: block 0 (left/orig), block 1 (right), block 2 (root if root-split), block 3 (child if non-leaf split). `XLogReadBufferForRedo` content-locks them in registration order, which is a **standard left-to-right, parent-up order** — safe against concurrent readers on the standby. [verified-by-code, ginxlog.c:415-426]

### Delete-page replay (`ginRedoDeletePage`)

Explicit lock order: **block 2 (left sibling) → block 0 (target) → block 1 (parent)**. The comment at line 485-487 says: "Lock left page first in order to prevent possible deadlock with `ginStepRight()`." This matches the README's stated invariant that replay locks pages in the same standard order as the primary's deletion algorithm. [from-comment, ginxlog.c:485-488]

Effects: left's `rightlink` is overwritten to bypass target; target gets `GIN_DELETED` flag + `deleteXid`; parent has its `PostingItem` for target deleted.

### Delete-listpages replay (`ginRedoDeleteListPages`)

The comment at lines 691-705 is the canonical explanation for why list-page deletion does not require simultaneous locks at replay even though it does at primary-time: "shiftList() takes exclusive lock on all the pages-to-be-deleted simultaneously. During replay, however, it should be all right to lock them one at a time. This is dependent on the fact that we are deleting pages from the head of the list, and that readers share-lock the next page before releasing the one they are on." [from-comment, ginxlog.c:691-705]

No FPIs are taken for deleted listpages; each is re-initialized empty with `GIN_DELETED`.

### Metapage handling

Metapage is **always replayed via `XLogInitBufferForRedo`** (not the normal `XLogReadBufferForRedo`), and the LSN check is **skipped**: comment at lines 535-538 says "This is essentially the same as a full-page image, so restore the metapage unconditionally without looking at the LSN, to avoid torn page hazards." This applies to both `UPDATE_META_PAGE` and `DELETE_LISTPAGE` redo. [from-comment, ginxlog.c:535-540]

### Recompression replay (`ginRedoRecompress`)

The detailed implementation of posting-list-segment redo. Handles four action types: `GIN_SEGMENT_INSERT`, `GIN_SEGMENT_DELETE`, `GIN_SEGMENT_REPLACE`, `GIN_SEGMENT_ADDITEMS` (replay reconstructs the new segment by re-merging old segment from disk with items in the WAL record). Includes the **pre-9.4 uncompressed-format conversion** at lines 130-164: if the page is in pre-9.4 format, it is first compressed before the recompression replay proceeds. The "tail copy" trick (lines 263-272) handles the case where the segment-rewrite needs more space than the original layout — the unmodified tail is copied to palloc memory so the in-place write area can grow. [verified-by-code, ginxlog.c:116-316]

## Masking (`gin_mask`)

- LSN + checksum + hint bits always masked.
- For `GIN_DELETED` pages: **whole content** masked (page may be initialized to empty differently on primary/standby). [from-comment, ginxlog.c:803-808]
- Otherwise: mask unused space if `pd_lower` looks valid.

## Cross-references

- **Dispatched from:** `access/transam/rmgr.c` via `RM_GIN_ID`.
- **Calls into:** `ginutil.c` (`GinInitBuffer`, `GinInitMetabuffer`), `gindatapage.c` (`GinDataPageAddPostingItem`, `GinPageDeletePostingItem`, `GinDataLeafPageGetPostingList`), `ginpostinglist.c` (`ginCompressPostingList`, `ginPostingListDecode`, `ginMergeItemPointers`), `xlogutils.c`.

## Open questions

- The `data->prevTail != InvalidBlockNumber` else-branch in `ginRedoUpdateMetapage` (line 596) suggests a third metapage-update sub-case ("new tail"); the corresponding primary path is `ginfast.c::ginEntryInsert` writing into a new fastupdate-list tail. Whether the LSN-comparison skip is correct for *that* sub-case is asserted by the same "metapage is FPI-equivalent" comment but not verified for the tail-page block. [unverified]
- Whether `XLOG_GIN_DELETE_PAGE` could ever observe a leaf page (the asserts at lines 492/501/511 require `GinPageIsData`); the README says only posting trees support page deletion, not entry tree. [verified-by-README]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
