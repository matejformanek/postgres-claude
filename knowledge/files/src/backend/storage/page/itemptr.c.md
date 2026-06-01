# `src/backend/storage/page/itemptr.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 132
- **Source:** `source/src/backend/storage/page/itemptr.c`

## Purpose

Trivial helpers for `ItemPointerData` — the 6-byte (block,offset)
identifier of a heap tuple ("TID"). Heavily macro/inline-defined in
`itemptr.h`; this `.c` file holds only the four routines that are too
big for inlining or are out-of-line for some reason. [from-comment]
(`itemptr.c:1-13`)

## Top of file

Single include: `storage/itemptr.h`. StaticAssert that
`sizeof(ItemPointerData) == 6` — load-bearing because TIDs are packed
into many on-disk and in-memory structures (Datum representation,
HeapTuple t_self, index entries). [verified-by-code]
(`itemptr.c:23-24`)

## Public surface (itemptr.h)

- `ItemPointerEquals(p1, p2) → bool`
- `ItemPointerCompare(p1, p2) → int32` — btree-style.
- `ItemPointerInc(p)` / `ItemPointerDec(p)` — step by ±1 across the
  block/offset boundary, treating ItemPointer as a 48-bit ordinal.

Most accessors (`ItemPointerGetBlockNumber`,
`ItemPointerGetOffsetNumber`, `ItemPointerSet`, `…NoCheck` variants)
are inline in `itemptr.h`.

## Invariants

- `sizeof(ItemPointerData) == 3 * sizeof(uint16)` (= 6 bytes), enforced
  at compile time. [verified-by-code]
- The `NoCheck` accessors are used by `ItemPointerCompare` and the
  `Inc/Dec` routines because user-supplied TIDs can legitimately have
  `ip_posid == 0` (e.g. predicate locks, snapshot internals).
  [from-comment] (`itemptr.c:53-56`)
- `ItemPointerInc/Dec` go *block-wise* once offset wraps PG_UINT16_MAX
  / 0 — they ignore `FirstOffsetNumber` / `MaxOffsetNumber`, treating
  the pair as raw uint16s.

## Cross-refs

- Used by indexscan, heapam (HOT chains), tidscan, predicate locks.

## Open questions

None — this file is essentially self-contained.

## Tag tally

`[verified-by-code]` 2 / `[from-comment]` 1 / `[unverified]` 0.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
