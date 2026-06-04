# `src/fe_utils/simple_list.c`

- **File:** `source/src/fe_utils/simple_list.c` (194 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Minimal singly-linked list facilities for frontend code, for lists of OIDs,
strings, and void pointers. The file comment is explicit that this is a
"very primitive" cousin of the backend `List` API (`pg_list.h`), sufficient for
needs like pg_dump's `--table`/`--exclude-table` accumulation. Each list is a
`{head, tail}` pair (defined in the header) appended to in O(1); membership is a
linear O(n) scan. Frontend memory rules apply: cells come from `pg_malloc`/
`pg_malloc_object` and are released with `pg_free`/`free`. [verified-by-code:
includes + comment at `simple_list.c:4-19`]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `simple_oid_list_append` | :26 | Append an `Oid` cell to the tail. |
| `simple_oid_list_member` | :45 | Linear search for an `Oid`; returns bool. |
| `simple_string_list_append` | :63 | Append a string; the value is **copied** into the cell. |
| `simple_string_list_member` | :87 | Linear search for a string; sets the first match's `touched` flag and returns bool. |
| `simple_oid_list_destroy` | :106 | Free all OID cells. |
| `simple_string_list_destroy` | :125 | Free all string cells. |
| `simple_string_list_not_touched` | :144 | Return the first cell whose `touched` flag is still false, else NULL. |
| `simple_ptr_list_append` | :162 | Append a `void *` cell (pointer not owned/copied). |
| `simple_ptr_list_destroy` | :181 | Free the list cells but NOT the pointed-to objects. |

## Internal landmarks

- Append idiom is identical across all three list types (`:34`–`:38`, `:74`–`:78`, `:170`–`:174`): `if (list->tail) tail->next = cell; else head = cell; tail = cell;`. Maintains both head and tail for O(1) append.
- `simple_string_list_append` allocates a flexible-array cell sized `offsetof(SimpleStringListCell, val) + strlen(val) + 1` and `strcpy`s the value in (`:67`–`:72`); it also initializes `touched = false`. This is the only list that copies its payload.
- `simple_oid_list_append` (`:30`) and `simple_ptr_list_append` (`:166`) use `pg_malloc_object` (typed single-object allocation) and store the value/pointer by value.
- The `touched` mechanism (`simple_string_list_member` sets it at `:95`, `simple_string_list_not_touched` reads it at `:150`) lets callers detect command-line items that never matched anything — pg_dump uses this to warn about a `--table=foo` pattern that matched no table.

## Invariants & gotchas

- **String lists copy; OID and pointer lists do not.** `simple_string_list_append` copies the string (`:59` comment: "need not survive past the call"), but `simple_ptr_list_append` stores the raw pointer and the caller must keep it valid (`:159` comment). [from-comment] `:59`, `:159`
- **`simple_ptr_list_destroy` frees only the cells, never the referents** (`:178` comment) — freeing the pointed-to objects is the caller's responsibility. The OID/string destroy functions fully free their cells (string payload is inline, so freeing the cell frees the string). [verified-by-code] `:181`, `:106`, `:125`
- **None of the `*_destroy` functions reset `list->head`/`list->tail` to NULL.** They walk and free the cells but leave the `{head, tail}` struct fields dangling. A list struct must not be reused after destroy without re-zeroing it. [verified-by-code] `:106`–`:119`, `:125`–`:138`, `:181`–`:194`
- **Membership is O(n) linear scan** for all variants — these lists are not meant for large or hot-path sets. [from-comment] `:5`
- `simple_string_list_member` sets `touched` as a **side effect of a lookup**, not only on explicit marking; a membership test doubles as "mark as used." [verified-by-code] `:95`

## Cross-references

- `source/src/include/fe_utils/simple_list.h` — the `SimpleOidList`/`SimpleStringList`/`SimplePtrList` struct + cell definitions and the `touched`/`val` flexible-array layout.
- `source/src/bin/pg_dump/pg_dump.c` and `pg_backup_archiver.c` — heavy consumers (table/schema include-exclude lists; the `touched`/`not_touched` "no match" warning).
- `source/src/include/nodes/pg_list.h` — the richer backend `List` API this deliberately does not replicate.

## Confidence tag tally

- `[verified-by-code]` × 5
- `[from-comment]` × 3
- `[inferred]` × 0
