# ginblock.h

- **Source path:** `source/src/include/access/ginblock.h` (346 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

On-disk page layouts for GIN: opaque struct, metapage struct, flag bits, page-type predicates, posting-list layout, null-category codes. [from-comment, ginblock.h:1-9]

## `GinPageOpaqueData` (the 8-byte page-trailer)

```c
{ BlockNumber rightlink; OffsetNumber maxoff; uint16 flags; }
```
Important: GIN deliberately does **not** include a `gin_page_id` word — the 8-byte opaque is small enough that it cannot collide with the page-IDs used by SP-GiST/BRIN, **as long as GIN doesn't use all high bits of `flags`**. [from-comment, ginblock.h:21-29]

## Flag bits (in `flags`)

- `GIN_DATA` — posting-tree page (not entry tree).
- `GIN_LEAF` — leaf level.
- `GIN_DELETED` — page is deleted, recyclable when `deleteXid` is globally invisible.
- `GIN_META` — metapage.
- `GIN_LIST` — fastupdate pending-list page.
- `GIN_LIST_FULLROW` — pending-list page contains complete rows (else partial).
- `GIN_INCOMPLETE_SPLIT` — split done but parent downlink not yet inserted.
- `GIN_COMPRESSED` — posting-tree leaf in 9.4+ compressed format (vs pg_upgraded uncompressed).

## Metapage (`GinMetaPageData`)

- `head`, `tail` — pending-list head/tail blocks.
- `tailFreeSize` — bytes free on tail page (for fast-path append).
- `nPendingPages`, `nPendingHeapTuples` — pending-list counters.
- `nTotalPages`, `nEntryPages`, `nDataPages`, `nEntries`, `ginVersion` — stats.

## Null categories

```c
#define GIN_CAT_NORM_KEY    0
#define GIN_CAT_NULL_KEY    1
#define GIN_CAT_EMPTY_ITEM  2
#define GIN_CAT_NULL_ITEM   3
#define GIN_CAT_EMPTY_QUERY (-1)  /* sentinel for extractQuery */
```

## Posting list / item access

- `GinPostingList` struct: `{ first: ItemPointerData, nbytes: uint16, bytes[FLEX] }`.
- `PostingItem` (internal-page child): `{ key: ItemPointerData rightBound, child_blkno: BlockIdData }`.
- `GinSetDownlink(itup, blkno)`, `GinGetDownlink(itup)`, `GinSetPostingTree(itup, blkno)`, `GinGetPostingOffset(itup)`, etc. — t_tid abuse macros.
