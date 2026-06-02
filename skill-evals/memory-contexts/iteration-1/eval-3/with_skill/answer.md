# Allocating > 1 GB for an aggregate transition state

## Why palloc rejects 2 GB
Regular `palloc` is capped at `MaxAllocSize = 1 GB - 1` (see SKILL.md
"Allocation cheat sheet" and "Hard rules": "Single-allocation cap is
`MaxAllocSize` (1 GB - 1) for regular palloc"). The "invalid memory alloc
request size" error is the `AllocSizeIsValid` check in
`source/src/include/utils/memutils.h` firing.

## The right API
Use the huge-allocation variant:

```c
buf = MemoryContextAllocHuge(my_ctx, sz);
/* or, allocating in CurrentMemoryContext: */
buf = palloc_extended(sz, MCXT_ALLOC_HUGE);
```

For growing the buffer, the matching realloc is `repalloc_huge(p, sz)`.

## The hard cap
SKILL.md "Allocation cheat sheet": "capped at `MaxAllocHugeSize`
(SIZE_MAX/2)." Defined in `source/src/include/utils/memutils.h:40-49`.
Practically that means ~8 EiB on 64-bit — your real limit is RAM /
work_mem / process address space, not the PG API.

## OOM behavior is unchanged
Huge allocations still follow the OOM-throws-ereport contract — they
`ereport(ERROR)` on failure, do **not** return NULL. SKILL.md "Hard rules":
"Do not test palloc's return for NULL unless you used `MCXT_ALLOC_NO_OOM`."
You can combine flags: `palloc_extended(sz, MCXT_ALLOC_HUGE | MCXT_ALLOC_NO_OOM)`
if you want to handle OOM yourself.

## Context-type restrictions
- **AllocSet** (default) — supports huge fine. Any chunk ≥ 8 KB goes
  straight to malloc per `knowledge/files/src/backend/utils/mmgr/aset.c.md`,
  so huge chunks are released to malloc immediately on pfree.
- **Slab** — fixed-size chunks; not appropriate (one giant buffer doesn't
  fit the model).
- **Generation** — fine for large allocations.
- **Bump** — works, but `pfree`/`repalloc` are not supported on bump
  chunks (SKILL.md "Common mistake #6"). For a transition state you'll
  probably want to repalloc as it grows, so **avoid Bump**.

## For an aggregate transition state specifically
Aggregate trans values must live in the aggregate's per-group memory
context (`aggcontext`) — get it via `AggCheckCallContext(fcinfo, &aggcontext)`
and either switch to it or use `MemoryContextAllocHuge(aggcontext, sz)`
directly. That context is reset between groups/queries appropriately.

## Cites
- SKILL.md "Allocation cheat sheet" (MCXT_ALLOC_HUGE / MemoryContextAllocHuge bullets),
  "Hard rules" (1 GB cap).
- `knowledge/idioms/memory-contexts.md` "The palloc API"
  (`MemoryContextAllocHuge`, `repalloc_huge`, MaxAllocHugeSize = SIZE_MAX/2)
  citing `source/src/include/utils/memutils.h:40-49`.
- `knowledge/files/src/backend/utils/mmgr/aset.c.md` (large chunks bypass
  freelists, go directly to malloc).
