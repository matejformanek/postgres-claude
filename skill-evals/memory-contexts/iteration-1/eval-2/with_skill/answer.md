# Scoping memory in a relcache build callback

## Will it leak?
**Yes**, if you palloc inside the build callback without switching context.
During relcache build, `CurrentMemoryContext` is typically
`CacheMemoryContext` (or a transient one) — but the failure mode SKILL.md
calls out as "Common mistake #3" is exactly: "Allocating in
`CacheMemoryContext` while building cache entries without switching —
permanent leak per entry. Switch in, switch out."

If you allocate small lookup tables directly into `CacheMemoryContext`,
they are *not* freed when the relcache entry is invalidated — only the
per-relation child contexts get blown away on invalidation. The result:
they accumulate forever in a long-running backend.

## The right pattern
Per `knowledge/idioms/memory-contexts.md` and the SKILL.md lifetime table
("Lifetime of a cache entry → a child of `CacheMemoryContext` you
control"), create a **child context of CacheMemoryContext** and parent
it under the RelationData / cache entry's lifetime:

```c
MemoryContext rulescxt;
MemoryContext oldcxt;

rulescxt = AllocSetContextCreate(CacheMemoryContext,
                                 "relation rules",        /* literal! */
                                 ALLOCSET_SMALL_SIZES);
MemoryContextCopyAndSetIdentifier(rulescxt, RelationGetRelationName(rel));

oldcxt = MemoryContextSwitchTo(rulescxt);
/* build lookup tables, palloc freely; everything lands in rulescxt */
MemoryContextSwitchTo(oldcxt);

/* store rulescxt on the relcache entry so invalidation can free it */
rel->rd_rulescxt = rulescxt;
```

Then on invalidation, `MemoryContextDelete(rel->rd_rulescxt)` frees the
whole subtree in one shot — no per-allocation pfree needed.

## Why a child context, not CacheMemoryContext directly
1. `CacheMemoryContext` lives for the backend lifetime — anything you
   palloc there leaks unless you remember every pointer.
2. A child context is the unit of cleanup. Reset/delete is recursive
   (`knowledge/idioms/memory-contexts.md`: "Reset and delete are recursive").
3. The sizing preset `ALLOCSET_SMALL_SIZES` (0 / 1KB / 8KB) is the right
   choice — SKILL.md "Sizing presets": "Use for many small contexts
   (per relcache entry, per query plan)."

## Don't forget
- The name argument to `AllocSetContextCreate` **must be a string
  literal** (StaticAssertExpr). Use `MemoryContextSetIdentifier` /
  `MemoryContextCopyAndSetIdentifier` for the relname (SKILL.md
  Common mistake #5).
- The reference implementation is in
  `source/src/backend/utils/cache/relcache.c` — SKILL.md "When in
  doubt, cite" points there for "per-relation child contexts under
  `CacheMemoryContext`."

## Cites
- SKILL.md "Picking the right context" (cache-entry row), Common mistakes #3, #5.
- `knowledge/idioms/memory-contexts.md` "Globally known contexts" table
  (CacheMemoryContext is backend-lifetime).
- `source/src/backend/utils/cache/relcache.c` — `rd_rulescxt`, `rd_indexcxt` pattern.
