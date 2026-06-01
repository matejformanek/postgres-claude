# gindatapage.c

- **Source path:** `source/src/backend/access/gin/gindatapage.c` (1947 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `ginbtree.c` (engine; this file plugs the data-tree vtable), `ginpostinglist.c` (varbyte codec), `ginxlog.c` (replay).

## Purpose

Routines for **GIN posting-tree pages** — both internal (`PostingItem` arrays) and leaf (multiple compressed posting-list segments). Implements the `GinBtree` vtable for data trees: `dataBeginPlaceToPage`, `dataExecPlaceToPage`, `dataFindChildPage`, `dataIsMoveRight`, `dataLocateItem`, `dataPrepareDownlink`, `dataFillRoot`. [from-comment, gindatapage.c:1-13]

## Segment-size constants

```c
#define GinPostingListSegmentMaxSize 384      /* bytes */
#define GinPostingListSegmentTargetSize 256
#define GinPostingListSegmentMinSize 128
```
A leaf page contains many independent segments (compressed posting lists). Inserts split a too-big segment into two; vacuum may merge undersized neighbors. [from-comment, gindatapage.c:25-37]

## Internal pages

Use the standard `PageHeader` + GIN opaque, but content is `PostingItem[]`: per-child `{ blockNumber, rightBound (ItemPointer) }`. The right-bound of the *page itself* is stored just after the header and accessed via `GinDataPageGetRightBound`. [from-README]

## Leaf pages

- Multiple `GinPostingList` segments stored between header and `pd_lower`.
- Right-bound of the page stored just after the header.
- The gap between `pd_lower` and `pd_upper` is **unused** — this allows full-page-image compression to skip the hole (`buffer_std = true`). [from-README]

## Key entry points

- `createPostingTree` — start a new posting tree from a sorted TID array; emits `XLOG_GIN_CREATE_PTREE`.
- `ginInsertItemPointers` (declared here but high-level entry in `gininsert.c`) — drives posting-tree inserts in batches.
- `dataBeginPlaceToPage` / `dataExecPlaceToPage` — the vtable hooks called by `ginPlaceToPage` in `ginbtree.c`. The "begin" function computes the new contents in palloc-temporaries (deciding INSERT vs SPLIT); the "exec" function copies the contents and emits WAL.
- `ginScanPostingTreeToDelete` — depth-first walks the posting tree under root cleanup-lock, marking empty leaves `GIN_DELETED`. Used by VACUUM stage 2.

## Insert WAL

Posting-tree leaf inserts emit **incremental** `XLOG_GIN_INSERT` records carrying a `ginxlogRecompressDataLeaf` action list. Each action is one of `GIN_SEGMENT_INSERT`, `_DELETE`, `_REPLACE`, `_ADDITEMS`. This is the same record shape replayed by `ginRedoRecompress` in `ginxlog.c`. [verified-by-code, gindatapage.c emit-site + ginxlog.c:117-316]

Internal-page inserts emit the simpler `ginxlogInsertDataInternal`.

## Locking

All page operations driven by the `ginbtree.c` engine; this file only owns within-page mechanics inside the CRIT section. Posting-tree page deletion follows the README's "left-sibling pre-locked" protocol; the deletion code itself is in `ginvacuum.c::ginScanPostingTreeToDelete`. [from-README, README:413-417]

Tags: [from-comment, gindatapage.c:1-37], [verified-by-code for WAL action mapping].

## Open questions

- The exact split policy (target vs. max) at line ~25-37 is the heuristic; whether it interacts adversely with very long posting lists is not analyzed in code comments. [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
