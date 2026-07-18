# hash_xlog.h

- **Source path:** `source/src/include/access/hash_xlog.h` (270 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

WAL record formats for the hash AM. [from-comment, hash_xlog.h:1-12]

## Info bytes (full table)

```c
XLOG_HASH_INIT_META_PAGE      0x00
XLOG_HASH_INIT_BITMAP_PAGE    0x10
XLOG_HASH_INSERT              0x20
XLOG_HASH_ADD_OVFL_PAGE       0x30
XLOG_HASH_SPLIT_ALLOCATE_PAGE 0x40
XLOG_HASH_SPLIT_PAGE          0x50
XLOG_HASH_SPLIT_COMPLETE      0x60
XLOG_HASH_MOVE_PAGE_CONTENTS  0x70
XLOG_HASH_SQUEEZE_PAGE        0x80
XLOG_HASH_DELETE              0x90
XLOG_HASH_SPLIT_CLEANUP       0xA0
XLOG_HASH_UPDATE_META_PAGE    0xB0
XLOG_HASH_VACUUM_ONE_PAGE     0xC0
```

`HASH_XLOG_FREE_OVFL_BUFS = 6` — buffer-block budget for the squeeze record.

## xl_hash_* structs (sample)

- `xl_hash_insert` — `offnum`. Buffer 0 = target page, buffer 1 = metapage.
- `xl_hash_add_ovfl_page` — `bmsize`, `bmpage_found`. 4 buffers.
- `xl_hash_split_allocate_page` — `new_bucket`, `old_bucket_flag`, `new_bucket_flag`. Buffer 0 = old primary, 1 = new primary, 2 = metapage.
- `xl_hash_split_complete` — `old_bucket_flag`, `new_bucket_flag`.
- `xl_hash_move_page_contents` / `xl_hash_squeeze_page` — bookkeeping for squeeze.
- `xl_hash_delete` — `clear_dead_marking`, `is_primary_bucket_page`, offset list (NO snapshot conflict horizon — see `hash_xlog.c.md`).
- `xl_hash_vacuum_one_page` — `snapshotConflictHorizon`, `isCatalogRel`, `ntuples`, offset list. **Only hash record with per-record conflict.**
- `xl_hash_update_meta_page` — `ntuples`.
- `xl_hash_init_meta_page` — full metapage contents replay.
- `xl_hash_init_bitmap_page` — bitmap size.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/hash-overflow-pages.md](../../../../idioms/hash-overflow-pages.md)

- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)