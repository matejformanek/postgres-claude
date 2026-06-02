# Allocating > 1 GB for an aggregate transition state

The error you're seeing is from the MaxAllocSize check — regular palloc
caps individual chunks at just under 1 GB (the exact value is 0x3fffffff,
i.e. 1 GB - 1). This check exists because PG uses int32 in a lot of
places for sizes historically.

To go past it, use the "huge" variants:

  palloc_extended(size, MCXT_ALLOC_HUGE)
  MemoryContextAllocHuge(ctx, size)
  repalloc_huge(p, size)

The cap for huge allocations is MaxAllocHugeSize which I believe is
SIZE_MAX/2 — so effectively unbounded on 64-bit.

OOM behavior is the same as regular palloc: it throws an ereport(ERROR)
unless you also pass MCXT_ALLOC_NO_OOM.

For an aggregate transition state, you want to allocate in the
aggregate's per-group context. Use AggCheckCallContext to get a handle
on that context and allocate there — otherwise your buffer ends up in
the per-tuple context and gets reset between input rows.

As for context types: Slab is fixed-size-chunk so it's not suitable.
Bump doesn't support pfree or repalloc, so if you ever want to grow
your buffer you can't use Bump either. AllocSet (the default) is what
you want — and for large chunks AllocSet bypasses its freelists and
calls malloc/free directly, so a huge alloc gets released to the OS
when you pfree it.
