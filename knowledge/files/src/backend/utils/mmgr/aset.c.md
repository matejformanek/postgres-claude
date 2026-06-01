# `src/backend/utils/mmgr/aset.c`

- **File:** `source/src/backend/utils/mmgr/aset.c` (1805 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The default `MemoryContext` implementation. Manages allocations in
malloc'd blocks of geometrically-doubling size, carving out
power-of-two-sized chunks from each block. Freed small chunks land on
per-size-class freelists (no coalescing); freed *large* chunks are
returned to malloc immediately. On context reset, every block except
the "keeper" is returned to malloc, so per-tuple contexts don't thrash.
On context delete, contexts created with `ALLOCSET_DEFAULT_SIZES` or
`ALLOCSET_SMALL_SIZES` are cached in a per-shape freelist of up to 100
empty contexts so repeated create/delete cycles avoid malloc.

## Top-of-file comment (verbatim, key paragraphs)

```
This is a new (Feb. 05, 1999) implementation of the allocation set
routines. AllocSet...() does not use OrderedSet...() any more.
Instead it manages allocations in a block pool by itself, combining
many small allocations in a few bigger blocks. AllocSetFree() normally
doesn't free() memory really. It just add's the free'd area to some
list for later reuse by AllocSetAlloc(). All memory blocks are free()'d
at once on AllocSetReset(), which happens when the memory context gets
destroyed.
            Jan Wieck

Performance improvement from Tom Lane, 8/99: for extremely large request
sizes, we do want to be able to give the memory back to free() as soon
as it is pfree()'d.  ...

Further improvement 12/00: ... we now handle only "small" power-of-2-size
chunks as chunks.  Anything "large" is passed off to malloc().  Change
the number of freelists to change the small/large boundary.
```
(`aset.c:16-43` [from-comment])

## Public surface

Creation (`memutils.h` API):
- `AllocSetContextCreate(parent, name, ...)` macro → enforces literal name.
- `AllocSetContextCreateInternal(parent, name, minContextSize,
  initBlockSize, maxBlockSize)` (`aset.c:347`).

Method-table entries (declared in `memutils_internal.h`, wired in
`mcxt.c:64-77`):
- `AllocSetAlloc` (`:1012`), `AllocSetFree` (`:1107`),
  `AllocSetRealloc` (`:1237`), `AllocSetReset` (`:546`),
  `AllocSetDelete` (`:632`), `AllocSetGetChunkContext` (`:1514`),
  `AllocSetGetChunkSpace` (`:1543`), `AllocSetIsEmpty` (`:1577`),
  `AllocSetStats` (`:1602`), `AllocSetCheck` (`:1680`, only under
  `MEMORY_CONTEXT_CHECKING`).

## Key types / data

- `AllocSetContext` (`aset.c:158-171`) — extends `MemoryContextData`
  with: `blocks` (head of doubly-linked block list, current allocation
  block at head), `freelist[ALLOCSET_NUM_FREELISTS]` (11 power-of-two
  size classes from 8B to 8KB), `initBlockSize`, `maxBlockSize`,
  `nextBlockSize`, `allocChunkLimit`, and `freeListIndex` (which
  `context_freelists[]` bucket this context is recyclable into, or -1).
- `AllocBlockData` (`aset.c:187-194`) — block header: owning aset,
  prev/next, `freeptr`/`endptr` defining unused space.
- `AllocFreeListLink` (`aset.c:128-131`) — single `MemoryChunk*` next
  pointer overlaid on the unused chunk body. Located via
  `GetFreeListLink(chk) = (char *)chk + ALLOC_CHUNKHDRSZ`
  (`:138-139` [verified-by-code]).
- `context_freelists[2]` (`aset.c:257-265`) — process-wide static
  freelist of up to `MAX_FREE_CONTEXTS = 100` recyclable contexts each
  for the default and small shapes. Threaded via `header.nextchild`
  on the reset-and-emptied context (`:240, 686`).

## Key invariants

- **Chunk size classes are pure power-of-two from 8 to 8192 bytes**
  (`ALLOC_MINBITS=3`, `ALLOCSET_NUM_FREELISTS=11`). Anything strictly
  larger than `allocChunkLimit` (capped at `ALLOC_CHUNK_LIMIT=8192`,
  and shrunk so ~`ALLOC_CHUNK_FRACTION=4` chunks fit per maxBlockSize
  block) is "large" → its own dedicated block via `AllocSetAllocLarge`
  (`:83-92, 516-519, 735-809` [verified-by-code]).
- **`ALLOC_CHUNK_LIMIT` must equal `ALLOCSET_SEPARATE_THRESHOLD`** from
  `memutils.h` (`aset.c:91-92` StaticAssertDecl [verified-by-code]).
  Callers like tuplesort use that to decide when to spill.
- **Freelist link reuses the chunk body**, which is why
  `sizeof(AllocFreeListLink) <= (1 << ALLOC_MINBITS)` is statically
  asserted (`aset.c:362-363` [verified-by-code]) — i.e. minimum chunk
  size 8 must hold one pointer. *No freelist coalescing* — power-of-two
  buckets stay segregated; that's the explicit design choice from the
  "12/00" header note.
- **Freelist value is stored in the MemoryChunk's 30-bit value field**
  (`MemoryChunkSetHdrMask(chunk, block, fidx, MCTX_ASET_ID)`,
  `aset.c:830` [verified-by-code]) — *not* the chunk size. Chunk size
  is derived as `1 << (fidx + ALLOC_MINBITS)` via
  `GetChunkSizeFromFreeListIdx` (`:146-147`).
- **Large (external) chunks use `MemoryChunkSetHdrMaskExternal`** and
  always sit at offset `ALLOC_BLOCKHDRSZ` from their dedicated block,
  so `ExternalChunkGetBlock(chunk) = (char *)chunk - ALLOC_BLOCKHDRSZ`
  (`:215-216, 769` [verified-by-code]).
- **The first block ("keeper") is allocated together with the context
  header in one malloc** (`:432-454`). On reset the keeper's data area
  is wiped/MAKE_MEM_NOACCESS'd but the block itself is not freed — this
  is the "no malloc thrashing for per-tuple contexts" property
  (`:540-543, 568-588, 610` [from-comment]). On delete, the whole
  malloc allocation is `free()`d in one call (`:725`).
- **Context recycling**: contexts with `(minContextSize, initBlockSize)
  ∈ {ALLOCSET_DEFAULT_*, ALLOCSET_SMALL_*}` are put on
  `context_freelists[]` instead of being freed, up to 100 each. On
  overflow the *entire* freelist is dropped at once (heuristic: queries
  that allocate many contexts free them in reverse order, so the oldest
  are likely the longest-lived) (`:219-241, 648-691` [from-comment]).
  `maxBlockSize` doesn't have to match — only the keeper-block shape
  does, and `maxBlockSize` is rewritten when the context is reused
  (`:415-416` [verified-by-code]).
- **Block doubling**: `nextBlockSize` starts at `initBlockSize` and
  doubles per new block up to `maxBlockSize`. The first block's
  actual size is `max(minContextSize, initBlockSize)` if `minContextSize
  != 0`, else `initBlockSize` (`:432-438, 493-495` [verified-by-code]).
- **Mid-range request handling**: even when a freelist has no entry,
  `AllocSetAlloc` rounds `size` *up to* `1 << (fidx + ALLOC_MINBITS)`
  before recording it (`:1085`); the wasted bytes are why power-of-two
  buckets above 8B exist at all (`:35-42, 1083-1086` [from-comment]).

## Functions of note

1. **`AllocSetContextCreateInternal` (`:346-531`)** — validates params
   (1 KB minimum block, `maxBlockSize <= MEMORYCHUNK_MAX_BLOCKOFFSET`,
   all MAXALIGN'd, `maxBlockSize` safe to double — `AllocHugeSizeIsValid`).
   If the param shape matches a `context_freelists[]` bucket and there's
   a recyclable context, reuses it (just re-runs `MemoryContextCreate`
   on the existing header, rewriting `maxBlockSize`). Otherwise
   `malloc`s a single block containing the context header + the keeper
   block, sets up Valgrind vpool/vchunk, computes `allocChunkLimit` by
   halving from 8KB until `~ALLOC_CHUNK_FRACTION` chunks of that size
   fit in `maxBlockSize`, and calls `MemoryContextCreate`. Comment
   notes "Avoid writing code that can fail between here and
   `MemoryContextCreate`" because the partial malloc would leak
   (`:456-459` [from-comment]).

2. **`AllocSetReset` (`:546-622`)** — walks the block list. The keeper
   has its data area `wipe_mem`'d (if `CLOBBER_FREED_MEMORY`) and its
   `freeptr` reset; every other block is freed via `free()` after
   explicit `VALGRIND_MEMPOOL_FREE` of the block-header vchunk
   (`:599-606`). After the loop `VALGRIND_MEMPOOL_TRIM` flushes all
   user-data vchunks except the one covering the
   `AllocSetContext`+keeper-header pair, and `nextBlockSize` is reset
   to `initBlockSize` (`:612-621` [verified-by-code]). Asserts that
   `mem_allocated == keepersize` afterwards — i.e. accounting only
   tracks the keeper.

3. **`AllocSetDelete` (`:632-726`)** — if the context is recyclable
   (`freeListIndex >= 0`), it's reset (if not already), and if the
   target `context_freelists[]` bucket would overflow `MAX_FREE_CONTEXTS`
   the *whole* bucket is dropped first; then the just-reset context is
   pushed on. Otherwise the block list is walked freeing non-keeper
   blocks, the vpool is destroyed, and the single malloc allocation
   (header + keeper) is `free()`d.

4. **`AllocSetAlloc` (`:1012-1100`)** — the hot path. **Size >
   allocChunkLimit → `AllocSetAllocLarge`** (tail call to noinline
   helper). Else compute freelist index, **pop from freelist if
   non-empty** (constant-time, no malloc), else **bump-allocate from
   the current block's `freeptr`**, else tail-call
   `AllocSetAllocFromNewBlock` (which mallocs a fresh block sized at
   `nextBlockSize`, doubles `nextBlockSize` up to `maxBlockSize`).
   Comment is emphatic: keep this function small and arrange all
   helpers as tail calls — "Allocating memory is often a bottleneck
   in many workloads" (`:1003-1009` [from-comment]).

5. **`AllocSetFree` (`:1107-1222`)** — branches on
   `MemoryChunkIsExternal(chunk)`:
   - External: validate block via `AllocBlockIsValid(block)` and
     `block->freeptr == block->endptr` (full single-chunk block),
     unlink from `set->blocks`, `free()` it. Errors as `ERROR` if the
     block looks bogus (`:1124-1125`).
   - Non-external: under `MEMORY_CONTEXT_CHECKING`, **detects double
     pfree by checking `chunk->requested_size == InvalidAllocSize`** —
     and chooses ERROR for double-free vs WARNING for write-past-end
     because double-free would corrupt the freelist if let through, but
     a stomped sentinel is already done damage and only warrants a
     post-mortem warning (`:1177-1202` [from-comment]). Then pushes the
     chunk onto `freelist[fidx]` and zeros its `requested_size` field.
6. **`AllocSetRealloc` (`:1237`)** — handles four cases: external chunk
   shrink in place / grow by malloc-realloc + re-vchunk; small chunk
   stays in same freelist bucket (in-place); small chunk crosses a
   bucket boundary (alloc new, copy, free old). [verified-by-code, not
   fully transcribed here — file lines 1237-1500 cover this.]

7. **`AllocSetGetChunkContext` (`:1514-1541`) /
   `AllocSetGetChunkSpace` (`:1543-1575`)** — read chunk header, branch
   on external vs not, return `block->aset` or the chunk size
   (`1 << (fidx + ALLOC_MINBITS)` for small, or
   `endptr - chunk_ptr + ALLOC_CHUNKHDRSZ` for large).
   `GetMemoryChunkContext` from `mcxt.c:759` dispatches here.

8. **`AllocSetCheck` (`:1680-end`, under `MEMORY_CONTEXT_CHECKING`)** —
   walks every block, every chunk, validates the method-ID, the
   block-link, the `requested_size`, and the sentinel byte past the
   end. Reports anomalies as `WARNING` (never `ERROR`/`FATAL`,
   intentionally, "otherwise you'll find yourself in an infinite loop
   when trouble occurs, because this routine will be entered again
   when elog cleanup tries to release memory" — same convention as
   `BumpCheck`).

## Cross-references

- `mcxt.c:64-77` — vtable wiring; `mcxt.c:1234+` — the public
  `MemoryContextAlloc*` / `palloc*` callers.
- `memutils_internal.h` — declares the eight `AllocSet*` callbacks.
- `memutils_memorychunk.h` — the chunk header used as
  `MemoryChunk` prefix.
- `memutils.h:157-179` — the `ALLOCSET_*_SIZES` macros consumed here.
- `memutils.h:182-187` — `ALLOCSET_SEPARATE_THRESHOLD = 8192`, asserted
  equal to `ALLOC_CHUNK_LIMIT`.
- `source/src/backend/utils/sort/tuplesort.c` — typical
  `ALLOCSET_SEPARATE_THRESHOLD` consumer [unverified].

## Open questions

- The `context_freelists[]` cache is process-wide, has no concurrency
  protection — fine in PG's process-per-backend model, but means an
  EXEC_BACKEND process and the postmaster have independent caches.
  [inferred] — not chased.
- The exact safety of `repalloc` shrinking an external chunk without
  re-malloc'ing the block: `AllocSetRealloc` does it in place via
  block accounting adjustments; whether Valgrind's vchunk for the
  block header still matches the new size is [unverified].
- The `set_sentinel` skip when `size == GetChunkSizeFromFreeListIdx(fidx)`
  (i.e. exact-fit power-of-two): no sentinel byte is written, so
  write-past-end of an exact-fit chunk is undetected even under
  `MEMORY_CONTEXT_CHECKING` (`:1063-1066` [verified-by-code]). This is
  documented as a deliberate trade-off (`:1039-1043` [from-comment]).

## Confidence tag tally

- `[verified-by-code]` × ~22
- `[from-comment]` × ~8
- `[inferred]` × 1
- `[unverified]` × 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
