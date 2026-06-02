# 2 GB allocation for an aggregate transition state

## What hit you

The cap on regular `palloc` is `MaxAllocSize`, which is `1 GB - 1`.
2 GB exceeds it and palloc rejects with "invalid memory alloc request
size".

## Use the huge-alloc API

- `palloc_extended(sz, MCXT_ALLOC_HUGE)` — in current context
- `MemoryContextAllocHuge(ctx, sz)` — in a specific context
- `repalloc_huge(ptr, sz)` — to grow

Hard cap is `MaxAllocHugeSize`, defined as `SIZE_MAX / 2`.

OOM still throws `ereport(ERROR)` by default — pass `MCXT_ALLOC_NO_OOM`
together with HUGE if you want a NULL return instead.

## Restrictions on context types

- AllocSet — supports huge allocations.
- Generation — supports huge allocations.
- Slab — chunks are a single fixed size, so huge doesn't apply.
- Bump — does not support `pfree` or `repalloc`. So if you need to grow
  the buffer or free it before the context is reset, you can't use
  Bump.

For a 2 GB growable aggregate buffer, AllocSet (or Generation) is the
right choice.

## Where to put it

For an aggregate, allocate in the per-group aggregate context, obtained
via:

```c
MemoryContext aggcontext;
if (!AggCheckCallContext(fcinfo, &aggcontext))
    elog(ERROR, "not called in aggregate context");
```

Then `MemoryContextAllocHuge(aggcontext, sz)` for the initial alloc and
`repalloc_huge` to grow.
