# `src/include/storage/indexfsm.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 26

## Role

Index Free Space Map — a thin wrapper around the generic
`freespace.h` FSM specialized for index relations. Provides
`GetFreeIndexPage` / `RecordFreeIndexPage` /
`RecordUsedIndexPage` / `IndexFreeSpaceMapVacuum` for nbtree,
GiST, GIN, BRIN bookkeeping of recyclable index pages.

[verified-by-code] `source/src/include/storage/indexfsm.h:20-24`

## Invariants

Same as `freespace.h` — fsm pages are advisory; readers must
re-acquire the candidate page and verify it's still reclaimable.

## Trust boundary (Phase D)

None.

## Cross-refs

- `knowledge/files/src/include/storage/freespace.h.md` (existing)
- `knowledge/files/src/backend/storage/freespace/indexfsm.c.md`
  (if exists)

## Issues

None.
