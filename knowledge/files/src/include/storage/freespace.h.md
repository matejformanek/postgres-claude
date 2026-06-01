# `src/include/storage/freespace.h`

- **Last verified commit:** `ef6a95c7c64`

## Purpose

Public surface of the heap FSM (freespace.c).

## Surface

- `GetRecordedFreeSpace(rel, heapBlk) → Size`
- `GetPageWithFreeSpace(rel, spaceNeeded) → BlockNumber`
- `RecordAndGetPageWithFreeSpace(rel, oldBlock, oldSpaceAvail,
  spaceNeeded) → BlockNumber`
- `RecordPageWithFreeSpace(rel, heapBlk, spaceAvail)`
- `XLogRecordPageWithFreeSpace(rlocator, heapBlk, spaceAvail)`
- `FreeSpaceMapPrepareTruncateRel(rel, nblocks) → BlockNumber`
- `FreeSpaceMapVacuum(rel)` / `FreeSpaceMapVacuumRange(rel, start,
  end)`

## Tag tally

`[verified-by-code]` 1.
