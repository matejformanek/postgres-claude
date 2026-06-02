# Relcache build callback — scoping

Palloc'ing directly into `CacheMemoryContext` does leak in practice:
relcache invalidation throws away its handle on the relcache entry,
but the chunks themselves stay allocated in `CacheMemoryContext`
forever — that's a per-relation backend-lifetime leak.

## Right way: child context per entry

Create a child `AllocSetContext` of `CacheMemoryContext`, store it on
the cache entry struct, and allocate everything inside it. On
invalidation you drop the cache entry and delete the child context.

```c
MemoryContext mycxt = AllocSetContextCreate(CacheMemoryContext,
                                            "my relation cache",
                                            ALLOCSET_SMALL_SIZES);

oldcxt = MemoryContextSwitchTo(mycxt);
/* build the tables */
MemoryContextSwitchTo(oldcxt);

rel->rd_mycxt = mycxt;
```

On invalidation: `MemoryContextDelete(rel->rd_mycxt)`.

## Notes

- `ALLOCSET_SMALL_SIZES` is the right preset — per-relation contexts
  are typically small and numerous.
- The `name` parameter to `AllocSetContextCreate` must be a string
  literal (compile-time constant). For a dynamic display label (the
  relation's name), use `MemoryContextSetIdentifier`.
- The pattern matches what relcache.c already does for things like the
  rules-context and the index-context — look at relcache.c for the
  precedent.
