# gist_private.h

- **Source path:** `source/src/include/access/gist_private.h` (567 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Implementation-private GiST declarations shared across `src/backend/access/gist/*.c`. [from-comment, gist_private.h:1-10]

## Key types

- `GISTInsertStack` — per-frame state during descent: page, downlink offset, parent pointer, LSN-at-visit.
- `GISTInsertState` — per-insert: stack, freespace, key sizes.
- `GISTSearchItem` / `GISTSearchHeapItem` — queue entries for `gistget.c`.
- `GISTScanOpaqueData` — scan-time state.
- `GISTBuildBuffers` / `GISTNodeBuffer` / `GISTNodeBufferPage` — buffering-build data structures.
- `GISTSearchTreeItem` — pairing-heap node.
- `GistEntryVector`, `GistSplitVector` — bulk-key types.
- `gistxlogPageSplit` / `gistxlogPage*` — record-format aliases (the records themselves live in `gistxlog.h`).

## Key constants

- `GIST_MAX_SPLIT_PAGES` — N-way split cap.
- `BUFFERING_OFF`, `BUFFERING_AUTO`, `BUFFERING_STATS`, `BUFFERING_ON` — `buffering` reloption values.
- `GIST_SORTED_BUILD_PAGE_NUM` — threshold for sorted-build packing.

## Prototypes

Functions across gist/gistget/gistsplit/gistutil/gistvacuum/gistbuild/gistbuildbuffers/gistscan/gistxlog.
