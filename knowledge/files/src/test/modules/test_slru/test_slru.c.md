# src/test/modules/test_slru/test_slru.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 257
**Verification depth:** full read

## Role

A test extension exposing the low-level SLRU (Simple LRU) API as SQL-callable functions, exercising a private SLRU bank ("TestSLRU") created at `shared_preload_libraries` time. It registers a custom `SlruDesc` (`TestSlruDesc`) via shmem callbacks and wraps `SimpleLru*` primitives (zero/read/write/sync/delete/truncate page) so regression SQL can drive SLRU correctness directly. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:3` [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:236`

## Public API

- `test_slru_page_write(pageno int8, data text)` — zeroes a page slot, marks it dirty/valid, copies data in (capped at `BLCKSZ-1`), and writes it. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:64`
- `test_slru_page_writeall()` — flushes all dirty SLRU pages via `SimpleLruWriteAll`. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:92`
- `test_slru_page_read(pageno int8, write_ok bool, xid xid)` — reads a page (loading from disk if needed) under exclusive bank lock; returns the buffer as text. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:99`
- `test_slru_page_readonly(pageno int8)` — reads via `SimpleLruReadPage_ReadOnly` and returns buffer text. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:118`
- `test_slru_page_exists(pageno int8)` — checks physical page existence on disk. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:137`
- `test_slru_page_sync(pageno int8)` — fsyncs the segment file containing the page via `SlruSyncFileTag`. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:151`
- `test_slru_page_delete(pageno int8)` — deletes the whole segment via `SlruDeleteSegment`. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:168`
- `test_slru_page_truncate(pageno int8)` — `SimpleLruTruncate` from the given page. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:183`
- `test_slru_delete_all()` — scans the SLRU directory deleting all segments. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:192`

## Invariants

- INV-1: After `SimpleLruZeroPage`, the slot's `page_number` equals the requested `pageno` (asserted). [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:76`
- INV-2: Mutating page state (write, read, exists) requires holding the bank lock for `pageno` exclusively; the lock is obtained via `SimpleLruGetBankLock`. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:70` [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:110`
- INV-3: `SimpleLruReadPage_ReadOnly` returns with the bank lock already held by the caller (asserted via `LWLockHeldByMe`), so the caller must release it. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:127` [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:130`
- INV-4: The module must be loaded via `shared_preload_libraries`; `_PG_init` errors otherwise. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:218`

## Notable internals

- SLRU bank is requested in a shmem `request_fn` callback (`test_slru_shmem_request`) registered via `RegisterShmemCallbacks`, calling `SimpleLruRequest(...)` with designated initializers: `nslots = NUM_TEST_BUFFERS (16)`, `nlsns = 0`, `long_segment_names = true`, `sync_handler = SYNC_HANDLER_NONE`, and tranche ids left 0 for slru.c to assign. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:233` [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:236`
- Provides two custom SLRU hooks: `PagePrecedes` (`test_slru_page_precedes_logically`, plain `page1 < page2`) and `errdetail_for_io_error` (formats the xid into an errdetail). [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:201` [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:207`
- `_PG_init` creates the SLRU directory `pg_test_slru` from the data dir root via `MakePGDirectory`. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:228`
- Directly pokes `TestSlruCtl->shared->page_dirty/page_status/page_buffer` to set up a writable page, demonstrating the raw shared-state layout. [verified-by-code] `source/src/test/modules/test_slru/test_slru.c:79`

## Cross-refs

- `source/src/backend/access/transam/slru.c` — `SimpleLruInit`/`SimpleLruRequest`/`SimpleLru*` implementations and `SlruDesc`/`SlruShared` layout.
- `source/src/include/access/slru.h` — SLRU public API, `SlruScanDirCbDeleteAll`, `SLRU_PAGES_PER_SEGMENT`.
- `source/src/include/storage/shmem.h` — `ShmemCallbacks`/`RegisterShmemCallbacks`.
- Companion: `source/src/test/modules/test_slru/test_multixact.c`.

## Potential issues

None.
