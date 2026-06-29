# `src/backend/utils/mmgr/mcxt.c`

- **File:** `source/src/backend/utils/mmgr/mcxt.c` (1946 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Type-independent layer of the memory-context API. Owns the global
context pointers (`TopMemoryContext`, `CurrentMemoryContext`, …), the
`mcxt_methods[]` vtable indexed by `MemoryContextMethodID`, the public
`palloc`/`pfree`/`repalloc`/`MemoryContextAlloc*` family, the tree
operations (`Reset`, `Delete`, `SetParent`, traversal), reset-callback
plumbing, `MemoryContextStats` dump, Valgrind vchunk bookkeeping for
caller-visible allocations, and the OOM-`ereport(ERROR)` policy
(`mcxt.c:1200-1214`).

## Top-of-file comment (verbatim, key paragraphs)

```
This module handles context management operations that are independent
of the particular kind of context being operated on.  It calls
context-type-specific operations via the function pointers in a
context's MemoryContextMethods struct.

A note about Valgrind support: when USE_VALGRIND is defined, we provide
support for memory leak tracking at the allocation-unit level.  ...
We use a separate vpool for each memory context.  The context-type-specific
code is responsible for creating and deleting the vpools, and also for
creating vchunks to cover its management data structures such as block
headers.
```
(`mcxt.c:1-27` [from-comment])

## Public surface (selected — full set in `memutils.h`/`palloc.h`)

- Globals: `CurrentMemoryContext`, `TopMemoryContext`, `ErrorContext`,
  `PostmasterContext`, `CacheMemoryContext`, `MessageContext`,
  `TopTransactionContext`, `CurTransactionContext`, `PortalContext`
  (`mcxt.c:161-176` [verified-by-code]).
- Lifecycle: `MemoryContextInit` (`:362`), `MemoryContextReset` (`:406`),
  `MemoryContextResetOnly` (`:425`), `MemoryContextResetChildren` (`:454`),
  `MemoryContextDelete` (`:475`), `MemoryContextDeleteChildren` (`:558`),
  `MemoryContextCreate` (`:1152`, called only by per-type creators).
- Tree: `MemoryContextSetParent` (`:689`), `MemoryContextGetParent`
  (`:783`), `MemoryContextIsEmpty` (`:795`).
- Callbacks: `MemoryContextRegisterResetCallback` (`:585`),
  `MemoryContextUnregisterResetCallback` (`:610`).
- Allocation: `MemoryContextAlloc{,Zero,Extended,Aligned,Huge}` (`:1234,
  1269, 1292, 1485, 1854`), `palloc{,0,_extended,_aligned}` (`:1390,
  1420, 1442, 1609`), `pfree` (`:1619`), `repalloc{,_extended,0,_huge}`
  (`:1635, 1670, 1707, 1886`), and `*_mul` arithmetic-safe variants
  (`:1775+`).
- Inspection: `MemoryContextStats` (`:866`), `MemoryContextStatsDetail`
  (`:881`), `MemoryContextMemAllocated` (`:814`),
  `MemoryContextMemConsumed` (`:838`).
- Method dispatch: `GetMemoryChunkContext` (`:759`), `GetMemoryChunkSpace`
  (`:773`).
- Identifiers + crit-section gate: `MemoryContextSetIdentifier` (`:664`),
  `MemoryContextAllowInCriticalSection` (`:746`).
- Signal-driven dump: `HandleLogMemoryContextInterrupt` (`:1326`),
  `ProcessLogMemoryContextInterrupt` (`:1343`).
- String helpers: `MemoryContextStrdup` (`:1897`), `pstrdup` (`:1910`),
  `pnstrdup` (`:1921`), `pchomp` (`:1938`).

## Key types / data

- `mcxt_methods[16]` — vtable indexed by `MemoryContextMethodID`. Real
  entries for `MCTX_ASET_ID`, `MCTX_GENERATION_ID`, `MCTX_SLAB_ID`,
  `MCTX_ALIGNED_REDIRECT_ID`, `MCTX_BUMP_ID`. All other IDs (including
  the reserved-for-glibc and wiped-memory slots `0`, `1`, `2`, `15`)
  point at `BogusFree`/`BogusRealloc`/`BogusGetChunkContext`/
  `BogusGetChunkSpace`, each of which `elog(ERROR)`s with the bad
  pointer + raw 64-bit header dump (`mcxt.c:64-153, 308-337`
  [verified-by-code]).
- `MCXT_METHOD(pointer, method)` macro — reads the chunk's 4-bit method
  ID via `GetMemoryChunkMethodID()` and indexes `mcxt_methods[]`
  (`mcxt.c:205-234` [verified-by-code]).
- `LogMemoryContextInProgress` static flag — guards
  `ProcessLogMemoryContextInterrupt` against re-entry, so rapidly-
  repeated `pg_log_backend_memory_contexts(pid)` requests can't recurse
  into infinite logging (`mcxt.c:179, 1353-1386` [verified-by-code]).

## Key invariants

- **Method-ID dispatch on every pfree/repalloc**: the uint64 immediately
  before any palloc'd pointer must carry the owning allocator's
  `MemoryContextMethodID` in its low 4 bits. Bogus pointers land in
  `BogusFree` which ereports with the header value so debugging is
  possible (`mcxt.c:213-234, 308-337` [verified-by-code]).
- **palloc never returns NULL.** OOM is handled inside the per-type
  `alloc` callback by calling `MemoryContextAllocationFailure` which
  `ereport(ERROR)`s unless `MCXT_ALLOC_NO_OOM` is set
  (`mcxt.c:1200-1214` [verified-by-code]). The non-`NULL` post-condition
  is asserted in `palloc`/`palloc0` (`mcxt.c:1413, 1433`).
- **No palloc in a critical section** unless the context has
  `allowInCritSection = true`. Enforced via `AssertNotInCriticalSection`
  on every `MemoryContextAlloc*` and `palloc*` path
  (`mcxt.c:198-199, 1240, 1274, 1297, 1397, 1427, 1449`
  [verified-by-code]). `ErrorContext` is opted in by
  `MemoryContextInit` (`mcxt.c:397`) so OOM-reporting allocations work
  during PANIC.
- **`MemoryContextDelete` is iterative, not recursive.** It descends to
  the deepest leaf, then unwinds, freeing siblings as it climbs. The
  comment explicitly cites the risk of "stack depth limit exceeded
  during transaction abort" as the reason — *do not* re-introduce
  recursion (`mcxt.c:474-509` [from-comment]).
- **Reset/delete callbacks fire in reverse-registration order**, are
  popped *before* invocation so a callback that errors won't be retried
  on subsequent reset/delete, and child callbacks fire before parent
  callbacks (cleanup walks bottom-up) (`mcxt.c:636-651, 533`
  [verified-by-code]; design statement at `README:158-161`
  [from-readme]).
- **`MemoryContextDeleteOnly` delinks from the parent *before* calling
  `delete_context`** so an error mid-delete leaves a leaked but
  consistent tree, not a busted-pointer crash (`mcxt.c:535-549`
  [verified-by-code], `from-comment`).
- **Children inherit `allowInCritSection` at create time** but not
  retroactively when `MemoryContextAllowInCriticalSection` is later
  toggled on the parent (`mcxt.c:1184-1191` [verified-by-code]).
- **`MemoryContextTraverseNext` is the only safe way to walk descendants
  without recursion** — pre-order, returns NULL when it climbs back up
  through `top` (`mcxt.c:279-300` [verified-by-code]). Used by
  `MemoryContextResetChildren`, `MemoryContextMemAllocated(recurse=true)`,
  `MemoryContextMemConsumed`, the >max_children summary path in
  `MemoryContextStatsInternal`, and `MemoryContextCheck`.

## Functions of note

1. **`MemoryContextInit` (`:362-398`)** — creates `TopMemoryContext` as
   an AllocSet with `ALLOCSET_DEFAULT_SIZES`, points `CurrentMemoryContext`
   at it (caller is expected to switch immediately), then creates
   `ErrorContext` as an 8K/8K/8K AllocSet with `allowInCritSection=true`.
   The size-floor on `ErrorContext` is the reason OOM can be reported
   as ERROR rather than PANIC: the comment calls it "the only case where
   retained memory in a context is *essential*" (`mcxt.c:380-396`
   [from-comment]). In non-EXEC_BACKEND builds, runs once in postmaster;
   in EXEC_BACKEND, every backend repeats it.

2. **`MemoryContextDelete` (`:475-509`)** — see invariant above.
   Iterative leaf-first descent; `MemoryContextDeleteOnly` does the
   actual per-context work: fires callbacks, delinks from parent
   (so partial failure leaks but doesn't dangle), clears `ident` (in
   case it pointed into the doomed context), then dispatches to the
   per-type `delete_context` method (`mcxt.c:517-550`
   [verified-by-code]).

3. **`MemoryContextAllocAligned` (`:1485-1591`)** — implements
   `palloc_aligned`. For `alignto <= MAXIMUM_ALIGNOF` it short-circuits
   to `MemoryContextAllocExtended`. Otherwise it overallocates
   (`size + alignto + sizeof(MemoryChunk) - MAXIMUM_ALIGNOF`), aligns the
   visible pointer up, and writes a "redirection" `MemoryChunk` in the
   bytes immediately before it. The redirection chunk has method ID
   `MCTX_ALIGNED_REDIRECT_ID`, stores `alignto` in the value field, and
   uses the block-offset field to point back to the unaligned origin so
   that `AlignedAllocFree`/`AlignedAllocRealloc` (in `alignedalloc.c`)
   can recover the real chunk on pfree/repalloc (`mcxt.c:1484-1591`
   [verified-by-code], with cross-impl in `alignedalloc.c:25-168`).
   This is why Slab contexts can't serve aligned allocations:
   over-allocation is impossible with fixed-size chunks
   (`mcxt.c:1478-1480` [from-comment]).

4. **`MemoryContextCreate` (`:1152-1192`)** — the *type-independent*
   half of context creation. Per-type creator does the malloc and fills
   the type-specific fields, *then* calls this to wire `methods`, link
   into parent, init `isReset=true`, etc. The comment lays out the
   4-step protocol and notes "Context routines generally assume that
   `MemoryContextCreate` can't fail, so this can contain Assert but not
   elog/ereport" (`mcxt.c:1118-1150, 1158` [from-comment]). The flow
   inherits `allowInCritSection` from parent (`:1185`).

5. **`palloc` / `palloc0` / `palloc_extended` (`:1389-1467`)** — these
   *duplicate* `MemoryContextAlloc*` rather than calling them, "to avoid
   increased overhead" (`mcxt.c:1392, 1422, 1444` [from-comment]). The
   tail call into `context->methods->alloc(context, size, flags)` is
   structured to let the compiler sibling-call-optimize, and OOM is
   *deliberately* handled inside the per-type alloc rather than wrapped
   here, so that the success path executes zero extra instructions after
   the tail call (`mcxt.c:1401-1413` [from-comment]).

6. **`pfree` / `repalloc` (`:1619-1662`)** — both go through `MCXT_METHOD`
   to dispatch on the chunk's encoded method-ID, *not* on
   `CurrentMemoryContext`. `repalloc` re-fetches the context only when
   `USE_ASSERT_CHECKING || USE_VALGRIND` is defined, since the per-type
   `realloc` already knows how to locate it from the chunk header
   (`mcxt.c:1635-1659` [verified-by-code]). This is what makes
   `pfree(p)`/`repalloc(p, size)` independent of the current context.

7. **`MemoryContextStats` / `MemoryContextStatsDetail` /
   `MemoryContextStatsInternal` (`:866-1015`)** — recursive dump with
   per-level depth limit (`max_level`, default 100) and per-parent child
   limit (`max_children`, default 100). When the dump is going to log
   (not stderr) it emits one `LOG_SERVER_ONLY` message per context to
   avoid building an unbounded `StringInfo` that might itself OOM
   (`mcxt.c:900-918, 995-1005` [from-comment]). Iterative summary of
   "more than max_children" uses `MemoryContextTraverseNext` to avoid
   stack growth (`:973-979`).

8. **`ProcessLogMemoryContextInterrupt` (`:1343-1387`)** — handles the
   `pg_log_backend_memory_contexts(pid)` signal. Re-entrancy guarded by
   the `LogMemoryContextInProgress` flag, wrapped in `PG_TRY`/
   `PG_FINALLY` so the flag is restored even on error. Issues a
   `LOG_SERVER_ONLY` "logging memory contexts of PID …" header line and
   then dumps `TopMemoryContext` with hardwired (100, 100) limits.

## Cross-references

- `aset.c` / `generation.c` / `slab.c` / `bump.c` / `alignedalloc.c` —
  the five per-type implementations dispatched through `mcxt_methods[]`.
- `source/src/include/utils/memutils_internal.h` — declares the
  per-impl callbacks and the `MemoryContextMethodID` enum.
- `source/src/include/utils/memutils_memorychunk.h` — the chunk-header
  layout that `GetMemoryChunkMethodID` reads.
- `source/src/include/nodes/memnodes.h` — `MemoryContextData`,
  `MemoryContextMethods`, `MemoryContextCounters`.
- `source/src/backend/access/transam/xact.c` — calls
  `AtEOXact_*`/`AtAbort_*` which reset `TopTransactionContext` /
  `CurTransactionContext` [unverified — not chased here].
- `source/src/backend/tcop/postgres.c` — resets `MessageContext` at top
  of `PostgresMain` loop [unverified — not chased here].
- `knowledge/idioms/memory-contexts.md` — the idiom-level digest.

## Open questions

- The exact ordering rules when `MemoryContextSetParent` moves a context
  *between* lifetime trees (e.g. transient → `CacheMemoryContext`).
  The function asserts no self-loop but does not check multi-level
  loops (`mcxt.c:684-686, 692` [from-comment]). Multi-level reparenting
  loops would silently corrupt the tree.
- `repalloc0(p, oldsize, size)` errors on `oldsize > size` but the
  comment says "Adjust the size of a previously allocated chunk and
  zero out the added space" — meaning it's strictly a grow-then-zero
  operation; not safe for shrink (`mcxt.c:1707-1719` [verified-by-code]).
  Whether any callers depend on the ERROR vs assertion behavior is
  [unverified].
- `MemoryContextMemConsumed` walks the subtree with a fresh
  zero-initialized counter struct each call; for very large subtrees
  this is O(n) per inquiry. Whether any production code path calls it
  in hot loops is [unverified].

## Confidence tag tally

- `[verified-by-code]` × ~20
- `[from-comment]` × ~10
- `[from-readme]` × 1
- `[unverified]` × 3

## Synthesized by
<!-- backlinks:auto -->
- [idioms/memory-contexts.md](../../../../../idioms/memory-contexts.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
- [idioms/memory-context-api-and-dispatch.md](../../../../../idioms/memory-context-api-and-dispatch.md)

