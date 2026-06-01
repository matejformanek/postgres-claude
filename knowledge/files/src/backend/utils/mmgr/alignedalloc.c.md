# `src/backend/utils/mmgr/alignedalloc.c`

- **File:** `source/src/backend/utils/mmgr/alignedalloc.c` (190 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

**Not a fully-fledged context type** — no creator, no `alloc` callback,
no `reset`/`delete`. Implements only the `free_p`, `realloc`,
`get_chunk_context`, `get_chunk_space` operations for the
"redirection chunks" produced by `MemoryContextAllocAligned` /
`palloc_aligned`. A redirection chunk carries
`MCTX_ALIGNED_REDIRECT_ID` in its method-ID slot so that `pfree` and
`repalloc` dispatched through `mcxt_methods[]` land here, recover the
real (unaligned) underlying chunk via `MemoryChunkGetBlock`, and
delegate back to whichever allocator actually owns the storage.

## Top-of-file comment (verbatim)

```
This is not a fully-fledged MemoryContext type as there is no means to
create a MemoryContext of this type.  The code here only serves to allow
operations such as pfree() and repalloc() to work correctly on a memory
chunk that was allocated by palloc_aligned().
```
(`alignedalloc.c:6-9` [from-comment])

## Public surface

- `AlignedAllocFree(void *pointer)` (`:29`).
- `AlignedAllocRealloc(void *pointer, Size size, int flags)` (`:70`).
- `AlignedAllocGetChunkContext(void *pointer)` (`:154`).
- `AlignedAllocGetChunkSpace(void *pointer)` (`:176`).
All wired into `mcxt_methods[MCTX_ALIGNED_REDIRECT_ID]` at
`mcxt.c:107-119`. The `alloc`, `reset`, `delete_context`, `is_empty`,
`stats` slots are `NULL` for this ID (never invoked because no context
of this type exists).

## Key invariants

- **Layout produced by `MemoryContextAllocAligned`** (`mcxt.c:1485-1591`):
  1. The owning allocator returns an unaligned chunk of size
     `size + alignto + sizeof(MemoryChunk) - MAXIMUM_ALIGNOF`.
  2. The visible (aligned) pointer is computed as
     `TYPEALIGN(alignto, unaligned + sizeof(MemoryChunk))`.
  3. The 16/8-byte `MemoryChunk` immediately preceding the aligned
     pointer has its `value` set to `alignto` and its block-offset
     pointing back to the unaligned start; method-ID =
     `MCTX_ALIGNED_REDIRECT_ID`.
  - `AlignedAllocFree` recovers the unaligned pointer with
    `MemoryChunkGetBlock(chunk)` (`:39`) and pfree's that, which
    cascades to the real allocator's `free_p`. [verified-by-code]
- **External flag is NEVER set** on a redirection chunk —
  `AlignedAllocFree` and `AlignedAllocGetChunkContext` assert
  `!MemoryChunkIsExternal(chunk)` (`:36, 161` [verified-by-code]).
  This is consistent with `MemoryContextAllocAligned` always using
  `MemoryChunkSetHdrMask` (not `SetHdrMaskExternal`) at
  `mcxt.c:1560`.
- **`alignto` ceiling**: `MemoryContextAllocAligned` asserts
  `alignto < 128 MB` (`mcxt.c:1500`) so it fits in the chunk's
  30-bit value field, and `alignto` must be a power of two.
  `AlignedAllocRealloc` re-asserts the power-of-two property
  (`:85` [verified-by-code]).
- **Realloc always allocates a fresh aligned chunk**: it does not try
  to grow in place. The comment explains why — `GetMemoryChunkSpace`
  on the unaligned chunk returns an *upper* bound (e.g. AllocSet
  rounds to power-of-two), so the only safe bound on bytes-to-memcpy
  is `GetMemoryChunkSpace(unaligned) -
  PallocAlignedExtraBytes(alignto) - sizeof(MemoryChunk)` (`:101-103`
  [from-comment]).

## Functions of note

1. **`AlignedAllocFree` (`:29-59`)** — fetches the unaligned chunk,
   under `MEMORY_CONTEXT_CHECKING` validates the sentinel byte just
   past `requested_size` (`:42-46`), creates a temporary Valgrind
   vchunk covering the pre-aligned-pointer slack so that Valgrind
   doesn't complain when the underlying `pfree` runs on the unaligned
   chunk, then **recursively `pfree(unaligned)`** — this is how the
   real allocator gets to run its own `AllocSetFree` /
   `GenerationFree` / etc.

2. **`AlignedAllocRealloc` (`:70-147`)** — reads `alignto` from the
   redirect chunk's value field, computes `old_size` as a safe
   upper-bound for memcpy (see invariant), calls
   `MemoryContextAllocAligned(ctx, size, alignto, flags)` for the new
   chunk, memcpy's `min(size, old_size)` bytes,
   `VALGRIND_MAKE_MEM_DEFINED` over the source bytes to silence
   reads-past-requested-size, then pfree's the old unaligned chunk
   via the same vchunk dance as `AlignedAllocFree`. **Cope cleanly
   with OOM** via `MemoryContextAllocationFailure` (`:118-123`
   [verified-by-code]).

3. **`AlignedAllocGetChunkContext` (`:154-168`)** — returns
   `GetMemoryChunkContext(MemoryChunkGetBlock(redirchunk))` — i.e.
   *the underlying allocator's context*, not some synthetic
   "aligned context". This is what makes `GetMemoryChunkContext(p)`
   work transparently for aligned and unaligned pointers.

4. **`AlignedAllocGetChunkSpace` (`:176-189`)** — returns the
   underlying chunk's `GetMemoryChunkSpace`. So an aligned chunk's
   space includes the alignment slack and the redirection
   `MemoryChunk`; callers using `GetMemoryChunkSpace` for accounting
   see the real cost.

## Cross-references

- `mcxt.c:1485-1591` — `MemoryContextAllocAligned`, the only producer
  of `MCTX_ALIGNED_REDIRECT_ID` chunks.
- `mcxt.c:107-119` — vtable wiring (NULLs for unused operations).
- `memutils_internal.h:73-80` — function prototypes.
- `memutils_memorychunk.h` — `MemoryChunkSetHdrMask`,
  `MemoryChunkGetBlock`, `MemoryChunkGetValue`.

## Open questions

- The `Slab` context cannot serve as the underlying allocator for
  `MemoryContextAllocAligned`, because Slab can't over-allocate
  (chunks are exactly `fullChunkSize`). Aligned alloc on a Slab
  context would fail at the underlying `MemoryContextAllocExtended`
  step — but I don't see an explicit guard. [verified-by-code: the
  comment at `mcxt.c:1478-1480` warns about this, no runtime check
  beyond the underlying alloc failing.]
- Whether `palloc_aligned` is ever called with `alignto` not a
  power-of-2: asserted but not runtime-checked. [verified-by-code:
  `Assert((alignto & (alignto - 1)) == 0)` at `mcxt.c:1503` and
  `alignedalloc.c:85`.]

## Confidence tag tally

- `[verified-by-code]` × ~6
- `[from-comment]` × 2
- `[unverified]` × 0

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
