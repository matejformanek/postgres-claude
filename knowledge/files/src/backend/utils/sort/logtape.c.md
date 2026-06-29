# `src/backend/utils/sort/logtape.c`

- **File:** `source/src/backend/utils/sort/logtape.c` (1184 lines)
- **Header:** `source/src/include/utils/logtape.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Provides the illusion of N independent "tape devices" multiplexed onto a
single underlying `BufFile`, with block-level space recycling so that the
peak disk footprint is essentially the data volume — not 2× as it would
be if each logical tape lived in its own file. (`logtape.c:1-25`
[from-comment])

> "any one tape dataset (with the possible exception of the final output)
> is written and read exactly once in a perfectly sequential manner.
> Therefore, a datum once read will not be required again, and we can
> recycle its space for use by the new tape dataset(s) being generated."
> (`logtape.c:14-20` [from-comment])

This is what lets `tuplesort.c`'s "balanced k-way merge" run in space ≈ N,
not 2N.

## Block-chain layout

Every BLCKSZ block ends with a `TapeBlockTrailer` (`:95-101`):
```c
struct TapeBlockTrailer { int64 prev; int64 next; };
```
- `prev == -1` → first block of a tape.
- `next < 0` → last block of a tape; `(- next)` is the number of valid
  payload bytes on this block.
- `TapeBlockPayloadSize = BLCKSZ - sizeof(TapeBlockTrailer)` (`:103`).

So each logical tape is a doubly-linked chain of physical blocks inside
the underlying BufFile, with the trailer stamped on every block. Macros
`TapeBlockGetTrailer / IsLast / GetNBytes / SetNBytes` (`:104-112`).

## Free-block recycling

- `freeBlocks[]` is a **min-heap** of recycled block numbers (`:51-52,
  216`). We always allocate the lowest free block — comment notes "it's
  not clear this helps much, but it can't hurt" and asks whether LIFO
  would be better (`:42-45` [from-comment]).
- `forgetFreeSpace` (`:215`): once `LogicalTapeSetForgetFreeSpace` is
  called (the final-merge case where we know we won't extend any more),
  released blocks are simply forgotten — the file just stops growing.
- **Block accounting**: `nBlocksAllocated >= nBlocksWritten`. Blocks in
  the gap have been handed out for writing but not flushed
  yet. `nHoleBlocks` counts unused gaps left by worker BufFile
  concatenation (parallel sort) — those are for stats only, never read
  or written (`:194-205` [from-comment]).
- **Holes are filled with zeros**: `ltsWriteBlock` fills the space
  between `nBlocksWritten` and the target block with zero blocks if
  needed, because BufFile doesn't support sparse files (`:237-268`
  [verified-by-code]). Comment: "BufFile does not support 'holes'."

## Per-tape preallocation (HashAgg case)

When many tapes are being written **concurrently** (e.g. HashAgg
spilling), each tape grabs a batch of block numbers ahead of time —
starting at `TAPE_WRITE_PREALLOC_MIN = 8`, doubling up to
`TAPE_WRITE_PREALLOC_MAX = 128` (`:117-125` [from-comment]). Per-tape
prealloc list is held in `LogicalTape.prealloc[]`, sorted descending so
consumption is from the end. This reduces fragmentation but can create
holes (the comment notes the trade-off).

## Read-buffering

While **writing**, the buffer holds one partially-written block
(`buffer_size == BLCKSZ`). While **reading from an unfrozen tape**, a
larger buffer can be set (`LogicalTapeRewindForRead(lt, buffer_size)`,
`:846`) and multiple blocks are pre-read in one go — this is where
tuplesort's `merge_read_buffer_size` calculation pays off. The buffer
holds payload only — block trailers are stripped (`:130-135`).
"With a larger buffer, 'pos' wouldn't be the same as offset within page"
— so `LogicalTapeTell` asserts `buffer_size == BLCKSZ` (`:1166-1175`),
i.e. seek positions are only meaningful on **frozen** tapes (random
access result tapes).

## Parallel sort: BufFile concatenation

When the leader takes over worker tapes, each worker has produced one
frozen tape in its own BufFile. The leader's `LogicalTapeImport`
(`:609`) concatenates the worker BufFiles into the leader's tapeset.
The `LogicalTape.offsetBlockNumber` field (`:153-155, 159`) is the bias
applied to block numbers during reads so each worker's blocks resolve to
the right region of the unified BufFile.

> "Workers should have produced one final materialized tape (their entire
> output) when this happens in leader. There will always be the same
> number of runs as input tapes, and the same number of input tapes as
> participants." (`:62-67` [from-comment])

## Public API

Set lifecycle:
- `LogicalTapeSetCreate(preallocate, fileset, worker)` (`:556`) — opens
  the `BufFile`. `fileset != NULL` → SharedFileSet path (parallel sort).
- `LogicalTapeSetClose(lts)` (`:667`).
- `LogicalTapeSetForgetFreeSpace(lts)` (`:750`) — stop tracking
  recyclable blocks.
- `LogicalTapeSetBlocks(lts)` (`:1180`) — `nBlocksWritten - nHoleBlocks`.

Per-tape lifecycle:
- `LogicalTapeCreate(lts)` (`:680`) — allocates a new write tape.
- `LogicalTapeImport(lts, worker, share)` (`:609`) — import frozen
  worker tape.
- `LogicalTapeClose(lt)` (`:733`).
- `LogicalTapeFreeze(lt, share)` (`:981`) — finalize for random-access
  reading; if `share != NULL`, fill in `TapeShare` for the leader
  (parallel-sort exit).
- `LogicalTapeRewindForRead(lt, buffer_size)` (`:846`) — flush
  write buffer, switch to read mode with the given prefetch buffer size.

I/O:
- `LogicalTapeWrite(lt, ptr, size)` (`:761`), `LogicalTapeRead(lt, ptr,
  size)` (`:928`).
- `LogicalTapeBackspace(lt, size)` (`:1062`) — only meaningful on frozen
  tapes (used for `tuplesort_gettuple` backward scan).
- `LogicalTapeSeek(lt, blocknum, offset)` (`:1133`),
  `LogicalTapeTell(lt, &blocknum, &offset)` (`:1162`) — frozen-tape only.

## Key invariants

- A tape is in exactly one of three states: writing (`writing=true`),
  reading (`writing=false`), or frozen (`frozen=true`, blocks are not
  released to the freelist when read past).
- `frozen` tapes survive being read multiple times and support
  random-access seeks; non-frozen tapes consume themselves on read
  (their blocks land in `freeBlocks[]`).
- All allocations are palloc'd in the caller's memory context — file is
  `OpenTemporaryFile`-backed — so any abort path via `ereport(ERROR)`
  cleans up automatically. Caller must keep all calls for one tapeset
  in the same palloc context. (`:54-60` [from-comment])
- `TAPE_WRITE_PREALLOC_MIN = 8`, `TAPE_WRITE_PREALLOC_MAX = 128`
  (`:124-125`).

## Cross-references

- `BufFile` — `source/src/backend/storage/file/buffile.c`. Logtape sits
  directly on top.
- `tuplesort.c` — the primary consumer; uses `LogicalTapeCreate`,
  `Write`, `Read`, `Rewind`, `Freeze`, `Close`, plus `Tell`/`Seek`/
  `Backspace` for random-access result tapes.
- `nodeAgg.c` (HashAgg) — also uses logtape for spilling; this is the
  case that motivated per-tape preallocation.
- `SharedFileSet` — `source/src/backend/storage/file/sharedfileset.c` —
  for parallel-sort BufFile sharing.

## Open questions

- The exact LIFO-vs-FIFO comment ("XXX perhaps a LIFO policy for free
  blocks would be better?", `:44-45`) — never resolved.
- Worst-case "hole" inflation from BufFile concatenation in
  many-worker parallel sorts: `nHoleBlocks` can in principle make
  `nBlocksWritten - nHoleBlocks` significantly smaller than file size,
  but bounds [unverified].

## Confidence tag tally

- `[verified-by-code]` × ~8
- `[from-comment]` × ~10
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/aggregate-hash-vs-sort.md](../../../../../idioms/aggregate-hash-vs-sort.md)

