# slru.h

- **Source path:** `source/src/include/access/slru.h`
- **Lines:** 255
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `slru.c`, all SLRU clients
  (`clog.c`, `subtrans.c`, `multixact.c`, `commit_ts.c`,
  `commands/async.c`, `storage/lmgr/predicate.c`).

## Purpose

Public interface to `slru.c`: the `SlruDesc` / `SlruShared`
descriptors, the page-status enum, the `SlruOpts` request bundle, and
all `SimpleLru*` prototypes. [from-comment] `slru.h:3-4`.

## Top-of-file comment (verbatim)

```
slru.h
    Simple LRU buffering for transaction status logfiles
```
[verified-by-code] `slru.h:1-4`.

## Key types

### `SlruPageStatus` (`slru.h:34-40`) [verified-by-code]

`SLRU_PAGE_EMPTY`, `SLRU_PAGE_READ_IN_PROGRESS`, `SLRU_PAGE_VALID`,
`SLRU_PAGE_WRITE_IN_PROGRESS`. `page_dirty` can be true only in
`VALID` or `WRITE_IN_PROGRESS` (with the latter implying re-dirtied).
[from-comment] `slru.h:29-33`.

### `SlruSharedData` (`slru.h:48-106`) [verified-by-code]

Per-SLRU shared state:
- `num_slots`.
- Arrays per slot: `page_buffer`, `page_status`, `page_dirty`,
  `page_number`, `page_lru_count`.
- `buffer_locks[]` (per-buffer LWLockPadded) and `bank_locks[]`
  (per-bank LWLockPadded).
- `bank_cur_lru_count[]` — per-bank monotonic counter; MRU =
  set this on access. [from-comment] `slru.h:69-83`.
- `group_lsn[]` and `lsn_groups_per_page` — optional WAL LSN
  tracking (pg_xact uses this; others set NULL).
- `latest_page_number` (atomic).
- `slru_stats_idx`.

### `SlruOpts` (`slru.h:115-184`) [verified-by-code]

Configuration record passed to `SimpleLruRequest`:
`name`, `desc`, `nslots`, `nlsns`, `sync_handler`, `Dir`,
`long_segment_names`, `PagePrecedes` callback,
`errdetail_for_io_error` callback, tranche IDs.

### `SlruDesc` (`slru.h:190-198`) [verified-by-code]

Per-backend handle: `options`, `shared`, `nbanks`.

## Constants

- `SLRU_MAX_ALLOWED_BUFFERS = (1024 * 1024 * 1024) / BLCKSZ` —
  internal-arithmetic safety cap. [verified-by-code] `slru.h:26`.

## Key invariants and locking

1. **Bank lock = bucket = pageno % nbanks.**
   `SimpleLruGetBankLock` returns the bank LWLock.
   [verified-by-code] `slru.h:206-214`.

2. **`latest_page_number` uses atomics, bypassing the bank lock.**
   [from-comment] `slru.h:46`.

3. **`PagePrecedes` semantics.** Returns true if every entry on
   `page1` is older than every entry on `page2`. Non-trichotomous —
   `!P(a,b) && !P(b,a)` does not imply equality. Modular arithmetic
   required when used with `SimpleLruTruncate`. [from-comment]
   `slru.h:156-165`.

4. **`SlruPagePrecedesUnitTests`** is a debug-only sanity check.
   [verified-by-code] `slru.h:230-234`.

## Public surface (prototypes)

- `SimpleLruRequest(...)` macro / `SimpleLruRequestWithOpts(*opts)` —
  `slru.h:216-219` [verified-by-code]
- `SimpleLruAutotuneBuffers(divisor, max)` — `slru.h:221`
  [verified-by-code]
- `SimpleLruZeroPage`, `SimpleLruZeroAndWritePage`,
  `SimpleLruReadPage`, `SimpleLruReadPage_ReadOnly`,
  `SimpleLruWritePage`, `SimpleLruWriteAll`, `SimpleLruTruncate`,
  `SimpleLruDoesPhysicalPageExist` — `slru.h:222-236`
  [verified-by-code]
- `SlruScanCallback`, `SlruScanDirectory`, `SlruDeleteSegment`,
  `SlruSyncFileTag` — `slru.h:238-243` [verified-by-code]
- `SlruScanDirCbReportPresence`, `SlruScanDirCbDeleteAll` —
  `slru.h:246-249` [verified-by-code]
- `check_slru_buffers(name, *newval)` — `slru.h:250` [verified-by-code]
- `shmem_slru_init`, `shmem_slru_attach` — `slru.h:252-253`
  [verified-by-code]

## Cross-references

- `slru.c` implements all prototypes.
- Each SLRU client declares its own `SlruDesc` and calls
  `SimpleLruRequest`.

## Confidence tag tally

- `[verified-by-code]`: 17
- `[from-comment]`: 5

## Synthesized by
<!-- backlinks:auto -->
- [idioms/slru-page-replacement.md](../../../../idioms/slru-page-replacement.md)
