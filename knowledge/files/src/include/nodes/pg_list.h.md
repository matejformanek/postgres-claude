# pg_list.h

- **Source:** `source/src/include/nodes/pg_list.h` (718 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## Purpose

Public interface to the `List` data structure. **Despite the
cons-cell vocabulary, the implementation is an expansible flat
array.** `:6-12` `[from-comment]`

## Types `:45-62`

```c
typedef union ListCell {
    void          *ptr_value;
    int            int_value;
    Oid            oid_value;
    TransactionId  xid_value;
} ListCell;

typedef struct List {
    NodeTag    type;             /* T_List / T_IntList / T_OidList / T_XidList */
    int        length;
    int        max_length;
    ListCell  *elements;         /* re-allocatable array */
    ListCell   initial_elements[FLEXIBLE_ARRAY_MEMBER];
} List;
```

## Invariants

- **Empty list ≡ NIL ≡ `(List *) NULL`.** A non-NIL List has
  `length >= 1`. `:64-68` `[from-comment]`
- The header is **stable** while the list is non-NIL; the `elements`
  array may move on resize.
- `elements == initial_elements` means the cells live in the same
  palloc chunk as the header (the common case for short lists).

## Inline accessors `:127-156`

- `list_head(l)` / `list_tail(l)` / `list_second_cell(l)` — NULL-safe.
- `list_length(l)` — O(1), NULL-safe (returns 0 for NIL).
- `list_nth_cell(l, n)` / `list_last_cell(l)` — assert-checked.
- `list_nth(l, n)` / `_int` / `_oid` — O(1) (array under the hood).
- `list_cell_number(l, c)` — index of cell `c`.
- `lnext(l, c)` — next ListCell or NULL.

## Cell-data macros `:172-202`

`lfirst(lc)` = `(lc)->ptr_value`. **lfirst takes a ListCell, not a
List** — historical wart from the cons-cell era. To get the first
data of a List, use `linitial(l)`. Family: `linitial`, `lsecond`,
`lthird`, `lfourth`, `llast`, each with `_int`, `_oid`, `_xid` (for
llast), and `_node(type, l)` for asserted node casts.

## Constructors `:208-302`

- `list_make_ptr_cell(v)` / `_int` / `_oid` / `_xid` — build one
  ListCell value.
- `list_make1(x)` … `list_make5(x1..x5)` — fixed-size literal lists
  of pointers. Variants `_int`, `_oid`, `_xid`.

## Iteration `:386-629`

### `foreach(cell, lst)` `:405-411`

Expands to a for-loop over indices in a hidden state struct named
`<cell>__state`. Hygiene rules `:386-403`:

- `cell` is NULL after normal exit; an early `break` leaves it at
  the current cell.
- Appending to the tail mid-iteration is safe (new cells will be
  visited).
- Deleting the current cell mid-iteration: only via
  `foreach_delete_current(lst, cell)` `:423-424`, which adjusts the
  loop index. The lst pointer must be reassigned: `mylist =
  foreach_delete_current(mylist, cell);`. The `cell` pointer is
  invalid for the rest of the iteration.
- Other insertions/deletions during iteration are undefined behavior
  (cells may be skipped or revisited).
- `foreach_current_index(cell)` `:435` gets the current zero-based
  index.

### `for_each_from(cell, lst, N)` `:446-461`

Like `foreach` but starts at index N.

### `for_each_cell(cell, lst, initcell)` `:470-485`

Start at a specific ListCell.

### Typed without external ListCell `:501-536`

- `foreach_ptr(type, var, lst)`
- `foreach_int(var, lst)` / `foreach_oid` / `foreach_xid`
- `foreach_node(type, var, lst)` — adds `castNode(type, ...)` assert

These declare loop-scoped variables and use a clever two-loop trick
to declare two different types. Trade-off: can't detect early-break
by checking `var` after the loop.

### Multi-list `:550-629`

- `forboth(c1, l1, c2, l2)` — walk two lists; stops at the shorter.
- `for_both_cell(c1, l1, ic1, c2, l2, ic2)` — both starting from
  given cells.
- `forthree`, `forfour`, `forfive`.

## External functions (in `list.c`)

Three big buckets — full enumeration in
`knowledge/files/src/backend/nodes/list.c.md`:

- **Mutators** that return the (possibly new) list: `lappend*`,
  `list_insert_nth*`, `lcons*`, `list_concat[_copy]`, `list_truncate`,
  `list_delete*`, `list_append_unique*`, `list_concat_unique*`,
  `list_deduplicate_oid`. All annotated `pg_nodiscard`.
- **Observers**: `list_member*`, `list_union*`, `list_intersection*`,
  `list_difference*`.
- **Maintenance**: `list_free`, `list_free_deep`, `list_copy*`,
  `list_sort` (+ `list_int_cmp`, `list_oid_cmp`).

## Cross-references

- Implementation: `source/src/backend/nodes/list.c`
- Idiom doc: `knowledge/idioms/node-types-and-lists.md`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/list-traversal-conventions.md](../../../../idioms/list-traversal-conventions.md)

- [idioms/node-types-and-lists.md](../../../../idioms/node-types-and-lists.md)