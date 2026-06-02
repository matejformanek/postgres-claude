# `src/include/utils/memutils_internal.h`

- **File:** `source/src/include/utils/memutils_internal.h` (176 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Internal contract between the type-independent memory-context core
(`mcxt.c`) and the per-implementation files (`aset.c`, `generation.c`,
`slab.c`, `bump.c`, `alignedalloc.c`). Declares every per-impl callback
that wires into `mcxt_methods[]`, defines the `MemoryContextMethodID`
enum (the 4-bit allocator tag stored in every `MemoryChunk` header),
exposes `MemoryContextCreate` for the per-impl creators to call, and
declares the OOM/size-failure helpers. Not part of the public API —
nothing outside `src/backend/utils/mmgr/` should include it
(`memutils_internal.h:1-13` [from-comment]).

## Public surface (per implementation)

Each allocator implementation exports the same 9-callback (or
10-callback under `MEMORY_CONTEXT_CHECKING`) shape, all named with the
implementation's prefix:

### AllocSet (`memutils_internal.h:21-36`)

`AllocSetAlloc`, `AllocSetFree`, `AllocSetRealloc`, `AllocSetReset`,
`AllocSetDelete`, `AllocSetGetChunkContext`, `AllocSetGetChunkSpace`,
`AllocSetIsEmpty`, `AllocSetStats`, `AllocSetCheck` (`#ifdef
MEMORY_CONTEXT_CHECKING`). Implementations in `aset.c`.

### Generation (`:38-53`)

`Generation{Alloc,Free,Realloc,Reset,Delete,GetChunkContext,
GetChunkSpace,IsEmpty,Stats,Check}` — in `generation.c`.

### Slab (`:56-71`)

`Slab{Alloc,Free,Realloc,Reset,Delete,GetChunkContext,GetChunkSpace,
IsEmpty,Stats,Check}` — in `slab.c`.

### Bump (`:82-96`)

`Bump{Alloc,Free,Realloc,Reset,Delete,GetChunkContext,GetChunkSpace,
IsEmpty,Stats,Check}` — in `bump.c`. Note `BumpFree`/`BumpRealloc` are
stubs that `ereport(ERROR)` — bump contexts don't support per-chunk
free (`knowledge/files/src/backend/utils/mmgr/bump.c.md`).

### AlignedAlloc (`:73-80`)

A **partial** vtable — only `AlignedAllocFree`, `AlignedAllocRealloc`,
`AlignedAllocGetChunkContext`, `AlignedAllocGetChunkSpace`. No
`Alloc`/`Reset`/`Delete`/`IsEmpty`/`Stats` because aligned allocations
aren't a real context type — they're a *redirection chunk* sitting in
front of an underlying real chunk. Comment: "These functions support
the implementation of `palloc_aligned()` and are not part of a
fully-fledged MemoryContext type." (`:73-76` [from-comment]).

The redirection-chunk machinery is in `mcxt.c:1485-1591`
(`MemoryContextAllocAligned`) and `alignedalloc.c` —
`AlignedAllocFree`/`AlignedAllocRealloc` recover the real chunk by
reading the redirection chunk's value field.

## `PallocAlignedExtraBytes` (`memutils_internal.h:98-105`)

```c
#define PallocAlignedExtraBytes(alignto) \
    ((alignto) + (sizeof(MemoryChunk) - MAXIMUM_ALIGNOF))
```

How much extra to over-allocate when `palloc_aligned` needs to satisfy
an alignment greater than `MAXIMUM_ALIGNOF`. The `alignto` term covers
the worst-case alignment slop; the
`sizeof(MemoryChunk) - MAXIMUM_ALIGNOF` term covers the redirection
chunk header (`:98-103` [from-comment]).

## `MemoryContextMethodID` enum (`memutils_internal.h:107-139`)

The crown jewel of this header. 4-bit allocator tag baked into every
palloc'd chunk:

| Value | Name | Meaning |
|---|---|---|
| 0 | `MCTX_0_RESERVED_UNUSEDMEM_ID` | matches never-used (0x00) memory |
| 1 | `MCTX_1_RESERVED_GLIBC_ID` | glibc small-chunk flag pattern |
| 2 | `MCTX_2_RESERVED_GLIBC_ID` | glibc > 128 KB chunk flag pattern |
| 3 | `MCTX_ASET_ID` | AllocSet (default) |
| 4 | `MCTX_GENERATION_ID` | Generation |
| 5 | `MCTX_SLAB_ID` | Slab |
| 6 | `MCTX_ALIGNED_REDIRECT_ID` | aligned-alloc redirection chunk |
| 7 | `MCTX_BUMP_ID` | Bump |
| 8–14 | `MCTX_{8,...,14}_UNUSED_ID` | reserved |
| 15 | `MCTX_15_RESERVED_WIPEDMEM_ID` | matches `wipe_mem`'d (0xFF) memory |

(`memutils_internal.h:121-139` [verified-by-code]).

Comment is crucial: "**ensure that `MemoryContextMethodID` has a value
for each possible bit-pattern** of `MEMORY_CONTEXT_METHODID_MASK`, and
make dummy entries for unused IDs in the `mcxt_methods[]` array. We
also try to avoid using bit-patterns as valid IDs if they are likely to
occur in garbage data, or if they could falsely match on chunks that
are really from malloc not palloc." (`:113-120` [from-comment]).

That's why `0`, `1`, `2`, `15` are deliberately *not* real allocators —
they correspond to bit-patterns that show up in uninitialized memory
(`0x00`), `wipe_mem`'d freed memory (`0xFF`), and glibc-malloc'd chunks
(`0x1`/`0x2` from glibc's own flag bits). A `pfree(p)` on any of those
patterns lands in `BogusFree` in `mcxt.c` and `elog(ERROR)`s with the
header dump.

### `MEMORY_CONTEXT_METHODID_BITS` / `_MASK` (`:141-147`)

- `MEMORY_CONTEXT_METHODID_BITS = 4` (`:145`).
- `MEMORY_CONTEXT_METHODID_MASK = 0xF` (`:146-147`).

Locks the encoding at 4 bits. Changing this would force a hdrmask
re-layout in `memutils_memorychunk.h`.

## Other internal entry points

### `MemoryContextCreate` (`memutils_internal.h:148-158`)

> "This routine handles the context-type-independent part of memory
> context creation. It's intended to be called from context-type-
> specific creation routines, and noplace else."

Signature: `(MemoryContext node, NodeTag tag, MemoryContextMethodID
method_id, MemoryContext parent, const char *name)`. Per-impl creators
first `malloc` their own struct (header + keeper block), fill the
impl-specific fields, then call this to wire methods, link into parent,
init `isReset=true`, etc. Implementation at `mcxt.c:1152-1192`.

### `MemoryContextAllocationFailure` (`:159-161`)

> `void *MemoryContextAllocationFailure(MemoryContext context, Size
> size, int flags);`

Called by every per-impl `alloc` function when malloc returns NULL.
Honours `MCXT_ALLOC_NO_OOM` (return NULL) vs raise `ereport(ERROR)`.
Implementation at `mcxt.c:1200-1214`.

### `MemoryContextSizeFailure` (`:163-164`)

> `pg_noreturn void MemoryContextSizeFailure(MemoryContext, Size, int);`

Raised when a request exceeds the relevant size cap (`MaxAllocSize`
without `MCXT_ALLOC_HUGE`, or `MaxAllocHugeSize` with it). Marked
`pg_noreturn`.

### `MemoryContextCheckSize` inline (`:166-174`)

```c
static inline void
MemoryContextCheckSize(MemoryContext context, Size size, int flags)
{
    if (unlikely(!AllocSizeIsValid(size)))
    {
        if (!(flags & MCXT_ALLOC_HUGE) || !AllocHugeSizeIsValid(size))
            MemoryContextSizeFailure(context, size, flags);
    }
}
```

The size-validation gate every per-impl `alloc` calls before doing real
work. `unlikely()` hint plus inline keeps the success path tight.

## Key invariants

- **Every chunk's hdrmask carries a valid `MemoryContextMethodID` in
  bits 0-3** — bogus values land in `BogusFree`/`BogusRealloc` in
  `mcxt.c:308-337` (`memutils_internal.h:113-120` [from-comment]).
- **All 16 method IDs must have entries in `mcxt_methods[]`** — even
  the reserved/garbage-detector slots map to `Bogus*` handlers, never
  random function pointers (`:113-115` [from-comment], implemented in
  `mcxt.c:64-153`).
- **`0`, `1`, `2`, `15` are intentionally not allocator IDs** so that
  freeing memory clobbered by `wipe_mem` (0xFF), zeroed memory (0x00),
  or glibc-malloc'd memory (flag bits 0x1/0x2) detects the mistake
  rather than dispatching into garbage (`:113-120` [from-comment]).
- **`MemoryContextCreate` is only called from per-impl creators** — the
  comment explicitly says "noplace else" (`:150-152` [from-comment]).
- **`AlignedAlloc` is a partial vtable** — it has no `alloc`/`reset`/
  `delete` because it's not a context type, just a redirection prefix
  in front of a chunk allocated by some other type (`:73-76`
  [from-comment]).

## Cross-references

- `mcxt.c` — `mcxt_methods[16]` table is the consumer of every callback
  declared here (`mcxt.c:64-153`); `Bogus*` impls at `:308-337`.
- `aset.c` / `generation.c` / `slab.c` / `bump.c` / `alignedalloc.c` —
  the per-impl files that define the prototypes here.
- `memutils.h` — public counterpart; `MemoryContextCheckSize` consumes
  `AllocSizeIsValid` / `AllocHugeSizeIsValid` from there.
- `memutils_memorychunk.h` — `MemoryChunk` header layout; the 4-bit
  method ID lives in the lowest bits of `hdrmask`.
- `palloc.h` — `MCXT_ALLOC_*` flag macros used by
  `MemoryContextAllocationFailure`.
- `knowledge/files/src/backend/utils/mmgr/README.md` — design index.

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 10

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-mmgr.md](../../../../subsystems/utils-mmgr.md)