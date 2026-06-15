---
path: src/test/modules/test_slru/test_slru.c
anchor_sha: e18b0cb7344
loc: 257
depth: read
---

# src/test/modules/test_slru/test_slru.c

## Purpose

Exercises the Simple LRU (SLRU) framework — the page-cache used for
fixed-size on-disk arrays like `clog`, `multixact`, `subtrans`,
`commit_ts`. Wraps each public `SimpleLru*` entry point as an SQL function so
isolation/regress tests can drive the SLRU layer directly: zero a page,
write/read/sync/truncate it, observe locking, scan the directory, delete
segments. The test sets up a custom SLRU named `pg_test_slru` with 16
buffer slots and long segment filenames. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `test_slru.c:215` | Must be in `shared_preload_libraries`; registers shmem callbacks |
| `test_slru_page_write` | `:64` | Zero a page, mark it dirty, write to disk |
| `test_slru_page_writeall` | `:92` | `SimpleLruWriteAll` flush |
| `test_slru_page_read` | `:99` | Read with optional write-OK |
| `test_slru_page_readonly` | `:118` | `SimpleLruReadPage_ReadOnly` (returns lock held in shared mode) |
| `test_slru_page_exists` | `:137` | `SimpleLruDoesPhysicalPageExist` |
| `test_slru_page_sync` | `:151` | `SlruSyncFileTag` on the segment containing a page |
| `test_slru_page_delete` | `:168` | `SlruDeleteSegment` on the segment |
| `test_slru_page_truncate` | `:183` | `SimpleLruTruncate` up to page |
| `test_slru_delete_all` | `:192` | `SlruScanDirectory` with delete-all callback |
| `test_slru_shmem_request` (static) | `:233` | Calls `SimpleLruRequest` with the test's config |
| `test_slru_page_precedes_logically` (static) | `:201` | Trivial `page1 < page2` ordering function |
| `test_slru_errdetail_for_io_error` (static) | `:207` | Custom error-detail hook returning the XID |

## Internal landmarks

- `TestSlruDir = "pg_test_slru"` (`:47`) — created relative to the data
  directory in `_PG_init` via `MakePGDirectory` (`:228`).
- 16-slot buffer (`NUM_TEST_BUFFERS`, `:41`) — small on purpose so eviction
  paths are easily exercised.
- `.long_segment_names = true` (`:244`) — picks the long-filename variant
  to focus the test on a less-covered code path.
- Each SQL function explicitly does the lock dance:
  `SimpleLruGetBankLock(ctl, pageno)` → `LWLockAcquire(LW_EXCLUSIVE)` → op →
  `LWLockRelease` (`:70-87`). `_ReadOnly` is the exception (`:127`) — it
  returns with the lock held in shared mode, which the test releases at
  `:132`.
- `Assert(LWLockHeldByMe(lock))` (`:130`) double-checks the read-only
  contract.

## Invariants & gotchas

- **Test module — never load in production.**
- **Must be in `shared_preload_libraries`** — `_PG_init` ereports otherwise
  (`:218-222`), because SLRU requires shmem allocation at postmaster start.
- The `LWLockAcquire(EXCLUSIVE)` around `SimpleLruZeroPage` is the same
  pattern real users follow — direct SLRU access is not lock-free even when
  the page is already cached.
- `SimpleLruTruncate(0)` would be a no-op; the truncate target is the
  highest page to KEEP.
- `SlruDeleteSegment` is a destructive low-level call; under normal
  operation only the SLRU's own truncate machinery should use it.

## Cross-refs

- `source/src/backend/access/transam/slru.c` — implementation.
- `source/src/include/access/slru.h` — `SimpleLruRequest`, `SlruDesc`,
  `ShmemCallbacks`.
- `knowledge/files/src/test/modules/test_slru/test_multixact.c.md` — sibling.
