# `src/include/storage/block.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 108

## Role

Disk-block-number primitive. Defines:

- `BlockNumber` — `uint32`, the calculation type
- `BlockIdData` — two `uint16` fields (`bi_hi`, `bi_lo`),
  SHORTALIGN-able storage form embedded in `ItemPointerData`
- Inline helpers: `BlockNumberIsValid`, `BlockIdSet`,
  `BlockIdEquals`, `BlockIdGetBlockNumber`

[verified-by-code] `source/src/include/storage/block.h:14-106`

## Invariants

- INV-1: `InvalidBlockNumber = 0xFFFFFFFF`, also reused as `P_NEW`
  in bufmgr.h. [verified-by-code] line 33.
- INV-2: `MaxBlockNumber = 0xFFFFFFFE` — one less than invalid.
  Hard cap on per-fork relation size: ~ 4 G blocks × BLCKSZ
  (typically 8 KB) = 32 TB per fork.
- INV-3: BlockId's `bi_hi/bi_lo` split is *purely for shortalign* —
  ItemPointer fits in 6 bytes only because of this. Changing the
  type breaks on-disk format.
  [from-comment] lines 43-51.

## Trust boundary (Phase D)

Header is pure typedef; no input path. Callers must validate
attacker-influenced BlockNumber values against
`RelationGetNumberOfBlocks` before passing to bufmgr — see
read_stream.h notes.

## Cross-refs

- `knowledge/files/src/include/storage/buf.h.md` —
  `Buffer = int` counterpart
- `knowledge/files/src/include/storage/relfilelocator.h.md` —
  what identifies the fork-file containing the block
- `knowledge/files/src/include/storage/itemptr.h.md` (existing) —
  `ItemPointerData` embeds `BlockIdData`

## Issues

None.
