# ginxlog.h

- **Source path:** `source/src/include/access/ginxlog.h` (219 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

WAL record formats and `XLOG_GIN_*` info bytes for GIN. [from-comment, ginxlog.h:1-9]

## Info bytes

| Bit | Meaning |
|---|---|
| `XLOG_GIN_CREATE_PTREE` (0x10) | Create a new posting tree leaf with a starting posting list |
| `XLOG_GIN_INSERT` (0x20) | Insert into entry tree OR posting tree; common header + tree-type-specific payload |
| `XLOG_GIN_SPLIT` (0x30) | Page split (always logged with FPI on every changed page) |
| `XLOG_GIN_VACUUM_PAGE` (0x40) | Entry-tree page vacuum (FPI) |
| `XLOG_GIN_VACUUM_DATA_LEAF_PAGE` (0x90) | Posting-tree leaf incremental recompression |
| `XLOG_GIN_DELETE_PAGE` (0x50) | Posting-tree page deletion |
| `XLOG_GIN_UPDATE_META_PAGE` (0x60) | Fastupdate metapage update |
| `XLOG_GIN_INSERT_LISTPAGE` (0x70) | New fastupdate listpage |
| `XLOG_GIN_DELETE_LISTPAGE` (0x80) | Bulk-delete consumed listpages |

## xlog struct family

- `ginxlogCreatePostingTree` — `size` + inline compressed list.
- `ginxlogInsert` — `flags` (ISDATA/ISLEAF/etc.) + per-tree-type payload.
- `ginxlogInsertEntry` — for entry tree: `isDelete`, `offset`, `tuple`.
- `ginxlogRecompressDataLeaf` — for posting-tree leaf: `nactions` + action stream (`GIN_SEGMENT_INSERT`/`_DELETE`/`_REPLACE`/`_ADDITEMS`).
- `ginxlogInsertDataInternal` — for posting-tree internal: `offset`, `newitem: PostingItem`.
- `ginxlogSplit` — `flags`, `leftChildBlkno`, `rightChildBlkno`, `rrlink` (right-of-right link).
- `ginxlogVacuumDataLeafPage` — wraps `ginxlogRecompressDataLeaf`.
- `ginxlogDeletePage` — `parentOffset`, `rightLink`, `deleteXid`.
- `ginxlogUpdateMeta` — `metadata: GinMetaPageData`, `ntuples`, `prevTail`, `newRightlink`.
- `ginxlogInsertListPage` — `rightlink`, `ntuples` + inline tuples.
- `ginxlogDeleteListPages` — `metadata`, `ndeleted`, list of deleted blocks.

Segment action constants: `GIN_SEGMENT_UNMODIFIED` (= 0), `GIN_SEGMENT_DELETE`, `GIN_SEGMENT_INSERT`, `GIN_SEGMENT_REPLACE`, `GIN_SEGMENT_ADDITEMS`.

See `ginxlog.c.md` for replay semantics.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)
