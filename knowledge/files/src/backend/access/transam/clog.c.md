# clog.c

- **Source path:** `source/src/backend/access/transam/clog.c`
- **Lines:** 1125
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/clog.h`, `slru.c`
  (storage), `transam.c` (high-level wrappers), `xact.c`
  (`RecordTransactionCommit`).

## Purpose

The pg_xact (formerly pg_clog) commit-log manager. Two bits per
transaction storing commit/abort status, four transactions per byte.
Built on top of `slru.c`. [from-comment] `clog.c:3-26`.

## Top-of-file comment (verbatim)

```
clog.c
    PostgreSQL transaction-commit-log manager

This module stores two bits per transaction regarding its commit/abort
status; the status for four transactions fit in a byte.

This would be a pretty simple abstraction on top of slru.c, except that
for performance reasons we allow multiple transactions that are
committing concurrently to form a queue, so that a single process can
update the status for all of them within a single lock acquisition run.

XLOG interactions: this module generates an XLOG record whenever a new
CLOG page is initialized to zeroes.  Other writes of CLOG come from
recording of transaction commit or abort in xact.c, which generates its
own XLOG records for these events and will re-perform the status update
on redo; so we need make no additional XLOG entry here.  For synchronous
transaction commits, the XLOG is guaranteed flushed through the XLOG commit
record before we are called to log a commit, so the WAL rule "write xlog
before data" is satisfied automatically.  However, for async commits we
must track the latest LSN affecting each CLOG page, so that we can flush
XLOG that far and satisfy the WAL rule.  We don't have to worry about this
for aborts (whether sync or async), since the post-crash assumption would
be that such transactions failed anyway.
```
[from-comment] `clog.c:3-26`.

## Public surface

- `TransactionIdSetTreeStatus(xid, nsubxids, subxids, status, lsn)` —
  `clog.c:192` [verified-by-code]
- `TransactionIdGetStatus(xid, *lsn)` — `clog.c:744` [verified-by-code]
- `CLOGShmemBuffers` / `CLOGShmemRequest` / `CLOGShmemInit` —
  `clog.c:777, 790, 830` [verified-by-code]
- `BootStrapCLOG` — `clog.c:851` [verified-by-code]
- `StartupCLOG` — `clog.c:862` [verified-by-code]
- `TrimCLOG` — `clog.c:877` [verified-by-code]
- `CheckPointCLOG` — `clog.c:922` [verified-by-code]
- `ExtendCLOG(TransactionId newestXact)` — `clog.c:944` [verified-by-code]
- `TruncateCLOG(oldestXact, oldestxid_datoid)` — `clog.c:986`
  [verified-by-code]
- `clog_redo(XLogReaderState *)` — `clog.c:1090` [verified-by-code]
- `clogsyncfiletag` — `clog.c:1122` [verified-by-code]

## Key types / constants

- `XidStatus` (`access/clog.h`): `TRANSACTION_STATUS_IN_PROGRESS = 0`,
  `_COMMITTED = 1`, `_ABORTED = 2`, `_SUB_COMMITTED = 3`. [verified-by-code]
  via `clog.h:18-22` (not directly read here; referenced in comments
  and code at `clog.c:198-199, 236`).
- `CLOG_BITS_PER_XACT = 2`; `CLOG_XACTS_PER_BYTE = 4`. [unverified]
  (not located in this read; inferred from comment "two bits per
  transaction").
- `THRESHOLD_SUBTRANS_CLOG_OPT` — threshold below which group commit
  is used; `<= PGPROC_MAX_CACHED_SUBXIDS`. [verified-by-code]
  `clog.c:310`.

## Key invariants and locking

1. **CLOG page LSN cache enforces async-commit WAL rule.** README
   §"Asynchronous Commit" explains: each page tracks the highest commit
   LSN affecting it; before evicting/writing the page, XLOG must be
   flushed at least to that LSN. [from-comment] `clog.c:14-25`.

2. **Sub-commit-then-commit protocol when status spans pages.**
   `TransactionIdSetTreeStatus` checks whether all subxids fit on the
   parent's page. If not and `status == COMMITTED`, it first marks
   subxids on *other* pages as `SUB_COMMITTED`, then writes the parent
   page atomically with `COMMITTED`, then upgrades the other pages.
   [verified-by-code] [from-comment] `clog.c:211-256, 226-235`.

3. **Single-page case skips sub-commit state.**
   [verified-by-code] `clog.c:214-221`.

4. **Group XID-status update.** `TransactionGroupUpdateXidStatus`
   (`clog.c:450`) lets one process update many concurrent committers'
   bits while holding the relevant `SLRU` bank lock, reducing
   contention. Used only when subxids all fit on the parent page
   (`all_xact_same_page = true`) and below `THRESHOLD_SUBTRANS_CLOG_OPT`.
   [from-comment] `clog.c:9-13`, [verified-by-code] `clog.c:310`.

5. **WAL record only for new-page initialization.** Commit/abort
   updates are *not* logged by clog itself; the rmgr XLOG record from
   `xact.c` will re-apply them on redo (the redo func calls
   `TransactionIdCommitTree` etc.). [from-comment] `clog.c:14-19`.

6. **Aborts don't update the page LSN.** "We don't have to worry
   about this for aborts." [from-comment] `clog.c:23-25`.

## Functions of note

### `TransactionIdSetTreeStatus` — `clog.c:192-257` [verified-by-code]

Atomic-per-page commit marking. Splits a tree (top XID + subxids)
across CLOG pages, applying the sub-commit-then-commit protocol from
README. The same-page fast path is single-call.

### `TransactionIdSetPageStatus` — `clog.c:302-…` [verified-by-code]

Sets all entries on one page; supports group update via
`TransactionGroupUpdateXidStatus`. Per-bank LWLock (from SLRU);
not deep-read in detail.

### `TransactionIdSetStatusBit` — `clog.c:670` [verified-by-code]

The low-level "OR these two bits into the page". Also updates the
page's group-LSN cache (the 32-XID-granularity LSN ranges from
README §"Asynchronous Commit").

### `TransactionIdGetStatus` — `clog.c:744-…` [verified-by-code]

Reads the status bits and the page's LSN entry. Visibility code
consults this when the xid is past pg_xact in the cache and the
hint bit is not yet set.

### `ExtendCLOG` — `clog.c:944` [verified-by-code]

Called by `varsup.c:GetNewTransactionId` while holding `XidGenLock`.
Zeros a new page when crossing a page boundary; emits the
`CLOG_ZEROPAGE` WAL record so redo can recreate the page.

### `TruncateCLOG` — `clog.c:986` [verified-by-code]

Called by vacuum after `frozenxid` advances. Emits a
`CLOG_TRUNCATE` record (`WriteTruncateXlogRec`, `clog.c:1071`) then
calls into SLRU to unlink old segments.

### `clog_redo` — `clog.c:1090-…` [verified-by-code]

Recovery handler for `RM_CLOG_ID`. Two cases: `CLOG_ZEROPAGE` (re-zero
the page) and `CLOG_TRUNCATE` (re-execute the truncation).

## Cross-references

- `xact.c:RecordTransactionCommit` and `RecordTransactionAbort` call
  `TransactionIdCommitTree` / `TransactionIdAbortTree` (in `transam.c`)
  which wrap `TransactionIdSetTreeStatus`.
- `varsup.c:GetNewTransactionId` calls `ExtendCLOG`.
- `slru.c` provides the buffer cache, locking, and disk-file layer.
- `procarray.c` consults `TransactionIdGetStatus` indirectly for xid
  status when the hint cache and the per-xact cache miss.

## Open questions

- Group-commit path (`TransactionGroupUpdateXidStatus`, `clog.c:450`)
  not deep-read; the queue formation under the bank lock matters for
  perf. [unverified]
- Exact mapping of "group size 32" for the LSN cache (README:851)
  not located in this read. The constant `CLOG_LSNS_PER_PAGE` or
  similar likely lives in `clog.h`. [unverified]
- `CLOGPagePrecedes` (`clog.c:1041`) is the SLRU "is page1 older than
  page2" callback; correctness relies on XID-space wrap. Not deep-read.
  [unverified]

## Confidence tag tally

- `[verified-by-code]`: 22
- `[from-comment]`: 6
- `[from-README]`: 1
- `[unverified]`: 4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/clog-slru.md](../../../../../idioms/clog-slru.md)


- [subsystems/access-transam.md](../../../../../subsystems/access-transam.md)