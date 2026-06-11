# Issues — `storage-buffer`

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent subsystem doc:** `knowledge/subsystems/storage-buffer.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | storage/buffer/freelist.c:274 | doc-drift | nit | `elog(ERROR, "no unpinned buffers available")` lacks errhint pointing at `pg_buffercache` or `shared_buffers` tuning guidance | open | knowledge/files/src/backend/storage/buffer/freelist.c.md §Potential issues |
| 2026-06-11 | storage/buffer/freelist.c:213 | undocumented-invariant | maybe | bgwriter latch wakeup assumes `PGPROC->procLatch` is never freed; race window with bgwriter exit can wake the wrong process | open | knowledge/files/src/backend/storage/buffer/freelist.c.md §Potential issues |
| 2026-06-11 | storage/buffer/freelist.c:467 | style | nit | `ring_max_kb = Max(ring_size_kb, ring_max_kb)` — variable named `_max_kb` actually carries the cap-floor-bound after this line; misleading | open | knowledge/files/src/backend/storage/buffer/freelist.c.md §Potential issues |
| 2026-06-11 | storage/buffer/buf_table.c:60 | undocumented-invariant | nit | `NBuffers + NUM_BUFFER_PARTITIONS` slack is a global cushion shared across partitions; pathological skew not bounded per-partition | open | knowledge/files/src/backend/storage/buffer/buf_table.c.md §Potential issues |
| 2026-06-11 | storage/buffer/buf_init.c:132 | undocumented-invariant | nit | `BufferManagerShmemInit` per-field init must cover all non-zero-default `BufferDesc` fields; relies on caller shmem zero-fill for the rest | open | knowledge/files/src/backend/storage/buffer/buf_init.c.md §Potential issues |
| 2026-06-11 | storage/buffer/localbuf.c:257 | leak | maybe | Orphaned AIO ref on a local buffer (post-abort) can permanently skip that buffer in clock sweep until backend exit — empty branch body | open | knowledge/files/src/backend/storage/buffer/localbuf.c.md §Potential issues |
| 2026-06-11 | storage/buffer/localbuf.c:931 | leak | maybe | `LocalBufferContext` (TopMemoryContext child) is never reset; temp-buffer storage retained for backend lifetime even after all temp tables dropped | open | knowledge/files/src/backend/storage/buffer/localbuf.c.md §Potential issues |
| 2026-06-11 | storage/buffer/localbuf.c:822 | stale-todo | nit | `XXX: We could have a slightly more efficient version of PinLocalBuffer() that does not support adjusting the usagecount` | open | knowledge/files/src/backend/storage/buffer/localbuf.c.md §Potential issues |
| 2026-06-11 | storage/buffer/localbuf.c:442 | undocumented-invariant | nit | `found = true` branch in `ExtendBufferedRelLocal` (hash entry survives without buffer slot) is unreachable in practice but undocumented | open | knowledge/files/src/backend/storage/buffer/localbuf.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

storage-buffer is the calibration subsystem (most-read; deepest docs).
First Phase A issues are likely to surface here — `bufmgr.c` has 8,967
lines and several `XXX` / `TODO` comments worth triaging.

Sweep A19 (2026-06-11) added 9 issues from the four tail files:
`buf_init.c`, `buf_table.c`, `freelist.c`, `localbuf.c`. The two
load-bearing observations:

1. **localbuf.c clock sweep can be permanently degraded** by an
   orphaned AIO ref left after error (line 257-263, currently an
   empty branch body). Worth a real fix or at least a comment.
2. **localbuf.c `LocalBufferContext` is backend-lifetime** by design
   (line 931, "we'll never give back a local buffer once it's created")
   — but a connection pooler running pgbouncer in transaction-pool
   mode with workloads that touch temp tables sporadically may see
   this as a memory leak. The trade-off is intentional.
