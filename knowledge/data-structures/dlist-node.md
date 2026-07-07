# dlist_node — intrusive doubly-linked-list primitive

`dlist_node` is the intrusive doubly-linked-list primitive used
everywhere PostgreSQL needs an unbounded ordered collection in
shared memory or backend-local memory. "Intrusive" because the
node struct is **embedded in the data** being linked — not
allocated separately as a wrapper. This avoids the allocation +
locality cost of separate list-cell objects. Used by buffer
manager free lists, latch chains, async-notify queues, plan
caches, MultiXact members, and dozens more.

Anchors:
- `source/src/include/lib/ilist.h:130-203` — struct + iterator
  types [verified-by-code]
- `source/src/include/lib/ilist.h:300-450` — operations
  (init / push / delete / iterate)
- `knowledge/data-structures/pgproc-fields.md` — PGPROC
  contains multiple dlist_node fields

## The two structs

```c
typedef struct dlist_node
{
    dlist_node *prev;
    dlist_node *next;
} dlist_node;

typedef struct dlist_head
{
    dlist_node head;   /* sentinel; .next = first, .prev = last */
} dlist_head;
```

[verified-by-code `ilist.h:136-161`]

Two pointers per node. `dlist_head` carries one sentinel
node; an empty list is the sentinel pointing at itself
(circular) — branchless head/tail manipulation.

## Intrusive vs separate-cell

Compare with the `List *` (`list.h`) API:

```c
List *list = lappend(NIL, some_table);   /* separate ListCell allocated */
```

vs

```c
dlist_node node_in_my_table;             /* embedded; no extra alloc */
dlist_push_tail(&db->tables, &my_table->list_node);
```

[from-comment `ilist.h:74-90`]

The intrusive approach:
- **No per-node allocation** — the node is part of the
  containing struct.
- **No malloc cost on add/remove** — O(1) without an
  allocator.
- **Cache-friendly** — the node and the data share a cache
  line.
- **Container retrieval** via `dlist_container(type, field,
  node_ptr)` — back-out the containing struct pointer from
  a node pointer using `offsetof`.

The tradeoff: a struct can be in only ONE dlist of a given
field at a time. To live in multiple lists simultaneously,
embed multiple `dlist_node` fields.

## The canonical usage pattern

```c
typedef struct my_table { /* ... */ dlist_node list_node; } my_table;

dlist_head head;
dlist_init(&head);

dlist_push_head(&head, &create_table(db, "a")->list_node);
dlist_push_tail(&head, &create_table(db, "b")->list_node);

dlist_iter iter;
dlist_foreach(iter, &head)
{
    my_table *tbl = dlist_container(my_table, list_node, iter.cur);
    /* use tbl */
}

dlist_delete(&some_table->list_node);
```

[verified-by-code `ilist.h:74-108` example block]

## The two iterators

[verified-by-code `ilist.h:177-203`]

```c
typedef struct dlist_iter
{
    dlist_node *cur;
    dlist_node *end;
} dlist_iter;

typedef struct dlist_mutable_iter
{
    dlist_node *cur;
    dlist_node *next;     /* saved next */
    dlist_node *end;
} dlist_mutable_iter;
```

- `dlist_iter` — **read-only iteration**. Modifying the list
  during iteration is forbidden; the iterator state is
  invalid after.
- `dlist_mutable_iter` — saves `next` before yielding `cur`,
  so the current node can be `dlist_delete`d safely. Adjacent
  nodes still cannot be modified.

The `dlist_foreach_modify(miter, &head)` macro is what enables
"walk the list, deleting matching entries."

## The circular trick

[from-comment `ilist.h:146-148`]

> Non-empty lists are internally circularly linked. Circular
> lists have the advantage of not needing any branches in
> the most common list manipulations.

After `dlist_init(&head)`, `head.head.next = &head.head` and
`head.head.prev = &head.head`. Insertion at head / tail does
not need an "is the list empty?" branch — the sentinel is
always a valid neighbor.

## dlist_init can be skipped

[verified-by-code `ilist.h:347-368` push functions]

`dlist_push_head` and `dlist_push_tail` accept an
uninitialized `dlist_head` whose pointers are NULL; they
detect the case and initialize as needed. Lets shared-memory
structs avoid an init step when the surrounding memory was
zero-allocated.

## Counted variant: dclist

```c
typedef struct dclist_head
{
    dlist_head dlist;
    uint32     count;
} dclist_head;
```

[verified-by-code `ilist.h:212-216`]

When the caller wants "current size" in O(1) instead of O(n)
walk-and-count. Most uses don't need the count; only callers
that frequently query size should use `dclist`.

## The container-retrieval macro

```c
#define dlist_container(type, field, node) \
    ((type *)((char *)(node) - offsetof(type, field)))
```

(Canonical implementation; `ilist.h` exposes it.) Given a
pointer to the embedded `dlist_node` and the name of the
field inside the parent struct, pointer arithmetic recovers
the parent pointer.

This is the only macro that makes the intrusive approach
ergonomic — without it, every iteration would need bespoke
`(char *) ptr - offsetof(...)` arithmetic.

## Common review-time concerns

- **One `dlist_node` field per list membership.** Adding a
  struct to two lists requires two `dlist_node` fields.
- **`dlist_foreach` is read-only.** Modifying the list
  during iteration corrupts the iterator state.
- **`dlist_foreach_modify`'s `next` is saved BEFORE yielding
  `cur`** — safe to delete `cur` in the loop body, NOT safe
  to insert/delete adjacent nodes.
- **A removed node's pointers are stale** unless
  `dlist_delete_thoroughly` is used (which sets prev/next to
  NULL). Compare `dlist_node_is_detached(node)` (uses the
  NULL sentinel).
- **Shared-memory dlists** — the `dlist_head` and every
  `dlist_node` in the list must live in shared memory; mixing
  shared and process-local memory in one list corrupts other
  backends' view.

## Invariants

- **[INV-1]** Intrusive: each `dlist_node` field allows ONE
  list membership.
- **[INV-2]** Empty list = sentinel pointing at itself
  (circular).
- **[INV-3]** `dlist_init` optional if surrounding memory
  is zero-initialized.
- **[INV-4]** `dlist_foreach` forbids list modification;
  `dlist_foreach_modify` permits deleting the current node.
- **[INV-5]** Container retrieval via
  `dlist_container(type, field, node)`; offsetof arithmetic.

## Useful greps

- All dlist consumers:
  `grep -RIn 'dlist_head\|dlist_node' source/src/backend | wc -l`
- The pattern in shared memory:
  `grep -RIn 'dlist_head' source/src/include/storage | head -20`
- dclist (counted) usage:
  `grep -RIn 'dclist_head\|dclist_count' source/src/backend | head -10`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/lib/ilist.h`](../files/src/include/lib/ilist.h.md) | 130 | struct + iterator types |
| [`src/include/lib/ilist.h`](../files/src/include/lib/ilist.h.md) | 300 | operations (init / push / delete / iterate) |
| [`src/include/lib/ilist.h`](../files/src/include/lib/ilist.h.md) | — | full API + macros |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/pgproc-fields.md` — PGPROC
  has multiple dlist_node fields for proc lists.
- `knowledge/idioms/list-traversal-conventions.md` —
  companion: PG's two list APIs (List* vs dlist*) and when
  to pick each.
- `knowledge/subsystems/storage-buffer.md` — buffer free
  list is a dlist in shared memory.
- `knowledge/subsystems/storage-ipc.md` — async-notify
  queues and SI message rings use dlist variants.
- `.claude/skills/coding-style/SKILL.md` — list-API choice
  is a style decision; List* for parser/planner, dlist* for
  storage / IPC.
- `source/src/include/lib/ilist.h` — the full API + macros.
