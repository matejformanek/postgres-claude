# Node types and Lists

PostgreSQL represents every tree it cares about — raw parse trees, analyzed
`Query` trees, planner `Path` trees, `Plan` trees, executor state trees —
as **tagged C structs** linked by `Node *` pointers, and linked lists of those
nodes as `List *`. Internalize these two patterns and most of the backend
reads the same way.

## The NodeTag scheme

Every node type is a struct whose first field is either `NodeTag type;` or
another node struct (which itself starts with `NodeTag`, recursively). The
tag identifies the runtime type — C "inheritance by convention".
[verified-by-code: `src/include/nodes/nodes.h:134-137`]

```c
typedef struct Node {
    NodeTag type;
} Node;
```

The tag values live in the generated header `nodes/nodetags.h`, included into
`enum NodeTag` [verified-by-code: `nodes.h:26-31`]. **You never hand-edit
nodetags.h.** `gen_node_support.pl` scans the headers listed in
`@all_input_files` and emits one `T_Foo` per struct found, in a stable order
[verified-by-code: `src/backend/nodes/gen_node_support.pl:53-77`].

Because the enum order is stable but not fixed, **inserting a new node type
renumbers later tags** — fine for in-memory use, but if any of those tags can
appear in serialized trees in the catalogs you must bump `CATALOG_VERSION_NO`
[from-README: `src/backend/nodes/README:107-115`].

### Creating, identifying, downcasting

- `makeNode(Foo)` → allocates `sizeof(Foo)` with `palloc0` and sets `type = T_Foo`. The zero-init means every field starts NULL / 0 / false [verified-by-code: `nodes.h:149-161`].
- `IsA(p, Foo)` → `nodeTag(p) == T_Foo`. Used everywhere as a runtime type test [verified-by-code: `nodes.h:164`].
- `castNode(Foo, p)` → like `(Foo *) p` but with an `Assert(IsA(p, Foo))` under `USE_ASSERT_CHECKING`. Prefer this over a raw C cast [verified-by-code: `nodes.h:173-183`].
- `nodeTag(p)` → reads the tag without a cast.

### Generated support functions

For each node, `gen_node_support.pl` emits members of five support families,
all of which `#include` `.funcs.c` files into the dispatch tables in
`copyfuncs.c` / `equalfuncs.c` / `outfuncs.c` / `readfuncs.c` /
`queryjumblefuncs.c` [from-README: `src/backend/nodes/README:46-58`]:

- `copyObject(p)` — deep copy. Each pointer field is recursively copied. Scalar fields straight-assigned.
- `equal(a, b)` — deep structural compare.
- `nodeToString(p)` — serialize to a Lisp-ish text form. Used to store parse trees in catalogs (e.g. `pg_rewrite.ev_action`) and to ship `PlannedStmt` to parallel workers.
- `stringToNode(s)` — inverse, used by the rewriter when loading rules and by parallel workers when receiving a plan.
- `JumbleQuery(query)` — produces the query-id used by `pg_stat_statements`.

You influence what gets emitted via `pg_node_attr(...)` on the struct (or on
individual fields). The list is in `nodes.h:43-125`. Common ones:
`custom_copy_equal`, `custom_read_write`, `no_copy_equal`, `nodetag_only`,
`equal_ignore`, `query_jumble_ignore`, `array_size(otherfield)`.

### Why this matters

The roundtrip `copyObject(stringToNode(nodeToString(p)))` is load-bearing for:
- **Plan caching**: cached plans live as a node tree that gets copied per
  execution so the executor can scribble on it.
- **Rules / views**: `pg_rewrite` stores the parse tree as the text form;
  every relation open re-parses it via `stringToNode`.
- **Parallel query**: the leader sends its `PlannedStmt` to workers as a
  serialized string [from-README: `nodes/README:25-32`].

If you add a node type that ends up in any of those paths and forget to
keep the read/write funcs in sync, you silently corrupt plans or rules.

## The List family

Once upon a time Postgres was Lisp. The cons-cell vocabulary survived even
after the rewrite to arrays [from-comment: `pg_list.h:6-12`]. Four list
flavors, distinguished by their own NodeTag:

- `T_List` — list of `void *` (almost always Node pointers)
- `T_IntList` — list of `int`
- `T_OidList` — list of `Oid`
- `T_XidList` — list of `TransactionId` (incomplete API surface)
[verified-by-code: `pg_list.h:19-27`]

Critical invariant: **the empty list is `NIL` (a null pointer)**, never an
allocated empty header. A non-NIL `List *` always has `length >= 1`. Code
that ignores this either crashes or silently treats "empty" as "not present"
[from-comment: `pg_list.h:64-68`].

`ListCell` is a union so the same machinery serves all four flavors
[verified-by-code: `pg_list.h:45-51`]. The cells live in a single
re-allocatable array `elements[]`; appends usually do not reallocate, and the
header is allocated together with the initial cells via FLEXIBLE_ARRAY_MEMBER
[verified-by-code: `pg_list.h:53-62`].

### The API you actually use

Construction:
- `NIL` — empty.
- `list_make1(x)`, `list_make2(x,y)`, ... `list_make5` — short literal lists.
- `lappend(list, ptr)` / `lappend_int(list, i)` / `lappend_oid(list, oid)` — append, returning the (possibly relocated) header. **Always reassign**: `list = lappend(list, x);`. Forgetting this is a classic bug because if the list was NIL you just leaked the only pointer.
- `lcons(ptr, list)` — prepend. O(N), prefer `lappend`.
- `list_concat(a, b)` — splice b onto a, returns a. b's cells are physically copied into a; b itself becomes a dangling header (don't reuse it).

Access:
- `list_length(l)` — O(1), safe on NIL.
- `linitial(l)`, `lsecond(l)`, `lthird(l)`, `lfourth(l)`, `llast(l)` plus `_int` / `_oid` variants for the integer flavors [verified-by-code: `pg_list.h:178-201`].
- `list_nth(l, n)` — O(1) (it's really an array under the hood).
- `lfirst(lc)` / `lfirst_int(lc)` / `lfirst_oid(lc)` — deref a `ListCell *`. `lfirst_node(Foo, lc)` adds a `castNode(Foo, ...)` assertion.

Iteration — `foreach`:

```c
ListCell *lc;
foreach(lc, mylist)
{
    Foo *x = lfirst_node(Foo, lc);
    ...
}
```

`foreach` expands to a `for` loop over indices into `elements[]`
[verified-by-code: `pg_list.h:405-411`]. **Hygiene rules** [from-comment:
`pg_list.h:385-403`]:

- `lc` is NULL after normal exit; an early `break` leaves it at the current
  cell.
- **Do not** mutate the list during iteration except in two narrow ways:
  - Appending to the *end* is safe — newly-appended cells will be visited.
  - Deleting the *current* cell only via `foreach_delete_current(lst, lc)`,
    which adjusts the loop index. Reassign the returned `List *`:
    `mylist = foreach_delete_current(mylist, lc);`. After this call, `lc`
    is invalid for the rest of the iteration.
- Inserting / deleting other cells during iteration is undefined — current
  semantics will skip or revisit elements.

Specialized iterators: `forboth(lc1, l1, lc2, l2)`, `forthree`, `forfour`,
`forfive` walk multiple lists in lockstep; `for_each_from(lc, l, N)` starts
mid-list.

## Lists of what?

The list type is *not* statically typed in C. A `List *` storing
`RangeTblEntry *` looks identical to one storing `Const *`. Look at the
field's comment / siblings in the same struct for the implied element type:
`fromlist`, `targetList`, `rtable`, `quals` — every Query field carrying a
list documents its element type. `lfirst_node(Foo, lc)` is your runtime
safety net.

## Value nodes (when "an integer" needs to live in a List)

To put a literal int / float / string into a `List *` you wrap it in one of
the value-node structs from `src/include/nodes/value.h` — `Integer`, `Float`,
`Boolean`, `String`, `BitString`. Each is just `NodeTag type;` plus the
payload field; constructors are `makeInteger(i)`, `makeString(s)`, etc.
Accessors `intVal(v)`, `strVal(v)`, `boolVal(v)`, `floatVal(v)` cast and
extract [verified-by-code: `value.h:79-88`]. The lexer emits these for SQL
literals; the parser passes them around. Once upon a time there was a single
`Value` union — hence the filename — but it was split into per-type structs.

## Call sites
<!-- callsites:auto -->

*Auto-extracted via glossary cross-reference of backticked C identifiers in this doc.*
*Refresh via `scripts/populate-idiom-callsites-v2.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`contrib/pg_stat_statements/pg_stat_statements.c`](../files/contrib/pg_stat_statements/pg_stat_statements.c.md) | — | `pg_stat_statements` — The contrib extension that hooks the planner, executor, and ProcessUtility paths to aggregate per-(userid, dbid, quer |
| [`src/backend/access/transam/varsup.c`](../files/src/backend/access/transam/varsup.c.md) | — | `TransactionId` — A 32-bit transaction identifier (XID) stamped into each tuple's xmin/xmax to drive MVCC visibility; XIDs are assigned |
| [`src/include/catalog/pg_rewrite.h`](../files/src/include/catalog/pg_rewrite.h.md) | — | `pg_rewrite` — The system catalog with one row per rewrite rule (CREATE RULE), holding the rule's event type, enable flag, INSTEAD f |
| [`src/include/nodes/pg_list.h`](../files/src/include/nodes/pg_list.h.md) | — | `ListCell` — One element of PostgreSQL's List |
| [`src/include/nodes/plannodes.h`](../files/src/include/nodes/plannodes.h.md) | — | `Plan` — The finished, executable tree produced by `create_plan` from the chosen Path — a tree of plan nodes (`SeqScan`, `Hash |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-plan-node`](../scenarios/add-new-plan-node.md)
- [`add-new-shared-memory-region`](../scenarios/add-new-shared-memory-region.md)
- [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md)
- [`add-startup-hook`](../scenarios/add-startup-hook.md)

<!-- /scenarios:auto -->
