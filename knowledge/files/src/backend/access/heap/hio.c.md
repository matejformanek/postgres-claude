# hio.c

- **Source path:** `source/src/backend/access/heap/hio.c`
- **Lines:** 884
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `hio.h`, `heapam.c` (consumer), `storage/freespace/*` (FSM), `storage/buffer/bufmgr.c`

## Purpose

Implements heap I/O placement: place a prepared tuple on a locked buffer (`RelationPutHeapTuple`), and the much harder problem of *finding* a buffer with enough free space, possibly extending the relation, while juggling FSM, VM pins, and the lock-ordering rule when two buffers are involved (UPDATE moving tuple to a new page). [verified-by-code, hio.c:1-30]

## Top-of-file comment
> "POSTGRES heap access method input/output code." (terse)

## Public surface (non-static functions)

- `RelationPutHeapTuple(Relation, Buffer, HeapTuple, bool token)` (hio.c:35) — Add tuple to the locked page; set `tuple->t_self`; fix `t_ctid` (unless `token`).
- `RelationGetBufferForTuple(Relation, Size len, Buffer otherBuffer, uint32 options, BulkInsertStateData*, Buffer *vmbuffer, Buffer *vmbuffer_other, int num_pages)` (hio.c:500) — Return a buffer with ≥ `len` bytes free, exclusive-locked. Optionally cooperate with `otherBuffer` (UPDATE source page) under a buffer-locking ordering rule (lower block-number first) to avoid deadlock.

## Static helpers

- `ReadBufferBI` (hio.c:86) — `ReadBufferExtended` wrapper that respects `BulkInsertState.strategy` if present.
- `GetVisibilityMapPins` (hio.c:138) — Acquires VM pins for one or two heap blocks, honouring the "lower block first" rule and dropping the heap buffer lock(s) if a VM page must be read.
- `RelationAddBlocks` (hio.c:236) — Bulk-extend the relation by `num_pages` (configurable; tries to grow geometrically under contention).

## Key types / structs
None defined here; uses `BulkInsertStateData` from `hio.h`. [verified-by-code]

## Key invariants and locking

- **`RelationPutHeapTuple` MUST hold `BUFFER_LOCK_EXCLUSIVE` on `buffer`.** The comment at hio.c:35-38 is emphatic: "EREPORT(ERROR) IS DISALLOWED HERE! Must PANIC on failure!!!" — because it's inside the critical section of an insertion. [from-comment, hio.c:35-38] **This is the canonical example of "no ereport inside critical section" in heap code.**
- Lock-ordering rule for two-buffer cases (UPDATE): always lock the buffer with the lower block number first. `GetVisibilityMapPins` and `RelationGetBufferForTuple` both implement this. [verified-by-code]
- The FSM-based search may return a buffer that no longer has the claimed free space (concurrent inserters); the loop re-checks after locking and re-tries with FSM if not. [verified-by-code, inferred from standard PG pattern]
- Extension lock: held only during the actual `smgrextend` call window. The bulk-extension path (`RelationAddBlocks`) extends multiple pages under one lock acquisition to amortise contention. [verified-by-code]
- Speculative insert: `RelationPutHeapTuple(token=true)` keeps the spec-token in `t_ctid`; if `token=false`, `t_ctid` is overwritten with the actual self-TID. [verified-by-code, hio.c:79-86]

## Functions of note

- `RelationGetBufferForTuple` (hio.c:500) — The complex one. Looks first at `BulkInsertState.current_buf`, then `RelData.targetBlock`, then FSM (`GetPageWithFreeSpace`), and as a last resort extends the relation. Coordinates with `otherBuffer` for cross-page UPDATEs (block-number ordering). Handles the FSM-staleness retry loop. [verified-by-code]
- `RelationAddBlocks` (hio.c:236) — Implements the post-PG 16 bulk-extension strategy: extend by an exponentially growing batch, register the extra blocks via FSM so concurrent inserters can pick them up. Uses `smgrzeroextend`. Updates `BulkInsertState.{next_free, last_free, already_extended_by}`. [verified-by-code]
- `GetVisibilityMapPins` (hio.c:138) — Two-buffer VM pinning: drops both heap buffer locks if it needs to read a VM page (because VM read may block on I/O), then re-acquires in canonical order.
- `ReadBufferBI` (hio.c:86) — One-liner adapter so callers can pass `bistate` and have its strategy ring used implicitly.

## Cross-references

- `RelationGetBufferForTuple` called by `heap_insert` (heapam.c:2004), `heap_multi_insert` (heapam.c:2282), `heap_update` (heapam.c:3201). [verified-by-code]
- `RelationPutHeapTuple` called by the same three plus `rewriteheap.c::raw_heap_insert` (rewriteheap.c:597). [verified-by-code]
- Outbound: bufmgr, freespace.c (`GetPageWithFreeSpace`, `RecordPageWithFreeSpace`), visibilitymap.c, lmgr.c (extension lock).

## Open questions

- Exact rules under which `RelationAddBlocks` chooses its batch size (`already_extended_by` heuristic). [unverified]
- Whether `RelationGetBufferForTuple` ever returns a buffer with the VM not yet pinned (i.e., caller is responsible for VM after the fact in some paths). [unverified]

## Confidence tag tally
`[verified-by-code]=11 [from-comment]=2 [from-readme]=0 [inferred]=1 [unverified]=2`
