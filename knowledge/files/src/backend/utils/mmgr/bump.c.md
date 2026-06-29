# `src/backend/utils/mmgr/bump.c`

- **File:** `source/src/backend/utils/mmgr/bump.c` (837 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Bump allocator — densest packing possible. Allocations have **no chunk
header** in production builds (`Bump_CHUNKHDRSZ = 0`), only MAXALIGN'd
data. Trade-off: `pfree`, `repalloc`, `GetMemoryChunkContext`,
`GetMemoryChunkSpace` *all error out* — the only way to release memory
is `MemoryContextReset` / `MemoryContextDelete`. Best for write-once /
short-lived workloads with many small allocations, e.g. sort spill
buffers.

## Top-of-file comment (verbatim, key paragraphs)

```
Bump is a MemoryContext implementation designed for memory usages which
require allocating a large number of chunks, none of which ever need to be
pfree'd or realloc'd.  Chunks allocated by this context have no chunk header
and operations which ordinarily require looking at the chunk header cannot
be performed.  For example, pfree, realloc, GetMemoryChunkSpace and
GetMemoryChunkContext are all not possible with bump allocated chunks.  The
only way to release memory allocated by this context type is to reset or
delete the context.

Bump is best suited to cases which require a large number of short-lived
chunks where performance matters.  Because bump allocated chunks don't
have a chunk header, it can fit more chunks on each block.  This means we
can do more with less memory and fewer cache lines.

In order to detect accidental usage of the various disallowed operations,
we do add a MemoryChunk chunk header in MEMORY_CONTEXT_CHECKING builds and
have the various disallowed functions raise an ERROR.

Allocations are MAXALIGNed.
```
(`bump.c:6-36` [from-comment])

## Public surface

- Creator: `BumpContextCreate(parent, name, minContextSize,
  initBlockSize, maxBlockSize)` (`:133`).
- Method-table callbacks (wired in `mcxt.c:122-133`): `BumpAlloc`,
  `BumpFree`, `BumpRealloc`, `BumpReset`, `BumpDelete`,
  `BumpGetChunkContext`, `BumpGetChunkSpace`, `BumpIsEmpty`,
  `BumpStats`, `BumpCheck`.
- The Free/Realloc/GetChunkContext/GetChunkSpace are stubs that
  `elog(ERROR)` with messages like `"pfree is not supported by the
  bump memory allocator"` (`:645-682` [verified-by-code]).

## Key types

- `BumpContext` (`:68-80`) — header + `initBlockSize`, `maxBlockSize`,
  `nextBlockSize`, `allocChunkLimit`, and `blocks` dlist with the
  current fill target at the head.
- `BumpBlock` (`:88-96`) — `dlist_node`, optional context back-pointer
  under `MEMORY_CONTEXT_CHECKING`, `freeptr`, `endptr`. Notably *no*
  per-chunk count.

## Key invariants

- **No chunk header in production** (`Bump_CHUNKHDRSZ = 0`); a
  `MemoryChunk` *is* prepended under `MEMORY_CONTEXT_CHECKING` purely
  to catch misuse (so `pfree` of a bump chunk gets routed via the
  method-ID dispatch to `BumpFree`, which then `elog(ERROR)`s with a
  clear message). `MemoryChunkSetHdrMask` *is* called in checking
  builds (`:421`) and the `MCTX_BUMP_ID` is the lowest 4 bits — that's
  what makes the misuse detection work via standard dispatch
  [verified-by-code].
- **No header → no method-ID prefix in production builds**. Production
  builds rely on the caller knowing not to pfree these chunks. Any
  callsite that *does* try `pfree(bump_chunk)` reads whatever 64-bit
  word happens to be before the chunk; if that word looks like a valid
  `MCTX_*_ID`, it'll dispatch to that allocator's `free_p`, which is
  effectively memory corruption. **Bump pointers must not leak to
  generic code** — this is the entire reason the file-header comment
  insists on short-lived, scope-confined use.
- **Keeper block + block doubling** match AllocSet/Generation pattern
  exactly (`:202-217, 461-468` [verified-by-code]). Validation in
  `BumpContextCreate` mirrors the others: 1 KB min, MAXALIGN'd,
  `maxBlockSize <= MEMORYCHUNK_MAX_BLOCKOFFSET`, must be safe to double
  (`:156-165`).
- **Large chunks** (size > `allocChunkLimit`) get a dedicated block,
  marked external in checking builds; placed at *tail* of the dlist
  (not head) so the current fill block stays at head for further small
  allocs (`:368-373` [verified-by-code], [from-comment]).
- **`BumpReset`** resets all non-keeper blocks via `BumpBlockFree`
  and resets the keeper via `BumpBlockMarkEmpty` (which just moves
  `freeptr` back to `block + Bump_BLOCKHDRSZ`; with `CLOBBER_FREED_MEMORY`
  it also wipe_mem's). The post-condition is "dlist has exactly one
  element" (the keeper), asserted at `:285-286`.

## Functions of note

1. **`BumpContextCreate` (`:133-241`)** — same shape as the other
   allocators. Note the `FIRST_BLOCKHDRSZ = MAXALIGN(sizeof(BumpContext))
   + Bump_BLOCKHDRSZ` Valgrind vchunk that covers both the context
   header and the keeper-block header in one go (`:49-50, 198`).
2. **`BumpAlloc` (`:516-553`)** — hot path is *very* short: compute
   chunk_size, branch off to `BumpAllocLarge` (noinline) for oversize,
   else look at head block; if not enough space, tail-call
   `BumpAllocFromNewBlock` (noinline). Otherwise tail-call
   `BumpAllocChunkFromBlock` (inline). Comment: "this function should
   only contain the most common code paths. Everything else should be
   in `pg_noinline` helper functions, thus avoiding the overhead of
   creating a stack frame" (`:506-514` [from-comment]).
3. **`BumpAllocChunkFromBlock` (`:393-443`)** — in production:
   `ptr = block->freeptr; block->freeptr += chunk_size; return ptr;`.
   In checking builds: writes `MemoryChunk` with `MCTX_BUMP_ID`,
   `set_sentinel`, paints the body NOACCESS for Valgrind.
4. **`BumpAllocLarge` (`:311-387`)** — dedicated block per oversize
   chunk; under checking builds the chunk is marked external. The
   block is `dlist_push_tail`'d so as not to disrupt the small-alloc
   block at the head — important: a single big alloc doesn't end the
   ability to use the current block for small fast ones.
5. **`BumpFree` / `BumpRealloc` / `BumpGetChunkContext` /
   `BumpGetChunkSpace`** (`:645-682`) — pure stubs that `elog(ERROR)`
   with hardcoded operation names. This is what the
   `MEMORY_CONTEXT_CHECKING` chunk header is designed to trigger when
   a stray `pfree(bump_chunk)` happens.
6. **`BumpCheck` (`:767-end`, under `MEMORY_CONTEXT_CHECKING`)** —
   walks every block, walks every chunk by adding `chunksize +
   Bump_CHUNKHDRSZ` (which exists only in checking builds), validates
   the block back-pointer, refuses to find an external chunk on a
   non-dedicated block.

## Cross-references

- `mcxt.c:122-133` — vtable wiring (note `BumpFree`/`BumpRealloc`
  populate the slot but `elog(ERROR)`).
- `memutils_internal.h:82-95` — public Bump callbacks.
- Bump was added in PG 17 (2024); see top-of-file copyright "2024-2026"
  (`:15`).
- Callers: tuplesort spill buffer is the canonical use case
  [unverified — not chased here].

## Open questions

- **Production-build pfree-of-bump-chunk semantics**: as noted in the
  invariant section above, in production builds there's no chunk
  header, so calling `pfree` on a bump chunk dispatches via whatever
  4 bits happen to precede the chunk. The only protection is "don't
  do that"; this is the most fragile interface point of the allocator.
  Any new caller of bump must be audited for chunk-pointer escape.
- The non-keeper "current" block is always at head, but
  `BumpAllocLarge` pushes oversize blocks to *tail*. After multiple
  large-then-small mixes the head should still be the latest small
  block. This is asserted only indirectly via the dlist-mutability
  pattern, not by a positive invariant check. [verified-by-code in
  `BumpAllocLarge` `:373` vs `BumpAllocFromNewBlock` `:490`.]

## Confidence tag tally

- `[verified-by-code]` × ~10
- `[from-comment]` × ~5
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
- [idioms/memory-context-slab-generation-bump.md](../../../../../idioms/memory-context-slab-generation-bump.md)

