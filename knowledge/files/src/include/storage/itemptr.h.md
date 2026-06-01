# `src/include/storage/itemptr.h`

- **Last verified commit:** `ef6a95c7c64`

## Purpose

Defines `ItemPointerData` (TID), the 6-byte (block,offset) identifier
of a heap tuple. Most accessors are inline functions here; only four
helpers are out-of-line in itemptr.c.

## Types

- `ItemPointerData` (~6 bytes): `BlockIdData ip_blkid` (two uint16
  halves) + `OffsetNumber ip_posid`. The two-uint16 block id is a
  packing trick so the whole struct doesn't need 4-byte alignment;
  `BlockIdGetBlockNumber` reassembles the 32-bit value.
- `ItemPointer = ItemPointerData *`.

## Inline accessors

- `ItemPointerGetBlockNumber(ptr)` / `NoCheck` variant.
- `ItemPointerGetOffsetNumber(ptr)` / `NoCheck`.
- `ItemPointerSet(ptr, blk, off)`, `ItemPointerSetInvalid`,
  `ItemPointerIsValid`, `ItemPointerCopy`.

## Out-of-line (itemptr.c)

`ItemPointerEquals`, `ItemPointerCompare`, `ItemPointerInc`,
`ItemPointerDec`.

## Invariants

- `sizeof(ItemPointerData) == 6` (StaticAssert in itemptr.c).
- `FirstOffsetNumber = 1`, `InvalidOffsetNumber = 0`.

## Tag tally

`[verified-by-code]` 2.
