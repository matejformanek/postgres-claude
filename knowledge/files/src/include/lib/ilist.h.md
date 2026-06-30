# `src/include/lib/ilist.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** ~1200 (large because of many inlines + extensive
  doc comment block)

## Role

Embedded/intrusive linked lists — **the workhorse list type in
the backend**, used in preference to the heap-allocated `List *`
(`pg_list.h`) wherever the set of containing objects is known and
list links can live inside them. No memory management at all;
caller owns the storage. Used heavily by lock manager
(`PROCLOCK` queues), proc array, plan trees with chained state,
walsender / walreceiver wait queues, etc.
[verified-by-code] `source/src/include/lib/ilist.h:1-43`

## API surface

Three concrete list types (line 136-280 of header):

- `dlist_head` / `dlist_node` — doubly-linked, no count
- `dclist_head` — doubly-linked **with count** (PG_UINT32_MAX cap)
- `slist_head` / `slist_node` — singly-linked

All three expose the same iterator-style API. Key macros:

- `DLIST_STATIC_INIT(name)`, `DCLIST_STATIC_INIT(name)`,
  `SLIST_STATIC_INIT(name)` — initializers; lines 281-283
- `dlist_container(type, member, ptr)` — back-cast iter cursor
  to containing struct (lines 593-)
- `dlist_foreach` / `dlist_foreach_modify` /
  `dlist_reverse_foreach` — loop macros; lines 623, 640, 654
- `dclist_count(head)` — only on dclist
- mirror APIs `slist_*`

## Invariants

- INV-1: Empty dlist can be EITHER `next == NULL` OR
  `next/prev → &head` (circular). Both forms are valid; circular
  is preferred because branch-free ops are possible.
  [from-comment] `source/src/include/lib/ilist.h:34-43`
- INV-2: `dlist_node` must be embedded as a field of the
  containing struct (not necessarily first). `dlist_container`
  uses `offsetof` to recover the outer pointer.
- INV-3: dclist count must not overflow `uint32`; caller-enforced.
  [from-comment] line 21-23.
- INV-4: No memory ops anywhere — caller owns node lifetime.

## Notable internals

- Heavy use of `static inline` to avoid call overhead in
  hot-path code (lock manager).
- Debug build adds `dlist_check` / `dlist_member_check` /
  `slist_check` (line 292-304).

## Trust boundary (Phase D)

None directly. Indirectly: when a `dlist` holds shared-memory
items (e.g. `PROCLOCK` per `LOCK`), the *containing* struct's
trust model applies; ilist itself adds nothing.

## Cross-refs

- `knowledge/files/src/include/nodes/pg_list.h.md` (if exists) —
  the heap-allocated `List *` alternative
- `knowledge/subsystems/storage-lmgr.md` — heavy ilist consumer

## Issues

None — pristine.

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/dlist-node.md](../../../../data-structures/dlist-node.md)
