# `src/backend/lib/ilist.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~130
- **Source:** `source/src/backend/lib/ilist.c`

Intrusive doubly- and singly-linked list helpers. Almost everything
lives as inline functions in `lib/ilist.h`; this `.c` file only holds
the rarely-used routines too big to inline: `slist_delete` (O(n) search
for a node) plus the `dlist_check`/`slist_check`/`dlist_member_check`
verifiers gated on `ILIST_DEBUG`. The header NOTES section explicitly
says "this file only contains functions that are too big to be
considered for inlining. See ilist.h for most of the goodies."
[verified-by-code]

The intrusive (embedded `dlist_node`/`slist_node` inside the caller's
struct) shape is the key reason this is heavily used: List/lappend is
non-intrusive and allocates; `dlist_*` allocates nothing, so it's the
preferred queue/list primitive inside lwlock-protected shmem and hot
backend loops. [inferred from idiom-prevalence]

## API / entry points

- `slist_delete(slist_head *, slist_node *)` — O(n) deletion when you
  don't already have a back-pointer. Asserts the node is in the list;
  callers with a back-pointer should use `slist_delete_current()` from
  the header. [verified-by-code §ilist.c:30]
- `dlist_member_check(const dlist_head *, const dlist_node *)`,
  `dlist_check(const dlist_head *)`, `slist_check(const slist_head *)`
  — debug-only integrity checks; compiled out unless `ILIST_DEBUG` is
  defined. `dlist_check` walks both directions and validates
  `cur->prev->next == cur` etc. [verified-by-code §ilist.c:54-129]

## Notable invariants / details

- `dlist_head.head` is the sentinel; an uninitialized (all-zero) head
  is a valid empty list — `dlist_check` returns OK if both pointers
  are NULL. [verified-by-code §ilist.c:84] This is the reason
  `dlist_head dlist = {0};` static initialization works.

## Potential issues

- None observed. File is short, stable since 2013-era refactor.
