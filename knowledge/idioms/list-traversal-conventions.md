# List traversal conventions

`List *` is the canonical heterogeneous container in PG backend code.
This idiom doc covers the **traversal patterns** — `foreach` and its
variants — because the modern array-backed `List` representation has
subtleties that the old linked-list `lcons`/`lnext` API didn't have.

Anchors:
- `source/src/include/nodes/pg_list.h` — `List` struct, `ListCell`,
  the traversal macros [verified-by-code]
- `source/src/backend/nodes/list.c` — the implementation
- `knowledge/idioms/node-types-and-lists.md` — companion: `List`
  construction + the heterogeneous-element-type story

## The shape

A `List` is an array of `ListCell` values, not a linked list. The
header struct lives in `pg_list.h`:

```c
typedef struct List {
    NodeTag    type;        /* T_List, T_IntList, T_OidList, T_XidList */
    int        length;      /* current valid element count */
    int        max_length;  /* allocated capacity */
    ListCell  *elements;    /* array; same memory context as the List */
    ListCell   initial_elements[FLEXIBLE_ARRAY_MEMBER];
} List;
```

`elements` typically points into `initial_elements[]` (inline) until
the list outgrows its initial capacity and is reallocated to a
separate buffer in the same memory context.

Empty list is the **NIL pointer** (`#define NIL ((List *) NULL)`),
following the same convention as `Bitmapset`.

## The four list flavors

By `NodeTag`:

- `T_List` — `ListCell` carries `ptr_value` (a Node pointer or
  arbitrary `void *`). Most common.
- `T_IntList` — `int_value`. Used for small integer collections.
- `T_OidList` — `oid_value`. Used for OID sets.
- `T_XidList` — `xid_value`. Used for transaction-id sets.

The flavor is set at creation (`lappend` / `lappend_int` /
`lappend_oid` / `lappend_xid`) and must not be mixed. The traversal
macros enforce the typed accessor via `lfirst()` / `lfirst_int()` /
`lfirst_oid()` / `lfirst_xid()`.

## The `foreach` macro — the canonical pattern

```c
ListCell *lc;

foreach(lc, my_list)
{
    MyType *x = (MyType *) lfirst(lc);
    /* ... do something with x ... */
}
/* lc is NULL here on normal loop exit. */
```

[verified-by-code `pg_list.h:405-411`]

Mechanics:

- Declares a `ForEachState lc__state` hidden in the surrounding scope.
- On each iteration sets `lc` to point at `elements[i]` and bumps `i`.
- On normal exit, `lc` is `NULL`; on `break`, `lc` is the cell where
  you broke.

## Mutation rules during `foreach`

The single most important rule: **don't change the List object while
the loop is iterating**, with two specific exceptions.

What's allowed:

- **Appending elements to the end** — new elements are guaranteed
  to be visited.
- **Deleting the current element via `foreach_delete_current(lst,
  lc)`** — adjusts the loop state so no element is skipped or
  re-visited.

What's forbidden (or at least surprising):

- Inserting before the current cell.
- Inserting after the current cell other than at the end.
- Deleting elements other than via `foreach_delete_current`.
- Reassigning the `ListCell *` to a different list.

The pre-PG 13 linked-list `List` allowed more aggressive mutation;
patches forward-ported from old PG versions often break this rule
silently. Catch it in review.

## The variant macros

| Macro | Use |
|---|---|
| `foreach(cell, lst)` | Standard, generic. |
| `foreach_int(var, lst)` | For `T_IntList` — `var` is `int`, not `ListCell *`. |
| `foreach_oid(var, lst)` | For `T_OidList`. |
| `foreach_xid(var, lst)` | For `T_XidList`. |
| `foreach_ptr(type, var, lst)` | Typed `T_List` iteration — `var` is `type *`. |
| `foreach_node(type, var, lst)` | Same as `foreach_ptr` but typed for Node subclasses. |
| `for_each_from(cell, lst, N)` | Start from element N. |
| `forboth(lc1, lst1, lc2, lst2)` | Parallel iteration over two lists. Stops at the shorter. |
| `forthree`, `forfour`, `forfive` | Up to 5-list parallel. |
| `foreach_delete_current(lst, var)` | Delete current; reassign list pointer. |
| `foreach_current_index(var)` | Get the 0-based index of the current element. |

[verified-by-code `pg_list.h:405-510+`]

The typed variants (`foreach_int`, `foreach_oid`, `foreach_ptr`,
`foreach_node`) are usually preferred over the bare `foreach` —
they eliminate one cast and one accessor call per loop body.

## The reassign-on-mutation rule

For list mutations that **may grow**, the function returns the
(potentially new) `List *`:

```c
my_list = lappend(my_list, new_element);   // always reassign
```

Same rule as `Bitmapset`. Code review must catch
`lappend(my_list, x);` with discarded return value.

`list_delete` / `list_delete_first` etc. also return the (possibly
NULL) updated `List *`. Reassign.

## Memory context

A `List` and its `ListCell` array live in the same `MemoryContext`,
captured at creation. Once allocated, the list cannot migrate
contexts — use `list_copy` (shallow) or `list_copy_deep` (deep) to
move elements to another context.

A `List *` stored long-term in a `RelOptInfo` or `Query` was
allocated in the planner's per-query context; lifetime-extension
requires a copy.

## Common antipatterns (will get a code review nit)

- **Old-style `lnext(list, lc)` traversal.** Outdated since the
  array-backed `List` rewrite (PG 13). Use `foreach`.
- **Direct array access via `list->elements[i]`** when a
  `foreach_*` macro applies. Bypasses the iterator state.
- **`lappend` return value discarded.** As above.
- **`lcons`** (prepend) abuse. `lcons` is O(N) (memmove the whole
  array). Only acceptable when the call site requires LIFO order;
  prefer `lappend` and reverse if needed.
- **`list_concat` on a list you also walk** — the resulting
  pointer may be a fresh allocation.

## Useful greps

- All `foreach_*` variants:
  `grep -n '^#define foreach' source/src/include/nodes/pg_list.h`
- Heavy mutation sites (review surface):
  `grep -RIn 'foreach_delete_current\|list_delete_nth_cell' source/src/backend`
- `lappend` callers (volume; this is one of the most-used backend APIs):
  `grep -RIn 'lappend' source/src/backend | wc -l`

## Cross-references

- `.claude/skills/parser-and-nodes/SKILL.md` §"Walker / mutator quick reference" — interaction with `expression_tree_walker` etc.
- `.claude/skills/executor-and-planner/SKILL.md` — `List`s drive plan/path enumeration.
- `.claude/skills/coding-style/SKILL.md` — prefer typed `foreach_*` variants in new code.
- `knowledge/data-structures/bitmapset.md` — sibling pattern; same NULL=empty + reassign-on-grow rules.
- `knowledge/idioms/node-types-and-lists.md` — construction side (`list_make1` through `list_make5`, `lappend`, `lcons`); flavored variants per NodeTag.
- `source/src/backend/nodes/list.c` — implementation (~1100 LOC).
