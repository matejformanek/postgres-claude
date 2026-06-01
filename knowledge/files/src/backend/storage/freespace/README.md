# `src/backend/storage/freespace/README`

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/backend/storage/freespace/README`

## Purpose

Comprehensive description of the Free Space Map (FSM): the per-relation
"how much free space is on each page" structure that lets inserters
find an extendable page quickly without scanning the heap.
[from-README]

## Key claims (all `[from-README]`)

- Each relation has its own FSM stored in a separate fork (the FSM
  fork, fork number 1) since PG 8.4 (lines 5–11).
- One byte per heap page → free space granularity is BLCKSZ/256 (lines
  16–19). Max value 255 means "≥ MaxFSMRequestSize free".
- **Within a page**: binary tree where leaves hold per-heap-page free
  space and internal nodes hold the max of their children (lines
  27–40). Search descends along the child whose value satisfies the
  request; update bubbles up.
- **Across pages**: same tree structure recursively — root page at
  block 0, leaves point to actual heap pages, intermediate FSM pages
  cover groups of leaves. Three-level tree handles the full 2^32-1
  block address space at default BLCKSZ (line 137).
- **`fp_next_slot`**: per-FSM-page "where to start next search" hint —
  spreads concurrent inserters across pages but still tries to fill
  pages sequentially for OS prefetcher friendliness (lines 79–87).
- **Locking** (lines 153–166): only one FSM page locked at a time
  while traversing; child locked, parent released. Shared lock to
  search, exclusive lock to update; `fp_next_slot` is updated under
  shared lock as a hint (cheap, can be reset if corrupted).
- **Recovery** (lines 168–199): FSM is **not WAL-logged**. Relies on
  self-correcting heuristics: every bubble-up checks root >= new
  value; every search verifies child satisfies parent's claim;
  corruption rebuilds the upper nodes on that page. VACUUM
  periodically rewrites all bottom-level entries and calls
  `FreeSpaceMapVacuum` to repropagate upward. Reads use
  `RBM_ZERO_ON_ERROR` (corruption tolerated). Writes use
  `MarkBufferDirtyHint` rather than `MarkBufferDirty`.
- **Post-WAL-replay subtlety**: a slot can claim free space in a
  PageIsNew() block that never reached disk (relation extension is
  not WAL-logged); detected by comparing against actual relation
  size, then marked full (lines 196–199).

## Why the lack of WAL matters

The FSM is a *hint*. Wrong values can cost time (retry insert
elsewhere) but cannot corrupt data — heap insertion always validates
the actual page's free space under buffer lock. This is what lets the
FSM skip WAL entirely.

## TODOs in upstream

- "fastroot" to skip upper levels with a single child.
- Special case for tables that fit in one FSM page.

## Cross-refs

- `knowledge/files/src/backend/storage/freespace/freespace.c.md`
- `knowledge/files/src/backend/storage/freespace/fsmpage.c.md`
- `knowledge/files/src/backend/storage/freespace/indexfsm.c.md`

## Tag tally

`[from-README]` 15.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
