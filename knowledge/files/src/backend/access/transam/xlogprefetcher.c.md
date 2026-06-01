# xlogprefetcher.c

- **Source path:** `source/src/backend/access/transam/xlogprefetcher.c`
- **Lines:** 1106
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogprefetcher.h`,
  `xlogreader.c` (wrapped), `xlogrecovery.c` (the consumer),
  `storage/buffer/bufmgr.c` (`PrefetchBuffer`).

## Purpose

Drop-in replacement for an `XLogReader` that looks ahead in the WAL
and issues async `PrefetchBuffer` calls for blocks that will be
needed soon by recovery. Effective mainly on Linux where
`posix_fadvise` does something useful. Only the main fork is
prefetched. [from-comment] `xlogprefetcher.c:13-22`.

## Top-of-file comment (verbatim)

```
xlogprefetcher.c
    Prefetching support for recovery.

This module provides a drop-in replacement for an XLogReader that tries to
minimize I/O stalls by looking ahead in the WAL.  If blocks that will be
accessed in the near future are not already in the buffer pool, it initiates
I/Os that might complete before the caller eventually needs the data.  When
referenced blocks are found in the buffer pool already, the buffer is
recorded in the decoded record so that XLogReadBufferForRedo() can try to
avoid a second buffer mapping table lookup.

Currently, only the main fork is considered for prefetching.  Currently,
prefetching is only effective on systems where PrefetchBuffer() does
something useful (mainly Linux).
```
[verified-by-code] `xlogprefetcher.c:3-22`.

## Public surface

- `XLogPrefetcherAllocate(reader)` — `xlogprefetcher.c:367`
  [verified-by-code]
- `XLogPrefetcherFree(prefetcher)` — `xlogprefetcher.c:395`
  [verified-by-code]
- `XLogPrefetcherGetReader(prefetcher)` — `xlogprefetcher.c:406`
  [verified-by-code]
- `XLogPrefetcherBeginRead(prefetcher, recPtr)` — `xlogprefetcher.c:967`
  [verified-by-code]
- `XLogPrefetcherReadRecord(prefetcher, **errmsg)` — `xlogprefetcher.c:986`
  [verified-by-code]
- `XLogPrefetcherComputeStats(prefetcher)` — `xlogprefetcher.c:415`
  [verified-by-code]
- `XLogPrefetcherNextBlock(pgsr_private, *lsn)` — `xlogprefetcher.c:464`
  [verified-by-code]
- Shmem + GUC hooks: `XLogPrefetchShmemRequest`,
  `XLogPrefetchShmemInit`, `XLogPrefetchResetStats`,
  `XLogPrefetchReconfigure`, `check_recovery_prefetch`,
  `assign_recovery_prefetch` — `xlogprefetcher.c:305-1100`
  [verified-by-code]
- `pg_stat_get_recovery_prefetch(PG_FUNCTION_ARGS)` —
  `xlogprefetcher.c:829` [verified-by-code]

## Key types

- `XLogPrefetcher` — wraps an `XLogReaderState *`, a
  `LsnReadQueue` of in-flight prefetches, per-block filters
  (relations / forks to skip), and stats counters.
  [verified-by-code] `xlogprefetcher.c:962-…`.
- `LsnReadQueue` — fixed-size circular buffer of LSN→prefetched
  buffer hints. Helpers: `lrq_alloc`, `lrq_inflight`,
  `lrq_completed`, `lrq_prefetch`, `lrq_complete_lsn`.
  [verified-by-code] `xlogprefetcher.c:213-303`.

## Key invariants and locking

1. **Single-reader, no cross-process locking on the queue.** The
   startup process is the only owner of the prefetcher state;
   shared-mem state is only counters.

2. **Filtering prevents repeated I/O for relations being created
   or truncated.** `XLogPrefetcherAddFilter` /
   `XLogPrefetcherIsFiltered` / `XLogPrefetcherCompleteFilters`
   suppress prefetch for blocks that will be invalid until a later
   record. [verified-by-code] `xlogprefetcher.c:861-957`.

3. **Distance and completion bookkeeping** are GUC-driven
   (`recovery_prefetch`, `maintenance_io_concurrency`).
   `XLogPrefetchReconfigure` rebuilds the queue on GUC change.
   [verified-by-code] `xlogprefetcher.c:345-365, 1086-1100`.

## Functions of note

### `XLogPrefetcherReadRecord` — `xlogprefetcher.c:986`
[verified-by-code]

The drop-in replacement: calls `XLogReadAhead` to decode further
records, walks the LSN queue to drain completed prefetches, then
returns the next decoded record (just like `XLogReadRecord`).

### `XLogPrefetcherNextBlock` — `xlogprefetcher.c:464`
[verified-by-code]

The callback `lrq_prefetch` uses to find the next block worth
prefetching: looks at each registered buffer in upcoming records,
checks filters, dispatches `PrefetchBuffer`.

### `pg_stat_get_recovery_prefetch` — `xlogprefetcher.c:829`
[verified-by-code]

Exposes counters: `prefetch`, `hit`, `skip_init`, `skip_new`,
`skip_fpw`, `skip_rep`, `wal_distance`, `block_distance`,
`io_depth`.

## Cross-references

- `xlogrecovery.c:ReadRecord` calls `XLogPrefetcherReadRecord`.
- `xlogreader.c:XLogReadAhead` is the underlying async-decode entry.
- `storage/buffer/bufmgr.c:PrefetchBuffer` is the I/O initiator.
- `pg_stat_recovery_prefetch` view consumes the SRF above.

## Open questions

- The `LsnReadQueue` sizing / dispatch heuristic (relationship to
  `maintenance_io_concurrency`) not deep-read. [unverified]
- Filter lifetime correctness across timeline switches not
  re-derived. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 17
- `[from-comment]`: 1
- `[unverified]`: 2
