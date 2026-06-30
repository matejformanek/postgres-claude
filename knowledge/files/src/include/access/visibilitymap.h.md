# visibilitymap.h

- **Source path:** `source/src/include/access/visibilitymap.h`
- **Lines:** 43
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `visibilitymap.c` (implementation, where the real comments live), `visibilitymapdefs.h` (the VISIBILITYMAP_ALL_VISIBLE / VISIBILITYMAP_ALL_FROZEN bit constants), `heapam.c`, `pruneheap.c`, `vacuumlazy.c` (consumers)

## Purpose

Public API for the per-relation visibility map (VM) fork. Two bits per heap page (`ALL_VISIBLE`, `ALL_FROZEN`) let consumers cheaply test "does this page need vacuuming?" / "are all tuples on this page frozen?" / "can index-only scan skip the heap fetch?". [from-comment]

## Top-of-file comment
> "visibility map interface" — terse; the substantial comment (the LOCKING and crash-safety discussion) lives in `visibilitymap.c`. [from-comment, visibilitymap.h:3-12]

## Public surface

- `#define VM_ALL_VISIBLE(r, b, v)` / `VM_ALL_FROZEN(r, b, v)` — convenience wrappers around `visibilitymap_get_status` (visibilitymap.h:24-27).
- `bool visibilitymap_clear(Relation rel, BlockNumber heapBlk, Buffer vmbuf, uint8 flags);` — clear specified bits; returns whether any bit actually changed.
- `void visibilitymap_pin(Relation rel, BlockNumber heapBlk, Buffer *vmbuf);` — pin VM page that maps heapBlk; extends the fork if needed.
- `bool visibilitymap_pin_ok(BlockNumber heapBlk, Buffer vmbuf);` — does the already-pinned `vmbuf` cover heapBlk?
- `void visibilitymap_set(BlockNumber heapBlk, Buffer vmBuf, uint8 flags, const RelFileLocator rlocator);` — set bits. Crucially, **does not WAL-log itself** — the operation that made the page all-visible is responsible for WAL.
- `uint8 visibilitymap_get_status(Relation rel, BlockNumber heapBlk, Buffer *vmbuf);` — read both bits.
- `void visibilitymap_count(Relation rel, BlockNumber *all_visible, BlockNumber *all_frozen);` — totals (used by pg_class stats).
- `BlockNumber visibilitymap_prepare_truncate(Relation rel, BlockNumber nheapblocks);` — drop VM pages no longer needed when heap is truncated.
- `BlockNumber visibilitymap_truncation_length(BlockNumber nheapblocks);` — compute number of VM blocks needed for an N-block heap.

## Key types / structs
None — uses `Buffer`, `BlockNumber`, `Relation` from elsewhere; bit constants in `visibilitymapdefs.h`. [verified-by-code, visibilitymap.h:17]

## Key invariants and locking

- VM is **conservative**: a set bit is authoritative; a clear bit means "unknown — might be all-visible, might not". [from-comment, visibilitymap.c:763-766]
- `ALL_FROZEN` may be set only when `ALL_VISIBLE` is also set for that page. [from-comment, visibilitymap.c:760-762]
- Changes to VM bits are NOT independently WAL-logged. The WAL record for the underlying heap modification (insert clearing visibility, prune setting visibility) is what drives both crash recovery and standby replay. [from-comment, visibilitymap.c:767-771]
- `PD_ALL_VISIBLE` on the heap page itself MUST be kept in sync with the VM bit. [from-comment, visibilitymap.c:780-782]
- The "examine heap page, then pin VM page, then re-lock" dance in heap modifiers is required because we don't want to hold a buffer lock across potential VM-page I/O — and we cannot atomically test-and-pin. The race window is small (PD_ALL_VISIBLE might have been set between the unlocked check and the relock). [from-comment, visibilitymap.c:797-812] **This dance is replicated in nearly every heap modifier and is a common source of bugs.**

## Functions of note

- `visibilitymap_set` — implementation at `visibilitymap.c:255`. Asserts that the heap-page LSN ≥ the LSN of the VM update, to keep crash recovery consistent. [unverified — implementation detail not deep-read]
- `visibilitymap_pin` — at `visibilitymap.c:204`. Extends the VM fork on demand.
- `visibilitymap_clear` — at `visibilitymap.c:151`. Called by every heap modifier that breaks all-visibility.

## Cross-references

- Pinning callers: `heap_insert`, `heap_update`, `heap_delete`, `heap_lock_tuple`, `heap_multi_insert`, `lazy_scan_heap`. [verified-by-code, heapam.c includes "access/visibilitymap.h"]
- Bit-clearing: same set, on the "writer" side.
- Bit-setting: `pruneheap.c::heap_page_prune_and_freeze` (via `log_heap_prune_and_freeze`'s redo) and `vacuumlazy.c`. [inferred]

## Open questions

- The exact handshake between `visibilitymap_set` and the LSN check inside it. [unverified]
- Why `visibilitymap_set` takes `RelFileLocator` rather than `Relation` — likely so it can be called from redo paths. [inferred]

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=6 [from-readme]=0 [inferred]=2 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/visibility-map-update.md](../../../../idioms/visibility-map-update.md)
