# storage_xlog.h

- **Source path:** `source/src/include/catalog/storage_xlog.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Prototypes for XLog support for backend/catalog/storage.c." Defines the WAL record formats emitted by storage.c.

## Key declarations

- `XLOG_SMGR_CREATE` (0x10), `XLOG_SMGR_TRUNCATE` (0x20) — info bytes for RM_SMGR_ID.
- `xl_smgr_create { RelFileLocator rlocator; ForkNumber forkNum; }` — payload of XLOG_SMGR_CREATE.
- `xl_smgr_truncate { BlockNumber blkno; RelFileLocator rlocator; uint32 flags; }` — payload of XLOG_SMGR_TRUNCATE (flags pick main / fsm / vm).
- `smgr_redo` (the replay function), `smgr_desc` / `smgr_identify` (for pg_waldump).

## Tally

`[verified-by-code]=1`
