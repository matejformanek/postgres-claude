# rmgr.h

- **Source path:** `source/src/include/access/rmgr.h`
- **Lines:** 62
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `rmgr.c`, `rmgrlist.h`, `xlog_internal.h`
  (defines `RmgrData`).

## Purpose

Defines `RmgrId` (uint8), the `RmgrIds` enum built from `rmgrlist.h`,
the built-in vs custom partitioning of the ID space, and helpers
`RmgrIdIsBuiltin` / `RmgrIdIsCustom` / `RmgrIdIsValid`.
[from-comment] `rmgr.h:3-4`.

## Top-of-file comment (verbatim)

```
rmgr.h

Resource managers definition
```
[verified-by-code] `rmgr.h:1-4`.

## Key types / constants

- `RmgrId = uint8`. [verified-by-code] `rmgr.h:11`.
- `RmgrIds` enum — generated from `#include "access/rmgrlist.h"` via
  the `PG_RMGR` macro, terminated by `RM_NEXT_ID`. [verified-by-code]
  `rmgr.h:25-29`.
- `RM_MAX_ID = UINT8_MAX = 255`. [verified-by-code] `rmgr.h:33`.
- `RM_MAX_BUILTIN_ID = RM_NEXT_ID - 1`. [verified-by-code]
  `rmgr.h:34`.
- `RM_MIN_CUSTOM_ID = 128`, `RM_MAX_CUSTOM_ID = UINT8_MAX`.
  [verified-by-code] `rmgr.h:35-36`.
- `RM_N_IDS = 256`, `RM_N_BUILTIN_IDS = RM_MAX_BUILTIN_ID + 1`,
  `RM_N_CUSTOM_IDS = RM_MAX_CUSTOM_ID - RM_MIN_CUSTOM_ID + 1 = 128`.
  [verified-by-code] `rmgr.h:37-39`.
- `RM_EXPERIMENTAL_ID = 128` — reserved slot for in-development
  extensions. [verified-by-code] `rmgr.h:60`.

## Inline helpers

- `RmgrIdIsBuiltin(rmid) = (rmid <= RM_MAX_BUILTIN_ID)`. [verified-by-code]
  `rmgr.h:41-45`.
- `RmgrIdIsCustom(rmid) = (rmid >= 128 && rmid <= 255)`.
  [verified-by-code] `rmgr.h:47-51`.
- `RmgrIdIsValid(rmid)` = either of the above. [verified-by-code]
  `rmgr.h:53`.

## Key invariants

1. **Widening `RmgrId` changes the on-disk WAL format.**
   [from-comment] `rmgr.h:18-20`.

2. **Built-in IDs are dense; custom IDs are sparse.** Built-in
   numbering follows the order in `rmgrlist.h`. Custom IDs are
   meant to be reserved on the PostgreSQL wiki to prevent collision
   between extensions. [from-comment] `rmgr.h:54-58`.

## Cross-references

- `rmgr.c` builds the `RmgrTable[]` and provides
  `RegisterCustomRmgr` validation.
- `rmgrlist.h` is the canonical list of built-in rmgrs (`PG_RMGR`
  expansion).
- `xlog_internal.h` defines `RmgrData` (the entry struct).

## Confidence tag tally

- `[verified-by-code]`: 12
- `[from-comment]`: 3
