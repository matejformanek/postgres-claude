# rmgr.c

- **Source path:** `source/src/backend/access/transam/rmgr.c`
- **Lines:** 170
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/rmgr.h`,
  `source/src/include/access/rmgrlist.h`,
  `source/src/include/access/xlog_internal.h` (defines `RmgrData`).

## Purpose

Builds the global `RmgrTable[RM_MAX_ID + 1]` array of resource-manager
records by `#include`-ing `access/rmgrlist.h` with a `PG_RMGR()` macro
expansion. Also provides `RmgrStartup` / `RmgrCleanup`,
`RegisterCustomRmgr` for extensions, and the SQL SRF
`pg_get_wal_resource_managers`. [verified-by-code] `rmgr.c:46-52`.

## Top-of-file comment (verbatim)

```
rmgr.c

Resource managers definition
```
[verified-by-code] `rmgr.c:1-4`.

## Public surface

- `RmgrTable[RM_MAX_ID + 1]` — `rmgr.c:50-52` [verified-by-code]
- `RmgrStartup(void)` — `rmgr.c:58` [verified-by-code]
- `RmgrCleanup(void)` — `rmgr.c:74` [verified-by-code]
- `RmgrNotFound(RmgrId rmid)` — `rmgr.c:91` [verified-by-code]
- `RegisterCustomRmgr(RmgrId rmid, const RmgrData *rmgr)` — `rmgr.c:107`
  [verified-by-code]
- `pg_get_wal_resource_managers(PG_FUNCTION_ARGS)` — `rmgr.c:150`
  [verified-by-code]

## Key types

- `RmgrData` — struct defined in `xlog_internal.h`: name, redo,
  desc, identify, startup, cleanup, mask, decode callbacks.
  [from-comment] `rmgr.c:46`.
- `PG_RMGR` macro — expands into a struct initializer for the table.
  [verified-by-code] `rmgr.c:47-48`.

## Key invariants and locking

1. **Built-in rmgr IDs are compile-time constants** from
   `rmgrlist.h`. Extensions register custom rmgrs into the
   `[RM_MIN_CUSTOM_ID..RM_MAX_CUSTOM_ID]` range.
   [verified-by-code] `rmgr.c:113-116`.

2. **Custom registration only during `shared_preload_libraries`.**
   `RegisterCustomRmgr` errors otherwise. [verified-by-code]
   `rmgr.c:118-121`.

3. **Name uniqueness enforced** — both ID and case-insensitive name
   collision rejected. [verified-by-code] `rmgr.c:123-139`.

4. **`RmgrNotFound` is the error path for unknown IDs in WAL**, with
   a hint pointing to `shared_preload_libraries`. [verified-by-code]
   `rmgr.c:90-95`.

## Functions of note

### `RegisterCustomRmgr` — `rmgr.c:107-146` [verified-by-code]

The full validation flow: non-empty name, ID in custom range,
called from `_PG_init` while
`process_shared_preload_libraries_in_progress`, slot empty, name
unique. On success, copies struct in and `ereport(LOG)`s.

### `RmgrStartup` / `RmgrCleanup` — `rmgr.c:58-83` [verified-by-code]

Called by `xlogrecovery.c:PerformWalRecovery` to give each rmgr a
chance to allocate / free recovery-only state.

## Cross-references

- `rmgrlist.h` is the canonical list of built-in rmgrs (heap, btree,
  hash, gin, gist, brin, spgist, xact, xlog, clog, multixact,
  commit_ts, generic, logical decoding, sequence, dbase, tablespace,
  relmap, standby, replorigin).
- `xlogrecovery.c:ApplyWalRecord` dispatches on `RmgrTable[rmid].rm_redo`.
- `pg_waldump` (frontend tool) uses `rm_desc` / `rm_identify` for
  human-readable record dumps.

## Open questions

None.

## Confidence tag tally

- `[verified-by-code]`: 13
- `[from-comment]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
