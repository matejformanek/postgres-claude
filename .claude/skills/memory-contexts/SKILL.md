---
name: memory-contexts
description: Allocate memory in PostgreSQL backend C — pick the right MemoryContext and use palloc / palloc0 / pstrdup / psprintf correctly. Covers CurrentMemoryContext / TopMemoryContext / per-query / per-tuple / ExecutorState context choice, MemoryContextSwitchTo discipline, the OOM-throws-ereport contract (no NULL checks), pfree vs MemoryContextReset vs MemoryContextDelete, the AllocSet vs Slab vs Generation vs Bump context-type cheat sheet, and leak-scoping in long-running backends. Use whenever a PG patch or extension calls palloc / palloc0 / MemoryContextAlloc, creates or switches a MemoryContext, picks AllocSet vs Slab vs Generation vs Bump, or debugs a context-shaped leak. Skip for plain malloc / free / jemalloc / mimalloc / tcmalloc, JVM / Go / .NET GC tuning, Rust Box / Rc / Arc / lifetimes, shared_buffers / work_mem production tuning, valgrind / heaptrack on non-PG programs, and C++ smart pointers.
when_to_load: Allocate memory in backend C (palloc/palloc0/MemoryContextAlloc); create or switch a `MemoryContext`; pick AllocSet vs Slab vs Generation vs Bump; debug a context-shaped leak.
companion_skills:
  - error-handling
  - debugging
  - coding-style
  - executor-and-planner
  - fmgr-and-spi
---

# Memory contexts — actionable rules

Reference doc: `knowledge/idioms/memory-contexts.md`.

## Allocation cheat sheet

- `palloc(n)` — allocate in `CurrentMemoryContext`. **Never returns NULL** — it
  calls `ereport(ERROR)` on OOM. Don't test for NULL.
- `palloc0(n)` — like palloc plus zero-fill.
- `pstrdup(s)` / `pnstrdup(s, n)` / `psprintf(fmt, ...)` — string variants.
- `palloc_object(T)`, `palloc_array(T, count)`, `palloc0_array(T, count)`
  — type-safe macros. Prefer these over raw size calculations.
- `palloc_extended(n, MCXT_ALLOC_NO_OOM)` — opt out of the OOM-throws contract
  (returns NULL on failure). Use only when you specifically can recover.
- `palloc_extended(n, MCXT_ALLOC_HUGE)` / `MemoryContextAllocHuge` — past the
  `MaxAllocSize` (≈1 GB) limit; capped at `MaxAllocHugeSize` (SIZE_MAX/2).
- `MemoryContextAlloc(ctx, n)` — allocate in a specific context without
  switching `CurrentMemoryContext`.
- `repalloc(p, n)` — grow/shrink. Goes to p's original context, not current.
- `pfree(p)` — free a chunk. Goes to its original context.

### Hard rules

- **`pfree(NULL)` is undefined** — always check first if pointer may be NULL.
- **`repalloc(NULL, n)` is undefined** — first allocation must be `palloc`.
- **`palloc(0)` is legal** — returns a usable chunk.
- **Do not test palloc's return for NULL** unless you used `MCXT_ALLOC_NO_OOM`.
- **Single-allocation cap is `MaxAllocSize` (1 GB - 1)** for regular palloc.
  Exceeding it raises `errmsg("invalid memory alloc request size %zu")` —
  switch to `MemoryContextAllocHuge` / `palloc_extended(..., MCXT_ALLOC_HUGE)`,
  capped at `MaxAllocHugeSize = SIZE_MAX/2`. Use `repalloc_huge` to grow.
  Slab is fixed-size so N/A; Bump cannot be repalloc'd; AllocSet and
  Generation both support huge chunks (AllocSet routes any chunk ≥ 8 KB
  straight to malloc).

## Picking the right context

Default rule: **`CurrentMemoryContext` should be the shortest-lived context
that still outlives the data you're allocating.**

| You need data to live until... | Allocate in / switch to |
|---|---|
| End of one tuple cycle | the executor's per-tuple ExprContext (usually already `CurrentMemoryContext` in expression eval); reset at the *start* of the next cycle |
| End of one statement | per-query context (executor sets this up; `estate->es_query_cxt` or `econtext->ecxt_per_query_memory`) or `MessageContext` |
| Across SRF calls (value-per-call) | `funcctx->multi_call_memory_ctx` from `SRF_FIRSTCALL_INIT()` |
| Across SRF calls (materialize) | `rsinfo->econtext->ecxt_per_query_memory` for the tuplestore |
| Across aggregate transitions (per group) | the aggcontext from `AggCheckCallContext(fcinfo, &aggcontext)` |
| End of current (sub)transaction | `CurTransactionContext` |
| End of top-level transaction | `TopTransactionContext` |
| Lifetime of one portal | the portal's private context (`PortalContext` when active) |
| Lifetime of a cache entry | a child of `CacheMemoryContext` you control (delete the child on invalidation; delete is recursive) |
| Backend lifetime / forever | `TopMemoryContext` — but only if truly forever |

**Avoid making `TopMemoryContext` or `CacheMemoryContext` `CurrentMemoryContext`.**
Allocating into them by accident is the classic permanent-leak bug.

## The switch idiom

```c
MemoryContext oldcxt = MemoryContextSwitchTo(target_cxt);
result = build_something();          /* allocs land in target_cxt */
MemoryContextSwitchTo(oldcxt);
return result;
```

You do NOT need to restore on error paths in normal code — transaction abort
will fix `CurrentMemoryContext`. If you use `PG_TRY`, declare `oldcxt`
`volatile` if you read it in `PG_CATCH`.

## Creating a context

```c
MemoryContext cxt = AllocSetContextCreate(parent,
                                          "my purpose",          /* MUST be a literal */
                                          ALLOCSET_DEFAULT_SIZES);
MemoryContextSetIdentifier(cxt, dynamic_name);  /* if you need a runtime label */
```

Cache-entry pattern (per-relation child of `CacheMemoryContext`, blown
away as a unit on invalidation — `MemoryContextDelete` is recursive):

```c
MemoryContext rulescxt = AllocSetContextCreate(CacheMemoryContext,
                                               "relation rules",
                                               ALLOCSET_SMALL_SIZES);
MemoryContextCopyAndSetIdentifier(rulescxt, RelationGetRelationName(rel));
oldcxt = MemoryContextSwitchTo(rulescxt);
/* build cache contents; everything lands in rulescxt */
MemoryContextSwitchTo(oldcxt);
rel->rd_rulescxt = rulescxt;            /* invalidation: MemoryContextDelete */
```
See `source/src/backend/utils/cache/relcache.c` for the real precedent
(`rd_rulescxt`, `rd_indexcxt`, `rd_pdcxt`, …).

Sizing presets:
- `ALLOCSET_DEFAULT_SIZES` — 0 / 8KB / 8MB. Use when the context may hold a lot.
- `ALLOCSET_SMALL_SIZES` — 0 / 1KB / 8KB. Use for many small contexts (per
  relcache entry, per query plan).
- `ALLOCSET_START_SMALL_SIZES` — small init, default max.

Pick a non-default context type when the allocation pattern fits:
- **Slab** (`SlabContextCreate(parent, name, blockSize, chunkSize)`) — all
  chunks are the same size. Good for reorder buffer txns, fixed-shape structs.
- **Generation** (`GenerationContextCreate(parent, name, min, init, max)`) —
  FIFO-ish allocation/free pattern. Good for queue-like buffering.
- **Bump** (`BumpContextCreate(...)`) — write-once, never pfree'd. Densest
  packing. **`pfree`/`repalloc`/`GetMemoryChunkContext` will NOT work** on
  bump chunks — only context reset/delete frees them.

## Cleanup

- `MemoryContextReset(cxt)` — frees all chunks AND deletes all child contexts.
- `MemoryContextResetOnly(cxt)` — only frees chunks; children remain.
- `MemoryContextDelete(cxt)` — frees everything including the context itself
  and all descendants.
- `MemoryContextDeleteChildren(cxt)` — keep cxt, delete its subtree.
- `MemoryContextRegisterResetCallback(cxt, cb)` — fire a callback the next
  time cxt is reset or deleted. Use for closing file handles, releasing
  refcounts, tearing down non-PG-owned resources.

## Common mistakes to avoid

1. **Testing `palloc(...)` for NULL.** It cannot return NULL. Delete the test.
2. **`pfree(p)` where p might be NULL.** Guard explicitly.
3. **Allocating in `CacheMemoryContext` while building cache entries** without
   switching — permanent leak per entry. Switch in, switch out.
4. **Returning per-tuple-context memory across the boundary.** The next tuple
   cycle resets that context. Either palloc into the caller's context or
   `datumCopy` / `pstrdup` / explicit copy.
5. **Non-constant string passed as `AllocSetContextCreate` name** — fails
   `StaticAssertExpr`. Use `MemoryContextSetIdentifier` for the dynamic part.
6. **Calling `pfree` / `repalloc` on a bump-context chunk** — undefined.
7. **`palloc` inside a critical section** — the context must have
   `allowInCritSection = true` (`MemoryContextAllowInCriticalSection`).
   Default contexts forbid it; the assertion fires only in assert builds.
8. **Using a saved `MemoryContext` after the context was deleted.** Especially
   common with `PortalContext` — a portal drop invalidates it.

## Checklist before committing

- [ ] No `NULL` checks on `palloc`/`palloc0`/`pstrdup`/`psprintf`.
- [ ] `pfree(p)` callers ensure `p != NULL`.
- [ ] Long-lived allocations explicitly switch into the right context.
- [ ] New `AllocSetContextCreate` uses string-literal name + appropriate size
      preset.
- [ ] If you stored a pointer somewhere persistent, you allocated it in a
      context that outlives the storing struct.
- [ ] For non-PG resource attached to a context lifetime, you registered a
      reset callback (don't rely on destructors or explicit cleanup paths).
- [ ] `volatile` qualifier on any `oldcxt` / pointer used across `PG_TRY` /
      `PG_CATCH`.
- [ ] If you used Slab/Generation/Bump, you understand which ops are unsupported
      (bump in particular).

## When in doubt, cite

- `src/backend/executor/execMain.c` — canonical `MemoryContextSwitchTo` pattern
  around `es_query_cxt`.
- `src/backend/utils/cache/relcache.c` — per-relation child contexts under
  `CacheMemoryContext`.
- `src/backend/utils/mmgr/mcxt.c` — type-independent operations.
- `src/backend/utils/mmgr/README` — the canonical design discussion.

## Cross-references

- `.claude/skills/error-handling/SKILL.md` — OOM-throws-ereport contract; `AbortTransaction` releases per-query contexts; `PG_TRY` / `volatile` rules.
- `.claude/skills/debugging/SKILL.md` — `pg_backend_memory_contexts`, `pg_log_backend_memory_contexts(pid)`, `MemoryContextStats(TopMemoryContext)` from the debugger.
- `.claude/skills/executor-and-planner/SKILL.md` — `es_query_cxt`, `ExprContext`, per-tuple contexts in plan nodes.
- `.claude/skills/fmgr-and-spi/SKILL.md` — `MultiCallMemoryCtx` for SRFs; `fcinfo->flinfo->fn_mcxt`.
- `.claude/skills/coding-style/SKILL.md` — `palloc` vs raw `malloc` rule; `pstrdup`, `psprintf` conventions.
- `knowledge/idioms/memory-contexts.md` — long-form idiom doc.
