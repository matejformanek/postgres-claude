# Scoping memory in a relcache build callback

Yes, if you palloc directly inside CacheMemoryContext, those allocations
will leak in the sense that they live for the lifetime of the backend and
won't be freed when the relcache entry is invalidated.

The standard PG idiom is to create a child context under CacheMemoryContext
and attach the pointer to that context to your RelationData (or whatever
cache-entry struct you're populating). Then on invalidation you just
MemoryContextDelete the whole child context and everything goes away.

Look at how relcache.c does it for rules and triggers — there are fields
like rd_rulescxt and rd_indexcxt that point to dedicated child contexts.
Inside the build path it does something like:

  cxt = AllocSetContextCreate(CacheMemoryContext, "name", ...);
  oldcxt = MemoryContextSwitchTo(cxt);
  ... populate ...
  MemoryContextSwitchTo(oldcxt);
  rel->rd_rulescxt = cxt;

And then RelationDestroyRelation / invalidation calls MemoryContextDelete
on those.

For a small per-relation lookup table I'd use ALLOCSET_SMALL_SIZES as the
sizing preset since each context is small. Also remember the name arg
must be a compile-time constant string — use MemoryContextSetIdentifier
if you want to attach the relation name dynamically.
