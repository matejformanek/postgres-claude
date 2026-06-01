# heapam_xlog.c

- **Source path:** `source/src/backend/access/heap/heapam_xlog.c`
- **Lines:** 1359
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `heapam_xlog.h` (record formats), `heapam.c` (emitters), `xlog.c` (rmgr dispatch), `pg_waldump` consumes the desc routines.

## Purpose

WAL redo for the heap access method. Two top-level dispatch functions (`heap_redo` for `RM_HEAP_ID`, `heap2_redo` for `RM_HEAP2_ID`) plus a `heap_mask` for the page-masking used by `wal_consistency_checking`. Each WAL opcode has a `heap_xlog_*` static handler. The desc/identify routines live in `access/rmgrdesc/heapdesc.c` (shared with frontend). [verified-by-code, heapam_xlog.c:1-30]

## Top-of-file comment
> "WAL replay logic for heap access method." [from-comment, heapam_xlog.c:1-13]

## Public surface (non-static functions)

- `heap_redo(XLogReaderState *record)` (line 1199) — dispatcher for RM_HEAP_ID opcodes.
- `heap2_redo(XLogReaderState *record)` (line 1245) — dispatcher for RM_HEAP2_ID opcodes.
- `heap_mask(char *pagedata, BlockNumber blkno)` (line 1281) — used by `wal_consistency_checking` to ignore hint-bit-only differences.

## Static handlers (per opcode)

- `heap_xlog_prune_freeze` (30) — replays the unified XLOG_HEAP2_PRUNE_* record. Handles cleanup-lock requirement, conflict horizon, VM bit setting, freeze plan application, redirect/dead/unused item changes, and FSM update.
- `fix_infomask_from_infobits` (266) — decodes XLHL_* bits into infomask/infomask2.
- `heap_xlog_delete` (290), `heap_xlog_insert` (366), `heap_xlog_multi_insert` (492), `heap_xlog_update` (697 — handles both UPDATE and HOT_UPDATE via `hot_update` parameter), `heap_xlog_confirm` (976 — speculative-insert confirmation), `heap_xlog_lock` (1015), `heap_xlog_lock_updated` (1089), `heap_xlog_inplace` (1152 — catalog inplace, also fires shared-inval messages).

## Key types / structs
None defined here; consumes structs from `heapam_xlog.h`.

## Key invariants and locking

- **Cleanup lock requirement.** `heap_xlog_prune_freeze` asserts: if `XLHP_CLEANUP_LOCK` is *not* set, then `XLHP_HAS_REDIRECTIONS | XLHP_HAS_DEAD_ITEMS` must also be unset (because those mutations require moving tuple data and thus need a cleanup lock). [verified-by-code, heapam_xlog.c:291-298]
- **Conflict horizon.** When `XLHP_HAS_CONFLICT_HORIZON` is set, redo on a hot standby calls `ResolveRecoveryConflictWithSnapshot(snapshot_conflict_horizon, …)` before applying the change. The horizon is read **unaligned** via memcpy. [verified-by-code, heapam_xlog.c:307-326]
- **VM bit setting from prune record.** The VM bits are set as part of the prune record's redo (lines after the prune sub-records are applied). This is the *only* path that sets VM bits in modern PG (the old XLOG_HEAP2_VISIBLE opcode is gone). [from-comment in heapam_xlog.h:336-342; verified-by-code]
- **FSM update.** `do_update_fsm` flag accumulated through the redo; if free space changed materially, `RecordPageWithFreeSpace` is called after the buffer is released. [verified-by-code, heapam_xlog.c around line 285]
- `XLOG_HEAP_INIT_PAGE` records: redo reinitialises the page from scratch via `PageInit`, then applies the operation. Used for first-insert-on-new-page cases. [verified-by-code, heapam_xlog.c:366+]
- `heap_xlog_inplace` (1152) emits shared-invalidation messages during redo via `XLogProcessSharedInval`/`CacheInvalidateRelcache` so standbys correctly invalidate their relcache after a catalog in-place update. [verified-by-code]
- Redo must be **idempotent**: every handler checks page LSN vs record LSN before applying (`XLogReadBufferForRedo` returns `BLK_NEEDS_REDO` vs `BLK_DONE`). [verified-by-code, standard PG pattern]

## Functions of note

1. **`heap_xlog_prune_freeze`** (line 30) — The most complex redo handler. After deserialising via `heap_xlog_deserialize_prune_and_freeze` (in `heapdesc.c`): apply freeze plans (in-place tuple header rewrites), call `heap_page_prune_execute` for the redirect/dead/unused offsets, optionally set VM bits, optionally record FSM space. Holds cleanup lock or exclusive lock based on the flag. [verified-by-code]

2. **`heap_xlog_update`** (line 697) — Used for both UPDATE and HOT_UPDATE. The challenging part: reconstructs the new tuple from `xl_heap_update` + optional prefix/suffix from the old tuple (stored in old buffer's old image). Handles cross-page case (old and new on different blocks; must reacquire both buffers in canonical order). [verified-by-code]

3. **`heap_xlog_multi_insert`** (line 492) — Iterates over the `xl_multi_insert_tuple` array, reconstructs each tuple's header, adds via `PageAddItemExtended`. Honours `XLH_INSERT_ALL_FROZEN_SET`: sets `PD_ALL_VISIBLE` on the page and the VM bits. [verified-by-code]

4. **`heap_mask`** (line 1281) — For `wal_consistency_checking`: masks volatile fields (hint bits, line pointer flags that flicker between LP_DEAD and LP_NORMAL until pruning) so masked-equality comparison works. [verified-by-code]

## Cross-references

- Called by: `xlog.c`'s rmgr dispatcher (`access/transam/rmgr.c` table); registered via `RM_HEAP_ID` and `RM_HEAP2_ID` in `access/transam/rmgrlist.h`.
- Calls into: `bufmgr.c` (`XLogReadBufferForRedo`, `XLogReadBufferForRedoExtended`), `visibilitymap.c` (`visibilitymap_pin`, `visibilitymap_set`), `pruneheap.c` (`heap_page_prune_execute`), `standby.c` (`ResolveRecoveryConflictWithSnapshot`), `freespace.c` (`RecordPageWithFreeSpace`), `inval.c` (for inplace records).

## Open questions

- Whether the FPI (full-page image) fast path in any record bypasses some of the field reconstruction logic — the `XLogReadBufferForRedo` return value drives this but I did not enumerate each handler's FPI branch. [unverified]
- `heap_xlog_logical_rewrite` is declared in heapam_xlog.h but implemented in `rewriteheap.c`, not here. [verified-by-code]

## Confidence tag tally
`[verified-by-code]=12 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=1`
