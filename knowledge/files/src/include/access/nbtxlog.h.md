# nbtxlog.h

- **Source path:** `source/src/include/access/nbtxlog.h` (367 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtxlog.c` (the replay functions), every emitter file under `access/nbtree/`.

## Purpose

Defines the on-disk WAL record formats for the nbtree resource manager: 14 `XLOG_BTREE_*` info bytes (high 4 bits of `xl_info`), one record `struct` per "kind", and the backup-block conventions (which blocks each variant registers, and what's in their `BufData` payload). [from-comment, nbtxlog.h:1-26]

## Info bytes (27-44)

```
0x00  XLOG_BTREE_INSERT_LEAF
0x10  XLOG_BTREE_INSERT_UPPER     (also clears INCOMPLETE_SPLIT on child)
0x20  XLOG_BTREE_INSERT_META      (also rewrites metapage)
0x30  XLOG_BTREE_SPLIT_L          (new item went to left half)
0x40  XLOG_BTREE_SPLIT_R          (new item went to right half)
0x50  XLOG_BTREE_INSERT_POST      (leaf insert with posting-list split)
0x60  XLOG_BTREE_DEDUP            (deduplication pass)
0x70  XLOG_BTREE_DELETE           (ad-hoc delete with snapshotConflictHorizon)
0x80  XLOG_BTREE_UNLINK_PAGE      (delete a half-dead page)
0x90  XLOG_BTREE_UNLINK_PAGE_META (same + metapage update)
0xA0  XLOG_BTREE_NEWROOT
0xB0  XLOG_BTREE_MARK_PAGE_HALFDEAD
0xC0  XLOG_BTREE_VACUUM           (VACUUM delete; no per-record conflict)
0xD0  XLOG_BTREE_REUSE_PAGE       (Hot Standby conflict at recycle time)
0xE0  XLOG_BTREE_META_CLEANUP     (metapage btm_last_cleanup_num_delpages update)
```

## Records

### `xl_btree_metadata` (49-58)

What's needed to rebuild the metapage: `version`, `root`, `level`, `fastroot`, `fastlevel`, `last_cleanup_num_delpages`, `allequalimage`.

### `xl_btree_insert` (79-87)

Just `offnum`. Used by INSERT_LEAF, INSERT_UPPER, INSERT_META, INSERT_POST. The new tuple is appended raw after the record. For INSERT_POST, a `uint16 postingoff` comes between the header and the tuple. Backup blocks: 0 = page; 1 = child (INSERT_UPPER/META); 2 = metapage (INSERT_META). [from-comment, nbtxlog.h:60-87]

### `xl_btree_split` (153-161)

Page-split record. Fields: `level`, `firstrightoff`, `newitemoff`, `postingoff`. Same struct for `_L` and `_R`.

The comment block at lines 89-152 is the **canonical explanation of split WAL** and is worth quoting in full when reading `_bt_split` or `btree_xlog_split`:

- "We save all the items going into the right sibling so that we can restore it completely from the log record. This way takes less xlog space than the normal approach, because if we did it standardly, XLogInsert would almost always think the right page is new and store its whole page image. The left page, however, is handled in the normal incremental-update fashion."
- "We always log the left page high key because suffix truncation can generate a new leaf high key using user-defined code."
- Backup blocks: 0 = original/left page (incremental); 1 = new right page (whole-page payload via `_bt_restore_page`); 2 = original right sibling (left-link fix); 3 = child block (clear INCOMPLETE_SPLIT, non-leaf splits only).

Posting-list-during-split handling: see lines 116-139 — `postingoff != 0` means REDO must rebuild a posting tuple for the *left* page; `newitem` is logged as `orignewitem` (pre-swap state) in that case.

### `xl_btree_dedup` (170-175)

`uint16 nintervals` + an array of `BTDedupInterval` describing which consecutive groups of items become posting lists.

### `xl_btree_reuse_page` (186-195)

`locator` (RelFileLocator — explicit because the buffer is NOT registered with the record) + `block` + `snapshotConflictHorizon` (FullTransactionId, matching the page's stored `safexid`) + `isCatalogRel`. **The standby uses `snapshotConflictHorizon` to resolve conflicting snapshots — this is the conflict point for nbtree page recycling.**

### `xl_btree_vacuum` (223-237) and `xl_btree_delete` (239-256)

Twin records: both describe deletion of any number of leaf items by offset, plus "updates" (partial-TID deletion from posting lists). Difference: `xl_btree_delete` carries a `snapshotConflictHorizon` (TransactionId, not FullTransactionId) + `isCatalogRel` for recovery-conflict resolution; `xl_btree_vacuum` does not, because the heap-vacuum WAL record already raised the conflict for the same TIDs. [from-comment, nbtxlog.h:198-222]

### `xl_btree_update` (264-269)

Per-posting-tuple metadata used inside the `xl_btree_vacuum`/`xl_btree_delete` payload. Says which TIDs *within* a posting list to drop, identified by 0-based offsets into the original list. The page offset of the posting tuple itself comes from the outer record's `updatedoffsets[]` payload.

### `xl_btree_mark_page_halfdead` (283-292)

What phase 1 of page deletion writes: `poffset` (location of removed downlink in subtree parent), plus the data needed to **recreate** the half-dead leaf from scratch: `leafblk`, `leftblk`, `rightblk`, `topparent`. Backup blocks: 0 = leaf (REGBUF_WILL_INIT); 1 = subtree parent.

### `xl_btree_unlink_page` (310-329)

What phase 2 of page deletion writes: `leftsib`, `rightsib`, `level`, `safexid` (FullTransactionId), plus extra fields for the case where the deletion is of an internal page (target ≠ leaf): `leafleftsib`, `leafrightsib`, `leaftopparent`. Backup blocks: 0 = target (WILL_INIT, rebuilt from scratch as a deleted page); 1 = left sib if any; 2 = right sib; 3 = leaf if target was internal; 4 = metapage if `_META` variant.

**The `safexid` field is what allows recovery to write the correct tombstone:** standby replay calls `BTPageSetDeleted(page, safexid)` with the same FullTransactionId the primary used, so both copies of the page advertise the same recycle horizon. The Hot Standby conflict, however, is *not* emitted here — it's deferred to the eventual `xl_btree_reuse_page` record at recycle time. [from-comment, nbtxlog.c:966-991; verified-by-code]

### `xl_btree_newroot` (344-350)

`rootblk`, `level`. Backup blocks: 0 = new root (with 2-tuple payload for a normal root split, empty for an empty-index root creation); 1 = left child (clear INCOMPLETE_SPLIT); 2 = metapage.

## Function prototypes (354-365)

- `btree_redo` — the dispatcher in `nbtxlog.c`.
- `btree_xlog_startup`/`btree_xlog_cleanup` — pre/post-replay (set up/tear down the `opCtx` memory context in nbtxlog.c).
- `btree_mask` — page-content masking for `wal_consistency_checking`.
- `btree_desc`/`btree_identify` — used by `pg_waldump` (defined in `access/rmgrdesc/nbtdesc.c`).

## Why this file is worth reading carefully

The on-disk format here is the canonical spec for what nbtree promises to crash-safe. Any change to a record type is an upgrade event; any divergence between the primary emitter and the REDO routine is a data-corruption bug. The header is the contract; nbtinsert.c/nbtpage.c are one side and nbtxlog.c is the other.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-nbtree.md](../../../../subsystems/access-nbtree.md)

- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)