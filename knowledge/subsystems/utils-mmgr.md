# Memory-context manager (palloc / MemoryContext)

- **Source path:** `source/src/backend/utils/mmgr/`
- **Header path:** `source/src/include/utils/{palloc.h,memutils.h,memutils_internal.h,memutils_memorychunk.h,memdebug.h,freepage.h,dsa.h,portal.h,relptr.h}` + `source/src/include/nodes/memnodes.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
- **README anchor:** `source/src/backend/utils/mmgr/README` (527 lines) — the canonical design narrative. Section map in `knowledge/files/src/backend/utils/mmgr/README.md`.
- **Companion docs:** `knowledge/idioms/memory-contexts.md` (idiom-level digest, decision tree, pitfalls); per-file docs under `knowledge/files/src/backend/utils/mmgr/` (one per `.c`).

## 1. Purpose

`utils/mmgr` is PostgreSQL's allocator. Backend code does almost no raw `malloc`/`free`; instead, every allocation lives in a `MemoryContext` node arranged in a per-backend tree, and **whole subtrees are freed in one shot** at statement/transaction/tuple boundaries by `MemoryContextReset` or `MemoryContextDelete`. The directory layers four concerns on top of `malloc`: (1) a type-independent dispatch + lifecycle layer (`mcxt.c`) that owns the global context pointers and the public `palloc`/`pfree` API; (2) five per-type allocator implementations (`aset.c`, `generation.c`, `slab.c`, `bump.c`, `alignedalloc.c`) wired through a 16-entry vtable indexed by a 4-bit ID stored in every chunk's header; (3) the portal-lifetime manager `portalmem.c`, which owns `TopPortalContext` and the per-portal context lifecycle; and (4) the cross-backend shared-memory allocator `dsa.c` built on top of the per-segment `FreePageManager` (`freepage.c`) — a parallel allocator family that does NOT plug into the `MemoryContext` vtable. The `memdebug.c` file holds the wipe / sentinel / Valgrind plumbing that every backend allocator file shares. [from-README] (`README:4-50`) [via knowledge/files/src/backend/utils/mmgr/README.md]

## 2. Mental model

To navigate this subsystem hold these concepts in your head:

- **Hierarchical contexts, vtable dispatch.** A `MemoryContext` is a pointer to a `MemoryContextData` node carrying `parent`/`firstchild`/`prev/nextchild` links, a `methods` vtable, an `isReset` flag, an `allowInCritSection` flag, and a `reset_cbs` callback list. Deleting a parent deletes the whole subtree; resetting a parent by default deletes children (use `MemoryContextResetOnly` + `MemoryContextResetChildren` to keep them as empty containers). [verified-by-code] (`memnodes.h:117-134`, `README:107-137`) [via knowledge/files/src/include/nodes/memnodes.h.md, README.md]
- **Every chunk carries a 4-bit method ID.** A uint64 `MemoryChunk` header sits immediately before every palloc'd pointer (except production-build bump chunks); its low 4 bits identify the owning allocator. `pfree(p)` and `repalloc(p, size)` look up that method ID and dispatch to the right per-type callback — they do NOT consult `CurrentMemoryContext`. [from-README] (`README:397-419`) [via knowledge/files/src/backend/utils/mmgr/README.md] [verified-by-code] (`mcxt.c:205-234, 1619-1659`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- **`CurrentMemoryContext` is a global pointing at the context where bare `palloc` allocates.** Swap it with the inline `MemoryContextSwitchTo(new)` (one global store, `palloc.h:137-145`). The rule of thumb from `README:91-96`: keep `CurrentMemoryContext` pointing at the **shortest-lived** context that still outlives the data being allocated. [from-README] [via knowledge/idioms/memory-contexts.md]
- **palloc never returns NULL, never accepts NULL into pfree/repalloc.** OOM raises `ereport(ERROR)` via `MemoryContextAllocationFailure` (`mcxt.c:1200-1214`). Opt out with `palloc_extended(size, MCXT_ALLOC_NO_OOM)`. `palloc(0)` is valid; `pfree(NULL)` is NOT valid; `repalloc(NULL, …)` is NOT valid. Regular `palloc` caps at `MaxAllocSize = 1 GB - 1` (`memutils.h:40`); use `palloc_extended(.., MCXT_ALLOC_HUGE)` or `MemoryContextAllocHuge` to go up to `MaxAllocHugeSize = SIZE_MAX/2`. [from-README] (`README:55-75`) [via knowledge/idioms/memory-contexts.md, knowledge/files/src/backend/utils/mmgr/README.md]
- **Five allocator types, picked at context creation.** `AllocSet` is the general-purpose default (power-of-two freelists, block doubling, keeper-on-reset); `Generation` is FIFO/queue-shaped (per-block alloc/free counters, no global freelist, single recycled empty block); `Slab` is fixed-size dense packing with per-block free list and 3-bucket fullness binning; `Bump` is densest possible (no chunk header, no pfree/repalloc allowed); `AlignedAlloc` is a redirection method ID, not a real context type — used only by `palloc_aligned`. [from-README] (`README:471-499`) [via knowledge/files/src/backend/utils/mmgr/README.md, aset.c.md, generation.c.md, slab.c.md, bump.c.md, alignedalloc.c.md]
- **Backend-private allocators are NOT shared.** Everything in `mcxt.c`/`aset.c`/`generation.c`/`slab.c`/`bump.c` is per-process state — there is no locking, no cross-backend visibility. The DSA family (`dsa.c` + `freepage.c`) is the *separate* path for cross-backend allocation via `dsa_pointer` opaque IDs that any attached backend can resolve via `dsa_get_address`. [verified-by-code] (no lock primitives in any backend allocator file) [via knowledge/files/src/backend/utils/mmgr/dsa.c.md]
- **No palloc in a critical section** unless the target context has `allowInCritSection = true`. Enforced via `AssertNotInCriticalSection` on every `MemoryContextAlloc*` and `palloc*` entry point (`mcxt.c:198-199, 1240, 1274, 1297, 1397, 1427, 1449`). `ErrorContext` is opted in by `MemoryContextInit` so OOM reporting works during PANIC. Children inherit `allowInCritSection` at create time only — toggling it on the parent does not retroactively propagate. [verified-by-code] (`mcxt.c:1184-1191`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- **Reset/delete callbacks are the lifetime-tied cleanup hook.** `MemoryContextRegisterResetCallback` attaches a one-shot callback to any context; callbacks fire in reverse-registration order, child callbacks fire before parent callbacks, and the callback record is popped before invocation so an erroring callback won't be retried on re-reset. [verified-by-code] (`mcxt.c:636-651, 533`, `README:139-170`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

## 3. Key files

- `README` (527 lines) — canonical design doc. Section map at `knowledge/files/src/backend/utils/mmgr/README.md`; load-bearing facts: method-ID dispatch, MemoryChunk layout, external-chunk flag, keeper block, block-level accounting.
- `mcxt.c` (1946 lines) — type-independent layer. Owns globals (`TopMemoryContext`, `CurrentMemoryContext`, `ErrorContext`, `CacheMemoryContext`, `MessageContext`, `TopTransactionContext`, `CurTransactionContext`, `PortalContext`, `PostmasterContext` at `mcxt.c:161-176`), `mcxt_methods[16]` vtable (`mcxt.c:64-153`), `MemoryContextInit`, `Reset`, `Delete`, `Create`, `SetParent`, `palloc`/`pfree`/`repalloc`/`MemoryContextAlloc*`, `MemoryContextAllocAligned`, `MemoryContextStats[Detail]`, `MemoryContextMemAllocated/Consumed`, the `pg_log_backend_memory_contexts(pid)` signal handler `ProcessLogMemoryContextInterrupt`, and the `MemoryContextStrdup`/`pstrdup`/`pnstrdup`/`psprintf`/`pchomp` string helpers. [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- `aset.c` (1805 lines) — `AllocSet`, the default. Power-of-two freelists (11 size classes, 8B…8KB), block-doubling from `initBlockSize` to `maxBlockSize`, `allocChunkLimit` boundary above which a chunk goes onto its own dedicated "external" block. Keeper block + context header malloc'd together (`aset.c:432-454`). Process-wide `context_freelists[2]` cache of up to 100 empty contexts each for the `ALLOCSET_DEFAULT_SIZES` and `ALLOCSET_SMALL_SIZES` shapes recycles contexts on delete. [via knowledge/files/src/backend/utils/mmgr/aset.c.md]
- `generation.c` (1244 lines) — `GenerationContext` for FIFO/queue workloads. Each block carries `nchunks`/`nfree`; on a block becoming empty, either parks in `set->freeblock` (capacity 1) or returns to malloc. No per-context freelist. Keeper-block pattern matches AllocSet. [via knowledge/files/src/backend/utils/mmgr/generation.c.md]
- `slab.c` (1194 lines) — `SlabContext` for fixed-size chunks. Each block sliced into `chunksPerBlock` chunks of `fullChunkSize`; per-block linked free list (next pointer overlaid on chunk body); 3-bucket fullness binning (`blocklist[SLAB_BLOCKLIST_COUNT=3]`) so "find a non-full block" is O(1); up to `SLAB_MAXIMUM_EMPTY_BLOCKS=10` empty blocks cached. **No realloc** — `SlabRealloc` `elog(ERROR)`s. **No keeper block** — context header is its own malloc. [via knowledge/files/src/backend/utils/mmgr/slab.c.md]
- `bump.c` (837 lines) — `BumpContext` for densest packing. **No chunk header in production builds** (`Bump_CHUNKHDRSZ = 0`). `BumpFree`, `BumpRealloc`, `BumpGetChunkContext`, `BumpGetChunkSpace` are all stubs that `elog(ERROR)` (`bump.c:645-682`). The only way to release bump memory is `MemoryContextReset` / `MemoryContextDelete`. Under `MEMORY_CONTEXT_CHECKING` a chunk header IS prepended so misuse routes through `mcxt_methods[MCTX_BUMP_ID]` to a clear error message. Added in PG 17. [via knowledge/files/src/backend/utils/mmgr/bump.c.md]
- `alignedalloc.c` (190 lines) — **not a real context type.** Only implements `free_p`/`realloc`/`get_chunk_context`/`get_chunk_space` for redirection chunks tagged `MCTX_ALIGNED_REDIRECT_ID`. `palloc_aligned` over-allocates in the underlying real allocator, aligns the visible pointer up, writes a redirection MemoryChunk in the bytes just before it; `pfree` of an aligned pointer dispatches here, which then `pfree`'s the underlying unaligned chunk. [via knowledge/files/src/backend/utils/mmgr/alignedalloc.c.md]
- `memdebug.c` (93 lines) — only `randomize_mem` is compiled (under `RANDOMIZE_ALLOCATED_MEMORY`); the rest is documentation. Macros (`wipe_mem`, `set_sentinel`, `sentinel_ok`, the `VALGRIND_MAKE_MEM_*` stubs) live in `utils/memdebug.h`. Sentinel byte = `0x7E`; freed-memory clobber = `0x7F`. [from-comment] (`memdebug.c:14-52`) [via knowledge/files/src/backend/utils/mmgr/memdebug.c.md]
- `portalmem.c` (1295 lines) — portal lifecycle + per-portal contexts. Owns `TopPortalContext` (`portalmem.c:93`), the portal-name `PortalHashTable`, the `PORTAL_NEW → DEFINED → READY → ACTIVE → DONE|FAILED` state machine, and the at-(sub)commit/abort/cleanup hooks called from `xact.c`. A holdable cursor's `holdContext` is a *sibling* of the portal context under `TopPortalContext` so the tuplestore can outlive the portal during HOLD. [via knowledge/files/src/backend/utils/mmgr/portalmem.c.md]
- `dsa.c` (2421 lines) — Dynamic Shared Area. Layered on DSM. Hands out `dsa_pointer` opaque IDs that any backend with `dsa_attach` to the same area can convert to a local pointer via `dsa_get_address`. Slab-of-spans internally; small objects (≤8 KB) come from size-class pools, large from per-segment `FreePageManager`. Segments grow on demand up to `DSA_MAX_SEGMENTS=1024`. Two-level locking: area-wide lock + per-pool lock. [via knowledge/files/src/backend/utils/mmgr/dsa.c.md]
- `freepage.c` (1886 lines) — page-level (4 KB) allocator used inside `dsa.c`. A `FreePageManager` tracks free runs of pages within a caller-provided region; bookkeeping (size-binned freelists + in-memory btree keyed by page number for coalescing) lives **inside the pages it manages**, using relative pointers so it works across backend mappings of the same DSM segment. [via knowledge/files/src/backend/utils/mmgr/freepage.c.md]

## 4. Key data structures

- **`MemoryContextData`** (`memnodes.h:117`) — abstract base for every context. Fields: `NodeTag type` (`T_AllocSetContext`, `T_GenerationContext`, `T_SlabContext`, `T_BumpContext`), `bool isReset`, `bool allowInCritSection`, `Size mem_allocated`, `const MemoryContextMethods *methods`, parent/sibling pointers, `name` (must be a compile-time literal — enforced by `StaticAssertExpr` in `AllocSetContextCreate`), `ident` (dynamic identifier; set via `MemoryContextSetIdentifier`), `reset_cbs`. [verified-by-code] (`memnodes.h:117-134`, `memutils.h:124-127`) [via knowledge/files/src/include/nodes/memnodes.h.md]
- **`MemoryContextMethods`** (`memnodes.h:58`) — 10-entry vtable: `alloc`, `free_p`, `realloc`, `reset`, `delete_context`, `get_chunk_context`, `get_chunk_space`, `is_empty`, `stats`, `check` (assert-only). Per-type implementations are declared in `memutils_internal.h` and wired into `mcxt.c:64-153` (the `mcxt_methods[16]` array). [verified-by-code] [via knowledge/files/src/include/nodes/memnodes.h.md, knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- **`MemoryContextMethodID`** (4-bit enum in `memutils_internal.h`) — values used: `MCTX_ASET_ID`, `MCTX_GENERATION_ID`, `MCTX_SLAB_ID`, `MCTX_ALIGNED_REDIRECT_ID`, `MCTX_BUMP_ID`. Slots `0`, `1`, `2`, `15` are reserved (glibc-pointer detection, wiped-memory detection) and point at `BogusFree`/`BogusRealloc`/`BogusGetChunkContext` — calling any of these `elog(ERROR)`s with the bad pointer plus the raw 64-bit header dump so misuse is debuggable. [verified-by-code] (`mcxt.c:64-153, 308-337`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- **`MemoryChunk`** (`memutils_memorychunk.h`) — the uint64 header immediately preceding every (non-bump-production) chunk pointer. Packs four fields: 4-bit method ID, 1-bit external flag, 30-bit value (allocator-specific: AllocSet freelist index, Generation/Slab/Bump chunk size, AlignedRedirect alignment), 30-bit block offset. The top bit of value and bottom bit of block-offset are *the same bit* — safe because MAXALIGN guarantees the offset's low bit is zero. [from-README] (`README:421-435`) [via knowledge/files/src/backend/utils/mmgr/README.md]
- **External chunks** — for "large" allocations (size > `allocChunkLimit`), the chunk gets its own dedicated block; the chunk header sets the external flag and stomps `MEMORYCHUNK_MAGIC` over the value+offset fields. The owning allocator finds the block by other means (in practice: the block always starts immediately before the chunk header at a known offset). [from-README] (`README:437-442`) [via knowledge/files/src/backend/utils/mmgr/README.md]
- **`AllocSetContext`** (`aset.c:158-171`) — extends `MemoryContextData` with: `blocks` (doubly-linked block list, current allocation block at head), `freelist[ALLOCSET_NUM_FREELISTS=11]`, `initBlockSize`, `maxBlockSize`, `nextBlockSize`, `allocChunkLimit`, `freeListIndex` (-1 or which `context_freelists[]` bucket this context is recyclable into). [verified-by-code] [via knowledge/files/src/backend/utils/mmgr/aset.c.md]
- **`GenerationContext`** (`generation.c:61-75`) — header + `initBlockSize`, `maxBlockSize`, `nextBlockSize`, `allocChunkLimit`, `block` (current head), `freeblock` (the at-most-one recycled empty block awaiting reuse), `blocks` dlist. Block header `GenerationBlock` carries `nchunks`/`nfree`. [verified-by-code] [via knowledge/files/src/backend/utils/mmgr/generation.c.md]
- **`SlabContext`** (`slab.c:103-130`) — `chunkSize`, `fullChunkSize` (chunk + header, MAXALIGN'd + optional sentinel), `blockSize`, `chunksPerBlock`, `curBlocklistIndex`, `blocklist_shift`, `emptyblocks` (dclist), `blocklist[SLAB_BLOCKLIST_COUNT=3]`. No keeper block. `SlabBlock` carries `nfree`, `nunused` (never-yet-handed-out), `freehead` (linked free list through chunk bodies), `unused` (high-water pointer). [verified-by-code] [via knowledge/files/src/backend/utils/mmgr/slab.c.md]
- **`BumpContext`** (`bump.c:68-80`) — header + `initBlockSize`, `maxBlockSize`, `nextBlockSize`, `allocChunkLimit`, `blocks` dlist. `BumpBlock` is minimal: `dlist_node`, optional context back-pointer (checking builds only), `freeptr`, `endptr`. No per-block chunk count. [verified-by-code] [via knowledge/files/src/backend/utils/mmgr/bump.c.md]
- **`Portal`** (`utils/portal.h`) — query-execution-state object. Carries `portalContext` (AllocSet child of `TopPortalContext`), optional `holdContext` (sibling, not child — survives portal drop), `cplan` (cached-plan refcount), `resowner`, `status`, `portalPinned`, `activeSubid`, etc. [from-comment] [via knowledge/files/src/backend/utils/mmgr/portalmem.c.md]
- **`dsa_area`** (per-backend handle, `dsa.c:347-373`) + **`dsa_area_control`** (shared, `dsa.c:287-319`) + **`dsa_area_pool`** (one per size class, with its own LWLock, `dsa.c:274-281`) + **`dsa_area_span`** (one per superblock, `dsa.c:183-196`) + **`dsa_segment_map`** (backend-private per-segment, `dsa.c:332-339`). [verified-by-code] [via knowledge/files/src/backend/utils/mmgr/dsa.c.md]

## 5. Context hierarchy and lifecycle

`MemoryContextInit` (`mcxt.c:362-398`) creates `TopMemoryContext` as an AllocSet with `ALLOCSET_DEFAULT_SIZES`, points `CurrentMemoryContext` at it, then creates `ErrorContext` as an 8K/8K/8K AllocSet with `allowInCritSection=true`. The size-floor on `ErrorContext` is the reason OOM can be reported as `ERROR` rather than `PANIC`: the comment calls retained memory in `ErrorContext` "the only case where retained memory in a context is *essential*". [from-comment] (`mcxt.c:380-396`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

Globally known contexts (root downward, from `memutils.h:53-67` and `README:174-258`):

| Global | Parent | Lifetime | Notes |
|---|---|---|---|
| `TopMemoryContext` | (root) | Backend lifetime | Effectively `malloc`. Avoid as `CurrentMemoryContext`. |
| `PostmasterContext` | TopMemoryContext | Postmaster lifetime | Deleted in each backend after auth. |
| `CacheMemoryContext` | TopMemoryContext | Backend lifetime | Relcache, catcache, etc. Has shorter-lived children. |
| `MessageContext` | TopMemoryContext | One protocol message | Reset at top of each `PostgresMain` loop iteration. Holds parse/plan trees in simple query mode. |
| `TopTransactionContext` | TopMemoryContext | Top-level xact | Reset on `COMMIT`/`ROLLBACK`. **NOT cleared on subxact abort.** |
| `CurTransactionContext` | == TopTransactionContext at top level | Current xact level | Child of TopTransactionContext in subxacts; cleared on subxact abort. |
| `PortalContext` | (pointer to active portal's portalContext) | Active portal | NOT a fixed context — global pointer that follows the active portal. |
| `TopPortalContext` | TopMemoryContext | Backend lifetime | Parent of every portal's `portalContext` and every holdable cursor's `holdContext` (`portalmem.c:93, 332-362`). [from-comment] |
| `ErrorContext` | TopMemoryContext | Permanent | Pre-allocated ≥ 8KB reserve so OOM is reportable as ERROR. `allowInCritSection=true`. |

[verified-by-code] [via knowledge/idioms/memory-contexts.md, knowledge/files/src/backend/utils/mmgr/mcxt.c.md, knowledge/files/src/backend/utils/mmgr/portalmem.c.md]

### Reset vs Delete vs ResetOnly

- `MemoryContextReset(ctx)` (`mcxt.c:406`) — deletes children first (recursively), then resets the context itself. After reset, `isReset == true` and the context holds only its keeper-block memory (AllocSet/Generation/Bump) or no blocks (Slab).
- `MemoryContextResetOnly(ctx)` (`mcxt.c:425`) — resets just `ctx`, leaves children intact.
- `MemoryContextResetChildren(ctx)` (`mcxt.c:454`) — recursively resets all descendants but leaves the context itself untouched. Uses iterative `MemoryContextTraverseNext` walk (`mcxt.c:279-300`) to avoid stack growth in deep trees.
- `MemoryContextDelete(ctx)` (`mcxt.c:475-509`) — **iterative, not recursive**. Descends to the deepest leaf, then unwinds, freeing siblings as it climbs. The comment explicitly cites "stack depth limit exceeded during transaction abort" as the reason — *do not* re-introduce recursion. The per-context worker `MemoryContextDeleteOnly` (`mcxt.c:517-549`) fires the context's reset callbacks (reverse-registration order, popping each callback record before invoking it), delinks from parent **before** calling `delete_context`, clears `ident`, then dispatches to the per-type `delete_context` method. Delinking-first means an error mid-delete leaks the subtree but never leaves a dangling pointer. [from-comment] (`mcxt.c:474-509, 533-549`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

### Callbacks (`MemoryContextRegisterResetCallback`, `mcxt.c:585`)

Fire **before** the next reset or delete, in **reverse registration order**, with **child callbacks before parent callbacks** during a tree walk. The callback record is popped before invocation, so a callback that `ereport(ERROR)`s won't be retried on subsequent reset/delete. Use cases: closing files (tuplesort), releasing refcounts (cached plans), freeing malloc'd state from non-PG libraries. [from-README] (`README:139-170, 158-161`) [verified-by-code] (`mcxt.c:636-651, 533`) [via knowledge/idioms/memory-contexts.md, knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

### `MemoryContextCreate` protocol (`mcxt.c:1152-1192`)

Type-independent half of context creation. The per-type creator does the malloc, fills the type-specific fields, **then** calls `MemoryContextCreate` to wire `methods`, link into parent, set `isReset=true`, inherit `allowInCritSection` from parent. The comment notes: "Context routines generally assume that `MemoryContextCreate` can't fail, so this can contain Assert but not elog/ereport". [from-comment] (`mcxt.c:1118-1150, 1158`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

## 6. Allocator types — when to pick each

| Type | Strengths | Trade-offs / restrictions | Typical callers |
|---|---|---|---|
| **AllocSet** (default) | Power-of-2 freelists, fast common path; large chunks (> `allocChunkLimit ≤ 8 KB`) directly malloc'd and individually freeable; keeper-block on reset; process-wide 100-entry context recycle cache. | Power-of-two rounding wastes bytes; no coalescing of freed chunks across size classes. | Everything not on this list. |
| **Generation** | FIFO/queue workloads: chunks alloc'd and freed in similar groups. Per-block counters, one recycled empty block — no global freelist scan. | No good for random-pattern frees: blocks won't empty out. | Logical-decoding apply / reorder spill paths [unverified — typical lore]. |
| **Slab** | Fixed-size dense packing, O(1) "find a non-full block" via 3-bucket fullness binning, returns fully-empty blocks to malloc. | `chunkSize` fixed at create time; **no realloc**; cannot serve `palloc_aligned` (can't over-allocate); no keeper. | Reorder buffer (`ReorderBufferTXN`, `ReorderBufferChange`), `RecordCacheArray` [unverified, from per-file doc lore]. |
| **Bump** | Densest packing — zero chunk header in production; smallest per-alloc cost. | **No `pfree`, `repalloc`, `GetMemoryChunkContext`, `GetMemoryChunkSpace`** — only `MemoryContextReset`/`Delete` releases. Bump pointers must not leak to generic code: in production builds there is NO method ID prefix, so a stray `pfree(bump_chunk)` reads whatever uint64 happens to precede the chunk and dispatches into garbage — effective memory corruption. | Sort spill buffers [unverified]. Added in PG 17. |

[from-README] (`README:471-499`) [via knowledge/files/src/backend/utils/mmgr/aset.c.md, generation.c.md, slab.c.md, bump.c.md]

### Block sizing — the keeper-block trick

AllocSet, Generation, and Bump share the same shape: `initBlockSize`, `maxBlockSize`, `nextBlockSize`. `nextBlockSize` starts at `initBlockSize` and doubles per new block up to `maxBlockSize`. The first block ("keeper") shares its malloc allocation with the context header — *one* malloc for both — and is **never returned to malloc on reset**. This is the key to per-tuple contexts not thrashing the system allocator. [from-README] (`README:444-468`) [verified-by-code] (`aset.c:432-454, 540-543, 568-588, 610`) [via knowledge/files/src/backend/utils/mmgr/README.md, aset.c.md]

Sizing presets (`memutils.h:157-179`):
- `ALLOCSET_DEFAULT_SIZES` — `0 / 8 KB / 8 MB` (minContextSize / initBlockSize / maxBlockSize). For contexts that may hold a lot.
- `ALLOCSET_SMALL_SIZES` — `0 / 1 KB / 8 KB`. For small contexts (one query plan).
- `ALLOCSET_START_SMALL_SIZES` — small init, default max.
- `SLAB_DEFAULT_BLOCK_SIZE = 8 KiB`, `SLAB_LARGE_BLOCK_SIZE = 8 MiB`. [verified-by-code] (`memutils.h:189-190`)

### AllocSet context recycling (`aset.c:219-241, 648-691`)

Contexts whose `(minContextSize, initBlockSize)` matches `ALLOCSET_DEFAULT_*` or `ALLOCSET_SMALL_*` are pushed onto a process-wide `context_freelists[2]` static cache instead of being freed on `AllocSetDelete`, up to `MAX_FREE_CONTEXTS = 100` per bucket. On overflow the *entire* bucket is dropped at once (heuristic: queries that allocate many contexts free them in reverse order, so the oldest are likely the longest-lived). `maxBlockSize` doesn't have to match — it's rewritten when the context is reused. No concurrency protection because PG is process-per-backend. [from-comment] (`aset.c:219-241, 648-691, 415-416`) [via knowledge/files/src/backend/utils/mmgr/aset.c.md]

## 7. palloc / pfree / repalloc semantics

### Allocation (`palloc.h:107-165`, `mcxt.c:1389-1467`)

- `palloc(size)` — allocate in `CurrentMemoryContext`. **Never returns NULL**; OOM is `ereport(ERROR)` via the per-type alloc's call to `MemoryContextAllocationFailure`. Asserted at `mcxt.c:1413`.
- `palloc0(size)` — `palloc` + zero-fill.
- `palloc_extended(size, flags)` — flags: `MCXT_ALLOC_HUGE` (allow up to `MaxAllocHugeSize`), `MCXT_ALLOC_NO_OOM` (return NULL on OOM), `MCXT_ALLOC_ZERO` (zero-fill).
- `palloc_aligned(size, alignto, flags)` — see §9.
- `MemoryContextAlloc(ctx, size)` and variants — allocate in a specified context without touching `CurrentMemoryContext`.
- Type-safe macros: `palloc_object(type)`, `palloc_array(type, count)`, `palloc0_array(type, count)`, `repalloc_array(type, ptr, count)` (`palloc.h:107-123`).
- String helpers: `pstrdup(s)`, `pnstrdup(s, n)`, `psprintf(fmt, …)`, `MemoryContextStrdup(ctx, s)`, `pchomp(s)` (`palloc.h:154-165`, `mcxt.c:1897-1938`).

The implementations duplicate the body of `MemoryContextAlloc*` rather than calling them — the comment at `mcxt.c:1392, 1422, 1444` says "to avoid increased overhead". The tail call into `context->methods->alloc(context, size, flags)` is structured for compiler sibling-call optimization, and OOM is handled inside the per-type alloc rather than wrapped here so the success path executes zero extra instructions after the tail call. [from-comment] (`mcxt.c:1401-1413`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

### Free / realloc (`mcxt.c:1619-1662`)

Both `pfree(p)` and `repalloc(p, size)` go through the `MCXT_METHOD(p, free_p)` / `MCXT_METHOD(p, realloc)` macro, which reads the chunk's 4-bit method ID via `GetMemoryChunkMethodID()` and dispatches through `mcxt_methods[]`. They do NOT consult `CurrentMemoryContext` — the chunk knows its own allocator. `repalloc` re-fetches the context only when `USE_ASSERT_CHECKING || USE_VALGRIND` is defined; in production it just dispatches. [verified-by-code] (`mcxt.c:1635-1659`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

This is what makes `pfree(p)` / `repalloc(p, size)` independent of which context is currently active — and conversely it's why bump chunks (no header in production) are dangerous if their pointers escape.

### Behavioral differences from malloc (`README:55-75`)

1. **`palloc` and `repalloc` `ereport(ERROR)` on OOM. They never return NULL.** Do not test for NULL.
2. **`palloc(0)` is valid.** Returns a real chunk; can be `repalloc`'d or `pfree`'d.
3. **`pfree(NULL)` is NOT valid.** Intentional, partly historical, partly performance.
4. **`repalloc(NULL, ...)` is NOT valid.** Necessary because `repalloc` derives the target context from the existing chunk header.
5. **`repalloc` operates in the chunk's original context** regardless of `CurrentMemoryContext` (`README:99-105`).
6. **Allocation size limit** is `MaxAllocSize = 1 GB - 1` (`memutils.h:40`). Use `MemoryContextAllocHuge` / `palloc_extended` with `MCXT_ALLOC_HUGE` to go past it (up to `MaxAllocHugeSize = SIZE_MAX/2`, `memutils.h:40-49`).

[from-README] [via knowledge/idioms/memory-contexts.md]

### Bump-context exceptions

`pfree`, `repalloc`, `GetMemoryChunkContext`, `GetMemoryChunkSpace` ALL `elog(ERROR)` on a bump chunk under `MEMORY_CONTEXT_CHECKING`. Under production builds: there is NO method ID prefix, so misuse is undefined. Audit any new caller of `BumpContextCreate` for chunk-pointer escape. [from-comment] (`bump.c:6-36, 645-682`) [via knowledge/files/src/backend/utils/mmgr/bump.c.md]

## 8. Per-tuple contexts and the executor

The executor creates a per-`ExprContext` private context that is reset at the **start** of each tuple cycle (not the end), so a plan node can hand back a tuple palloc'd in its per-tuple context and the caller is guaranteed it remains valid until the next call into the node. [from-README] (`README:308-368`) [via knowledge/idioms/memory-contexts.md]

If you write an SQL function, comparator, or hook that runs inside expression evaluation, allocating into `CurrentMemoryContext` is correct — that's the short-lived expression context. **Index/sort comparators are a notable exception**: btree and hash support functions still must not leak, because they're called inside long-lived contexts. [from-README] (`README:328-342`) [via knowledge/idioms/memory-contexts.md]

## 9. Aligned allocation (`palloc_aligned`)

`MemoryContextAllocAligned(ctx, size, alignto, flags)` (`mcxt.c:1485-1591`) — for `alignto <= MAXIMUM_ALIGNOF` it short-circuits to `MemoryContextAllocExtended`. Otherwise it over-allocates `size + alignto + sizeof(MemoryChunk) - MAXIMUM_ALIGNOF` in the underlying context, aligns the visible pointer up via `TYPEALIGN`, and writes a redirection `MemoryChunk` in the bytes immediately before it. The redirection chunk:

- has method ID `MCTX_ALIGNED_REDIRECT_ID`,
- stores `alignto` (asserted < 128 MB, power of two) in the value field,
- uses the block-offset field to point back to the unaligned origin.

`pfree(p)` of an aligned pointer dispatches via `mcxt_methods[MCTX_ALIGNED_REDIRECT_ID].free_p = AlignedAllocFree`, which recovers the unaligned chunk via `MemoryChunkGetBlock` and recursively `pfree`'s the unaligned chunk (`alignedalloc.c:29-59`). `AlignedAllocRealloc` always allocates a fresh aligned chunk — never grows in place — because `GetMemoryChunkSpace` on the underlying allocator returns an upper bound (e.g. AllocSet rounds to power-of-two). `AlignedAllocGetChunkContext` returns the *underlying* allocator's context so `GetMemoryChunkContext(p)` works transparently. [verified-by-code] (`alignedalloc.c:29-189`) [via knowledge/files/src/backend/utils/mmgr/alignedalloc.c.md]

**Slab cannot serve as the underlying allocator** for `palloc_aligned` — fixed-size chunks can't over-allocate. The comment at `mcxt.c:1478-1480` warns; no runtime guard beyond the underlying alloc failing. [from-comment] [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

## 10. Inspection and debugging

- **`MemoryContextStats(TopMemoryContext)`** (`mcxt.c:866`) — dump the whole tree to stderr.
- **`MemoryContextStatsDetail(ctx, max_level, max_children, print_to_stderr)`** (`mcxt.c:881`) — controlled depth; default `max_level=100`, `max_children=100`. When dumping to log (not stderr), emits one `LOG_SERVER_ONLY` per context to avoid building an unbounded `StringInfo` that might itself OOM. [from-comment] (`mcxt.c:900-918, 995-1005`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- **`MemoryContextMemAllocated(ctx, recurse)`** (`mcxt.c:814`) — bytes consumed; O(n) when recursing.
- **`MemoryContextMemConsumed(ctx, &counters)`** (`mcxt.c:838`) — fills a `MemoryContextCounters` (`nblocks`/`freechunks`/`totalspace`/`freespace`). Walks subtree with a fresh counter each call.
- **`pg_log_backend_memory_contexts(pid)`** SQL function → `HandleLogMemoryContextInterrupt` (`mcxt.c:1326`) sets a flag, `ProcessLogMemoryContextInterrupt` (`mcxt.c:1343-1387`) at the next CHECK_FOR_INTERRUPTS dumps `TopMemoryContext` with hardwired `(100, 100)` limits to the target backend's log. Re-entrancy guarded by `LogMemoryContextInProgress` flag wrapped in `PG_TRY`/`PG_FINALLY`. [verified-by-code] [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- **`MemoryContextCheck(ctx)`** — under `MEMORY_CONTEXT_CHECKING` (`memnodes.h:106-113`); per-type `*Check` walks blocks/chunks, validates method-ID, block-link, `requested_size`, sentinel byte. Reports anomalies as `WARNING`, never `ERROR`/`FATAL`, because elog cleanup would re-enter the checker ("you'll find yourself in an infinite loop"). [from-comment] (`aset.c:1680-end`) [via knowledge/files/src/backend/utils/mmgr/aset.c.md]
- **`MemoryContextTraverseNext(start, top)`** (`mcxt.c:279-300`) — the only safe way to walk descendants without recursion. Pre-order, returns NULL when it climbs back up through `top`. Used by `MemoryContextResetChildren`, `MemoryContextMemAllocated(recurse=true)`, `MemoryContextMemConsumed`, the `>max_children` summary path in `MemoryContextStatsInternal`, and `MemoryContextCheck`. [verified-by-code] [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]

Debug-build options ([from-comment] (`memdebug.c:14-52`) [via knowledge/files/src/backend/utils/mmgr/memdebug.c.md]):

- `CLOBBER_FREED_MEMORY` — `wipe_mem` overwrites freed memory with `0x7F`. Catches use-after-free.
- `MEMORY_CONTEXT_CHECKING` — adds `requested_size` field to `MemoryChunk` headers; writes `0x7E` sentinel just past requested space when rounded-up chunk has slack; `*Check` verifies on free. Also adds an `isChunkFree[]` bool array per Slab context. **Sentinel is not written for exact-fit chunks** (where `size == GetChunkSizeFromFreeListIdx(fidx)`) — write-past-end of an exact-fit power-of-two chunk is undetected (`aset.c:1063-1066`, deliberate trade-off). [from-comment]
- `USE_VALGRIND` — every allocator file maintains a Valgrind vpool per context and vchunks per allocation. `requested_size` doubles as the NOACCESS region before the chunk header.
- `RANDOMIZE_ALLOCATED_MEMORY` — `randomize_mem` fills new chunks with a non-zero pseudorandom byte sequence (mod 251) so callers that assume zero-init crash visibly.

## 11. Common pitfalls (codebase-confirmed)

1. **Allocating into a long-lived context when you meant a short-lived one.** E.g. forgetting to switch out of `CacheMemoryContext` inside a relcache build callback ⇒ permanent leak for the backend's lifetime. The fix is a child context that you reset. Rule of thumb: keep `CurrentMemoryContext` pointing at the **shortest-lived** context that still outlives the data. [from-README] (`README:91-96`) [via knowledge/idioms/memory-contexts.md]
2. **Testing palloc for NULL.** Pointless — it cannot return NULL unless you passed `MCXT_ALLOC_NO_OOM`. [from-README] (`README:59-62`)
3. **`pfree(NULL)`** — segfaults; intentional. [from-README] (`README:69-75`)
4. **`repalloc(NULL, ...)`** — invalid; `repalloc` needs the existing chunk's header to find its context. [from-README]
5. **`pfree` across contexts is fine** — but `pfree` of a chunk whose owning context was already deleted is use-after-free. After `MemoryContextDelete`, you must drop every pointer into that subtree.
6. **Returning palloc'd data without copying.** If a function returns a pointer that lives in the callee's per-tuple context, the next tuple cycle will stomp it. Either `palloc` into the caller's context (via `MemoryContextSwitchTo`) or copy. [from-README]
7. **Variable used in `PG_TRY` body and `PG_CATCH` must be `volatile`** — including a saved `oldcxt` if you rely on it inside catch. The `MemoryContextSwitchTo` idiom typically does NOT need an explicit restore on the error path: `AbortTransaction` resets `CurrentMemoryContext` to `TopMemoryContext` automatically.
8. **Non-constant context name** — `AllocSetContextCreate` enforces a string literal via `StaticAssertExpr`. Use `MemoryContextSetIdentifier` for the dynamic part. [verified-by-code] (`memutils.h:124-127`)
9. **`palloc` in a critical section** — `AssertNotInCriticalSection` fires unless the target context has `allowInCritSection = true`. Only `ErrorContext` is opted in by default. Use `MemoryContextAllowInCriticalSection(ctx, true)` to opt a context in (rarely needed; usually a sign the design should switch to alloca / stack / pre-allocated buffer). [verified-by-code] (`memnodes.h:124`, `memutils.h:93-94`, `mcxt.c:198-199`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
10. **Bump-context chunk pointers escaping to generic code** — production builds have no method ID prefix; a stray `pfree(bump_chunk)` is memory corruption. Confine bump pointers to the same scope that owns the BumpContext. [from-comment] (`bump.c:6-36`) [via knowledge/files/src/backend/utils/mmgr/bump.c.md]
11. **Slab `repalloc`** — `SlabRealloc` is an `elog(ERROR)` stub. Don't `repalloc` slab chunks. [verified-by-code] (`slab.c`, `memutils_internal.h:59`) [via knowledge/files/src/backend/utils/mmgr/slab.c.md]
12. **Slab + `palloc_aligned`** — `MemoryContextAllocAligned` over-allocates; Slab refuses non-`fullChunkSize` requests. Will fail at the underlying alloc. [from-comment] (`mcxt.c:1478-1480`)
13. **`MemoryContextDelete` of a context that's `CurrentMemoryContext`** — leaves `CurrentMemoryContext` dangling. Always switch out first.
14. **Reparenting between lifetime trees** — `MemoryContextSetParent` asserts no self-loop but does NOT check multi-level loops; a multi-level loop would silently corrupt the tree. [from-comment] (`mcxt.c:684-686, 692`) [unverified — open question in `mcxt.c.md`]
15. **`palloc(0)` is fine** but easy to confuse with NULL. Returns a real (small) chunk that can be `repalloc`'d or `pfree`'d. [from-README]

## 12. The DSA side — shared memory allocation

`dsa.c` and `freepage.c` are the *other* allocator family — for **cross-backend** allocation in DSM-backed shared heaps. They do NOT plug into the `MemoryContext` vtable; you don't `palloc` into a DSA area. The API is `dsa_create` / `dsa_attach` / `dsa_allocate(area, size)` / `dsa_free(area, dp)` / `dsa_get_address(area, dp)`. [verified-by-code] (`dsa.h`) [via knowledge/files/src/backend/utils/mmgr/dsa.c.md]

Key invariants relevant to the rest of mmgr:

- **`dsa_pointer` is an opaque uint64 (or uint32 with `USE_SMALL_DSA_POINTER`)** encoding segment-index + offset; the same `dsa_pointer` resolves to different local addresses in different backends. Pointers cannot be cached across backends as local pointers; they MUST be re-resolved with `dsa_get_address` in each backend that uses them. [verified-by-code] (`dsa.h:52-69`) [via knowledge/files/src/backend/utils/mmgr/dsa.c.md]
- **Two-level locking**: area-wide `lock` for segment creation + page-manager calls, per-pool `LWLock` for small-object pool operations. Locking order is area-lock then sclass-lock; small-object alloc/free only takes the per-pool lock unless a fresh superblock is needed. [verified-by-code] (`dsa.c:728-771, 877-947`) [via knowledge/files/src/backend/utils/mmgr/dsa.c.md]
- **`FreePageManager`** is the per-segment page-level allocator; bookkeeping (size-binned freelists + in-place btree for coalescing) lives inside the managed pages using relative pointers, so the same FPM state is valid across backend mappings of the same DSM segment. Used only by `dsa.c` in-tree. [from-comment] (`freepage.c:6-43`) [via knowledge/files/src/backend/utils/mmgr/freepage.c.md]
- **`dsa_get_address` is not free of side effects** — it may map newly-created segments and unmap freed ones via `check_for_freed_segments`. Must be called in backend-local code with a valid resource owner if the area was attached without `dsa_pin_mapping`. [verified-by-code] (`dsa.c:407, 853, 956+`) [via knowledge/files/src/backend/utils/mmgr/dsa.c.md]

Major consumers: parallel-query shared state (`nodes/execParallel.c`), shared hash tables (`dshash.c`), cumulative-stats shared regions. [unverified — per-file doc references]

## 13. Portal-context lifecycle (`portalmem.c`)

The portal layer is a specialized client of the memory-context API: every portal owns a private AllocSet child of `TopPortalContext`, and holdable cursors get a *sibling* `holdContext` so the materialized tuplestore can outlive the portal during HOLD.

Key invariants ([from-comment] [via knowledge/files/src/backend/utils/mmgr/portalmem.c.md]):

- **Status transitions go through marker functions** (`MarkPortalActive`, `MarkPortalDone`, `MarkPortalFailed`) — never direct assignment. `MarkPortalActive` records the current subtransaction in `activeSubid`, used by `AtSubAbort_Portals` to decide which portals to kill.
- **`PortalDrop` is single-pass and idempotent under abort retry.** Hash-table delete happens early (`portalmem.c:516`) so a failed cleanup step doesn't loop. "Better to leak a little memory than to get into an infinite error-recovery loop."
- **Cached-plan refcount handoff is the most subtle ownership contract**: caller did `GetCachedPlan` (refcount++), passes the `CachedPlan*` to `PortalDefineQuery`, ownership transfers, refcount released by `PortalReleaseCachedPlan` inside `PortalDrop`. `PortalDefineQuery` must NOT `ereport` between the refcount handoff and storing `cplan`.
- **Pinned portals** are protected from `PortalDrop` but NOT from transaction-abort cleanup — `AtAbort_Portals` will unpin and kill them.
- **`PortalContext` (the global) ≠ `TopPortalContext`** — `PortalContext` is a pointer to the *currently active* portal's `portalContext`. [verified-by-code] (`portalmem.c` cross-reference to `mcxt.c`)

Two-phase abort: `AtAbort_Portals` marks portals failed and runs cleanup hooks (which can `ereport`); `AtCleanup_Portals` runs after the resource owner is torn down and actually drops the portals (no `ereport` possible by that point — contexts are deleted in known-safe order). [from-comment] (`portalmem.c:782+, 860+`) [via knowledge/files/src/backend/utils/mmgr/portalmem.c.md]

## 14. Cross-references

### Within mmgr (per-file docs)

- `knowledge/files/src/backend/utils/mmgr/README.md` — section map of the canonical design doc, load-bearing facts about chunk headers + dispatch.
- `knowledge/files/src/backend/utils/mmgr/mcxt.c.md` — type-independent layer, globals, vtable, `palloc`/`pfree`/`repalloc`, stats, signal handler, OOM policy.
- `knowledge/files/src/backend/utils/mmgr/aset.c.md` — default allocator: power-of-two freelists, keeper block, context recycle cache.
- `knowledge/files/src/backend/utils/mmgr/generation.c.md` — FIFO/queue allocator: per-block counters, single recycled empty block.
- `knowledge/files/src/backend/utils/mmgr/slab.c.md` — fixed-size: 3-bucket fullness binning, empty-block cache, no realloc, no aligned.
- `knowledge/files/src/backend/utils/mmgr/bump.c.md` — densest packing: no chunk header, reset/delete-only release, escape hazard.
- `knowledge/files/src/backend/utils/mmgr/alignedalloc.c.md` — redirection method ID for `palloc_aligned`.
- `knowledge/files/src/backend/utils/mmgr/memdebug.c.md` — `wipe_mem`/`set_sentinel`/`randomize_mem`/Valgrind macros.
- `knowledge/files/src/backend/utils/mmgr/portalmem.c.md` — portal lifecycle and per-portal contexts.
- `knowledge/files/src/backend/utils/mmgr/dsa.c.md` — DSA shared-memory allocator.
- `knowledge/files/src/backend/utils/mmgr/freepage.c.md` — per-segment page allocator used by DSA.

### Header docs

- `knowledge/files/src/include/nodes/memnodes.h.md` — `MemoryContextData`, `MemoryContextMethods`, `MemoryContextCounters`.
- `source/src/include/utils/palloc.h` — the public allocation API (no per-file doc; covered by idiom).
- `source/src/include/utils/memutils.h` — context creation + globals + size presets (no per-file doc).
- `source/src/include/utils/memutils_internal.h` — `MemoryContextMethodID` enum + per-impl prototypes.
- `source/src/include/utils/memutils_memorychunk.h` — `MemoryChunk` layout + accessors.
- `source/src/include/utils/memdebug.h` — `wipe_mem`/`set_sentinel`/Valgrind macro real definitions.
- `source/src/include/utils/freepage.h` — `FreePageManager` public types, `FPM_PAGE_SIZE`.
- `source/src/include/utils/dsa.h` — DSA public API + flags + size policy constants.
- `source/src/include/utils/portal.h` — `Portal` struct definition.

### Idiom-level companion

- `knowledge/idioms/memory-contexts.md` — the digest with decision tree, the `MemoryContextSwitchTo` pattern, the common-mistakes list. Cross-link from this synthesis: any "how do I write code that uses contexts correctly?" question routes there first; this synthesis is the "what is the subsystem and how is it built?" view.

### Cross-subsystem touch-points

- `source/src/backend/access/transam/xact.c` — calls `AtEOXact_*` / `AtAbort_*` which reset `TopTransactionContext` / `CurTransactionContext`, and calls `PreCommit_Portals` / `AtAbort_Portals` / `AtCleanup_Portals` / `AtSubCommit_Portals` / `AtSubAbort_Portals` / `AtSubCleanup_Portals`. [unverified — see `knowledge/files/src/backend/utils/mmgr/mcxt.c.md` and `portalmem.c.md` open-questions; not traced in this synthesis pass]
- `source/src/backend/tcop/postgres.c` — resets `MessageContext` at top of `PostgresMain` loop. [unverified — open question in `mcxt.c.md`]
- `source/src/backend/tcop/pquery.c` + `source/src/backend/commands/portalcmds.c` — execute portals + implement `DECLARE CURSOR` / `FETCH` / `CLOSE`; portal cleanup hook lives here.
- `source/src/backend/utils/cache/plancache.c` — cached-plan refcount that portals participate in.
- `source/src/backend/storage/ipc/dsm.c` — DSM segment infrastructure that DSA segments are backed by.
- `source/src/backend/storage/lmgr/lwlock.c` — DSA areas allocate LWLocks from a caller-supplied tranche; tranche IDs are scarce (`dsa.c:415-418`).
- `source/src/backend/executor/execExpr*.c` + `executor/execMain.c` — the per-`ExprContext` per-tuple reset cycle that the `README:308-368` section formalizes.

## 15. Open questions / unverified

Aggregated from per-file open-questions:

- **Reparenting semantics across lifetime trees** (`MemoryContextSetParent`): no multi-level-loop check; behavior of moving a context from a transient tree into `CacheMemoryContext` not fully specified. [from-comment] (`mcxt.c:684-686, 692`) [via knowledge/files/src/backend/utils/mmgr/mcxt.c.md]
- **`repalloc0` shrink semantics**: documented as grow-then-zero, errors if `oldsize > size`; callers depending on the error rather than assertion behavior are [unverified] (`mcxt.c:1707-1719`).
- **`MemoryContextMemConsumed` cost**: O(n) per inquiry over the subtree, no caching; whether any hot path calls it in a loop is [unverified].
- **`context_freelists[]` and `EXEC_BACKEND`**: process-wide static, no concurrency protection — fine in fork-per-backend, but EXEC_BACKEND processes have independent caches. [inferred] (`aset.c.md`)
- **`AllocSet` external-chunk shrink Valgrind vchunk match**: whether `AllocSetRealloc` updates the block-header vchunk to match a shrunk external chunk is [unverified] (`aset.c.md`).
- **`GenerationFree` of the keeper** as `freeblock`: defensive NULLify exists, but the comment "`GenerationBlockFree ... never expects to free the freeblock`" suggests a path could exist; semantics under reset/realloc interleavings are [inferred] (`generation.c:303-307`).
- **`dsa_free` recursive-into-large-path locking**: area-lock vs per-sclass-lock release/reacquire pairs not exhaustively audited; comment doesn't state the lock-order argument explicitly (`dsa.c:892`) [unverified].
- **`dsa_set_size_limit` interaction with no-contiguous-run-large-enough**: does `make_new_segment` fail cleanly within the limit? [unverified] (`dsa.c.md`).
- **Portal `PortalCleanup` ↔ `PortalDrop` sequencing on mid-fetch error**: `portalmem.c:498-505` hints `cleanup` may have already run via `MarkPortalFailed`; not fully traced (`portalmem.c.md`).

---

**Document maintenance.** This synthesis follows the same shape as `access-heap.md`, `access-transam.md`, `storage-lmgr.md`, `storage-ipc.md`. Per-file docs are the citation-bearing primary corpus; when source changes, update the per-file doc first, then re-verify the cross-cites here. Last full verification against the commit at the top of this file: 2026-06-01.
