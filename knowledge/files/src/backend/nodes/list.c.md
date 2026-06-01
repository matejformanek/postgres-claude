# list.c

- **Source:** `source/src/backend/nodes/list.c` (1709 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## Purpose

Implementation of the generic `List` API declared in
`source/src/include/nodes/pg_list.h`. Despite the cons-cell vocabulary
(`lappend`, `lcons`, `lfirst`, ...), the implementation is an expansible
**flat array** of `ListCell` (a union). `:27-40` `[from-comment]`

## Representation invariants

- Empty list ≡ `NIL` (a NULL pointer). A non-NIL `List` is guaranteed
  `length >= 1`. `:67-68 pg_list.h` `[from-comment]`
- `List` struct holds `length`, `max_length`, and a pointer `elements`
  to a re-allocatable ListCell array. The header allocation includes a
  `initial_elements[]` flexible array so small lists are one palloc
  (header + cells together). `:53-62 pg_list.h` `[verified-by-code]`
- `IsPointerList(l)` / `IsIntegerList(l)` / `IsOidList(l)` /
  `IsXidList(l)` treat NIL as a valid list of any type. `:55-58`
  `[verified-by-code]`
- `check_list_invariants` (assert-only) verifies `length > 0`,
  `length <= max_length`, valid NodeTag. `:64-78` `[verified-by-code]`

## Allocation strategy `:90-145`

- `new_list(type, min_size)` always rounds `max_size` up to a power of
  two minus the LIST_HEADER_OVERHEAD, with a floor of 8 ListCell
  units. This lets short fixed-length lists fit in one allocation and
  amortizes growth. `:108-127` `[verified-by-code]`
- `enlarge_list` either (a) moves cells out of `initial_elements[]`
  into a separately palloc'd block in the **same MemoryContext** as the
  header (using `MemoryContextAlloc(GetMemoryChunkContext(list), ...)`)
  or (b) `repalloc`s the existing array. `:176-226` `[verified-by-code]`
- The List header is **never** moved once allocated, so a stable
  `List *` pointer survives any number of resizes. The `elements`
  array may move. `:179-185` `[from-comment]`

## DEBUG_LIST_MEMORY_USAGE `:27-45, :108-135`

Forces every list-mutating operation to reallocate cells so that any
caller still holding a pre-mutation `ListCell *` will trip a Valgrind
read or hit poisoned memory. Auto-enabled under `USE_VALGRIND`. Cells
are clobbered with `wipe_mem`/`VALGRIND_MAKE_MEM_NOACCESS` when
abandoned.

## Function map

| Line | Function | Notes |
|---|---|---|
| 90 | `new_list` | static; sizes header+cells in one palloc |
| 155 | `enlarge_list` | static; grows the array, possibly moving it |
| 235-296 | `list_make1_impl` … `list_make5_impl` | constructor variants for short literals |
| 305 | `new_head_cell` / `new_tail_cell` | static; memmove for prepend, no-op for append |
| 339 | `lappend` | the workhorse; **must reassign return value** |
| 357/375/393 | `lappend_int` / `_oid` / `_xid` | typed variants |
| 415 | `insert_new_cell` | static helper for insertion at arbitrary pos |
| 439/453/467 | `list_insert_nth` / `_int` / `_oid` | O(N) insertion |
| 495/513/531 | `lcons` / `_int` / `_oid` | prepend; O(N), prefer `lappend` |
| 561 | `list_concat` | splice `list2` cells into `list1`; `list2` becomes dangling |
| 598 | `list_concat_copy` | non-destructive variant |
| 631 | `list_truncate` | shrink to new_size |
| 661/682 | `list_member` / `_ptr` | linear scan; `list_member` uses `equal()` |
| 702/722/742 | `list_member_int` / `_oid` / `_xid` | typed |
| 767 | `list_delete_nth_cell` | core deletion (memmove tail down); frees whole list if it goes empty |
| 841 | `list_delete_cell` | thin wrapper |
| 853 | `list_delete` | linear-scan + `equal()` |
| 872 | `list_delete_ptr` | linear-scan pointer eq |
| 943/957 | `list_delete_first` / `_last` | O(N) / O(1) |
| 983 | `list_delete_first_n` | chop N elements off the head |
| 1066-1170 | `list_union*` | de-duplicating union, O(N·M) |
| 1174-1234 | `list_intersection*` | O(N·M) |
| 1237-1340 | `list_difference*` | O(N·M) |
| 1343-1402 | `list_append_unique*` | append iff not already member |
| 1405-1493 | `list_concat_unique*` | concat skipping dupes |
| 1495 | `list_deduplicate_oid` | sort + collapse, used for OIDs |
| 1520 | `list_free_private` | static; common impl for `list_free` / `list_free_deep` |
| 1546/1560 | `list_free` / `list_free_deep` | latter also pfrees pointed-to objects |
| 1573-1672 | `list_copy*` | shallow / head / tail / deep |
| 1674 | `list_sort` | qsort over the elements array via `list_sort_comparator` |
| 1691/1703 | `list_int_cmp` / `list_oid_cmp` | ready-made comparators |

## `foreach` semantics (declared in `pg_list.h:386-411`)

The `foreach(cell, lst)` macro expands to a `for` loop over indices
into `elements[]`, with a hidden state struct `cell##__state`. Key
consequences `[from-comment pg_list.h:394-403]`:

- Appending to the list **during** iteration is safe; new cells are
  visited.
- Deleting the current cell is only safe via
  `foreach_delete_current(lst, cell)`, which adjusts the iterator
  index. `pg_list.h:423-424` `[verified-by-code]`
- Inserting or deleting other cells during iteration is undefined.
- `cell` is NULL after a normal loop exit; `break` leaves it at the
  current cell.

There is also `foreach_ptr`, `foreach_int`, `foreach_oid`,
`foreach_xid`, `foreach_node(type, var, lst)`, `forboth`, `forthree`,
`forfour`, `forfive`, `for_each_from`, `for_each_cell`.
`pg_list.h:501-629` `[verified-by-code]`

## API hygiene rules

- **Always reassign** the return value of mutating ops:
  `mylist = lappend(mylist, x);`. Forgetting this leaks the result if
  the input was NIL (the function returned a freshly allocated header)
  or if the array was relocated. The header `pg_nodiscard` annotation
  catches some misuses. `pg_list.h:643-705` `[verified-by-code]`
- `list_concat(a, b)` returns `a` enlarged by `b`'s contents. `b`'s
  header is left dangling — never use `b` afterward. `:561-596`
  `[from-comment]`
- Lists are typed at runtime via `type` field. Mixing `lappend` with
  an `IntList` will fail an assertion. `:341, 359, 377, 395`
  `[verified-by-code]`

## Cross-references

- Header: `source/src/include/nodes/pg_list.h`
- Idiom: `knowledge/idioms/node-types-and-lists.md`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
