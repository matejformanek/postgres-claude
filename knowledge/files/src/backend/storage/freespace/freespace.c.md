# `src/backend/storage/freespace/freespace.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~870
- **Source:** `source/src/backend/storage/freespace/freespace.c`

## Purpose

The cross-page logic of the Free Space Map: maps a heap block number
to (logical FSM level, page, slot), navigates the upper-level FSM
pages to find a heap page with enough free space, and propagates
updates back up. The in-page tree is delegated to fsmpage.c.
[from-comment] (`freespace.c:14-22`)

## Top of file

Defines the free-space category granularity:
- `FSM_CATEGORIES = 256` — one byte per slot.
- `FSM_CAT_STEP = BLCKSZ / 256` — bytes per category step (32 at
  default BLCKSZ).
- `MaxFSMRequestSize = MaxHeapTupleSize` — the 255 category cap.

Tree depth:
- `FSM_TREE_DEPTH = 3` if `SlotsPerFSMPage >= 1626`, else 4 (line 75).
- `FSM_ROOT_LEVEL = depth - 1`, leaves at level 0.

## Public surface (freespace.h)

- `GetRecordedFreeSpace(rel, heapBlk) → Size`
- `GetPageWithFreeSpace(rel, spaceNeeded) → BlockNumber`
- `RecordAndGetPageWithFreeSpace(rel, oldBlock, oldSpaceAvail,
  spaceNeeded)`
- `RecordPageWithFreeSpace(rel, heapBlk, spaceAvail)`
- `XLogRecordPageWithFreeSpace(rlocator, heapBlk, spaceAvail)`
- `FreeSpaceMapPrepareTruncateRel(rel, nblocks) → BlockNumber`
- `FreeSpaceMapVacuum(rel)` / `FreeSpaceMapVacuumRange(rel, start,
  end)`

## Types

- `FSMAddress` (lines 84–88): logical address (level, logpageno) —
  the abstraction this file works in.

## Functions of note (read-only inspection)

- `GetPageWithFreeSpace` (line 137): trivial wrapper that converts
  spaceNeeded to a category and calls `fsm_search`.
- `fsm_search` (declared at line 111): top-of-tree descent. Each
  level: lock FSM page shared, scan its in-page tree via
  `fsm_search_avail` (fsmpage.c), if found descend, if missing
  restart from root (the "child concurrent update" recovery path
  described in README §Locking).
- `fsm_set_and_search` / `RecordPageWithFreeSpace` (line 109):
  update leaf, bubble up via fsmpage.c's `fsm_set_avail`.
- `fsm_logical_to_physical` (line 98): the tree-arithmetic that maps
  (level, logpageno) to a physical FSM-fork block number
  (`n + n/F + 1 + n/F^2 + 1 + …` from README).
- `fsm_extend` / `fsm_readbuf` (lines 100–101): on-demand FSM-fork
  growth and read; uses `RBM_ZERO_ON_ERROR` per README contract.
- `FreeSpaceMapVacuum`: VACUUM uses this to repropagate bottom-level
  values upward at end-of-pass.

## Invariants

- Writes use `MarkBufferDirtyHint`, not `MarkBufferDirty` —
  intentionally a hint. [from-README]
- Search descent locks only one page at a time. [from-README]
- After WAL replay, a leaf slot may indicate free space in a block
  that doesn't exist (extension is not WAL-logged); validated against
  `smgrnblocks` and treated as full when mismatched. [from-README]

## Cross-refs

- Outbound: `fsmpage.c` (intra-page tree), `bufmgr.c`
  (`ReadBufferExtended(RBM_ZERO_ON_ERROR)`,
  `MarkBufferDirtyHint`), `smgr.c` (`smgrnblocks`,
  `smgrtruncate`).
- Inbound: `heap_multi_insert`, `RelationGetBufferForTuple`
  (heapam), `indexfsm.c`.

## Open questions

- The exact recovery path inside `fsm_search` for the "child has less
  than parent claimed" case — README explains the design but I didn't
  walk every branch of the code. `[unverified]`

## Tag tally

`[from-comment]` 2 / `[from-README]` 4 / `[verified-by-code]` 2 /
`[unverified]` 1.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
