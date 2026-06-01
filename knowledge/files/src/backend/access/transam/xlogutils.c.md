# xlogutils.c

- **Source path:** `source/src/backend/access/transam/xlogutils.c`
- **Lines:** 1034
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogutils.h`,
  `xlogreader.c`, `xlogrecovery.c`, every redo handler.

## Purpose

Helpers shared by redo routines: buffer-fetch with "missing /
truncated" hazard tracking (`XLogReadBufferForRedo*`,
`XLogReadBufferExtended`), the invalid-page hash for tolerating
references to no-longer-existing pages until they are dropped,
fake-relcache entries, drop/truncate forwarding, and the canonical
read-page callbacks used by readers in normal backends (e.g. logical
decoding) — not by the startup process. [from-comment]
`xlogutils.c:3-7`.

## Top-of-file comment (verbatim)

```
xlogutils.c

PostgreSQL write-ahead log manager utility routines

This file contains support routines that are used by XLOG replay functions.
None of this code is used during normal system operation.
```
[verified-by-code] `xlogutils.c:3-7`.

## Public surface

Redo-helper buffer fetch:

- `XLogReadBufferForRedo(record, block_id, *buf)` — `xlogutils.c:303`
  [verified-by-code]
- `XLogInitBufferForRedo(record, block_id)` — `xlogutils.c:315`
  [verified-by-code]
- `XLogReadBufferForRedoExtended(record, …, mode, get_cleanup_lock,
  *buf)` — `xlogutils.c:340` [verified-by-code]
- `XLogReadBufferExtended(rlocator, forknum, blkno, mode, recent_buffer)`
  — `xlogutils.c:460` [verified-by-code]

Invalid-page tracking:

- `report_invalid_page(elevel, rlocator, forkno, blkno, present)` —
  `xlogutils.c:86` [verified-by-code]
- `log_invalid_page` / `forget_invalid_pages` /
  `forget_invalid_pages_db` / `XLogHaveInvalidPages` /
  `XLogCheckInvalidPages` — `xlogutils.c:101-234` [verified-by-code]

Drop forwarding:

- `XLogDropRelation` — `xlogutils.c:630` [verified-by-code]
- `XLogDropDatabase` — `xlogutils.c:641` [verified-by-code]
- `XLogTruncateRelation` — `xlogutils.c:660` [verified-by-code]

Fake relcache:

- `CreateFakeRelcacheEntry(rlocator)` — `xlogutils.c:571`
  [verified-by-code]
- `FreeFakeRelcacheEntry(fakerel)` — `xlogutils.c:618`
  [verified-by-code]

Reader callbacks for non-startup readers:

- `XLogReadDetermineTimeline(state, wantPage)` — `xlogutils.c:707`
  [verified-by-code]
- `wal_segment_open(state, nextSegNo, …)` — `xlogutils.c:806`
  [verified-by-code]
- `wal_segment_close(state)` — `xlogutils.c:831` [verified-by-code]
- `read_local_xlog_page` / `_no_wait` / `_guts` —
  `xlogutils.c:845, 857, 869` [verified-by-code]
- `WALReadRaiseError(WALReadError *)` — `xlogutils.c:1011`
  [verified-by-code]

## Key invariants and locking

1. **Invalid pages must be resolved by end of recovery.**
   `XLogCheckInvalidPages` PANICs if any are still recorded.
   [verified-by-code] `xlogutils.c:234-…`. The hash is populated by
   `log_invalid_page` whenever a redo asks for a block in a
   non-existent or already-truncated relation; `XLogDrop*` /
   `XLogTruncateRelation` remove entries that get superseded.

2. **`XLogReadBufferForRedo` returns one of {`BLK_NEEDS_REDO`,
   `BLK_DONE`, `BLK_RESTORED`, `BLK_NOTFOUND`}.** The handler
   uses this to decide whether to apply the delta, skip (page
   already at/past the record's LSN), use the FPI, or accept that
   the page is gone. [unverified] — exact enum lives in
   `xlogutils.h`.

3. **Hot-standby readers must lock pages even though only Startup
   writes.** The README says PageSet/GetLSN must be done under
   buffer lock unless you are Startup; the redo helpers issue
   appropriate locks. [from-README] (README:620-626).

4. **Fake relcache entries** let drop/truncate forwarding work
   without a full pg_class lookup during recovery.
   [verified-by-code] `xlogutils.c:571-628`.

5. **`read_local_xlog_page*` is for non-startup readers in a
   running backend** (e.g. logical decoding from WAL); it waits via
   `WaitForReplicationOrigin` etc. [verified-by-code] (around
   `xlogutils.c:845-1010`).

## Functions of note

### `XLogReadBufferForRedoExtended` — `xlogutils.c:340` [verified-by-code]

The heart of redo buffer access. For each registered block: fetch /
init the buffer, check whether the block's LSN is already at or past
the record's `EndRecPtr` (skip), or whether the record carries an
FPI (restore image), else return `BLK_NEEDS_REDO`.

### `XLogReadBufferExtended` — `xlogutils.c:460` [verified-by-code]

Lower-level: open the smgr relation (fake relcache entry), check the
block exists (extending the file if needed), pin it. Handles the
"page was beyond EOF" / "relation no longer exists" hazards by
calling `log_invalid_page`.

### `XLogTruncateRelation` — `xlogutils.c:660` [verified-by-code]

When redo of a truncate record sees a smaller post-truncate length,
remove invalid-page entries for blocks above the cutoff (they are
no longer "missing").

### `wal_segment_open` / `read_local_xlog_page_guts` —
`xlogutils.c:806, 869` [verified-by-code]

Standard callbacks for a backend that wants to read WAL via
`XLogReader` (logical decoding, `pg_walinspect`). The startup
process uses different callbacks in `xlogrecovery.c`.

## Cross-references

- Every redo handler in `access/heap/heapam.c`, `nbtxlog.c`,
  `ginxlog.c`, `gistxlog.c`, `hash_xlog.c`, `spgxlog.c`,
  `brin_xlog.c` calls `XLogReadBufferForRedo`.
- `xlogrecovery.c:CheckRecoveryConsistency` consults
  `XLogHaveInvalidPages` to determine consistency at the
  end-of-redo barrier.
- `storage/smgr/smgr.c` is the layer the fake-relcache wraps.

## Open questions

- The `XLogRedoAction` enum values not enumerated here. [unverified]
- The `recent_buffer` optimization in `XLogReadBufferExtended` (using
  a hint from the prefetcher) not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 22
- `[from-comment]`: 1
- `[from-README]`: 1
- `[unverified]`: 3
