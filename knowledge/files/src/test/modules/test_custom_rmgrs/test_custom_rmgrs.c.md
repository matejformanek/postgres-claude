# src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 140
**Verification depth:** full read

## Role

The canonical example of an extension-provided custom WAL resource manager. It defines an `RmgrData` (no-op redo, a textual-payload desc/identify) and registers it under `RM_EXPERIMENTAL_ID` during `_PG_init`, plus a SQL function that inserts a custom WAL record carrying an arbitrary text payload. Used to test the `RegisterCustomRmgr` machinery and the custom-rmgr ID range. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:12` [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:55`

## Public API

- `test_custom_rmgrs_insert_wal_record(payload text)` — inserts a WAL record of the custom rmgr type carrying the text payload; returns the record's LSN. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:118`
- `testcustomrmgrs_redo(XLogReaderState *)` — redo callback; no-op except PANIC on unknown op code. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:81`
- `testcustomrmgrs_desc(StringInfo, XLogReaderState *)` — appends the payload bytes to the desc buffer. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:90`
- `testcustomrmgrs_identify(uint8 info)` — maps the single op code to its name string. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:105`

## Invariants

- INV-1: The custom rmgr must be registered from `_PG_init` while loaded via `shared_preload_libraries`, otherwise `RegisterCustomRmgr` fails. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:68`
- INV-2: The info byte must be masked with `~XLR_INFO_MASK` before comparing to op codes (the high bits are reserved by xlog). [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:84` [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:108`
- INV-3: A redo callback must PANIC on an unrecognized op code rather than silently continue (recovery-correctness contract). [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:86`

## Notable internals

- `RmgrData` is a static designated-initializer struct supplying `rm_name`, `rm_redo`, `rm_desc`, `rm_identify` (no `rm_startup`/`rm_cleanup`/decode hooks since there's no real structure to recover or decode). [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:55`
- The WAL record is `xl_testcustomrmgrs_message` (a `Size message_size` header + `FLEXIBLE_ARRAY_MEMBER` payload); insertion registers the fixed header then the payload as two `XLogRegisterData` calls and flags the record `XLOG_MARK_UNIMPORTANT`. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:32` [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:130`
- Uses `RM_EXPERIMENTAL_ID` as the rmid, with a code comment directing real extensions to reserve a unique ID via the PG wiki Custom WAL Resource Managers page. [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:42` [verified-by-code] `source/src/test/modules/test_custom_rmgrs/test_custom_rmgrs.c:47`

## Cross-refs

- `source/src/backend/access/transam/rmgr.c` — `RegisterCustomRmgr`, custom rmgr ID range (`RM_CUSTOM_MIN_ID`..`RM_CUSTOM_MAX_ID`), `RM_EXPERIMENTAL_ID`.
- `source/src/include/access/xlog_internal.h` — `RmgrData` struct and the RMGR API contract.
- `source/src/include/access/xloginsert.h` — `XLogBeginInsert`/`XLogRegisterData`/`XLogInsert`/`XLogSetRecordFlags`.

## Potential issues

None.
