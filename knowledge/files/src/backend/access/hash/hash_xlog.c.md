# hash_xlog.c

- **Source path:** `source/src/backend/access/hash/hash_xlog.c` (1154 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/hash_xlog.h` (record formats), all emitter files.

## Purpose

WAL redo (`hash_redo`) and masking (`hash_mask`) for the hash AM. 13 record types. [from-comment, hash_xlog.c:1-13]

## Record-to-handler table

| Info | Handler | Notes |
|---|---|---|
| `XLOG_HASH_INIT_META_PAGE` (0x00) | `hash_xlog_init_meta_page` | metapage init from scratch (CREATE INDEX) |
| `XLOG_HASH_INIT_BITMAP_PAGE` (0x10) | `hash_xlog_init_bitmap_page` | initial bitmap page during CREATE INDEX |
| `XLOG_HASH_INSERT` (0x20) | `hash_xlog_insert` | 2 blocks: target page + metapage. Metapage update is incremental |
| `XLOG_HASH_ADD_OVFL_PAGE` (0x30) | `hash_xlog_add_ovfl_page` | 4 blocks: new overflow page (INIT), previous-last (link update), bitmap page, metapage |
| `XLOG_HASH_SPLIT_ALLOCATE_PAGE` (0x40) | `hash_xlog_split_allocate_page` | New primary bucket page + metapage update (maxbucket, lowmask, highmask, spares) |
| `XLOG_HASH_SPLIT_PAGE` (0x50) | `hash_xlog_split_page` | Move N tuples from old to new bucket page; payload includes the new tuples |
| `XLOG_HASH_SPLIT_COMPLETE` (0x60) | `hash_xlog_split_complete` | Clear `H_BUCKET_BEING_SPLIT` on old + `H_BUCKET_BEING_POPULATED` on new + set `H_NEEDS_SPLIT_CLEANUP` on old |
| `XLOG_HASH_MOVE_PAGE_CONTENTS` (0x70) | `hash_xlog_move_page_contents` | Squeeze: move tuples from one overflow page to a previous one |
| `XLOG_HASH_SQUEEZE_PAGE` (0x80) | `hash_xlog_squeeze_page` | Compact a bucket (post-vacuum) |
| `XLOG_HASH_DELETE` (0x90) | `hash_xlog_delete` | VACUUM tuple removal; NO recovery conflict (heap pruning already published it) |
| `XLOG_HASH_SPLIT_CLEANUP` (0xA0) | `hash_xlog_split_cleanup` | Clear `H_NEEDS_SPLIT_CLEANUP` on old after VACUUM verifies it's safe |
| `XLOG_HASH_UPDATE_META_PAGE` (0xB0) | `hash_xlog_update_meta_page` | Post-VACUUM tuple-count adjustment |
| `XLOG_HASH_VACUUM_ONE_PAGE` (0xC0) | `hash_xlog_vacuum_one_page` | Opportunistic LP_DEAD cleanup at insert time. **Emits recovery conflict** via `ResolveRecoveryConflictWithSnapshot(snapshotConflictHorizon)` because this happens outside a heap-vacuum context |

## Recovery-correctness notes [HIGH-RISK]

### Split is logged across MULTIPLE records, NOT atomically

Per README §"WAL Considerations" (lines 588-602): a split causes one `SPLIT_ALLOCATE_PAGE` + one or more `SPLIT_PAGE` (per old-page worth of moves) + one `SPLIT_COMPLETE`. Between any two of these, a crash can leave the bucket "mid-split" — `H_BUCKET_BEING_SPLIT` set on old and `H_BUCKET_BEING_POPULATED` set on new. Recovery is implicit: the reader algorithm handles both flags correctly, and the next inserter on the old bucket runs `_hash_finish_split`. [from-README, README:596-613]

### `XLOG_HASH_DELETE` has NO snapshotConflictHorizon

Comment-context: heap pruning already published the cutoff via `XLOG_HEAP2_PRUNE_VACUUM_SCAN`, so the index VACUUM record need not duplicate. [from-README, README:619; verified-by-code, no Resolve call in `hash_xlog_delete`]

### `XLOG_HASH_VACUUM_ONE_PAGE` DOES emit conflict

Because it happens at insert time (no preceding heap-vacuum record to anchor the cutoff). The `snapshotConflictHorizon` is the AM's local cutoff computed from the killed items.

### Metapage updates

Several record types touch the metapage. Replay always re-applies the increments — metapage is *not* fully overwritten unless `XLOG_HASH_INIT_META_PAGE` (which is the only "write whole metapage" record). For `XLOG_HASH_INSERT`, only the tuple-count is bumped.

### Squeeze records (`MOVE_PAGE_CONTENTS`, `SQUEEZE_PAGE`)

Move tuples from one overflow page to an earlier page in the bucket chain. Per README §"Freeing an overflow page", the move-and-delink must be atomic on standby to avoid the user seeing the same tuple twice. The records carry both source and destination state. [from-README, README:558-561]

## Masking (`hash_mask`)

- LSN/checksum/hint bits masked as standard.
- For bitmap pages: the page content is the bitmap itself; masked carefully.
- For pages in `H_BUCKET_BEING_SPLIT` state: certain flags are masked (the populated-during-split state can race between primary and standby).

## Cross-references

- **Dispatched from:** `access/transam/rmgr.c` via `RM_HASH_ID`.
- **Calls into:** `xlogutils.c`, `standby.c::ResolveRecoveryConflictWithSnapshot`.

## Open questions

- Whether a standby that replayed `SPLIT_ALLOCATE_PAGE` but not `SPLIT_COMPLETE` exposes correct read semantics to a Hot Standby query. The reader algorithm's "scan both old and new with moved-by-split filter" should handle it, but no test specifically exercises this. [unverified]
