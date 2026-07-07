# Slab, Generation, and Bump — the three specialized allocators

PG has three memory-context implementations beyond
[[memory-context-allocset-internals|AllocSet]]: **Slab** (fixed-size
chunks, packed densely), **Generation** (FIFO/lifespan-grouped
allocations, no global freelist), and **Bump** (no chunk header at all,
no free, only reset/delete). Each was added for a specific workload
where AllocSet's general-purpose machinery was either wasteful or
incorrect.

All three share the chunk-header dispatch convention from
[[memory-context-api-and-dispatch]] — the 4-bit `MemoryContextMethodID`
that lets `pfree` find its way back to the right allocator. They differ
in **block management**, **free-chunk tracking**, and **what
operations are even legal**.

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

Slab:
- `source/src/backend/utils/mmgr/slab.c:1` — banner comment, structure.
- `source/src/backend/utils/mmgr/slab.c:101-130` — `SlabContext` struct.
- `source/src/backend/utils/mmgr/slab.c:146-154` — `SlabBlock` struct.
- `source/src/backend/utils/mmgr/slab.c:209-263` — blocklist indexing.
- `source/src/backend/utils/mmgr/slab.c:321-426` — `SlabContextCreate`.
- `source/src/backend/utils/mmgr/slab.c:658-723` — `SlabAlloc`.
- `source/src/backend/utils/mmgr/slab.c:728-850` — `SlabFree`.

Generation:
- `source/src/backend/utils/mmgr/generation.c:1` — banner.
- `source/src/backend/utils/mmgr/generation.c:61-98` — context + block.
- `source/src/backend/utils/mmgr/generation.c:152-280` — create.
- `source/src/backend/utils/mmgr/generation.c:282-337` — reset.
- `source/src/backend/utils/mmgr/generation.c:552-628` — alloc hot path.
- `source/src/backend/utils/mmgr/generation.c:718-825` — `GenerationFree`
  (and the recycle/keeper logic).

Bump:
- `source/src/backend/utils/mmgr/bump.c:1` — banner.
- `source/src/backend/utils/mmgr/bump.c:68-96` — context + block.
- `source/src/backend/utils/mmgr/bump.c:122-249` — create.
- `source/src/backend/utils/mmgr/bump.c:517-553` — `BumpAlloc` hot path.
- `source/src/backend/utils/mmgr/bump.c:641-682` — the unsupported
  operations and their `elog(ERROR)` stubs.

Users to keep in mind while reading:
- `source/src/backend/replication/logical/reorderbuffer.c:345-365` —
  Slab for `change`/`txn`, Generation for `tup`.
- `source/src/backend/utils/sort/tuplesort.c:673` — Bump for sort tuples.
- `source/src/backend/utils/sort/tuplestore.c:277` — Generation.
- `source/src/backend/access/common/tidstore.c:181` — Bump for radix-
  tree nodes.
- `source/src/backend/access/gist/gistvacuum.c:167` — Generation for
  per-page state during vacuum.
- `source/src/backend/executor/nodeAgg.c:2045` — Bump for hashagg
  spill-out tuples.

## At a glance

| Property                        | AllocSet   | Slab          | Generation    | Bump      |
|---------------------------------|------------|---------------|---------------|-----------|
| MethodID                        | `MCTX_ASET_ID` (3) | `MCTX_SLAB_ID` (5) | `MCTX_GENERATION_ID` (4) | `MCTX_BUMP_ID` (7) |
| Variable chunk sizes            | yes (power-of-2 buckets) | **no** (one fixed size) | yes | yes |
| `pfree` supported               | yes        | yes           | yes           | **no** (elog ERROR) |
| `repalloc` supported            | yes        | only same-size | yes (copy)   | **no** |
| Chunk header (release build)    | 8 B        | 8 B           | 8 B           | **0 B** |
| Block return on empty           | only on Delete (non-keeper) | yes, with empty-block cache | yes, with single `freeblock` slot | only on Reset/Delete |
| Workload sweet-spot             | general    | many same-size objects | FIFO / lifespan-grouped | bulk-load + discard |

Each row maps to a code citation below.

## Slab — fixed-size chunks, fullest-block-first

Slab is designed for workloads that allocate millions of equally-sized
objects with mixed lifetimes (e.g. reorderbuffer's per-row `change` and
`txn` records). The fixed chunk size lets it skip the freelist
arithmetic AllocSet needs, and dense packing means fewer blocks for the
same total memory.

### Struct shape

`SlabContext` [slab.c:101-130]:

```c
typedef struct SlabContext
{
    MemoryContextData header;
    uint32      chunkSize;        /* requested (non-aligned) chunk size */
    uint32      fullChunkSize;    /* chunk + header + MAXALIGN padding */
    uint32      blockSize;
    int32       chunksPerBlock;
    int32       curBlocklistIndex; /* fullest non-empty list */
    int32       blocklist_shift;
    dclist_head emptyblocks;       /* cache of completely-empty blocks */
    dlist_head  blocklist[SLAB_BLOCKLIST_COUNT];  /* partitioned by nfree */
} SlabContext;
```

`SlabBlock` [slab.c:146-154]:

```c
typedef struct SlabBlock
{
    SlabContext *slab;
    int32        nfree;     /* free + unused chunks */
    int32        nunused;   /* chunks never yet allocated */
    MemoryChunk *freehead;  /* head of LIFO free-list */
    MemoryChunk *unused;    /* high watermark for never-allocated chunks */
    dlist_node   node;      /* slot in blocklist[] */
} SlabBlock;
```

Two key invariants from the comment at slab.c:43-64:

1. **`nfree` includes both the free-list chunks (previously pfree'd)
   and the `nunused` watermark chunks (never yet allocated).** On a
   freshly-malloc'd block, all chunks are "unused", `freehead = NULL`,
   `unused = &chunks[1]`, `nunused = chunksPerBlock - 1`, because the
   first chunk is being returned to the caller immediately.

2. **Free chunks form a LIFO stack stored *inside* the chunks' user
   data.** This is the same in-chunk linked-list trick AllocSet uses,
   for the same reason: zero per-chunk bookkeeping overhead beyond the
   chunk header itself.

### The blocklist partition

`SLAB_BLOCKLIST_COUNT = 3` [slab.c:95]. Blocks are bucketed by how many
free chunks they have:

- `blocklist[0]` — completely full blocks (`nfree == 0`).
- `blocklist[1]` — blocks with few free chunks (the "almost full" tier).
- `blocklist[2]` — blocks with many free chunks (the "almost empty"
  tier).

The bucketing is by a configurable shift `blocklist_shift`
[slab.c:118-119], computed at create time [slab.c:402-404] so that
`chunksPerBlock >> blocklist_shift < SLAB_BLOCKLIST_COUNT - 1`. The
indexing math [slab.c:209-238]:

```c
static inline int32
SlabBlocklistIndex(SlabContext *slab, int nfree)
{
    int32 index;
    int32 blocklist_shift = slab->blocklist_shift;
    /* two's-complement trick: 0 stays 0, anything else stays non-zero */
    index = -((-nfree) >> blocklist_shift);
    return index;
}
```

The two's-complement trick exploits `-0 == 0` so that any positive
`nfree` produces a non-zero index after the sign-flip-shift-flip, while
`nfree == 0` cleanly indexes the "full" bucket. Avoids a branch.

### Fullest-block-first allocation

`SlabAlloc` [slab.c:658-723] always allocates from
`slab->blocklist[curBlocklistIndex]`, which is the **lowest non-zero**
index where blocks exist — i.e., the fullest non-full bucket. The
comment at slab.c:246-249 explains the policy:

> We give priority to fuller blocks so that these are filled before
> emptier blocks. This is done to increase the chances that mostly-
> empty blocks will eventually become completely empty so they can
> be free'd.

Without this, you'd get pathological scenarios where allocations
spread across many half-empty blocks and none of them ever became
returnable.

`SlabGetNextFreeChunk` [slab.c:270-306] returns either the head of
`freehead` (a previously-pfree'd chunk, LIFO order for cache locality)
or — if `freehead == NULL` — the `unused` watermark chunk, advancing
`unused += fullChunkSize` and decrementing `nunused`. The "freehead
before unused" preference is documented at slab.c:60-64: previously-
used chunks are more likely to be in cache than never-touched memory.

### Block transitions

After every `SlabAlloc`, the block's `nfree` decreases. If that pushes
it into a lower bucket, the block is moved [slab.c:712-719]:

```c
new_blocklist_idx = SlabBlocklistIndex(slab, block->nfree);
if (slab->curBlocklistIndex != new_blocklist_idx) {
    dlist_delete_from(blocklist, &block->node);
    dlist_push_head(&slab->blocklist[new_blocklist_idx], &block->node);
    if (dlist_is_empty(blocklist))
        slab->curBlocklistIndex = SlabFindNextBlockListIndex(slab);
}
```

`SlabFree` [slab.c:728-850] does the reverse — `nfree` increases, the
block may move to a higher (emptier) bucket. Two special cases at the
end [slab.c:813-849]:

- **Block becomes completely empty** (`nfree == chunksPerBlock`):
  delete from the blocklist and try to push onto `emptyblocks` (a
  dclist that caches up to `SLAB_MAXIMUM_EMPTY_BLOCKS = 10` blocks for
  reuse). If the cache is full, actually `free(block)` to the OS.
- **`curBlocklistIndex` may need to be re-found** if the current
  index's list became empty.

The empty-blocks cache trades 10 blocks worth of memory for avoiding
malloc/free churn in workloads that drain and refill blocks in
oscillation.

### `SlabContextCreate` — sizing

`SlabContextCreate(parent, name, blockSize, chunkSize)`
[slab.c:321-426] takes block and chunk sizes, derives
`chunksPerBlock`, refuses if it would be zero (`block size too small
for chunk size`), and computes `blocklist_shift`. The
`fullChunkSize = Slab_CHUNKHDRSZ + MAXALIGN(chunkSize [+ 1 sentinel])`
includes the MAXALIGN padding and (under `MEMORY_CONTEXT_CHECKING`) one
sentinel byte.

There is **no keeper block** for Slab — the comment at slab.c:430-433
notes "we don't keep any keeper blocks or anything like that". Reset
frees every block, with the `emptyblocks` cache as the only
inter-reset retention. `[verified-by-code]`

### `SlabRealloc` is restrictive

`SlabRealloc` [slab.c:866+] succeeds **only** when called with
`size == chunkSize`. Otherwise `elog(ERROR, "%s is not supported", "realloc")`.
The comment at slab.c:856-864 justifies: Slab is fundamentally fixed-
size; any size change defeats the design.

### Who uses Slab

`reorderbuffer.c:345-355`:

```c
buffer->change_context = SlabContextCreate(new_ctx, "Change",
                                           SLAB_DEFAULT_BLOCK_SIZE,
                                           sizeof(ReorderBufferChange));
buffer->txn_context = SlabContextCreate(new_ctx, "TXN",
                                        SLAB_DEFAULT_BLOCK_SIZE,
                                        sizeof(ReorderBufferTXN));
```

Logical decoding builds and tears down millions of `ReorderBufferChange`
and `ReorderBufferTXN` records of identical size per replication
session. Slab packs them densely and recycles whole blocks as
transactions commit and their changes get spooled.

## Generation — FIFO-friendly, no global freelist

Generation [generation.c:14-33] is designed around two observations:

1. **Many workloads allocate in groups with similar lifespan**
   ("generations"): a tuple is built, processed, and discarded
   together with its peers in the same scan/sort/decode batch.
2. **A general freelist (like AllocSet's) costs CPU and cache.** If
   you never need to coalesce free chunks because chunks of the same
   generation get freed together anyway, you can skip the freelist
   entirely.

So Generation's policy is: **no freelist at all**. Just `nchunks` and
`nfree` per block, and a block becomes free-to-OS the moment all its
chunks have been pfree'd.

### Struct shape

`GenerationContext` [generation.c:61-75]:

```c
typedef struct GenerationContext
{
    MemoryContextData header;
    uint32            initBlockSize;
    uint32            maxBlockSize;
    uint32            nextBlockSize;
    uint32            allocChunkLimit;
    GenerationBlock  *block;        /* current alloc target */
    GenerationBlock  *freeblock;    /* single recycle slot, may be NULL */
    dlist_head        blocks;       /* doubly-linked block list */
} GenerationContext;
```

`GenerationBlock` [generation.c:89-98]:

```c
struct GenerationBlock
{
    dlist_node          node;
    GenerationContext  *context;
    Size                blksize;
    int                 nchunks;   /* chunks ever allocated on this block */
    int                 nfree;     /* chunks pfree'd so far */
    char               *freeptr;
    char               *endptr;
};
```

**Key difference from AllocSet**: `nchunks` counts *ever-allocated*
chunks, not currently-live ones. When `nfree == nchunks` the block is
fully drained.

### The single `freeblock` recycle slot

When a block drains to empty in `GenerationFree` [generation.c:798-824]:

```c
if (IsKeeperBlock(set, block) || set->block == block)
    GenerationBlockMarkEmpty(block);          /* case 1, 2 */
else if (set->freeblock == NULL) {
    GenerationBlockMarkEmpty(block);          /* case 3 */
    set->freeblock = block;
} else
    GenerationBlockFree(set, block);          /* otherwise free() */
```

Three exceptions to "free the empty block":

1. **It's the keeper block** — like AllocSet, Generation has a keeper
   block allocated in the same malloc as the context header
   [generation.c:128-134]. Never returned to the OS.
2. **It's the current alloc target** (`set->block`) — freeing it would
   leave `set->block` dangling.
3. **There's no `freeblock` saved yet** — keep this one for future
   FIFO recycling.

Otherwise, the empty block is `free()`'d back to malloc immediately.

The "single freeblock slot" is the Generation-specific optimization:
in a perfect FIFO workload (allocate generation N, then N+1, then
drain N, then drain N+1...), one freeblock is enough to keep the
malloc/free count near zero. More than one would just be hoarding
without benefit.

### Reset preserves the keeper

`GenerationReset` [generation.c:290-337] walks every block:
- The keeper block gets `GenerationBlockMarkEmpty` (rewind freeptr,
  clear nchunks/nfree).
- Other blocks get `GenerationBlockFree` (return to OS).
- `freeblock` is NULL'd because it may be one of the freed blocks.
- `nextBlockSize` is reset to `initBlockSize`.

After reset, `set->block = KeeperBlock(set)`, the block list contains
only the keeper, and `freeblock == NULL`.

### `GenerationRealloc` does an alloc + copy + free

Without a freelist, `GenerationRealloc` [generation.c:834+] can't
extend in place except in the lucky case where the new size fits in
the same chunk. Otherwise: alloc new chunk in the current block, copy
data over, pfree the old chunk. Functionally correct, but expensive —
which is the design's bet: callers who care about realloc should pick
AllocSet, not Generation.

### Who uses Generation

`reorderbuffer.c:365`:

```c
buffer->tup_context = GenerationContextCreate(new_ctx, "Tuples",
                                              SLAB_DEFAULT_BLOCK_SIZE,
                                              SLAB_LARGE_BLOCK_SIZE,
                                              SLAB_LARGE_BLOCK_SIZE);
```

Logical decoding's per-tuple data is variable-size (Slab won't do), and
decoded tuples within one replicated transaction tend to be freed
together when the transaction is dispatched — perfect Generation fit.

`tuplestore.c:277` uses Generation for the same reason: tuplestore
holds rows for the duration of a scan, then discards them all.

`gistvacuum.c:167` uses Generation for `page_set_context`: per-page
state during gist vacuum that lives until the page is processed.

## Bump — densest possible, no free

Bump [bump.c:1-37] is the most aggressive trade-off: **no chunk header
at all** in release builds, no `pfree`, no `repalloc`. The only way to
recover memory is `MemoryContextReset` or `MemoryContextDelete`.

### Why no header

A `MemoryChunk` header is 8 bytes (16 with `MEMORY_CONTEXT_CHECKING`).
For workloads that allocate millions of tiny objects, that 8-byte
overhead can dominate the actual payload. Removing it:

- **Saves 8 B per allocation.** For 100 M chunks: 800 MB.
- **Improves cache density.** More chunks per cache line, fewer
  cache-line fetches per pass.

The cost: no allocator-specific operations are possible on a chunk,
because there's no header to dispatch from. So `pfree`/`repalloc`/
`GetMemoryChunkContext`/`GetMemoryChunkSpace` all `elog(ERROR)`
[bump.c:641-682]:

```c
void BumpFree(void *pointer) {
    elog(ERROR, "%s is not supported by the bump memory allocator", "pfree");
}
void *BumpRealloc(void *p, Size s, int f) {
    elog(ERROR, "%s is not supported by the bump memory allocator", "realloc");
    return NULL;
}
MemoryContext BumpGetChunkContext(void *p) {
    elog(ERROR, "%s is not supported by the bump memory allocator",
         "GetMemoryChunkContext");
    return NULL;
}
Size BumpGetChunkSpace(void *p) {
    elog(ERROR, "%s is not supported by the bump memory allocator",
         "GetMemoryChunkSpace");
    return 0;
}
```

Under `MEMORY_CONTEXT_CHECKING` builds, Bump *does* maintain a chunk
header [bump.c:52-57] so these errors are still raised cleanly (not
SEGV) and sentinel bytes/double-free detection still work. But in
release builds the chunk *literally has zero bytes* of allocator
metadata.

### Struct shape

`BumpContext` [bump.c:68-80]:

```c
typedef struct BumpContext
{
    MemoryContextData header;
    uint32            initBlockSize;
    uint32            maxBlockSize;
    uint32            nextBlockSize;
    uint32            allocChunkLimit;
    dlist_head        blocks;
} BumpContext;
```

`BumpBlock` [bump.c:88-96]:

```c
struct BumpBlock
{
    dlist_node node;
#ifdef MEMORY_CONTEXT_CHECKING
    BumpContext *context;
#endif
    char       *freeptr;
    char       *endptr;
};
```

That's it. No chunk count, no free count, no freelist. The block holds
data starting after the header and ending at `endptr`; `freeptr` is
the bump pointer that monotonically advances during allocations and
only resets on `BumpReset`.

### `BumpAlloc` — three lines of real work

`BumpAlloc` [bump.c:517-553] hot path:

```c
chunk_size = MAXALIGN(size);    /* +1 sentinel under CHECKING */
if (chunk_size > set->allocChunkLimit)
    return BumpAllocLarge(...);
required_size = chunk_size + Bump_CHUNKHDRSZ;  /* CHUNKHDRSZ = 0 in release */
block = dlist_container(BumpBlock, node, dlist_head_node(&set->blocks));
if (BumpBlockFreeBytes(block) < required_size)
    return BumpAllocFromNewBlock(...);
return BumpAllocChunkFromBlock(context, block, size, chunk_size);
```

`BumpAllocChunkFromBlock` returns `block->freeptr` (no chunk header to
initialize) and bumps `block->freeptr += chunk_size`. Faster than any
other allocator for the common path.

### `BumpAllocLarge` — keeps the chunk header trick

For oversized chunks, `BumpAllocLarge` [bump.c:313-380ish] allocates a
dedicated block (like AllocSet's oversized path) and *does* set up a
chunk header marked external. The reason: `pfree` on these large
chunks still has to do something — but Bump's `pfree` is `elog(ERROR)`
regardless. The header is there for diagnostic crash messages and the
`MEMORY_CONTEXT_CHECKING` path, not for actual free behavior.

### Reset is the only release

`BumpReset` [bump.c:251+]:
- Walk the block list.
- Keeper block: rewind `freeptr` to data-start (mark empty).
- Other blocks: `free(block)`.
- `nextBlockSize` resets to `initBlockSize`.

Bump is the only allocator where reset is the *primary* recovery
mechanism — everywhere else, reset is "between transactions" or
"between tuples"; for Bump, it's "after the bulk operation is done".

### Who uses Bump

`tuplesort.c:673`:

```c
state->base.tuplecontext = BumpContextCreate(state->base.sortcontext,
                                             "Caller tuples",
                                             ALLOCSET_DEFAULT_SIZES);
```

The sort holds copies of all input tuples until the sort completes,
then dumps them all. No tuple is individually pfree'd during sort.
Perfect Bump fit.

`nodeAgg.c:2045` uses Bump for hashagg's `hash_tuplescxt`: the
hashtable tuples are alive for the entire hash phase, freed in bulk.

`tidstore.c:181` uses Bump for radix tree node storage during the
TidStore phase of vacuum: nodes accumulate, never get individually
freed.

`nodeRecursiveunion.c:222`, `nodeSetOp.c:607`, `nodeSubplan.c:937` —
executor operators that accumulate tuples in a per-tuple-batch context
and discard them as a group.

## Choosing between the four allocators

A short decision tree, in priority order:

1. **Do you need `pfree` / `repalloc` on individual chunks?**
   - No → **Bump**. The densest, the fastest, the simplest.
   - Yes → continue.
2. **Are all chunks the same size?**
   - Yes → **Slab**. Dense packing, fullest-block-first.
   - No → continue.
3. **Will chunks be freed in lifespan-groups (FIFO-ish)?**
   - Yes → **Generation**. No freelist overhead.
   - No → **AllocSet**. The general-purpose default.

The pattern in PG: most code uses AllocSet by default and the
specialized allocators only where profiling identified the workload.
Slab and Generation arrived in 9.6, Bump in PG 17.

## Invariants

Across all three:

- **The chunk-header methodID dispatch** still works for Slab and
  Generation chunks; Bump release-build chunks have no header at all
  and dispatch is irrelevant because every operation but `palloc` /
  reset / delete is forbidden.
- **No keeper block in Slab.** Reset frees every block; only the
  `emptyblocks` cache (up to 10 blocks) survives.
- **Keeper block in Generation and Bump.** Same trick as AllocSet:
  allocated in the same malloc as the context header.
- **`palloc(0)` is still valid on all four**; `pfree(NULL)` and
  `repalloc(NULL, n)` are still forbidden on AllocSet, Slab, and
  Generation. On Bump, all of `pfree`/`repalloc` are forbidden
  regardless of argument.

Slab-specific:
- **`chunkSize` is fixed at create time.** `SlabAlloc(set, n)` with
  `n != chunkSize` raises ERROR.
- **`SLAB_BLOCKLIST_COUNT >= 2`** [slab.c:93].
- **Free chunks form a LIFO stack in the chunks' own memory.**

Generation-specific:
- **At most one `freeblock` retained.** If a second block goes empty
  while `freeblock` is non-NULL, that second block is `free()`'d
  immediately.
- **`nchunks` is monotonically increasing on a block** until the block
  is fully drained (`nfree == nchunks`) and either becomes the
  `freeblock` or is freed.

Bump-specific:
- **No `pfree` / `repalloc` / `GetMemoryChunkContext` / `GetMemoryChunkSpace`.**
- **Reset and delete are the only releases.** Long-lived pointers
  into a Bump context are a footgun — any code that calls `pfree` on
  them ERRORs at runtime.
- **Under `MEMORY_CONTEXT_CHECKING`, Bump has a chunk header for
  diagnostics**; in release builds, chunks are header-less.

## Useful greps

```bash
# Find every Slab/Generation/Bump context in the tree, by name:
grep -RnE 'SlabContextCreate|GenerationContextCreate|BumpContextCreate' source/src/backend

# Count chunk-header bytes by allocator:
grep -nE 'Slab_CHUNKHDRSZ|Generation_CHUNKHDRSZ|Bump_CHUNKHDRSZ' \
    source/src/backend/utils/mmgr/*.c

# See how blocklist transitions are reasoned about (slab):
sed -n '209,310p' source/src/backend/utils/mmgr/slab.c

# Inspect a Generation context's block list at runtime (gdb):
#   (gdb) p ((GenerationContext *) ctx)->blocks
#   (gdb) p ((GenerationContext *) ctx)->freeblock

# Find every Bump user — they're the workloads where reset is the
# primary release point:
grep -Rn 'BumpContextCreate' source/src/backend
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 181 | Bump for radix- tree nodes |
| [`src/backend/access/gist/gistvacuum.c`](../files/src/backend/access/gist/gistvacuum.c.md) | 167 | Generation for per-page state during vacuum |
| [`src/backend/executor/nodeAgg.c`](../files/src/backend/executor/nodeAgg.c.md) | 2045 | Bump for hashagg spill-out tuples |
| [`src/backend/replication/logical/reorderbuffer.c`](../files/src/backend/replication/logical/reorderbuffer.c.md) | 345 | Slab for change/txn, Generation for tup |
| [`src/backend/utils/mmgr/bump.c`](../files/src/backend/utils/mmgr/bump.c.md) | 1 | banner |
| [`src/backend/utils/mmgr/bump.c`](../files/src/backend/utils/mmgr/bump.c.md) | 68 | context + block |
| [`src/backend/utils/mmgr/bump.c`](../files/src/backend/utils/mmgr/bump.c.md) | 122 | create |
| [`src/backend/utils/mmgr/bump.c`](../files/src/backend/utils/mmgr/bump.c.md) | 517 | BumpAlloc hot path |
| [`src/backend/utils/mmgr/bump.c`](../files/src/backend/utils/mmgr/bump.c.md) | 641 | the unsupported operations and their elog(ERROR) stubs |
| [`src/backend/utils/mmgr/generation.c`](../files/src/backend/utils/mmgr/generation.c.md) | 1 | banner |
| [`src/backend/utils/mmgr/generation.c`](../files/src/backend/utils/mmgr/generation.c.md) | 61 | context + block |
| [`src/backend/utils/mmgr/generation.c`](../files/src/backend/utils/mmgr/generation.c.md) | 152 | create |
| [`src/backend/utils/mmgr/generation.c`](../files/src/backend/utils/mmgr/generation.c.md) | 282 | reset |
| [`src/backend/utils/mmgr/generation.c`](../files/src/backend/utils/mmgr/generation.c.md) | 552 | alloc hot path |
| [`src/backend/utils/mmgr/generation.c`](../files/src/backend/utils/mmgr/generation.c.md) | 718 | GenerationFree (and the recycle/keeper logic) |
| [`src/backend/utils/mmgr/slab.c`](../files/src/backend/utils/mmgr/slab.c.md) | 1 | banner comment, structure |
| [`src/backend/utils/mmgr/slab.c`](../files/src/backend/utils/mmgr/slab.c.md) | 101 | SlabContext struct |
| [`src/backend/utils/mmgr/slab.c`](../files/src/backend/utils/mmgr/slab.c.md) | 146 | SlabBlock struct |
| [`src/backend/utils/mmgr/slab.c`](../files/src/backend/utils/mmgr/slab.c.md) | 209 | blocklist indexing |
| [`src/backend/utils/mmgr/slab.c`](../files/src/backend/utils/mmgr/slab.c.md) | 321 | SlabContextCreate |
| [`src/backend/utils/mmgr/slab.c`](../files/src/backend/utils/mmgr/slab.c.md) | 658 | SlabAlloc |
| [`src/backend/utils/mmgr/slab.c`](../files/src/backend/utils/mmgr/slab.c.md) | 728 | SlabFree |
| [`src/backend/utils/sort/tuplesort.c`](../files/src/backend/utils/sort/tuplesort.c.md) | 673 | Bump for sort tuples |
| [`src/backend/utils/sort/tuplestore.c`](../files/src/backend/utils/sort/tuplestore.c.md) | 277 | Generation |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md)
- [`add-new-replication-message`](../scenarios/add-new-replication-message.md)
- [`fix-memory-leak`](../scenarios/fix-memory-leak.md)

<!-- /scenarios:auto -->
## Cross-references

- [[memory-context-api-and-dispatch]] — the abstract API and the 4-bit
  chunk-header methodID that lets `pfree` find the right allocator (and
  ERROR cleanly on a Bump chunk).
- [[memory-context-allocset-internals]] — the default allocator. This
  doc's "decision tree" routes everything not-specialized back to it.
- [[apply-streaming-and-parallel]] — the reorderbuffer's Slab+Slab+
  Generation triad is one of the most studied real-world uses of the
  specialized allocators.
- [[heap-tuple-freeze]] — vacuum's TidStore uses Bump for radix-tree
  node storage.
- [[parallel-state-propagation]] — the worker's per-tuple context is a
  Bump in some operators (HashAgg spill, sort).
