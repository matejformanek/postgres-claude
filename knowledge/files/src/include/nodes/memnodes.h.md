# memnodes.h

- **Source:** `source/src/include/nodes/memnodes.h` (~155 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Defines `MemoryContextData`, the header common to every memory
context (AllocSet, Slab, Generation, Bump). Method-table-based
dispatch — each context kind supplies a `MemoryContextMethods *`.

## Types

### `MemoryContextCounters` `:29-36`

Stats summary returned by `MemoryContextStats`: `nblocks`,
`freechunks`, `totalspace`, `freespace`. Biased toward AllocSet's
shape. `:20-27` `[from-comment]`

### `MemoryContextMethods` `:58`

Function-pointer table:
- `alloc(context, size, flags)` → void *
- `free_p(context, pointer)`
- `realloc(context, pointer, size, flags)` → void *
- `reset(context)`
- `delete_context(context)`
- `get_chunk_context(pointer)` → MemoryContext (for cross-context lookups)
- `get_chunk_space(pointer)` → Size
- `is_empty(context)` → bool
- `stats(context, ...)` → fill MemoryContextCounters
- `check(context)` (assert-only)

### `MemoryContextData` `:117`

```c
typedef struct MemoryContextData {
    NodeTag                    type;        /* T_AllocSetContext, T_SlabContext,
                                              T_GenerationContext, T_BumpContext */
    bool                       isReset;
    bool                       allowInCritSection;
    Size                       mem_allocated;
    const MemoryContextMethods *methods;
    MemoryContext              parent;
    MemoryContext              firstchild;
    MemoryContext              prevchild;
    MemoryContext              nextchild;
    const char                *name;
    const char                *ident;
    MemoryContextCallback     *reset_cbs;
} MemoryContextData;
```

Lifetime is hierarchical: deleting a context deletes all children.
Reset → reclaim everything but the context struct itself.

## Cross-references

- Implementation: `src/backend/utils/mmgr/{aset.c,slab.c,generation.c,bump.c,mcxt.c}`.
- Idiom: `knowledge/idioms/memory-contexts.md`
  (or `.claude/skills/memory-contexts/`).
