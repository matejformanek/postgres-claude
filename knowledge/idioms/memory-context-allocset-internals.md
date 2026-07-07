# AllocSet internals — the default memory allocator

AllocSet is the general-purpose memory allocator that backs ~90% of PG's
contexts (everything created via `AllocSetContextCreate` —
`TopMemoryContext`, `ExprContext` per-tuple contexts, the planner's
per-statement context, the executor's per-query context, and so on).
The design is two-tier: small/medium chunks go into one of 11
power-of-2-sized freelists; large chunks get a dedicated block each.
Two more tricks — the **keeper block** that survives reset, and the
**context freelist** that recycles recently-deleted contexts — make
common-case alloc/reset cycles almost malloc-free.

The dispatch frame and chunk-header bit layout this builds on are in
[[memory-context-api-and-dispatch]]. The two cousins that share the
chunk-header convention but make different design trade-offs are in
[[memory-context-slab-generation-bump]].

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

- `source/src/backend/utils/mmgr/aset.c:1` — the whole AllocSet
  implementation, ~1500 lines.
- `source/src/backend/utils/mmgr/aset.c:158-171` — `AllocSetContext`
  struct (the per-set bookkeeping).
- `source/src/backend/utils/mmgr/aset.c:187-194` — `AllocBlockData`
  struct (the per-block bookkeeping).
- `source/src/backend/utils/mmgr/aset.c:267-322` — `AllocSetFreeIndex`
  (the size→freelist hash, hot enough to hand-tune).
- `source/src/backend/utils/mmgr/aset.c:346-531` —
  `AllocSetContextCreateInternal` (context creation, including the
  freelist-recycle path).
- `source/src/backend/utils/mmgr/aset.c:1011-1100` — `AllocSetAlloc`
  (the hot path — freelist hit or block-carve).
- `source/src/backend/utils/mmgr/aset.c:733-809` —
  `AllocSetAllocLarge` (oversized chunks, dedicated block).
- `source/src/backend/utils/mmgr/aset.c:859-987` —
  `AllocSetAllocFromNewBlock` (out-of-space-in-active-block path, with
  the free-space scavenging trick).
- `source/src/backend/utils/mmgr/aset.c:1106-1222` — `AllocSetFree`
  (freelist push or external-block immediate free).
- `source/src/include/utils/memutils.h:1` — `ALLOCSET_DEFAULT_SIZES`,
  `ALLOCSET_SMALL_SIZES`, `ALLOCSET_SEPARATE_THRESHOLD`.

## The struct

`AllocSetContext` [aset.c:158-171] embeds the abstract
`MemoryContextData` as `header` and adds:

```c
typedef struct AllocSetContext
{
    MemoryContextData header;
    AllocBlock        blocks;         /* head of doubly-linked block list */
    MemoryChunk      *freelist[ALLOCSET_NUM_FREELISTS];  /* 11 lists */
    uint32  initBlockSize;            /* first non-keeper block size */
    uint32  maxBlockSize;             /* cap on block size */
    uint32  nextBlockSize;            /* will-be-doubled size for next block */
    uint32  allocChunkLimit;          /* chunks > this go to oversized path */
    int     freeListIndex;            /* index in context_freelists[], or -1 */
} AllocSetContext;
```

And `AllocBlockData` [aset.c:187-194]:

```c
typedef struct AllocBlockData
{
    AllocSet    aset;        /* back-pointer to owning set */
    AllocBlock  prev;        /* doubly-linked block list */
    AllocBlock  next;
    char       *freeptr;     /* start of unused space in this block */
    char       *endptr;      /* end of this block */
} AllocBlockData;
```

A block is conceptually `[ AllocBlockData header | MAXALIGN padding |
chunks in use | unused space ]`. Allocation bumps `freeptr` forward;
when there's not enough room, a new block is allocated and pushed to the
head of the block list. The previously-active (now-not-quite-full) block
gets its remaining space carved into the freelists (see "the carve
trick" below).

## The 11 freelists — why 11, why power-of-2

`ALLOCSET_NUM_FREELISTS = 11` [aset.c:84], `ALLOC_MINBITS = 3`
[aset.c:83]. Freelist `k` holds chunks of size `1 << (k + 3)`:

| k  | chunk size |
|----|------------|
| 0  | 8 B        |
| 1  | 16 B       |
| 2  | 32 B       |
| 3  | 64 B       |
| 4  | 128 B      |
| 5  | 256 B      |
| 6  | 512 B      |
| 7  | 1 KiB      |
| 8  | 2 KiB      |
| 9  | 4 KiB      |
| 10 | 8 KiB      |

`ALLOC_CHUNK_LIMIT = 8 KiB` [aset.c:85] is the cutoff; anything above
falls through to `AllocSetAllocLarge`. The 8-byte minimum is determined
by two constraints documented at aset.c:68-73:

1. `1<<ALLOC_MINBITS >= MAXALIGN` — chunks must be aligned to 8 bytes
   on all PG-supported platforms.
2. The chunk's memory itself stores an `AllocFreeListLink` (a
   `MemoryChunk *next` pointer, 8 bytes on 64-bit) when on a freelist,
   so chunks must be at least 8 bytes. `[from-comment]`

The power-of-2 design [aset.c:59-62] is a recyclability bet: we waste
up to half a chunk per allocation (a 9-byte request gets a 16-byte
chunk), but the wasted space is bounded by a constant ratio rather than
growing with churn. The alternative — exact-size freelists — would
produce arbitrarily many small freelist heads as workloads vary.

Anything in the midrange between "small power-of-2" and "large" used
to be inefficient pre-PG-7.1; the fix [aset.c:35-42] was to just
forward midrange requests to `malloc()` via `AllocSetAllocLarge`.

`StaticAssertDecl(ALLOC_CHUNK_LIMIT == ALLOCSET_SEPARATE_THRESHOLD)`
[aset.c:91-92] cross-pins the in-file constant with the public one in
`memutils.h`.

## `AllocSetFreeIndex` — the size→bucket hash

`AllocSetFreeIndex(size)` [aset.c:276-322] computes
`ceil(log2(size >> ALLOC_MINBITS))`. The function has two backends:

- **Bit-scan path** (`HAVE_BITSCAN_REVERSE`): one
  `pg_leftmost_one_pos32` instruction call. On any modern x86/ARM,
  that's a `BSR` or `LZCNT` — one cycle.
- **Lookup-table fallback**: `pg_leftmost_one_pos[256]` byte lookup, with
  hand-unrolled 16-bit handling. A `StaticAssertDecl` at aset.c:307-308
  pins `ALLOC_CHUNK_LIMIT < 1<<16` so the unrolled form is always safe.

The comment at aset.c:294-298 — "Yes, this function is enough of a
hot-spot to make it worth this much trouble" — speaks for itself.
Memory allocation runs in the inner loop of every query.

## Block sizing — `initBlockSize`, `maxBlockSize`, and the doubling

By default [README:447-452, memutils.h]:

```c
#define ALLOCSET_DEFAULT_MINSIZE   0
#define ALLOCSET_DEFAULT_INITSIZE  (8 * 1024)      /* 8KB */
#define ALLOCSET_DEFAULT_MAXSIZE   (8 * 1024 * 1024) /* 8MB */
```

So the first non-keeper block is 8KB, the next is 16KB, then 32KB,
doubling until 8MB. The doubling lives in `AllocSetAllocFromNewBlock`
[aset.c:932-935]:

```c
blksize = set->nextBlockSize;
set->nextBlockSize <<= 1;
if (set->nextBlockSize > set->maxBlockSize)
    set->nextBlockSize = set->maxBlockSize;
```

`minContextSize` is the first block's size if non-zero; otherwise the
first block is `initBlockSize`. This lets callers say "I expect this
context to be small — start with a tiny first block" (e.g. the
relcache's per-relation contexts use `ALLOCSET_SMALL_SIZES`) or "I'm
going to hold lots of stuff — start big" (the executor's per-query
context).

`allocChunkLimit` [aset.c:516-519]:

```c
set->allocChunkLimit = ALLOC_CHUNK_LIMIT;
while ((set->allocChunkLimit + ALLOC_CHUNKHDRSZ) >
       ((maxBlockSize - ALLOC_BLOCKHDRSZ) / ALLOC_CHUNK_FRACTION))
    set->allocChunkLimit >>= 1;
```

`ALLOC_CHUNK_FRACTION = 4` [aset.c:87]. The idea: if `maxBlockSize` is
small, the largest in-block chunk should be at most a quarter of the
block. Otherwise a single oversized chunk would dominate the block and
all the remaining free space would be wasted. For the default 8MB
maxBlockSize, this loop never fires — 8KB is well under 8MB/4.

## The keeper block

Every AllocSet starts life with a special first block called the
**keeper** [aset.c:243-248]:

```c
#define KeeperBlock(set) \
    ((AllocBlock) (((char *) set) + MAXALIGN(sizeof(AllocSetContext))))

#define IsKeeperBlock(set, block) ((block) == (KeeperBlock(set)))
```

Unlike subsequent blocks, the keeper block is allocated **in the same
malloc** as the `AllocSetContext` struct itself [aset.c:432-454]:

```c
firstBlockSize = MAXALIGN(sizeof(AllocSetContext)) +
    ALLOC_BLOCKHDRSZ + ALLOC_CHUNKHDRSZ;
if (minContextSize != 0)
    firstBlockSize = Max(firstBlockSize, minContextSize);
else
    firstBlockSize = Max(firstBlockSize, initBlockSize);

set = (AllocSet) malloc(firstBlockSize);
```

So `malloc` is called *once* to get both the context header and the
keeper block's space. The point: `AllocSetReset` [aset.c:534-...]
doesn't free the keeper — it just rewinds `freeptr` and clears the
freelists. This avoids malloc-thrashing for the very common
"per-tuple context that gets reset constantly and accumulates a
few hundred bytes between resets" pattern [README:464-468].

If the keeper is bigger than `initBlockSize`, the savings compound: a
reset returns the entire context to "one big empty block ready to
accept allocations" without any allocator calls. The README at line
462-468 calls this out explicitly.

## The context freelist (recycling whole contexts)

Beyond the keeper-per-context trick, there's a second optimization
[aset.c:218-265]: the static `context_freelists[2]` array, with one
slot for default-sized contexts (`ALLOCSET_DEFAULT_SIZES`) and one for
small (`ALLOCSET_SMALL_SIZES`):

```c
static AllocSetFreeList context_freelists[2] = { {0, NULL}, {0, NULL} };

#define MAX_FREE_CONTEXTS 100
```

When `AllocSetDelete` runs on a context with a matching
`freeListIndex >= 0` [aset.c:392-399], the context isn't actually
freed — it's reset to keeper-only state and pushed onto the freelist
via `nextchild` (repurposed for this off-tree linkage).

The next `AllocSetContextCreate` with matching parameters
[aset.c:404-430] picks the recycled context off the freelist, re-runs
`MemoryContextCreate` to fix up the parent/name/methods, and returns
it. **One `malloc` saved per recycle.** When the list hits 100
contexts, the next delete on a recyclable one wipes the whole list to
keep the process compact [README excerpt at aset.c:232-237].

The "last-in-first-out" recycle order [aset.c:230-231] improves
locality: the most recently freed context is most likely still in cache.

## `AllocSetAlloc` — the hot path

`AllocSetAlloc` [aset.c:1011-1100] is intentionally minimal so the
compiler can apply tail-call optimization on the rare paths
[aset.c:1003-1009]. The structure:

```c
void *
AllocSetAlloc(MemoryContext context, Size size, int flags)
{
    AllocSet set = (AllocSet) context;
    int fidx;
    MemoryChunk *chunk;
    AllocBlock block;
    Size chunk_size, availspace;

    /* (1) oversized → dedicated block */
    if (size > set->allocChunkLimit)
        return AllocSetAllocLarge(context, size, flags);

    /* (2) freelist hit → pop and return */
    fidx = AllocSetFreeIndex(size);
    chunk = set->freelist[fidx];
    if (chunk != NULL) {
        AllocFreeListLink *link = GetFreeListLink(chunk);
        set->freelist[fidx] = link->next;
        return MemoryChunkGetPointer(chunk);  /* + valgrind dance */
    }

    /* (3) carve from active block */
    chunk_size = GetChunkSizeFromFreeListIdx(fidx);
    block = set->blocks;
    availspace = block->endptr - block->freeptr;
    if (unlikely(availspace < (chunk_size + ALLOC_CHUNKHDRSZ)))
        return AllocSetAllocFromNewBlock(context, size, flags, fidx);
    return AllocSetAllocChunkFromBlock(context, block, size, chunk_size, fidx);
}
```

Three branches, with all the failure / slow-path logic factored into
`pg_noinline` helpers so this function compiles to a tight ~50 lines of
assembly. The freelist link [aset.c:122-139] is stored **inside** the
chunk's user data area (which is unused when the chunk is on the
freelist):

```c
typedef struct AllocFreeListLink { MemoryChunk *next; } AllocFreeListLink;
#define GetFreeListLink(chkptr) \
    (AllocFreeListLink *) ((char *) (chkptr) + ALLOC_CHUNKHDRSZ)
```

So the freelist is a single-linked stack with no extra allocation
overhead. `pfree` pushes onto the head; alloc pops from the head.

## `AllocSetAllocChunkFromBlock` — carving from the active block

`AllocSetAllocChunkFromBlock` [aset.c:815-851] is the inlined chunk-
creation helper. It:

1. Treats `block->freeptr` as the new chunk's start.
2. Bumps `block->freeptr` by `chunk_size + ALLOC_CHUNKHDRSZ`.
3. `MemoryChunkSetHdrMask(chunk, block, fidx, MCTX_ASET_ID)` — stores
   the freelist index (not the chunk size — they're equivalent for
   AllocSet, and the index is what `pfree` needs) in the chunk header's
   value field, plus the block offset.

The chunk size is recoverable from the freelist index via
`GetChunkSizeFromFreeListIdx(fidx)` [aset.c:146-147]:

```c
#define GetChunkSizeFromFreeListIdx(fidx) \
    ((((Size) 1) << ALLOC_MINBITS) << (fidx))
```

So `pfree` can look at the chunk header, pull the fidx, and push the
chunk onto the right freelist — all in cache-friendly code.

## The free-space carve trick

When `AllocSetAllocFromNewBlock` [aset.c:859-987] runs (current block
is full), the obvious thing to do is allocate a new block. The clever
thing — done before that — is to **carve up the remaining free space in
the active block into chunks and push them onto the freelists**
[aset.c:887-926]:

```c
while (availspace >= ((1 << ALLOC_MINBITS) + ALLOC_CHUNKHDRSZ))
{
    /* compute the largest power-of-2 chunk that fits */
    Size availchunk = availspace - ALLOC_CHUNKHDRSZ;
    int  a_fidx = AllocSetFreeIndex(availchunk);
    if (availchunk != GetChunkSizeFromFreeListIdx(a_fidx))
    {
        a_fidx--;
        availchunk = GetChunkSizeFromFreeListIdx(a_fidx);
    }

    /* carve a chunk, push it onto freelist[a_fidx] */
    chunk = (MemoryChunk *) block->freeptr;
    block->freeptr += availchunk + ALLOC_CHUNKHDRSZ;
    MemoryChunkSetHdrMask(chunk, block, a_fidx, MCTX_ASET_ID);

    link = GetFreeListLink(chunk);
    link->next = set->freelist[a_fidx];
    set->freelist[a_fidx] = chunk;
}
```

Why: because once we push this block down the list (it's no longer the
head, and we'll never carve from it again), that remaining space would
be wasted forever otherwise. By pre-carving into power-of-2 chunks,
that space becomes useful for future allocations of those sizes. The
loop runs at most `ALLOCSET_NUM_FREELISTS - 1 = 10` iterations because
each iteration consumes at least `1 << ALLOC_MINBITS = 8` bytes and the
remaining space was, by precondition, less than `ALLOC_CHUNK_LIMIT =
8192`. `[verified-by-code]`

The new block then gets `nextBlockSize` (and the doubling kicks in for
subsequent blocks), is added to the head of the block list, and the
caller's chunk is carved from it.

The malloc-failure retry [aset.c:956-962] is also worth noting: if a
large block alloc fails, halve the requested size and retry, down to
1 MB minimum. Useful in tight-memory situations to get *some* progress.

## `AllocSetAllocLarge` — the oversized path

For `size > allocChunkLimit` (default 8KB), `AllocSetAllocLarge`
[aset.c:733-809] allocates a **dedicated block** that contains
exactly one chunk:

```c
blksize = chunk_size + ALLOC_BLOCKHDRSZ + ALLOC_CHUNKHDRSZ;
block = malloc(blksize);
chunk = (MemoryChunk *) (block + ALLOC_BLOCKHDRSZ);
MemoryChunkSetHdrMaskExternal(chunk, MCTX_ASET_ID);
```

`MemoryChunkSetHdrMaskExternal` sets the chunk's "external" bit. This
matters because the 30-bit value field can only encode chunk sizes up
to `2^30 - 1 ≈ 1GB`; for `palloc_huge` allocations that may go up to
2GB-ish, the value field is insufficient. The external flag tells
`pfree` to use a different recovery scheme: `ExternalChunkGetBlock`
[aset.c:215-216]:

```c
#define ExternalChunkGetBlock(chunk) \
    (AllocBlock) ((char *) chunk - ALLOC_BLOCKHDRSZ)
```

— the block header is exactly `ALLOC_BLOCKHDRSZ` bytes before the
chunk header, because external chunks always own their entire block.
No offset math needed. `[from-comment]`

The new dedicated block is **spliced underneath** the active block
[aset.c:786-793], not at the head:

```c
if (set->blocks != NULL) {
    block->prev = set->blocks;
    block->next = set->blocks->next;
    if (block->next) block->next->prev = block;
    set->blocks->next = block;
}
```

Why "under" rather than "at the head"? Because the head is the active
block we're still allocating from. Pushing the oversized block down
means we don't lose the unused space remaining in the active block.
That's the same impulse that drives the carve trick.

## `AllocSetFree` — two paths

`AllocSetFree` [aset.c:1106-1222] branches on `MemoryChunkIsExternal`:

**External path** [aset.c:1115-1157]:
1. `ExternalChunkGetBlock` to get the dedicated block.
2. Sanity check: `block->freeptr == block->endptr` (block is full
   because the one chunk is the entire usable space). If not, elog
   ERROR — corrupt pointer.
3. Delink block from the doubly-linked block list.
4. `set->header.mem_allocated -= block->endptr - (char *) block;`
5. `free(block)` — return to malloc.

**Normal path** [aset.c:1158-1221]:
1. `MemoryChunkGetBlock(chunk)` recovers the block via the offset
   stored in the chunk header.
2. `fidx = MemoryChunkGetValue(chunk)` — the freelist index.
3. Sanity-check fidx, store the freelist `next` pointer in the chunk's
   data area, push onto `freelist[fidx]`. **No malloc/free at all.**

Two diagnostic checks under `MEMORY_CONTEXT_CHECKING`
[aset.c:1192-1202]:

- **Double-pfree detection**: free chunks have `requested_size =
  InvalidAllocSize`. Hitting that on entry to free → `elog(ERROR,
  "detected double pfree in %s %p")`.
- **Write-past-end detection**: `set_sentinel(p, requested_size)`
  writes a sentinel byte just past `requested_size`; a corrupted
  sentinel triggers `elog(WARNING, "detected write past chunk end")`.

The comment at aset.c:1177-1191 explains the asymmetry between ERROR
(double pfree) and WARNING (write past end): a double-pfree creates a
corrupted freelist that *will* cause downstream confusion, so kill the
backend immediately. Write-past-end is already-done damage; whining is
useful but stopping isn't.

## Reset and delete

`AllocSetReset` (after aset.c:540) walks the block list and frees
every non-keeper block; the keeper is rewound to empty
(`freeptr = data start`). All freelist heads are NULL'd.

`AllocSetDelete` (around aset.c:670-726) frees every block including
the keeper (via `free(set)` at the end, which releases both the
context header and the keeper-block storage in one shot). The
freelist-recycle path (described above) intercepts before this if
`freeListIndex >= 0`.

The `Assert(context->mem_allocated == keepersize)` at aset.c:715
verifies the accounting: after reset, only the keeper's storage is
left, and `mem_allocated` should match that.

## Invariants

- **`set->blocks` is never NULL** after creation. The keeper block is
  always present.
- **Block list is doubly-linked**, head = currently-active block.
  Allocations come from the head; new blocks become the new head;
  oversized blocks splice underneath the head.
- **External chunks always sit on their own dedicated block**, where
  the block holds exactly that one chunk. So
  `ExternalChunkGetBlock(chunk) = chunk - ALLOC_BLOCKHDRSZ`.
- **The freelist link lives inside the chunk's user data area**, which
  is safe because the chunk is unused while on the freelist. Minimum
  chunk size (8 bytes) is sized to hold this pointer.
- **`requested_size = InvalidAllocSize`** in `MEMORY_CONTEXT_CHECKING`
  builds marks a chunk as currently-free. Used for double-pfree
  detection.
- **`nextBlockSize` only grows**, capped at `maxBlockSize`. Doubling
  amortizes malloc overhead.
- **A context can have at most one entry** in the static
  `context_freelists[]` arrays. `freeListIndex` is -1 for non-
  recyclable parameter combinations.

## Useful greps

```bash
# Spot every place that picks ALLOCSET_SMALL_SIZES vs the default:
grep -RnE 'ALLOCSET_(DEFAULT|SMALL|START_SMALL)_SIZES' source/src/backend

# Find users of palloc_huge / repalloc_huge (oversized allocs):
grep -RnE 'palloc_huge|repalloc_huge|MCXT_ALLOC_HUGE' source/src

# Trace the freelist macros end-to-end:
sed -n '120,150p;240,260p;700,810p' source/src/backend/utils/mmgr/aset.c

# Inspect runtime context state (gdb):
#   (gdb) p ((AllocSet) CurrentMemoryContext)->blocks->freeptr
#   (gdb) p ((AllocSet) CurrentMemoryContext)->freelist
#   (gdb) call MemoryContextStats(TopMemoryContext)
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 1 | whole AllocSet implementation, ~1500 lines |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 158 | AllocSetContext struct (the per-set bookkeeping) |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 187 | AllocBlockData struct (the per-block bookkeeping) |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 267 | AllocSetFreeIndex (the size→freelist hash, hot enough to hand-tune) |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 346 | AllocSetContextCreateInternal (context creation, including the freelist-recycle path) |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 733 | AllocSetAllocLarge (oversized chunks, dedicated block) |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 859 | AllocSetAllocFromNewBlock (out-of-space-in-active-block path, with the free-space scavenging trick) |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 1011 | AllocSetAlloc (the hot path — freelist hit or block-carve) |
| [`src/backend/utils/mmgr/aset.c`](../files/src/backend/utils/mmgr/aset.c.md) | 1106 | AllocSetFree (freelist push or external-block immediate free) |
| [`src/include/utils/memutils.h`](../files/src/include/utils/memutils.h.md) | 1 | ALLOCSET_DEFAULT_SIZES, ALLOCSET_SMALL_SIZES, ALLOCSET_SEPARATE_THRESHOLD |

<!-- /callsites:auto -->

## Cross-references

- [[memory-context-api-and-dispatch]] — the abstract MemoryContext API
  and the 4-bit chunk header that makes this dispatch table work.
- [[memory-context-slab-generation-bump]] — the three specialized
  allocators that share the chunk-header convention but make different
  block-management trade-offs.
- [[expression-evaluator-flow]] — the per-tuple ExprContext reset
  rhythm, which is the classic "keeper block keeps malloc out of the
  hot path" use case.
- [[heap-tuple-visibility-mvcc]] — relcache subsidiary contexts that
  use `ALLOCSET_SMALL_SIZES` (small per-relation contexts).
- [[parallel-state-propagation]] — `ApplyContext` (worker) and the
  worker startup memory split.
- [[cost-units-gucs]] — the planner's per-statement context lives in an
  AllocSet child of `MessageContext`.
