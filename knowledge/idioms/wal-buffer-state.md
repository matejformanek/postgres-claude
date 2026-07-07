# WAL buffer state — XLogCtl, xlblocks, and AdvanceXLInsertBuffer

WAL records are first copied into a ring of in-memory pages
(`XLogCtl->pages`, sized by `wal_buffers` GUC). The buffer ring's
state lives in `XLogCtl` (the WAL shared-memory control struct)
and is indexed by a parallel array `xlblocks[]`: each slot's
atomic uint64 holds the END LSN of whatever page currently
occupies that buffer index. When an inserter reaches a page that
hasn't been allocated yet, `AdvanceXLInsertBuffer` runs the
buffer-slot recycle path — evict (flush) the old page, zero the
new buffer, write the XLog page header, and atomically publish
the new end-LSN into `xlblocks[idx]`. Two LWLocks gate this:
`WALBufMappingLock` (page allocation) and `WALWriteLock` (the
flusher).

Anchors:
- `source/src/backend/access/transam/xlog.c:575` —
  static XLogCtlData *XLogCtl [verified-by-code]
- `source/src/backend/access/transam/xlog.c:457-469` —
  XLogCtlData struct head [verified-by-code]
- `source/src/backend/access/transam/xlog.c:1673` —
  GetXLogBuffer [verified-by-code]
- `source/src/backend/access/transam/xlog.c:2025-2185` —
  AdvanceXLInsertBuffer [verified-by-code]
- `source/src/backend/access/transam/xlog.c:403-452` —
  XLogCtlInsert struct + WALInsertLocks pointer [verified-by-code]
- `knowledge/idioms/xloginsertlock-partitioning.md` — companion
- `knowledge/idioms/wal-page-write-flush.md` — companion
- `.claude/skills/wal-and-xlog/SKILL.md` — companion

## XLogCtl — the WAL control block

[verified-by-code `xlog.c:457-470, 575`]

```c
static XLogCtlData *XLogCtl = NULL;   /* shared-memory pointer */

typedef struct XLogCtlData
{
    XLogCtlInsert   Insert;          /* inserter sub-control */
    XLogwrtRqst     LogwrtRqst;       /* requested Write/Flush LSNs */
    XLogRecPtr      RedoRecPtr;       /* recent copy for read-only access */
    XLogRecPtr      asyncXactLSN;
    XLogRecPtr      replicationSlotMinLSN;
    XLogSegNo       lastRemovedSegNo;
    /* ... fake LSN counters, init flags, etc. ... */

    pg_atomic_uint64 *xlblocks;       /* end-LSN of page in each buffer */
    int              XLogCacheBlck;   /* highest valid index in xlblocks */
    char            *pages;            /* the actual XLOG buffer array */
    XLogRecPtr       InitializedUpTo; /* highest end-LSN initialized */
    /* ... */
} XLogCtlData;
```

`XLogCtl` is a backend-static pointer set by `XLOGShmemInit`
[`xlog.c:5345`]; every process maps the same shared block.

## xlblocks[] — what each buffer slot holds

[verified-by-code via `xlog.c:2051, 2370, 5326`]

`xlblocks` is an array of `pg_atomic_uint64`, one per WAL buffer
page. `xlblocks[idx]` stores the END LSN of the page currently
sitting in `pages[idx]` — i.e., `pageBeginLSN + XLOG_BLCKSZ`.

Why "end-LSN" not "start-LSN":
- Comparing "have we written past this page yet?" is `Write >=
  xlblocks[idx]` — cheap.
- During slot recycling, `xlblocks[idx] = InvalidXLogRecPtr`
  signals "this page is being initialized; don't read it"
  (`xlog.c:2131`).

`XLogRecPtrToBufIdx(lsn)` does `(lsn / XLOG_BLCKSZ) %
wal_buffers` — the LSN modulo the ring size.

## GetXLogBuffer — find or wait for the right page

[verified-by-code `xlog.c:1673` and surrounding]

Called per record after lock acquire. For a given target
`XLogRecPtr ptr`:

1. Compute `idx = XLogRecPtrToBufIdx(ptr)`.
2. Read `xlblocks[idx]` atomically.
3. If it covers `ptr` (i.e., the page starting at `ptr - (ptr %
   XLOG_BLCKSZ)` is still the one in that slot) — return a
   pointer into `pages[idx]`.
4. Else, the slot needs to be recycled — call
   `AdvanceXLInsertBuffer(ptr, tli, false)`.

The fast path is a single atomic read + comparison — no locks if
the page is already there.

## AdvanceXLInsertBuffer — the slot recycle path

[verified-by-code `xlog.c:2025-2185`]

```c
LWLockAcquire(WALBufMappingLock, LW_EXCLUSIVE);

while (upto >= XLogCtl->InitializedUpTo || opportunistic)
{
    nextidx = XLogRecPtrToBufIdx(XLogCtl->InitializedUpTo);

    OldPageRqstPtr = pg_atomic_read_u64(&XLogCtl->xlblocks[nextidx]);
    if (LogwrtResult.Write < OldPageRqstPtr) {
        /* the old occupant isn't yet on disk — must flush it */

        if (opportunistic)
            break;

        /* Bump LogwrtRqst.Write */
        SpinLockAcquire(&XLogCtl->info_lck);
        if (XLogCtl->LogwrtRqst.Write < OldPageRqstPtr)
            XLogCtl->LogwrtRqst.Write = OldPageRqstPtr;
        SpinLockRelease(&XLogCtl->info_lck);

        RefreshXLogWriteResult(LogwrtResult);
        if (LogwrtResult.Write < OldPageRqstPtr) {
            LWLockRelease(WALBufMappingLock);  /* deadlock avoidance */

            WaitXLogInsertionsToFinish(OldPageRqstPtr);

            LWLockAcquire(WALWriteLock, LW_EXCLUSIVE);
            /* ... maybe XLogWrite ... */
            LWLockRelease(WALWriteLock);

            LWLockAcquire(WALBufMappingLock, LW_EXCLUSIVE);
            continue;
        }
    }

    /* Slot is free; initialize new page. */
    pg_atomic_write_u64(&xlblocks[nextidx], InvalidXLogRecPtr);
    pg_write_barrier();
    MemSet(NewPage, 0, XLOG_BLCKSZ);
    NewPage->xlp_magic = XLOG_PAGE_MAGIC;
    NewPage->xlp_tli = tli;
    NewPage->xlp_pageaddr = NewPageBeginPtr;
    if (XLogSegmentOffset(NewPageBeginPtr, wal_segment_size) == 0) {
        /* long header for first page of segment */
        NewLongPage->xlp_sysid = ControlFile->system_identifier;
        NewPage->xlp_info |= XLP_LONG_HEADER;
    }
    pg_write_barrier();
    pg_atomic_write_u64(&xlblocks[nextidx], NewPageEndPtr);
    XLogCtl->InitializedUpTo = NewPageEndPtr;
}

LWLockRelease(WALBufMappingLock);
```

## The two write barriers

[verified-by-code `xlog.c:2127-2132, 2169`]

```
xlblocks[nextidx] = InvalidXLogRecPtr;   /* "being recycled" */
pg_write_barrier();                       /* (1) */
MemSet(NewPage, 0, XLOG_BLCKSZ);
/* fill xlp_magic, xlp_tli, xlp_pageaddr */
pg_write_barrier();                       /* (2) */
xlblocks[nextidx] = NewPageEndPtr;        /* publish */
```

Barrier (1) ensures readers see `InvalidXLogRecPtr` BEFORE the
new page's bytes are visible — without it, a concurrent reader
might see partial garbage.

Barrier (2) ensures the page contents (zero fill + header) are
fully visible BEFORE the slot's `xlblocks` entry advertises the
new end-LSN. `GetXLogBuffer` reads `xlblocks` without holding
WALBufMappingLock, so the write order matters.

## WALBufMappingLock vs WALWriteLock

| Lock | Purpose | Held by |
|---|---|---|
| WALBufMappingLock | Serialize page initialization | inserter triggering recycle, or opportunistic background path |
| WALWriteLock | Serialize XLogWrite() calls | the recycler if it must flush; checkpointer; XLogFlush callers |
| WAL insert locks (8) | Per-record insertion | inserters |

`AdvanceXLInsertBuffer` releases WALBufMappingLock BEFORE
acquiring WALWriteLock to avoid deadlock with another inserter
that holds an insert-lock and is waiting on
WALBufMappingLock.

## InitializedUpTo — the high-water mark

`XLogCtl->InitializedUpTo` is the highest LSN that's been
allocated a buffer slot. Only protected by `WALBufMappingLock`.
The loop in `AdvanceXLInsertBuffer` advances it page by page; the
opportunistic path can stop early if it'd need to flush.

## Opportunistic pre-initialization

Called from the background WAL writer to pre-allocate buffer
slots without ever blocking on a flush. Passes `opportunistic =
true`; the function bails on the first slot that would require
flushing. Keeps the buffer ring "hot" for normal-path inserters
during quiet periods.

## wal_buffers GUC

Sized to `wal_buffers_mb` MB by default `-1` (auto, ~3% of
shared_buffers, max 16 MB). Each slot is one XLOG page
(typically 8 KB), so 16 MB = 2048 slots. Larger settings smooth
write spikes but consume shared memory.

## Common review-time concerns

- **xlblocks reads are lock-free** — only writes are
  WALBufMappingLock-protected. Memory-order subtleties depend on
  the barriers.
- **xlblocks[idx] == InvalidXLogRecPtr means "being recycled"** —
  don't dereference pages[idx].
- **The long page header is per-segment** — XLP_LONG_HEADER adds
  sysid + seg_size + xlog_blcksz to the first page of each WAL
  segment.
- **InitializedUpTo only advances** — never wraps; the buffer
  index wraps via modulo.
- **Pre-init is opportunistic** — the background WAL writer
  populates the ring; inserters trigger the slow path only on
  miss.
- **Sizing wal_buffers too low** causes inserter-driven flushes
  on every page miss; observe `wal_buffers_full` in pg_stat_wal.

## Invariants

- **[INV-1]** `XLogCtl` is one shared-memory struct, mapped read-
  write by all backends.
- **[INV-2]** `xlblocks[idx]` holds the END LSN of the page in
  `pages[idx]`; `InvalidXLogRecPtr` during recycle.
- **[INV-3]** Two write barriers in AdvanceXLInsertBuffer enforce
  the publish-after-init order.
- **[INV-4]** WALBufMappingLock and WALWriteLock are acquired in
  that order; release WALBufMappingLock before acquiring
  WALWriteLock to avoid deadlock with inserters.
- **[INV-5]** `InitializedUpTo` monotonically increases under
  WALBufMappingLock.

## Useful greps

- The control struct:
  `grep -n 'XLogCtlData\|XLogCtlInsert\|^XLogCtl ' source/src/backend/access/transam/xlog.c | head -15`
- Buffer ring + xlblocks:
  `grep -n 'xlblocks\|XLogRecPtrToBufIdx\|InitializedUpTo' source/src/backend/access/transam/xlog.c | head -15`
- Recycler:
  `grep -n 'AdvanceXLInsertBuffer\|WALBufMappingLock' source/src/backend/access/transam/xlog.c | head -10`
- Page header writers:
  `grep -n 'xlp_magic\|XLP_LONG_HEADER\|XLogLongPageHeader' source/src/backend/access/transam/xlog.c | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 403 | XLogCtlInsert struct + WALInsertLocks pointer |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 457 | XLogCtlData struct head |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 575 | static XLogCtlData XLogCtl |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 1673 | GetXLogBuffer |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | 2025 | AdvanceXLInsertBuffer |
| [`src/backend/access/transam/xlog.c`](../files/src/backend/access/transam/xlog.c.md) | — | full module |
| [`src/include/access/xlog.h`](../files/src/include/access/xlog.h.md) | — | public LSN ops |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/xloginsertlock-partitioning.md` —
  who calls GetXLogBuffer + AdvanceXLInsertBuffer.
- `knowledge/idioms/wal-page-write-flush.md` — XLogWrite drains
  the buffer ring to disk.
- `knowledge/idioms/atomic-memory-barriers.md` — the
  pg_write_barrier semantics.
- `knowledge/data-structures/xlogrecord.md` — what gets copied
  into the pages.
- `knowledge/subsystems/transam-xlog.md` — module overview.
- `.claude/skills/wal-and-xlog/SKILL.md` — companion.
- `source/src/backend/access/transam/xlog.c` — full module.
- `source/src/include/access/xlog.h` — public LSN ops.
