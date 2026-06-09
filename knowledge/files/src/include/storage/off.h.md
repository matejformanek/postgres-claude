# `src/include/storage/off.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 57

## Role

`OffsetNumber` — 1-based `uint16` index into the line-pointer
array on a buffer page. Counterpart of `BlockNumber`; together
they form an `ItemPointer` (TID).

## Public API

- `OffsetNumber` typedef = `uint16`
- `InvalidOffsetNumber = 0`
- `FirstOffsetNumber = 1`
- `MaxOffsetNumber = BLCKSZ / sizeof(ItemIdData)` — = 2048 with
  default 8 KB BLCKSZ (because `ItemIdData` is 4 bytes via its
  bitfield layout — see itemid.h)
- Macros: `OffsetNumberIsValid`, `OffsetNumberNext`,
  `OffsetNumberPrev`

[verified-by-code] `source/src/include/storage/off.h:14-56`

## Invariants

- INV-1: 1-based, not 0-based. `FirstOffsetNumber = 1`.
- INV-2: `MaxOffsetNumber` depends on compile-time BLCKSZ.
  Increasing BLCKSZ proportionally increases the offset range.

## Trust boundary (Phase D)

- Inputs that synthesize an `ItemPointer` from external data
  (e.g. `tid` SQL type input parser, FDW row reconstruction)
  must validate `OffsetNumberIsValid(off)` — but note that
  validity here only means *non-zero and ≤ MaxOffsetNumber*; it
  does NOT mean the line pointer at that offset actually
  exists on the page. Per-page validation happens at heap-access
  time.

## Cross-refs

- `knowledge/files/src/include/storage/itemid.h.md` — what an
  offset points at
- `knowledge/files/src/include/storage/itemptr.h.md` (existing) —
  the (block, offset) tuple

## Issues

None.
