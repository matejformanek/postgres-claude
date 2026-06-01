# hio.h

- **Source path:** `source/src/include/access/hio.h`
- **Lines:** 62
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `hio.c` (implementations), `heapam.c` (the primary consumer — insert/update path)

## Purpose

Tiny header exposing two functions and one state struct that together make up the "where does the next heap tuple go" decision used by `heap_insert`, `heap_multi_insert`, and `heap_update`. `BulkInsertStateData` is shared between `heapam.c` and `hio.c` only (the typedef `BulkInsertState` is in `heapam.h`). [from-comment, hio.h:21-28]

## Top-of-file comment
> "POSTGRES heap access method input/output definitions." (terse)

## Public surface

- `extern void RelationPutHeapTuple(Relation relation, Buffer buffer, HeapTuple tuple, bool token);` (hio.h:54) — Place an already-prepared tuple at the specified, already-locked-and-extended buffer. Updates `tuple->t_self` to the actual TID. `token` flag = this is a speculative insertion (do not stomp on the spec token stored in t_ctid). [verified-by-code]
- `extern Buffer RelationGetBufferForTuple(Relation relation, Size len, Buffer otherBuffer, uint32 options, BulkInsertStateData *bistate, Buffer *vmbuffer, Buffer *vmbuffer_other, int num_pages);` (hio.h:56) — The hard one: find or extend a page with enough free space, taking the FSM, VM, and concurrent-extension considerations into account.

## Key types / structs

- `BulkInsertStateData` (hio.h:29) — Returned by `GetBulkInsertState`. Carries:
  - `strategy` — a BUFFER_USAGE_BULKWRITE access strategy ring (so a copy-in doesn't blow the shared buffer cache).
  - `current_buf` — last-used target page; if non-Invalid, we hold an extra pin on it.
  - `next_free`, `last_free`, `already_extended_by` — bulk-extension scratch state. The XXX comment notes these should probably migrate into `RelationData` alongside `targetBlock`. [from-comment, hio.h:38-50]

## Key invariants and locking

- `RelationPutHeapTuple` requires the caller to hold `BUFFER_LOCK_EXCLUSIVE` on `buffer`. The companion `hio.c` comment is blunter: "EREPORT(ERROR) IS DISALLOWED HERE! Must PANIC on failure!!!" (hio.c:35-38). [from-comment, hio.c:35-38]
- If `BulkInsertStateData.current_buf` is `!InvalidBuffer`, the holder owns one **extra** pin on that buffer (beyond any borrowed via parameters). [from-comment, hio.h:23-25]
- `RelationGetBufferForTuple`'s `vmbuffer` / `vmbuffer_other` out-params are pinned VM pages corresponding to the target heap blocks; the caller must release them. [inferred from signature and from hio.c usage]

## Functions of note

- `RelationGetBufferForTuple` — the heart of heap insertion. Strategy: try the relation's "target block" cached in RelData; consult FSM; possibly extend; handle the cross-buffer locking-order pitfall in UPDATE (otherBuffer ≠ target). Implementation at `hio.c:500`. [verified-by-code]
- `RelationPutHeapTuple` — pure mechanics: PageAddItem, set t_self, fix t_ctid if not speculative. [verified-by-code, hio.c:35-86]

## Cross-references

- Called by `heapam.c::heap_insert` (~line 2004), `heap_multi_insert` (~line 2282), and `heap_update` (~line 3201). [verified-by-code]
- `BulkInsertState` returned by `GetBulkInsertState` (heapam.c:1937) and freed by `FreeBulkInsertState`.

## Open questions
None — interface is small.

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=4 [from-readme]=0 [inferred]=1 [unverified]=0`
