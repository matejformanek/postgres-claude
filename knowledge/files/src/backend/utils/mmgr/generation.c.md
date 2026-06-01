# `src/backend/utils/mmgr/generation.c`

- **File:** `source/src/backend/utils/mmgr/generation.c` (1244 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Specialized `MemoryContext` for workloads where chunks are allocated and
freed in roughly FIFO order, or in "generations" with similar lifespans
— e.g. tuple-queue patterns. No global freelist: each block just counts
allocated vs freed chunks, and a block whose two counts equal is either
recycled as `freeblock` for the next allocation or returned to malloc.

## Top-of-file comment (verbatim)

```
This memory context is based on the assumption that the chunks are freed
roughly in the same order as they were allocated (FIFO), or in groups with
similar lifespan (generations - hence the name of the context). This is
typical for various queue-like use cases, i.e. when tuples are constructed,
processed and then thrown away.

The memory context uses a very simple approach to free space management.
Instead of a complex global freelist, each block tracks a number
of allocated and freed chunks.  The block is classed as empty when the
number of free chunks is equal to the number of allocated chunks.  When
this occurs, instead of freeing the block, we try to "recycle" it, i.e.
reuse it for new allocations.  This is done by setting the block in the
context's 'freeblock' field.  If the freeblock field is already occupied
by another free block we simply return the newly empty block to malloc.
```
(`generation.c:15-31` [from-comment])

## Public surface

- Creator: `GenerationContextCreate(parent, name, minContextSize,
  initBlockSize, maxBlockSize)` (`:162`).
- Method-table callbacks (wired in `mcxt.c:80-91`): `GenerationAlloc`,
  `GenerationFree`, `GenerationRealloc`, `GenerationReset`,
  `GenerationDelete`, `GenerationGetChunkContext`,
  `GenerationGetChunkSpace`, `GenerationIsEmpty`, `GenerationStats`,
  `GenerationCheck` (under `MEMORY_CONTEXT_CHECKING`).

## Key types

- `GenerationContext` (`:61-75`) — header + `initBlockSize`,
  `maxBlockSize`, `nextBlockSize`, `allocChunkLimit`, `block` (current
  fill target — head of list), `freeblock` (the at-most-one recycled
  empty block waiting for reuse), `blocks` dlist head.
- `GenerationBlock` (`:88-98`) — `dlist_node`, back-pointer to context,
  `blksize`, `nchunks`, `nfree`, `freeptr`/`endptr`. Block is empty
  iff `nchunks == 0` (`:118`); per the doc comment, an "empty" state
  for recycling is `nchunks == nfree`, in which case `GenerationFree`
  resets `nchunks = nfree = 0` and either recycles or frees.

## Key invariants

- **No per-context freelist.** Pfree just decrements `block->nfree`; if
  the block becomes empty it's either dropped into `set->freeblock`
  (if NULL) or `free()`d immediately. The recycling slot holds *at
  most one* block (`:25-28` [from-comment]).
- **Keeper block** lives in the same malloc as the context header, is
  never returned to malloc, same idiom as AllocSet (`:208-211, 286-289,
  314-318` [verified-by-code], [from-comment]).
- **Large chunks (size > `allocChunkLimit`) go on dedicated single-chunk
  blocks** with `MemoryChunkSetHdrMaskExternal` and `MCTX_GENERATION_ID`
  (`:404-405`). `allocChunkLimit` is computed so at least
  `Generation_CHUNK_FRACTION = 8` chunks of that size fit in
  `maxBlockSize`, capped at `MEMORYCHUNK_MAX_VALUE` (`:51, 264-267`
  [verified-by-code]).
- **Block doubling** identical to AllocSet — `nextBlockSize` starts at
  `initBlockSize`, doubles up to `maxBlockSize` (`:250-252` plus the
  AllocFromNewBlock helper [verified-by-code]).
- **Validation in create** mirrors AllocSet/Bump: 1 KB minimum,
  MAXALIGN'd, `maxBlockSize <= MEMORYCHUNK_MAX_BLOCKOFFSET`
  (`:177-197`).

## Functions of note

1. **`GenerationContextCreate` (`:162-279`)** — same shape as
   `AllocSetContextCreateInternal` and `BumpContextCreate`: malloc one
   chunk for header + keeper, Valgrind-create vpool + cover-vchunk,
   init keeper, set `block = keeper`, `freeblock = NULL`, compute
   `allocChunkLimit`, finish with `MemoryContextCreate`.
2. **`GenerationReset` (`:291-337`)** — clears `freeblock` *first* (so
   the freeing pass doesn't try to "recycle" into a slot that's being
   torn down), walks the dlist, marks keeper empty in place, frees all
   non-keeper blocks, then `VALGRIND_MEMPOOL_TRIM` and
   `nextBlockSize = initBlockSize`. Sets `set->block = KeeperBlock(set)`
   so new allocations resume from the keeper.
3. **`GenerationDelete` (`:343-354`)** — `GenerationReset` then
   `VALGRIND_DESTROY_MEMPOOL` and `free(context)` (single malloc).
4. **`GenerationAllocLarge` (`:362-429`)** — mallocs a dedicated block
   sized exactly to the chunk, marks `MemoryChunk` as external,
   `dlist_push_head`'s into `set->blocks`. Note `block->nchunks=1,
   nfree=0` so pfree of this chunk will satisfy "empty" and free the
   whole block.
5. **`GenerationAlloc`** (not shown above but follows `:466+` pattern;
   reachable via `mcxt_methods[MCTX_GENERATION_ID].alloc`) — bumps from
   `set->block->freeptr`; on overflow, if `set->freeblock` exists and
   fits, recycles it (no malloc), else `malloc`s a new block sized by
   `nextBlockSize`. The recycling path is what makes Generation
   cheaper than AllocSet for steady-state queue workloads
   [verified-by-code via the larger `:430-700` block, not all
   transcribed].
6. **`GenerationFree`** — decrements `nfree`/`nchunks` counters; when
   block becomes empty, either parks it in `freeblock` or frees it.
   External chunks always free their block immediately
   [verified-by-code via grep on this file].
7. **`GenerationRealloc`** — if the new size fits in the current chunk
   the chunk just gets a bigger `requested_size`; otherwise alloc +
   memcpy + free, since there's no in-block growth (chunks are bump-
   allocated, the next chunk's bytes are taken) [verified-by-code].

## Cross-references

- `mcxt.c:80-91` — vtable wiring.
- `memutils_internal.h:38-53` — function prototypes.
- Callers: logical-decoding reorder buffer historically used Slab; the
  apply/spill paths use Generation for FIFO tuple buffers
  [unverified — not chased].
- `aset.c` and `bump.c` share the keeper-block + `MemoryChunk`-based
  bookkeeping pattern; this is the FIFO-tuned middle ground.

## Open questions

- Whether `freeblock` ever holds the keeper itself: `GenerationReset`
  clears `freeblock` to NULL before the walk and the walk uses
  `GenerationBlockMarkEmpty` (no free) for the keeper, so the keeper
  shouldn't end up in `freeblock` — but the comment "`GenerationBlockFree
  ... never expects to free the freeblock`" (`:303-307`) suggests
  there's a code path where it could [verified-by-code that the
  defensive NULLify exists; semantics under contention or after
  reset/realloc interleavings: inferred].
- Concurrency: Generation contexts are single-threaded backend memory,
  no locking — `freeblock` is just a per-context cache field.
  [verified-by-code: no lock primitives in file.]

## Confidence tag tally

- `[verified-by-code]` × ~10
- `[from-comment]` × ~4
- `[inferred]` × 1
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
