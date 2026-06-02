# Relcache build callback — scoping the cached lookup tables

## Yes, raw palloc leaks

If your callback runs with `CurrentMemoryContext == CacheMemoryContext`
(or you switch into it explicitly), every alloc lives for the **backend
lifetime** — relcache entries are flushed by invalidation, but the
individual chunks you palloc'd into the parent context are never
reclaimed. Classic leak. See SKILL.md "Common mistakes" #3.

## The pattern: a child context per cache entry

Create an `AllocSetContext` as a **child of `CacheMemoryContext`**, store
its pointer on the relcache entry, allocate everything inside it.
Invalidation then frees the whole subtree via a single
`MemoryContextDelete()` — **delete is recursive**, so one call frees the
context and everything in it. SKILL.md "Cleanup" section.

```c
MemoryContext rulescxt = AllocSetContextCreate(CacheMemoryContext,
                                               "relation rules",
                                               ALLOCSET_SMALL_SIZES);
MemoryContextCopyAndSetIdentifier(rulescxt, RelationGetRelationName(rel));

oldcxt = MemoryContextSwitchTo(rulescxt);
/* build the lookup tables here — everything lands in rulescxt */
MemoryContextSwitchTo(oldcxt);

rel->rd_mycxt = rulescxt;
```

Then on invalidation:

```c
if (rel->rd_mycxt)
{
    MemoryContextDelete(rel->rd_mycxt);   /* frees everything, recursively */
    rel->rd_mycxt = NULL;
}
```

## Two API rules to follow

1. **Size preset**: use `ALLOCSET_SMALL_SIZES` (0 / 1 KB / 8 KB). Per-relation
   contexts are typically small and there are many of them; small sizes
   keep overhead down. SKILL.md "Creating a context".

2. **Name must be a string literal**. `AllocSetContextCreate`'s name argument
   is checked with `StaticAssertExpr` and **must be a compile-time literal**.
   For the dynamic part (e.g. relation name) use
   `MemoryContextSetIdentifier()` or `MemoryContextCopyAndSetIdentifier()`.
   SKILL.md "Common mistakes" #5.

## Precedent in the tree

See `source/src/backend/utils/cache/relcache.c` —
`rd_rulescxt`, `rd_indexcxt`, `rd_pdcxt` are exactly this pattern:
per-relation child of `CacheMemoryContext`, stored on `Relation`,
deleted as a unit when the entry is rebuilt or evicted.
SKILL.md "When in doubt, cite" lists this file as canonical.
