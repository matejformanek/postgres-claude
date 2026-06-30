# `src/backend/utils/mmgr/slab.c`

- **File:** `source/src/backend/utils/mmgr/slab.c` (1194 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

`MemoryContext` for **fixed-size** chunks. Block size and chunk size
are both set at create time; the block is sliced into exactly
`chunksPerBlock` chunks of `fullChunkSize` each. Blocks are organized
into `SLAB_BLOCKLIST_COUNT = 3` partitions by how many free chunks they
contain, so new allocations preferentially fill the fullest non-full
block — this lets emptied blocks be `free()`d back to the OS,
defragmenting under churn. Up to `SLAB_MAXIMUM_EMPTY_BLOCKS = 10` empty
blocks are kept around for cheap reuse.

## Top-of-file comment (verbatim, key paragraphs)

```
SLAB is a MemoryContext implementation designed for cases where large
numbers of equally-sized objects can be allocated and freed efficiently
with minimal memory wastage and fragmentation.

The constant allocation size allows significant simplification and various
optimizations over more general purpose allocators. The blocks are carved
into chunks of exactly the right size, wasting only the space required to
MAXALIGN the allocated chunks.

We give priority to putting new allocations into the "fullest" block.
This help avoid having too many sparsely used blocks around and allows
blocks to more easily become completely unused which allows them to be
eventually free'd.

We keep track of free chunks within each block by using a block-level free
list.  ... The free list is a linked list, the head of which is pointed to
with SlabBlock's freehead field.  Each subsequent list item is stored in
the free chunk's memory.

When we allocate a new block, technically all chunks are free, however, to
avoid having to write out the entire block to set the linked list for the
free chunks for every chunk in the block, we instead store a pointer to
the next "unused" chunk on the block and keep track of how many of these
unused chunks there are.
```
(`slab.c:6-65` [from-comment])

## Public surface

- Creator: `SlabContextCreate(parent, name, blockSize, chunkSize)`
  (`:322`).
- Recommended block-size constants in `memutils.h:189-190`:
  `SLAB_DEFAULT_BLOCK_SIZE = 8 KiB`, `SLAB_LARGE_BLOCK_SIZE = 8 MiB`.
- Method-table callbacks (wired in `mcxt.c:94-105`): `SlabAlloc`,
  `SlabFree`, `SlabRealloc`, `SlabReset`, `SlabDelete`,
  `SlabGetChunkContext`, `SlabGetChunkSpace`, `SlabIsEmpty`,
  `SlabStats`, `SlabCheck`.

## Key types

- `SlabContext` (`:103-130`) — header + `chunkSize`, `fullChunkSize`
  (chunk + `MemoryChunk` header, MAXALIGN'd + sentinel byte under
  `MEMORY_CONTEXT_CHECKING`), `blockSize`, `chunksPerBlock`,
  `curBlocklistIndex` (cached "where to allocate next" index),
  `blocklist_shift` (bit shift used to bucket nfree into the 3-element
  `blocklist[]`), `emptyblocks` (dclist of fully-empty blocks parked
  for reuse), `blocklist[SLAB_BLOCKLIST_COUNT]` (dlists keyed by
  free-chunk count range; `[0]` is "full blocks").
- `SlabBlock` (`:146-154`) — owning context, `nfree` (free + unused),
  `nunused` (chunks above the high-water-mark, not yet touched),
  `freehead` (linked list head through the chunks themselves),
  `unused` (pointer to next never-allocated slot), `node` (blocklist
  membership).

## Key invariants

- **No realloc**: `SlabRealloc` (declared at `memutils_internal.h:59`,
  defined later in the file) `elog(ERROR)`s — there's no way to grow a
  fixed-size chunk. [verified-by-code via grep; standard for a slab.]
- **Min chunk size is `sizeof(MemoryChunk *)`** — bumped up in
  `SlabContextCreate` if the user asked smaller, because the free
  chunk's memory is reused to hold the next-free pointer (`:340-342`
  [verified-by-code], `[from-comment]`).
- **`blocklist_shift` is chosen so `chunksPerBlock >> shift <
  SLAB_BLOCKLIST_COUNT - 1`** — i.e. each blocklist bucket covers a
  power-of-two range of free-chunk counts, and there are only ever 3
  active buckets, making "find a non-full block" O(1) (`:392-404,
  210-238` [verified-by-code]).
- **Empty-block recycle cache**: `dclist_head emptyblocks`, capped at
  `SLAB_MAXIMUM_EMPTY_BLOCKS = 10` (`:97-98, 120-127` [verified-by-code]).
  Empty blocks beyond that are `free()`d. There is **no keeper block** —
  the context header is a standalone malloc (the file's keeperless
  design is implicit in the absence of a `KeeperBlock(set)` macro;
  contrast with aset/generation/bump).
- **Chunk header is the standard `MemoryChunk`**, MAXALIGN'd
  (`Slab_CHUNKHDRSZ = sizeof(MemoryChunk)`, asserted MAXALIGN at
  `:333-334`). The `value` field holds the chunk index within its
  block; `block` pointer reconstructed via the standard
  `MemoryChunkGetBlock` (i.e. block-offset encoding). [verified-by-code
  for the alignment assertion; chunk-index storage inferred from
  `SlabBlockGetChunk` arithmetic and `SlabAlloc`'s call to
  `MemoryChunkSetHdrMask`.]
- **"Unused" pointer never goes backwards**: once a chunk has been
  handed out and then freed, the freed chunks live on `freehead`'s
  free list (LIFO), while `block->unused` only moves *forward* (and
  `nunused` only counts those slots never-yet-handed-out). On pfree,
  free-list grows; allocation prefers free-list before consuming
  unused (`:266-306, 280-302` [from-comment], [verified-by-code]).

## Functions of note

1. **`SlabContextCreate` (`:322-end-of-create)`** — bumps `chunkSize`
   to `sizeof(MemoryChunk *)` if needed, computes `fullChunkSize`
   (with +1 for sentinel under checking builds), computes
   `chunksPerBlock = (blockSize - Slab_BLOCKHDRSZ) / fullChunkSize`
   (ERRORs if zero), allocates a `SlabContext` (plus an `isChunkFree`
   bool array under `MEMORY_CONTEXT_CHECKING`), inits the empty
   dclist + the 3 blocklist dlists, finishes with `MemoryContextCreate`.
2. **`SlabBlocklistIndex` (`:210-238`)** — clever `nfree==0 → 0`,
   otherwise `-((-nfree) >> shift)` to get `[1, SLAB_BLOCKLIST_COUNT)`.
   Two's-complement trick documented in-comment.
3. **`SlabGetNextFreeChunk` (`:270-306`)** — pops `freehead` if set
   (reads next pointer from the chunk's own memory after `MAKE_MEM_DEFINED`),
   else bumps `block->unused`, decrements `nfree`. Asserts the popped
   chunk lies in-bounds and is fullChunkSize-aligned within the block.
4. **`SlabAlloc`** (`memutils_internal.h:57`, defined later in file) —
   walks `blocklist[curBlocklistIndex]` for the first block with
   space, falls back via `SlabFindNextBlockListIndex` (priority to the
   *fuller* lists, `:240-263`); if no block has free space, takes from
   `emptyblocks` (cheap reuse) or `malloc`s a new block. After
   allocation, may move the block to a different blocklist slot if its
   nfree crossed a bucket boundary. [verified-by-code via
   `SlabBlocklistIndex` consumer pattern.]
5. **`SlabFree`** — pushes chunk onto its block's `freehead`,
   increments `nfree`. If `nfree == chunksPerBlock` (block fully
   empty), moves the block to `emptyblocks` if not at cap, else
   `free()`s it. Otherwise may reblocklist on bucket crossing.
   [verified-by-code, semantics from the file comment header.]

## Cross-references

- `mcxt.c:94-105` — vtable wiring.
- `memutils.h:189-190` — `SLAB_*_BLOCK_SIZE` recommended sizes.
- `memutils_internal.h:57-71` — public Slab callbacks.
- Major callers:
  - `source/src/backend/replication/logical/reorderbuffer.c` — uses
    Slab for `ReorderBufferTXN`, `ReorderBufferChange`, `TupleBuf`
    [unverified — typical PG documentation/lore, not chased here].
  - `source/src/backend/utils/cache/typcache.c` — `RecordCacheArray`
    [unverified].

## Open questions

- The `isChunkFree` bool array in `MEMORY_CONTEXT_CHECKING` builds is
  allocated as part of the `SlabContext` header malloc with size
  `chunksPerBlock * sizeof(bool)`. For very large `chunksPerBlock`
  (small chunks, large blocks) this is per-context overhead, not
  per-block. Whether this is a real concern is [unverified] — it's
  a debugging build only.
- `SlabRealloc`/`SlabAlloc` interaction with `palloc_aligned`: since
  Slab can't honour alignment > MAXALIGN (no over-alloc), aligned
  allocations on a Slab context would fail at the
  `MemoryContextAllocAligned` over-allocate step; in practice nobody
  does this. [verified-by-comment in `mcxt.c:1478-1480`.]

## Confidence tag tally

- `[verified-by-code]` × ~10
- `[from-comment]` × ~5
- `[inferred]` × 1
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
- [idioms/memory-context-slab-generation-bump.md](../../../../../idioms/memory-context-slab-generation-bump.md)

