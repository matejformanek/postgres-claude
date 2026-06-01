# slru.c

- **Source path:** `source/src/backend/access/transam/slru.c`
- **Lines:** 1905
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/slru.h`, `clog.c`,
  `subtrans.c`, `multixact.c`, `commit_ts.c`, and (outside transam)
  `commands/async.c` and `storage/lmgr/predicate.c` which also use
  SLRUs.

## Purpose

Generic "Simple LRU" page-buffer machinery for permanent SLRU files
indexed by transaction-ID-like counters that wrap around. Used by all
pg_xact / pg_subtrans / pg_multixact / pg_commit_ts / pg_notify /
pg_serial caches, and by extensions. [from-comment] `slru.c:3-10`.

## Top-of-file comment (verbatim)

```
slru.c
   Simple LRU buffering for wrap-around-able permanent metadata

This module is used to maintain various pieces of transaction status
indexed by TransactionId (such as commit status, parent transaction ID,
commit timestamp), as well as storage for multixacts, serializable
isolation locks and NOTIFY traffic.  Extensions can define their own
SLRUs, too.

...

We use per-bank control LWLocks to protect the shared data structures,
plus per-buffer LWLocks that synchronize I/O for each buffer.  The
bank's control lock must be held to examine or modify any of the bank's
shared state.  A process that is reading in or writing out a page
buffer does not hold the control lock, only the per-buffer lock for the
buffer it is working on.  One exception is latest_page_number, which is
read and written using atomic ops.

"Holding the bank control lock" means exclusive lock in all cases
except for SimpleLruReadPage_ReadOnly(); see comments for
SlruRecentlyUsed() for the implications of that.
```
[from-comment] `slru.c:3-35`.

## Public surface

- `SimpleLruShmemSize(nslots, nlsns)` — `slru.c:202` [verified-by-code]
- `SimpleLruRequestWithOpts(const SlruOpts *)` — `slru.c:246` [verified-by-code]
- `SimpleLruZeroPage(ctl, pageno)` — `slru.c:397` [verified-by-code]
- `SimpleLruZeroAndWritePage(ctl, pageno)` — `slru.c:466` [verified-by-code]
- `SimpleLruReadPage(ctl, pageno, write_ok, xid)` — `slru.c:550`
  [verified-by-code]
- `SimpleLruReadPage_ReadOnly(ctl, pageno, opaque)` — `slru.c:654`
  [verified-by-code]
- `SimpleLruWritePage(ctl, slotno)` — `slru.c:781` [verified-by-code]
- `SimpleLruDoesPhysicalPageExist` — `slru.c:795` [verified-by-code]
- `SimpleLruWriteAll(ctl, allow_redirtied)` — `slru.c:1372` [verified-by-code]
- `SimpleLruTruncate(ctl, cutoffPage)` — `slru.c:1458` [verified-by-code]
- `SlruDeleteSegment(ctl, segno)` — `slru.c:1576` [verified-by-code]
- `SlruScanDirectory(ctl, callback, data)` — `slru.c:1844` [verified-by-code]
- `SlruSyncFileTag(ctl, ftag, path)` — `slru.c:1884` [verified-by-code]
- `SimpleLruAutotuneBuffers(divisor, max)` — `slru.c:235` [verified-by-code]

## Key types / structs

- `SlruShared` / `SlruCtl` / `SlruDesc` — defined in `slru.h`; per-SLRU
  control structure containing page array, dirty flags, page numbers,
  bank LWLocks, per-buffer LWLocks, segment-file naming callbacks,
  page-precedes callback, `latest_page_number` atomic.
- `SlruOpts` — request descriptor: number of slots, number of LSN
  groups per page, sync callback, "long segments" flag, page-precedes
  callback, name. [verified-by-code] `slru.c:246-266`.
- `SlruShared->ControlLocks` — array of bank LWLocks (one per bank;
  bank = `pageno >> nBuffersPerBank_shift`).

## Key invariants and locking

1. **Per-bank locking.** Each bank has its own control LWLock; readers
   and writers of a bank's state must hold it. Banks are determined by
   the low bits of the page number. [from-comment] `slru.c:18-19, 25-31`.

2. **Per-buffer I/O lock.** A page-I/O-in-progress holder takes the
   per-buffer LWLock exclusive and *releases the bank lock*. Waiters
   for I/O acquire the per-buffer lock in shared mode and release it
   immediately. [from-comment] `slru.c:37-45`.

3. **`latest_page_number` is atomic and lock-free.** Read/written via
   `pg_atomic_*`. [from-comment] `slru.c:29-31`.

4. **The latest page is never evicted.** "We will never swap out the
   latest page (since we know it's going to be hit again eventually)."
   [from-comment] `slru.c:21-23`.

5. **Read-only fast path can use shared bank lock.**
   `SimpleLruReadPage_ReadOnly` returns the slot under shared bank
   lock; the caller must respect `SlruRecentlyUsed()`'s constraints
   on shared-only LRU updates. [from-comment] `slru.c:33-35`, code at
   `slru.c:654-700`, helper at `slru.c:1173`.

6. **Re-dirtying during write is permitted.** Like bufmgr, if someone
   writes between dirty→clean and the actual fsync, the page is
   re-marked dirty. [from-comment] `slru.c:47-49`.

7. **PagePrecedes callback** must implement wraparound-aware
   comparison. Unit-test helpers (`SlruPagePrecedesUnitTests`) exist.
   [verified-by-code] `slru.c:1665, 1750`.

## Functions of note

### `SimpleLruReadPage` — `slru.c:550-653` [verified-by-code]

Core read path. Locates the page in the buffer array, reads from disk
if absent, manages LRU promotion. Returns the slot number; caller may
then read/modify the slot under the bank lock (until releasing).

### `SimpleLruReadPage_ReadOnly` — `slru.c:654-700` [verified-by-code]

Optimization for hot reads: tries shared bank lock first; falls back
to exclusive if the page must be paged in. Used by `clog`/`subtrans`
visibility lookups.

### `SlruSelectLRUPage` — `slru.c:1219` [verified-by-code]

Pick a victim slot inside one bank: linear scan over the bank's slots,
prefer clean over dirty, never pick the latest-page slot, write out
the chosen victim if dirty.

### `SimpleLruWriteAll` — `slru.c:1372-1457` [verified-by-code]

Used by `CheckPoint*` functions of each SLRU client. Iterates all
banks, writing dirty pages. The `allow_redirtied` flag controls
whether to retry pages dirtied between write and lock re-acquisition.

### `SimpleLruTruncate` — `slru.c:1458` [verified-by-code]

Removes obsolete segment files older than `cutoffPage`. Uses
`SlruScanDirectory` with `SlruScanDirCbDeleteCutoff` callback. Honors
the page-precedes callback for wraparound.

### `SlruPhysicalReadPage` / `SlruPhysicalWritePage` —
`slru.c:853, 925` [verified-by-code]

Synchronous read/write of one BLCKSZ page from the on-disk segment
file. Uses pgstat wait events and emits errdetail via the SLRU's
optional `io_error_detail` callback.

## Cross-references

- Every SLRU client (`clog.c`, `subtrans.c`, `multixact.c`,
  `commit_ts.c`, `commands/async.c`, `storage/lmgr/predicate.c`) calls
  these primitives.
- `storage/sync.c` handles deferred fsyncs via `SlruSyncFileTag`.
- `storage/shmem*.c` — `shmem_slru_init` / `shmem_slru_attach` are
  shmem callbacks (`slru.c:267, 359`).

## Open questions

- Bank-count autotuning (`SimpleLruAutotuneBuffers`) is GUC-driven;
  exact heuristic not re-derived. [unverified]
- Page-replacement victim policy details when all slots are pinned
  / under I/O not analyzed. [unverified]
- The interaction between SLRU writes and the global sync queue
  (`storage/sync.c`) — exactly when fsyncs are deferred vs. inline —
  not analyzed. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 22
- `[from-comment]`: 10
- `[unverified]`: 3
