# `src/include/utils/memutils_memorychunk.h`

- **File:** `source/src/include/utils/memutils_memorychunk.h` (253 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Defines the **`MemoryChunk` header** that AllocSet, Generation, Slab,
and AlignedAlloc all stamp in front of every user-visible palloc'd
pointer. Encodes four pieces of information into a single uint64
`hdrmask`:

1. Which allocator owns this chunk (`MemoryContextMethodID`, 4 bits).
2. An "external chunk" flag (1 bit).
3. A 30-bit value the allocator can use for anything (typically chunk
   size or freelist index).
4. A 30-bit offset back to the block header.

Bump is the one allocator that opts out: it stores no chunk header in
production builds (see `bump.c`'s comment about a zero-overhead chunk).

Crucially, **the high bit of field #3 and the low bit of field #4 are
the same bit**. This works because chunk and block pointers are both
`MAXALIGN`ed, so the block offset is always even (lowest bit 0)
(`memutils_memorychunk.h:36-43` [from-comment]).

## Public surface

### Constants (`memutils_memorychunk.h:91-108`)

- `MEMORYCHUNK_MAX_VALUE = 0x3FFFFFFF` — max value an allocator may
  stuff in field #3 (`:93-96`).
- `MEMORYCHUNK_MAX_BLOCKOFFSET = 0x3FFFFFFF` — max block-to-chunk
  distance (`:99-102`). Both must be "1 less than a power of 2"
  (`:94, 100` [from-comment]).

The block-offset cap is what bounds `maxBlockSize` in
`AllocSetContextCreateInternal` — see `aset.c`'s param-validation
asserting `maxBlockSize <= MEMORYCHUNK_MAX_BLOCKOFFSET`
(`aset.c:367-378` [verified-by-code]).

### `MemoryChunk` struct (`:124-132`)

```c
typedef struct MemoryChunk
{
#ifdef MEMORY_CONTEXT_CHECKING
    Size        requested_size;
#endif
    uint64      hdrmask;        /* must be last */
} MemoryChunk;
```

8 bytes in production; 16 bytes under `MEMORY_CONTEXT_CHECKING`
because the per-chunk requested size is stored for sentinel-byte
boundary checks. The `hdrmask` **must remain the last field**
(`:131` [from-comment]) so that `PointerGetMemoryChunk(p)` can locate
it by `((char *) p) - sizeof(MemoryChunk)`.

### Pointer ↔ chunk macros (`:134-139`)

- `PointerGetMemoryChunk(p)` → `(MemoryChunk *)((char *) p -
  sizeof(MemoryChunk))`.
- `MemoryChunkGetPointer(c)` → `(void *)((char *) c +
  sizeof(MemoryChunk))`.

### Bit-layout details (`:110-113`)

- `MEMORYCHUNK_EXTERNAL_BASEBIT = 4` (after the 4 method-ID bits).
- `MEMORYCHUNK_VALUE_BASEBIT = 5`.
- `MEMORYCHUNK_BLOCKOFFSET_BASEBIT = 34` (= 5 + 29 — note **29** not
  30: that's the "shared bit" trick). `:113` [verified-by-code].

So 4 + 1 + 30 + 30 = 65 bits in a 64-bit word, made to fit by
overlapping bit 34 between the value and block-offset fields. The mask
`MEMORYCHUNK_BLOCKOFFSET_MASK = 0x3FFFFFFE` (`:108`) clears the
overlapping low bit when reading the offset back.

### `MEMORYCHUNK_MAGIC` (`:115-122`)

```c
#define MEMORYCHUNK_MAGIC \
    (UINT64CONST(0xB1A8DB858EB6EFBA) >> MEMORYCHUNK_VALUE_BASEBIT \
                                    << MEMORYCHUNK_VALUE_BASEBIT)
```

A magic constant stored in the value+offset bits of **external**
chunks. Round-trip shift clears the low 5 bits (method ID + external
flag) so they don't collide. Comment: "this must mask out the bits used
for storing the `MemoryContextMethodID` and the external bit"
(`:117-119` [from-comment]).

`HdrMaskCheckMagic(hdrmask)` (private, `:155-157`) checks an external
chunk hasn't been stomped — used in `MemoryChunkIsExternal`'s assert
(`:206-211`).

### Setters

#### `MemoryChunkSetHdrMask` (`:158-182`)

Non-external case. Encodes `block`, `value`, `methodid` into
`chunk->hdrmask`. Asserts:
- `chunk >= block`.
- `blockoffset` fits in `MEMORYCHUNK_BLOCKOFFSET_MASK` (i.e. is even +
  ≤ max) — i.e. both pointers were MAXALIGNed.
- `value <= MEMORYCHUNK_MAX_VALUE`.
- `methodid <= MEMORY_CONTEXT_METHODID_MASK`.

Final encoding:
`hdrmask = (blockoffset << 34) | (value << 5) | methodid`.

#### `MemoryChunkSetHdrMaskExternal` (`:184-197`)

External case. Used when fields 3+4 can't hold the values needed —
typically because the chunk is "large" and gets its own dedicated
block, so the allocator computes block address differently
(e.g. `aset.c` uses `chunk - ALLOC_BLOCKHDRSZ` for external chunks,
`aset.c:215-216`).

Encoding:
`hdrmask = MEMORYCHUNK_MAGIC | (1 << 4) | methodid`.

The external bit is `1 << MEMORYCHUNK_EXTERNAL_BASEBIT = 1 << 4`.

### Getters

#### `MemoryChunkIsExternal` (`:199-214`)

Reads bit 4. Also asserts the magic round-trips, so a corrupted
external chunk traps immediately under `USE_ASSERT_CHECKING`
(`:206-211` [from-comment]).

#### `MemoryChunkGetValue` (`:216-227`)

Non-external only — asserts `!HdrMaskIsExternal`. Returns bits 5..34
right-shifted.

#### `MemoryChunkGetBlock` (`:229-240`)

Non-external only — asserts `!HdrMaskIsExternal`. Returns `chunk -
blockoffset`, where `blockoffset` is bits 34..63 masked with
`MEMORYCHUNK_BLOCKOFFSET_MASK` (i.e. clearing the shared low bit).

### Macro cleanup (`:242-252`)

The header `#undef`s every private helper at the end —
`MEMORYCHUNK_BLOCKOFFSET_MASK`, `MEMORYCHUNK_EXTERNAL_BASEBIT`,
`MEMORYCHUNK_VALUE_BASEBIT`, `MEMORYCHUNK_BLOCKOFFSET_BASEBIT`,
`MEMORYCHUNK_MAGIC`, `HdrMaskIsExternal`, `HdrMaskGetValue`,
`HdrMaskBlockOffset`, `HdrMaskCheckMagic` — so they don't leak as
macros into translation units that include this header
(`:242-251` [verified-by-code]). Notably:
**you cannot use these macros outside this header**; the inline
accessors are the only public way in.

## Key invariants

- **Every chunk header ends with an 8-byte field whose low 4 bits are
  the `MemoryContextMethodID`** — this is the universal dispatch
  contract that `MCXT_METHOD` in `mcxt.c:205-234` relies on, and the
  reason every allocator must stamp `MemoryChunkSetHdrMask*` before
  returning a pointer (`:13-16` [from-comment]).
- **Chunk and block pointers must be MAXALIGNed**. The bit-29 sharing
  between fields 3 and 4 only works because the low bit of any
  MAXALIGNed offset is 0 (`:36-43` [from-comment], asserted in
  `MemoryChunkSetHdrMask` at `:175`).
- **`hdrmask` must be the last field of `MemoryChunk`** so
  `PointerGetMemoryChunk(p)` works regardless of whether
  `MEMORY_CONTEXT_CHECKING` is defined (`:131` [from-comment]).
- **`MEMORYCHUNK_MAX_VALUE = MEMORYCHUNK_MAX_BLOCKOFFSET = 2^30 - 1`**
  bounds anything an allocator can stash. AllocSet uses the value
  field for the freelist index (small chunks), not the chunk size —
  size is recovered as `1 << (fidx + ALLOC_MINBITS)`
  (`aset.c:146-147, 830` [verified-by-code]).
- **External chunks**: the allocator that sets `MemoryChunkSetHdr
  MaskExternal` is on its own for recovering the block pointer.
  `MemoryChunkGetBlock` asserts `!IsExternal` — calling it on an
  external chunk is a bug (`:235-240` [verified-by-code]).
- **`MEMORYCHUNK_MAGIC` defends external chunks against overwrite**:
  any stomp on bits 5-63 of an external chunk's hdrmask trips the
  assert in `MemoryChunkIsExternal` (`:206-211` [from-comment]).
- **Bump opts out**: in production builds, `bump.c` allocates chunks
  without a `MemoryChunk` header at all — accepted because Bump
  doesn't support `pfree`/`repalloc`/`GetChunkContext` anyway. See
  `knowledge/files/src/backend/utils/mmgr/bump.c.md`. [verified-by-code]

## Cross-references

- `mcxt.c:205-234` — `MCXT_METHOD` / `GetMemoryChunkMethodID` macros
  that pull the method ID out of the hdrmask.
- `mcxt.c:759, 773` — `GetMemoryChunkContext` / `GetMemoryChunkSpace`
  dispatch via the method ID.
- `aset.c:215-216, 769, 830` — example consumer:
  external-chunk-block-recovery + `MemoryChunkSetHdrMask` call sites.
- `memutils_internal.h:107-147` — `MemoryContextMethodID` enum and
  `MEMORY_CONTEXT_METHODID_BITS/_MASK`.
- `palloc.h` — public allocator API; the chunk-header layout here is
  why `pfree(p)`/`repalloc(p,…)` can dispatch without a context arg.
- `knowledge/files/src/backend/utils/mmgr/README.md` — design index;
  the chunk-header section diagrams this exact bit layout.

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 9

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-mmgr.md](../../../../subsystems/utils-mmgr.md)