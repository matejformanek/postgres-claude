# `src/backend/storage/freespace/indexfsm.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 75
- **Source:** `source/src/backend/storage/freespace/indexfsm.c`

## Purpose

A thin specialization of the heap FSM for index AMs that need to
track *whole-page-free* vs *in-use* (not byte-granular free space).
Uses the same on-disk FSM format as heap but only two values: 0
(used) or `BLCKSZ - 1` (free). [from-comment] (`indexfsm.c:14-21`)

## Public surface (indexfsm.h)

- `GetFreeIndexPage(rel) → BlockNumber` — get a free page and mark
  it used.
- `RecordFreeIndexPage(rel, blkno)` — mark free (value = BLCKSZ-1).
- `RecordUsedIndexPage(rel, blkno)` — mark used (value = 0).
- `IndexFreeSpaceMapVacuum(rel)` — wrapper over
  `FreeSpaceMapVacuum`.

## Implementation

All four functions are 2-line wrappers around freespace.c equivalents
(asking for half-a-page of free space is enough to distinguish used
vs free).

## Cross-refs

- Inbound: `nbtree/nbtpage.c`, `gin/ginutil.c`, `gist/gistutil.c`,
  `hash/hashpage.c`, etc.
- Outbound: freespace.c.

## Tag tally

`[from-comment]` 1 / `[verified-by-code]` 2.
