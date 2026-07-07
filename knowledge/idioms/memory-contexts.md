# Memory contexts in PostgreSQL backend code

PG does almost no raw `malloc`/`free`. Allocations go through `palloc()` into a
hierarchical `MemoryContext`; whole subtrees are freed in one shot when their
context is reset or deleted, typically at transaction/query/tuple boundaries.

Anchors:
- `source/src/backend/utils/mmgr/README` — canonical design document
- `source/src/include/utils/palloc.h` — the allocation API
- `source/src/include/utils/memutils.h` — context creation + globals
- `source/src/include/nodes/memnodes.h` — `MemoryContextData` struct
- `source/src/backend/utils/mmgr/mcxt.c` — type-independent management
- `source/src/backend/utils/mmgr/{aset,generation,slab,bump}.c` — implementations
- Wiki Developer FAQ — memory section [from-wiki]
- SPI memory chapter: <https://www.postgresql.org/docs/current/spi-memory.html> [from-docs]

## The model

A `MemoryContext` is a pointer to a `MemoryContextData` node (memnodes.h:117).
Each context has a parent, a sibling list of children, a `methods` vtable
identifying its type (AllocSet / Generation / Slab / Bump), and a list of
reset callbacks [verified-by-code] (`memnodes.h:117-134`).

`CurrentMemoryContext` is a global pointing at the context where bare `palloc`
allocates. Switch it with the inline `MemoryContextSwitchTo(new)`, which
returns the previous context for restoration [verified-by-code]
(`palloc.h:137-145`).

The basic operations (`README:14-28`) [from-readme]:
- Create a context (as a child of some existing context).
- Allocate a chunk inside a context (palloc).
- Reset a context — free all chunks, keep the context object.
- Delete a context — free everything including the context and all children.
- Inquire total memory used.

Reset and delete are recursive: deleting a parent deletes all descendants;
resetting a parent by default deletes children (use `MemoryContextResetOnly`
+ `MemoryContextResetChildren` if you want them kept as empty containers)
[from-readme] (`README:119-124`).

## The palloc API

From `palloc.h` [verified-by-code]:

- `palloc(size)` — allocate in `CurrentMemoryContext`.
- `palloc0(size)` — `palloc` + zero-fill.
- `palloc_extended(size, flags)` — with `MCXT_ALLOC_HUGE`,
  `MCXT_ALLOC_NO_OOM`, `MCXT_ALLOC_ZERO`.
- `palloc_aligned(size, alignto, flags)` — alignment-controlled.
- `repalloc(p, size)` — grow/shrink an existing chunk, **in its original
  context regardless of `CurrentMemoryContext`** [from-readme] (`README:99-105`).
- `repalloc0(p, oldsize, size)` — repalloc with zero-fill of new tail.
- `pfree(p)` — free an individual chunk. Also routes to original context.
- `MemoryContextAlloc(ctx, size)` and variants — allocate in a specified
  context without switching `CurrentMemoryContext`.
- `MemoryContextAllocHuge(ctx, size)` / `repalloc_huge(p, size)` —
  allow up to `MaxAllocHugeSize` (`SIZE_MAX/2`) [verified-by-code]
  (`memutils.h:40-49`).

Type-safe macros: `palloc_object(type)`, `palloc_array(type, count)`,
`palloc0_array`, `repalloc_array` [verified-by-code] (`palloc.h:107-123`).

String helpers: `pstrdup(s)`, `pnstrdup(s, n)`, `psprintf(fmt, ...)`,
`MemoryContextStrdup(ctx, s)`, `pchomp(s)` [verified-by-code]
(`palloc.h:154-165`).

### Critical behavioral differences from malloc

From `README:55-75` [from-readme]:

1. **`palloc` and `repalloc` `ereport(ERROR)` on OOM. They never return NULL.**
   Do not test for NULL. To opt out, use `palloc_extended(size, MCXT_ALLOC_NO_OOM)`.
2. **`palloc(0)` is valid.** Returns a real chunk; can be repalloc'd or pfree'd.
3. **`pfree(NULL)` is NOT valid.** Intentional, partly historical, partly
   performance.
4. **`repalloc(NULL, ...)` is NOT valid.** Necessary because repalloc derives
   the target context from the existing chunk header.
5. **Allocation size limit** is `MaxAllocSize = 1 GB - 1` (`memutils.h:40`) for
   regular `palloc`. Use `MemoryContextAllocHuge` / `palloc_extended` with
   `MCXT_ALLOC_HUGE` to go past it.

## Globally known contexts

From `memutils.h:53-67` [verified-by-code] and `README:174-258` [from-readme]:

| Global | Lifetime | Notes |
|---|---|---|
| `TopMemoryContext` | Backend lifetime | Root of the tree. Effectively `malloc`. Avoid as `CurrentMemoryContext`. |
| `PostmasterContext` | Postmaster lifetime | Deleted in each backend after auth. |
| `CacheMemoryContext` | Backend lifetime | Relcache, catcache, etc. Has shorter-lived children. |
| `MessageContext` | One protocol message | Reset at top of each PostgresMain loop iteration. Holds parse/plan trees in simple query mode. |
| `TopTransactionContext` | Top-level xact | Reset on COMMIT/ROLLBACK. **NOT cleared on subxact abort.** |
| `CurTransactionContext` | Current xact level | Same as TopTransactionContext at top level; child context in subxacts. Cleared on subxact abort. |
| `PortalContext` | Active portal | Pointer to the active portal's private context. |
| `ErrorContext` | Permanent | Pre-allocated ≥ 8KB reserve so OOM is reportable as ERROR. |

Rule of thumb (`README:91-96`) [from-readme]: keep `CurrentMemoryContext`
pointing at the **shortest-lived** context that still outlives the data being
allocated. Allocating into a long-lived context (especially `TopMemoryContext`
or `CacheMemoryContext`) is how permanent leaks happen.

## Per-tuple contexts in the executor

The executor creates a per-`ExprContext` private context that is reset at the
**start** of each tuple cycle (not the end), so a plan node can hand back a
tuple palloc'd in its per-tuple context and the caller is guaranteed it
remains valid until the next call into the node [from-readme]
(`README:308-368`).

If you write an SQL function, comparator, or hook that runs inside expression
evaluation, allocating into `CurrentMemoryContext` is correct — that's the
short-lived expression context. Index/sort comparators are a notable exception
historically: btree and hash support functions still must not leak, because
they're called inside long-lived contexts [from-readme] (`README:328-342`).

## The MemoryContextSwitchTo idiom

```c
MemoryContext oldcxt = MemoryContextSwitchTo(target);
result = some_allocation();
MemoryContextSwitchTo(oldcxt);
```

`MemoryContextSwitchTo` is inline; the cost is one global store
[verified-by-code] (`palloc.h:137-145`). Always restore the old context before
returning, including on error paths — except that if an `ereport(ERROR)` fires,
abort processing will fix `CurrentMemoryContext` for you. Code that needs the
restore on error normally relies on the abort path, not on PG_TRY.

Example (`execMain.c:180-274`) [verified-by-code]:
```c
oldcontext = MemoryContextSwitchTo(estate->es_query_cxt);
/* ... build executor state ... */
MemoryContextSwitchTo(oldcontext);
```

## Creating contexts

Most code uses one of these (`memutils.h:112-151`) [verified-by-code]:

- `AllocSetContextCreate(parent, "name", ALLOCSET_DEFAULT_SIZES)` — general
  purpose. Name **must be a compile-time string constant** (enforced by
  `StaticAssertExpr`); use `MemoryContextSetIdentifier` to attach a dynamic id.
- `SlabContextCreate(parent, "name", blockSize, chunkSize)` — fixed-size
  chunks, dense packing.
- `GenerationContextCreate(parent, "name", min, init, max)` — FIFO-ish
  lifetimes.
- `BumpContextCreate(parent, "name", min, init, max)` — bump allocator.
  **No `pfree`, no `repalloc`, no `GetMemoryChunkContext` / `GetMemoryChunkSpace`
  on bump chunks.** Only context reset/delete frees the memory
  [from-comment] (`bump.c` top comment).

Sizing presets (`memutils.h:157-179`) [verified-by-code]:
- `ALLOCSET_DEFAULT_SIZES` — 0 / 8KB / 8MB. For contexts that may hold a lot.
- `ALLOCSET_SMALL_SIZES` — 0 / 1KB / 8KB. For small contexts (e.g. one query plan).
- `ALLOCSET_START_SMALL_SIZES` — small init, default max.

## Context types — when to pick each

`README:471-499` [from-readme]:

- **AllocSet** (default) — general purpose. Power-of-2 freelists for small
  chunks, anything ≥ 8KB goes directly to malloc and is freeable on pfree.
  First block is retained on reset to avoid malloc thrashing
  [from-readme] (`README:463-468`).
- **Slab** — fixed-size chunks, e.g. reorder buffer txn structs. Keeps chunks
  densely packed; blocks released when fully empty
  [from-comment] (`slab.c` top).
- **Generation** — chunks allocated in FIFO order with similar lifespans.
  No global freelist; a block returns to malloc when all its chunks are pfree'd
  [from-comment] (`generation.c` top).
- **Bump** — densest packing possible (no chunk header). Best for many small
  short-lived allocations. Only reset/delete frees
  [from-comment] (`bump.c` top).

## Reset / delete callbacks

A `MemoryContextCallback` can be attached to any context; the callback fires
once, just before the next reset or delete [from-readme] (`README:139-170`).
Use cases: closing files on tuplesort, releasing reference counts, freeing
malloc-managed memory from non-PG libraries.

```c
MemoryContextCallback *cb = palloc(sizeof(MemoryContextCallback));
cb->func = my_cleanup;
cb->arg  = state;
MemoryContextRegisterResetCallback(my_ctx, cb);
```

Callbacks fire in reverse registration order; child-context callbacks fire
before parent callbacks during a tree reset [from-readme] (`README:158-161`).

## Common mistakes (codebase-confirmed)

1. **Allocating into a long-lived context when you meant a short-lived one.**
   E.g. forgetting to switch out of `CacheMemoryContext` inside a relcache
   build callback ⇒ permanent leak. The fix is a child context that you reset.
2. **Testing palloc for NULL.** Pointless — it cannot return NULL unless you
   passed `MCXT_ALLOC_NO_OOM` [from-readme] (`README:59-62`).
3. **`pfree(NULL)`** — segfaults; intentional [from-readme] (`README:69-75`).
4. **Returning palloc'd data without copying.** If a function returns a pointer
   that lives in the callee's per-tuple context, the next tuple cycle will
   stomp it. Either palloc into the caller's context (via
   `MemoryContextSwitchTo`) or copy.
5. **Variable used in `PG_TRY` body and `PG_CATCH` must be `volatile`** — and
   the same rule applies to a saved `oldcxt` if you rely on it inside catch.
6. **Non-constant context name** — `AllocSetContextCreate` enforces a string
   literal via `StaticAssertExpr` [verified-by-code] (`memutils.h:124-127`).
   Use `MemoryContextSetIdentifier` for the dynamic part.
7. **palloc in a critical section** — disallowed unless the context has
   `allowInCritSection = true` (see `MemoryContextAllowInCriticalSection`)
   [verified-by-code] (`memnodes.h:124`, `memutils.h:93-94`).
8. **Bump-context chunks** silently break `pfree`, `repalloc`,
   `GetMemoryChunkContext` — only delete/reset the whole context
   [from-comment] (`bump.c` top).

## Inspection / debugging

- `MemoryContextStats(TopMemoryContext)` — dump the whole tree to stderr.
- `MemoryContextStatsDetail(ctx, max_level, max_children, print_to_stderr)`
  — controlled depth.
- `MemoryContextMemAllocated(ctx, recurse)` — bytes consumed.
- `MemoryContextMemConsumed(ctx, &counters)` — fill a `MemoryContextCounters`
  with `nblocks/freechunks/totalspace/freespace` [verified-by-code]
  (`memutils.h:74-92`, `memnodes.h:29-35`).
- Define `MEMORY_CONTEXT_CHECKING` at build time to enable `MemoryContextCheck`
  and per-chunk sentinels [verified-by-code] (`memnodes.h:106-113`).

The signal `pg_log_backend_memory_contexts(pid)` triggers
`ProcessLogMemoryContextInterrupt`, which dumps the target backend's contexts
to its server log [verified-by-code] (`memutils.h:104-105`).

## Quick decision tree

- Data that should live until end of statement → palloc in
  `MessageContext` (simple query) or the executor's per-query context.
- Data that should live until end of (sub)transaction → switch into
  `CurTransactionContext` before allocating.
- Data needed only for one tuple cycle → use the executor's per-tuple
  ExprContext; it gets reset for you.
- Cached metadata that should live as long as the backend → child of
  `CacheMemoryContext`, reset/deleted when the cache entry is invalidated.
- Allocating thousands of same-size structs (e.g. reorder buffer entries) →
  `SlabContextCreate`.
- Write-once / never-pfree workload (e.g. tuplesort spill buffer) →
  `BumpContextCreate`.
- Need cleanup of a non-PG resource tied to a context lifetime →
  `MemoryContextRegisterResetCallback`.

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/mmgr/mcxt.c`](../files/src/backend/utils/mmgr/mcxt.c.md) | — | type-independent management |
| [`src/include/nodes/memnodes.h`](../files/src/include/nodes/memnodes.h.md) | — | MemoryContextData struct |
| [`src/include/utils/memutils.h`](../files/src/include/utils/memutils.h.md) | — | context creation + globals |
| [`src/include/utils/palloc.h`](../files/src/include/utils/palloc.h.md) | — | allocation API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md)
- [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md)
- [`add-new-data-type`](../scenarios/add-new-data-type.md)
- [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md)
- [`add-new-shared-memory-region`](../scenarios/add-new-shared-memory-region.md)
- [`add-new-system-view`](../scenarios/add-new-system-view.md)
- [`add-new-table-am`](../scenarios/add-new-table-am.md)
- [`fix-memory-leak`](../scenarios/fix-memory-leak.md)

<!-- /scenarios:auto -->
## Open questions / unverified

- Exact behavior of `MemoryContextSetParent` when the new parent is in a
  different lifetime tree [unverified] — used in some catalog code to "adopt"
  contexts but I haven't traced the semantics.
- Whether `palloc_extended(..., MCXT_ALLOC_NO_OOM)` skips registering with the
  per-context accounting [unverified] — `README:521-527` says accounting is at
  block level so individual NO_OOM chunks probably still count.
- Whether `MemoryContextDelete` on a context that has unregistered reset
  callbacks runs them in any defined order beyond "reverse of registration"
  [from-readme] but cross-tree ordering for unrelated subtrees is unspecified.
