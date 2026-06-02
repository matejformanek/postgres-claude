# 2 GB allocation for an aggregate transition state

## The cap that bit you

Regular `palloc` is limited to `MaxAllocSize = 1 GB - 1`. Exceeding it
raises `errmsg("invalid memory alloc request size %zu")` —
exactly the error you saw. SKILL.md "Allocation cheat sheet" /
"Hard rules"; constant defined in
`source/src/include/utils/memutils.h:40-49`.

## The huge-alloc API

Switch to one of:

- `palloc_extended(sz, MCXT_ALLOC_HUGE)` — current context
- `MemoryContextAllocHuge(ctx, sz)` — specific context
- `repalloc_huge(ptr, sz)` — to grow a huge chunk

Hard cap is `MaxAllocHugeSize = SIZE_MAX / 2`. OOM still throws
`ereport(ERROR)` unless you also set `MCXT_ALLOC_NO_OOM`.

## Context-type restrictions

SKILL.md "Creating a context" + the updated huge bullet:

- **AllocSet** — fine; chunks ≥ 8 KB get routed straight to malloc anyway.
- **Generation** — fine, supports huge chunks.
- **Slab** — N/A, all chunks are a single fixed size.
- **Bump** — N/A for a growable buffer: `pfree` and `repalloc` are
  **not supported** on bump chunks (they're undefined). Only context
  reset/delete frees them. SKILL.md "Common mistakes" #6.

So for a 2 GB transition state you want AllocSet (or Generation) plus
the huge API, not Bump.

## Where to put the allocation — the aggcontext

For aggregate transition state, the canonical context is the
**aggcontext** returned by `AggCheckCallContext(fcinfo, &aggcontext)`.
That gives you a context that lives across all transition calls in the
group; you allocate (and grow) the buffer there. SKILL.md lifetime
table row "Across aggregate transitions (per group)".

```c
MemoryContext aggcontext;

if (!AggCheckCallContext(fcinfo, &aggcontext))
    elog(ERROR, "my_trans called in non-aggregate context");

if (PG_ARGISNULL(0))
{
    MemoryContext oldcxt = MemoryContextSwitchTo(aggcontext);
    state = MemoryContextAllocHuge(aggcontext, initial_size);
    MemoryContextSwitchTo(oldcxt);
}
else
{
    state = (MyState *) PG_GETARG_POINTER(0);
    /* to grow: state = repalloc_huge(state, new_size); */
}
```

## TL;DR

- Cap is `MaxAllocSize = 1 GB - 1` → error "invalid memory alloc request size".
- Use `MemoryContextAllocHuge` / `palloc_extended(..., MCXT_ALLOC_HUGE)` /
  `repalloc_huge`, capped at `MaxAllocHugeSize = SIZE_MAX/2`.
- Allocate in the aggcontext from `AggCheckCallContext`.
- Don't use Bump (no pfree/repalloc); Slab is fixed-size.
- OOM still ereports unless you opt out with `MCXT_ALLOC_NO_OOM`.
