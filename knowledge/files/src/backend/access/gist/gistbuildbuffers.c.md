# gistbuildbuffers.c

- **Source path:** `source/src/backend/access/gist/gistbuildbuffers.c` (759 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The temp-file-backed **node buffers** used by GiST's buffering build algorithm. Each internal node at certain levels has an attached buffer; new index tuples are pushed into buffers during top-down traversal instead of being inserted into a leaf immediately. When a buffer fills, it's flushed to the level below in bulk. [from-README, README:297-423]

## Key types

- `GISTBuildBuffers` — the per-build coordinator. Owns the temp `BufFile`, free-page list, level map, and the emptying queue.
- `GISTNodeBuffer` — one buffer per buffered internal node. Has an in-memory "last page" + a list of swapped-out pages.
- `GISTNodeBufferPage` — fixed-size page of `IndexTuple`s, stored in the temp file.

## Key entry points

- `gistInitBuildBuffers` — start a new build, decide `level_step` (which levels have buffers).
- `gistAllocateNewPageBuffer` (static) — get a free page from the temp file.
- `gistGetNodeBuffer` — find or create the buffer for a given internal-node block.
- `gistPushItupToNodeBuffer` — append a tuple to a buffer; if last-page full, allocate next.
- `gistPopItupFromNodeBuffer` — pop one tuple for cascade emptying.
- `gistRelocateBuildBuffersOnSplit` — when a buffered internal node splits, distribute its buffer tuples to the new siblings using opclass `penalty`.
- `gistFreeBuildBuffers` — close temp file, release memory.

## Memory state machine

Each buffer is in one of two states:
- (a) **Last page in memory**: active append target. Auto-switches here on push/pop.
- (b) **Swapped out**: all pages on disk. Used when memory pressure is high (during emptying, every *other* buffer is forced to state b).

[from-README, README:344-350]

## Emptying

Triggered when a top-level buffer becomes ½ full. Continues until ½ of the buffer has been emptied (guarantees lower-level buffers stay ≤ ½ full). Tuples flow down via repeated `gistGetNodeBuffer` + `gistPushItupToNodeBuffer`, or hit a leaf and call `gistplacetopage`. [from-README, README:401-409]

## Split of a buffered node

When a buffered internal page is split (by an incoming downlink insert), the buffer must split too. All tuples are scanned through and pushed to whichever child has lower `penalty` — exactly the same selection rule used at descent time.

Tags: [from-comment]; [from-README, README:297-423 — extensively cited].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
