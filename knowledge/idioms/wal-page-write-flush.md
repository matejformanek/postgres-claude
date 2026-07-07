# WAL page write & flush — XLogWrite, XLogFlush, fsync discipline

`XLogWrite` walks the WAL buffer ring, batches consecutive
contiguous pages into a single `pg_pwrite`, opens / closes segment
files as it crosses 16 MB segment boundaries, and PANICs on any
write error. `XLogFlush` is the higher-level "I need WAL up to
LSN X durable on disk before I can return" entry point — it waits
for inserters to finish, calls `XLogWrite` if not already past the
request, then issues an fsync. Together they implement the
write-then-fsync sequence that guarantees commit durability and
WAL-before-data ordering.

Anchors:
- `source/src/backend/access/transam/xlog.c:2325` — XLogWrite
  [verified-by-code]
- `source/src/backend/access/transam/xlog.c:2452-2456` —
  pgstat_report_wait_start(WAIT_EVENT_WAL_WRITE) + pg_pwrite
  [verified-by-code]
- `source/src/backend/access/transam/xlog.c:2473-2476` —
  PANIC on write failure [verified-by-code]
- `source/src/backend/access/transam/xlog.c:2801` — XLogFlush
  [verified-by-code]
- `source/src/backend/access/transam/xlog.c:2486-2495` —
  end-of-segment fsync + archive notify [verified-by-code]
- `knowledge/idioms/xloginsertlock-partitioning.md` — companion
- `knowledge/idioms/wal-buffer-state.md` — companion
- `.claude/skills/wal-and-xlog/SKILL.md` — companion

## Entry points

| Function | What it guarantees | Caller |
|---|---|---|
| `XLogWrite` | WAL pages written to OS (not yet fsync'd) up to a target LSN | XLogFlush, AdvanceXLInsertBuffer, WAL writer |
| `XLogFlush` | WAL durable on disk up to a target LSN | RecordTransactionCommit, FlushBuffer (BUFFER_LOCK_SHARE), checkpoint |
| `IssueXLogFlush` | unconditional fsync of the current segment | XLogFlush internals |

The asymmetric pair lets the bgwriter/walwriter call XLogWrite
WITHOUT fsync (for throughput) while commit paths call XLogFlush
(for durability).

## XLogWrite — the page-batch writer

[verified-by-code `xlog.c:2325-2620`]

```c
static void
XLogWrite(XLogwrtRqst WriteRqst, TimeLineID tli, bool flexible)
{
    /* Must run inside a critical section */
    Assert(CritSectionCount > 0);

    RefreshXLogWriteResult(LogwrtResult);

    curridx = XLogRecPtrToBufIdx(LogwrtResult.Write);
    while (LogwrtResult.Write < WriteRqst.Write)
    {
        EndPtr = pg_atomic_read_u64(&XLogCtl->xlblocks[curridx]);
        if (LogwrtResult.Write >= EndPtr)
            elog(PANIC, "xlog write request past end of log");
        LogwrtResult.Write = EndPtr;
        ispartialpage = WriteRqst.Write < LogwrtResult.Write;

        if (!XLByteInPrevSeg(LogwrtResult.Write, openLogSegNo,
                             wal_segment_size)) {
            /* Switch to new segment */
            if (openLogFile >= 0) XLogFileClose();
            openLogFile = XLogFileInit(openLogSegNo, tli);
        }

        /* Gather contiguous pages into one write() */
        if (npages == 0) { startidx = curridx; startoffset = ...; }
        npages++;

        last_iteration = WriteRqst.Write <= LogwrtResult.Write;
        finishing_seg = !ispartialpage && (startoffset + npages*XLOG_BLCKSZ) >= wal_segment_size;

        if (last_iteration || curridx == XLogCacheBlck || finishing_seg) {
            /* pg_pwrite the batch */
            from = XLogCtl->pages + startidx * XLOG_BLCKSZ;
            nbytes = npages * XLOG_BLCKSZ;
            do {
                pgstat_report_wait_start(WAIT_EVENT_WAL_WRITE);
                written = pg_pwrite(openLogFile, from, nleft, startoffset);
                pgstat_report_wait_end();

                if (written <= 0) {
                    if (errno == EINTR) continue;
                    ereport(PANIC, "could not write to log file %s", ...);
                }
                nleft -= written;
            } while (nleft > 0);

            npages = 0;

            if (finishing_seg) {
                issue_xlog_fsync(openLogFile, openLogSegNo);
                /* notify archiver, signal checkpointer if needed */
            }
        }
        curridx = NextBufIdx(curridx);
    }
}
```

Key properties:
- **Critical section asserted** — interrupts during write would
  leave WAL in an inconsistent state. The caller (XLogFlush,
  AdvanceXLInsertBuffer) starts the critical section.
- **Batch writes** — npages accumulates consecutive contiguous
  buffer slots; one pg_pwrite per batch.
- **Segment boundary forces flush** — `finishing_seg` triggers
  immediate fsync at end of every 16 MB segment.
- **PANIC on write failure** — any errno != EINTR aborts the
  backend (and forces recovery).

## The batch trigger conditions

[verified-by-code `xlog.c:2426-2433`]

```c
last_iteration  = WriteRqst.Write <= LogwrtResult.Write;
finishing_seg   = !ispartialpage &&
                  (startoffset + npages * XLOG_BLCKSZ) >= wal_segment_size;

if (last_iteration || curridx == XLogCacheBlck || finishing_seg)
    /* dump batch */
```

Three reasons to flush a batch:
1. **last_iteration** — we've reached the request.
2. **curridx == XLogCacheBlck** — wrapped the ring; next page
   isn't contiguous in memory.
3. **finishing_seg** — completed a 16 MB segment; must fsync
   even mid-iteration.

## Segment file lifecycle

[verified-by-code `xlog.c:2381-2398, 2486-2495`]

When `LogwrtResult.Write` crosses a segment boundary
(16 MB default):
1. Close the prior segment file (`XLogFileClose`).
2. Compute new `openLogSegNo`.
3. Open or create the new file (`XLogFileInit` —
   pre-allocates the file + zeroes it via writes).
4. After the LAST page of the segment is written:
   `issue_xlog_fsync` immediately.
5. Notify the archiver (`XLogArchiveNotify`) so it knows the
   segment is ready to ship.

The "fsync at segment-end" is an optimization vs. "open the
prior segment again later to fsync".

## XLogFlush — durability for commit

[verified-by-code `xlog.c:2801` and surrounding]

The path RecordTransactionCommit uses:

```c
void
XLogFlush(XLogRecPtr record)
{
    /* Already flushed? quick exit */
    if (record <= LogwrtResult.Flush)
        return;

    /* Loop until we've flushed past record. */
    for (;;)
    {
        /* Wait for any inserters whose work overlaps this region. */
        insertpos = WaitXLogInsertionsToFinish(record);

        LWLockAcquire(WALWriteLock, LW_EXCLUSIVE);
        RefreshXLogWriteResult(LogwrtResult);
        if (record <= LogwrtResult.Flush) {
            LWLockRelease(WALWriteLock);
            break;
        }

        /* Build the request and write */
        WriteRqst.Write = insertpos;
        WriteRqst.Flush = record;
        XLogWrite(WriteRqst, ..., false);
        issue_xlog_fsync(openLogFile, openLogSegNo);

        /* Publish new flush position */
        SpinLockAcquire(&XLogCtl->info_lck);
        XLogCtl->LogwrtRqst.Flush = ...;
        SpinLockRelease(&XLogCtl->info_lck);
        pg_atomic_write_u64(&XLogCtl->logFlushResult, LogwrtResult.Flush);

        LWLockRelease(WALWriteLock);
        break;
    }
}
```

Note the ordering: **wait inserters → acquire WALWriteLock →
re-check → XLogWrite → fsync → update flush position →
release**. The "wait inserters before acquiring WALWriteLock" is
the same deadlock-avoidance principle from AdvanceXLInsertBuffer.

## fsync method dispatch

`issue_xlog_fsync` reads `wal_sync_method` GUC and dispatches:
- `fsync` — POSIX fsync.
- `fdatasync` — POSIX fdatasync (metadata-free).
- `open_sync` / `open_datasync` — O_SYNC / O_DSYNC at open time;
  no separate fsync call.
- `fsync_writethrough` — macOS F_FULLFSYNC.

Default depends on platform; Linux is typically `fdatasync`,
macOS `fsync_writethrough`.

## Wait events for observability

[verified-by-code `xlog.c:2454-2456`]

```c
pgstat_report_wait_start(WAIT_EVENT_WAL_WRITE);
written = pg_pwrite(...);
pgstat_report_wait_end();
```

`pg_stat_activity.wait_event = 'WALWrite'` indicates a backend
stuck in pg_pwrite. Similarly `WALSync` for fsync. High counts
correlate with disk saturation.

`pg_stat_wal` aggregates: `wal_write`, `wal_sync`, `wal_write_time`,
`wal_sync_time` (when `track_wal_io_timing = on`).

## PANIC discipline

[verified-by-code `xlog.c:2473-2476`]

> A failed write is treated as PANIC because the WAL is the
> system of record; a corrupted WAL on disk means inconsistency.

PANIC kills the whole cluster and forces crash recovery. The
EINTR retry [`xlog.c:2466-2467`] is the only retryable case.

## Common review-time concerns

- **XLogWrite needs CritSectionCount > 0** — caller must start a
  critical section.
- **Don't hold WALInsertLocks while calling XLogWrite** —
  inverse of the AdvanceXLInsertBuffer rule.
- **fsync at segment end is unconditional** — even if
  WriteRqst.Flush < end-of-segment.
- **Archive notify happens here** — touching this needs care vs.
  archive recovery.
- **track_wal_io_timing** has nontrivial overhead — leave off in
  high-write production.
- **PANIC on write failure cannot be downgraded** —
  it is intentionally catastrophic.

## Invariants

- **[INV-1]** XLogWrite runs inside a critical section
  (`CritSectionCount > 0`).
- **[INV-2]** Batch boundaries are: end-of-request, ring-wrap,
  end-of-segment.
- **[INV-3]** Segment-end forces fsync regardless of caller's
  Flush request.
- **[INV-4]** Write failure (non-EINTR) is PANIC; no retry.
- **[INV-5]** XLogFlush calls WaitXLogInsertionsToFinish BEFORE
  acquiring WALWriteLock (deadlock avoidance).

## Useful greps

- The writer:
  `grep -n '^XLogWrite\|pg_pwrite\|WAIT_EVENT_WAL_WRITE' source/src/backend/access/transam/xlog.c | head -10`
- The flusher:
  `grep -n '^XLogFlush\|issue_xlog_fsync\|logFlushResult' source/src/backend/access/transam/xlog.c | head -10`
- Segment file lifecycle:
  `grep -n 'XLogFileInit\|XLogFileClose\|XLogFileOpen\|openLogSegNo' source/src/backend/access/transam/xlog.c | head -10`
- fsync methods:
  `grep -RIn 'wal_sync_method\|WAL_SYNC_METHOD' source/src/backend/access/transam/xlog.c source/src/backend/utils/misc | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 2325 | XLogWrite |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 2452 | pgstat_report_wait_start(WAIT_EVENT_WAL_WRITE) + pg_pwrite |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 2473 | PANIC on write failure |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 2486 | end-of-segment fsync + archive notify |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 2801 | XLogFlush |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | — | full module |
| [`src/backend/access/transam/xlogarchive.c`](../files/src/backend/access/transam/xlogarchive.c.md) | — | XLogArchiveNotify |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-wal-record`](../scenarios/add-new-wal-record.md)
- [`bump-catversion`](../scenarios/bump-catversion.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/xloginsertlock-partitioning.md` — produces
  the byte ranges XLogWrite drains.
- `knowledge/idioms/wal-buffer-state.md` — the ring being read.
- `knowledge/idioms/commit-sequence.md` —
  RecordTransactionCommit → XLogFlush.
- `knowledge/idioms/checkpoint-flow.md` — checkpoint calls
  XLogWrite + XLogFlush.
- `knowledge/data-structures/xlogrecord.md` — record format on
  disk.
- `knowledge/subsystems/transam-xlog.md` — module overview.
- `.claude/skills/wal-and-xlog/SKILL.md` — companion.
- `source/src/backend/access/transam/xlog.c` — full module.
- `source/src/backend/access/transam/xlogarchive.c` —
  XLogArchiveNotify.
