# xlog.c

- **Source path:** `source/src/backend/access/transam/xlog.c`
- **Lines:** 10195
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xloginsert.c` (record assembly), `xlogrecovery.c` (replay),
  `xlogreader.c` (record decode), `xlogutils.c` (redo helpers),
  `source/src/include/access/{xlog.h,xlog_internal.h,xlogdefs.h}`,
  `source/src/backend/postmaster/{checkpointer.c,walwriter.c,startup.c}`.

## Purpose

The WAL manager's runtime spine: it coordinates database startup
(`StartupXLOG`), the WAL insertion fast-path (`XLogInsertRecord`), flushing
to disk (`XLogFlush`, `XLogBackgroundFlush`), segment-file lifecycle (init,
copy, install, recycle, remove), the control file (`pg_control`), and
checkpoint accounting. [from-comment] `xlog.c:6-28`.

## Top-of-file comment (verbatim)

```
xlog.c
    PostgreSQL write-ahead log manager

The Write-Ahead Log (WAL) functionality is split into several source
files, in addition to this one:

xloginsert.c - Functions for constructing WAL records
xlogrecovery.c - WAL recovery and standby code
xlogreader.c - Facility for reading WAL files and parsing WAL records
xlogutils.c - Helper functions for WAL redo routines

This file contains functions for coordinating database startup and
checkpointing, and managing the write-ahead log buffers when the
system is running.

StartupXLOG() is the main entry point of the startup process.  It
coordinates database startup, performing WAL recovery, and the
transition from WAL recovery into normal operations.

XLogInsertRecord() inserts a WAL record into the WAL buffers.  Most
callers should not call this directly, but use the functions in
xloginsert.c to construct the WAL record.  XLogFlush() can be used
to force the WAL to disk.
```
[from-comment] `xlog.c:3-25`.

## Public surface

Insert/flush/wait (called by `xloginsert.c` and across the tree):

- `XLogInsertRecord` — `xlog.c:784` [verified-by-code]
- `XLogFlush` — `xlog.c:2801` [verified-by-code]
- `XLogBackgroundFlush` — `xlog.c:3004` [verified-by-code]
- `XLogNeedsFlush` — `xlog.c:3159` [verified-by-code]
- `XLogSetAsyncXactLSN` — `xlog.c:2630` [verified-by-code]
- `XLogSetReplicationSlotMinimumLSN` — `xlog.c:2687` [verified-by-code]
- `WaitXLogInsertionsToFinish` — `xlog.c:1545` [verified-by-code]
- `WALReadFromBuffers` — `xlog.c:1789` [verified-by-code]

Startup + recovery transition (driven by startup process):

- `StartupXLOG` — `xlog.c:5846` [verified-by-code]
- `LocalProcessControlFile` — `xlog.c:5270` [verified-by-code]
- `BootStrapXLOG` — `xlog.c:5454` [verified-by-code]
- `XLogInitNewTimeline` — `xlog.c:5631` [verified-by-code]
- `SwitchIntoArchiveRecovery` — `xlog.c:6709` [verified-by-code]
- `ReachedEndOfBackup` — `xlog.c:6747` [verified-by-code]
- `ShutdownXLOG` — `xlog.c:7102` [verified-by-code]

State queries:

- `RecoveryInProgress` — `xlog.c:6834` [verified-by-code]
- `GetRecoveryState` — `xlog.c:6870` [verified-by-code]
- `XLogInsertAllowed` — `xlog.c:6889` [verified-by-code]
- `LocalSetXLogInsertAllowed` — `xlog.c:6922` [verified-by-code]
- `GetRedoRecPtr` — `xlog.c:6937` [verified-by-code]
- `GetFullPageWriteInfo` — `xlog.c:6967` [verified-by-code]
- `GetInsertRecPtr` — `xlog.c:6982` [verified-by-code]
- `GetFlushRecPtr` — `xlog.c:6999` [verified-by-code]
- `GetLastImportantRecPtr` — `xlog.c:7056` [verified-by-code]

Segment-file lifecycle:

- `XLogFileInit`, `XLogFileCopy`, `InstallXLogFileSegment`, `XLogFileOpen`,
  `XLogFileClose` — `xlog.c:3431-3739` [verified-by-code]
- `PreallocXlogFiles`, `RemoveOldXlogFiles`, `RemoveTempXlogFiles`,
  `RemoveNonParentXlogFiles`, `RemoveXlogFile`, `CheckXLogRemoved` —
  `xlog.c:3741-4148` [verified-by-code]
- `ValidateXLOGDirectoryStructure` — `xlog.c:4150` [verified-by-code]
- `CleanupBackupHistory` — `xlog.c:4212` [verified-by-code]

Control file:

- `InitControlFile`, `WriteControlFile`, `ReadControlFile`,
  `UpdateControlFile` — `xlog.c:4255-4641` [verified-by-code]
- Data-checksum state machine — `xlog.c:4674-4979` [verified-by-code]
- `GetSystemIdentifier`, `GetMockAuthenticationNonce`,
  `GetFakeLSNForUnloggedRel`, `GetDefaultCharSignedness` —
  `xlog.c:4643-5022` [verified-by-code]

Shared memory:

- `XLOGShmemRequest`, `XLOGShmemInit`, `XLOGShmemAttach` —
  `xlog.c:5294-5453` [verified-by-code]

## Key types / structs

### `XLogwrtRqst` (`xlog.c:326-330`) / `XLogwrtResult` (`xlog.c:332-336`) [verified-by-code]

Paired request/result LSNs for the `Write` and `Flush` watermarks. The
request is shared (`XLogCtl->LogwrtRqst`, protected by `info_lck`); the
result lives in two atomic globals (`logWriteResult`, `logFlushResult`)
plus a per-backend cached copy `LogwrtResult`. [from-comment]
`xlog.c:298-307`.

### `WALInsertLock` (`xlog.c:374-379`) [verified-by-code]

`{ LWLock lock; pg_atomic_uint64 insertingAt; XLogRecPtr lastImportantAt; }`.
There are `NUM_XLOGINSERT_LOCKS = 8` of them (`xlog.c:157`). Padded to a
cache line (`WALInsertLockPadded`, `xlog.c:388-392`). To insert you take
*one*; to lock out all inserters (e.g. for `XLOG_SWITCH`,
`XLOG_CHECKPOINT_REDO`) you take *all eight*. [from-comment]
`xlog.c:339-372`.

### `XLogCtlInsert` (`xlog.c:403-…`) [verified-by-code]

Insertion-side shared state: `insertpos_lck` (spinlock),
`CurrBytePos`/`PrevBytePos` ("usable byte positions"), `RedoRecPtr`,
`fullPageWrites`, `runningBackups`. The "usable byte position" encoding
strips page headers so reserving space and computing the resulting
LSN can be done without per-page bookkeeping (see `XLogBytePosToRecPtr`
`xlog.c:1899`). [from-comment] `xlog.c:404-415`.

### `XLogCtlData` (deep in file, ~`xlog.c:430-540`)

Big shared-memory blob holding `Insert`, `LogwrtRqst`, page
descriptors (`xlblocks[]`), `xlogCtlBufLwLocks[]`, `InsertTimeLineID`,
`SharedRecoveryState`, etc. [unverified] (not deep-read here)

### Module globals: insertion bookkeeping

- `ProcLastRecPtr`, `XactLastRecEnd`, `XactLastCommitEnd` —
  per-backend last-insert positions. The comment at `xlog.c:246-258`
  explains the parallel-mode subtlety: leader/worker write WAL
  independently, and `WaitForParallelWorkersToFinish` rolls up the
  leader's value. [from-comment]
- `RedoRecPtr` — backend-local cached copy; refreshed when holding an
  insertion lock; **may be `InvalidXLogRecPtr`** (`xlog.c:273-278`).
  [from-comment]
- `doPageWrites` — local cache of `(fullPageWrites || runningBackups > 0)`;
  recheck after acquiring WAL insertion lock. [from-comment]
  `xlog.c:283-292`.
- `LocalRecoveryInProgress` — three-state: `true` means "not known,
  check shared". [from-comment] `xlog.c:227-231`.
- `LocalXLogInsertAllowed` — `1` / `0` / `-1`; the comment relies on
  `1 == true`, `0 == false`. [from-comment] `xlog.c:233-243`.

## Key invariants and locking

1. **WAL insertion is two-step under critical section.** `START_CRIT_SECTION`
   wraps both reserve (`ReserveXLogInsertLocation` /
   `ReserveXLogSwitch`) and copy (`CopyXLogRecordToWAL`).
   [from-comment] [verified-by-code] `xlog.c:824-857`, `856`.

2. **Holding any WALInsertLock pins `RedoRecPtr` and `fullPageWrites`.**
   "Holding onto an insertion lock also protects RedoRecPtr and
   fullPageWrites from changing until the insertion is finished."
   [from-comment] `xlog.c:846-847`.

3. **`XLOG_SWITCH` / `XLOG_CHECKPOINT_REDO` need all 8 insertion locks.**
   `WALInsertLockAcquireExclusive` is used. [verified-by-code]
   `xlog.c:911-941`.

4. **`insertingAt` is updated before sleeping while holding the lock.**
   Otherwise two inserters could deadlock when each must evict a WAL
   buffer the other has dirtied. [from-comment] `xlog.c:353-363`.

5. **Insertion CRC happens only after `xl_prev` is filled.** The
   `ReserveXLogInsertLocation` call sets `xl_prev`; CRC is computed
   `xlog.c:946-953`. Order matters because `xl_prev` is part of the
   CRC payload. [verified-by-code]

6. **`XLogInsertAllowed()` returns false during recovery** —
   `XLogInsertRecord` ereports if called (`xlog.c:815`). Recovery
   instead calls `UpdateMinRecoveryPoint` (`xlog.c:2721`). [verified-by-code]

7. **`XLogFlush` first refreshes the cached `LogwrtResult`; short-circuit
   if `record <= LogwrtResult.Flush`.** [verified-by-code]
   `xlog.c:2820-2822`. After short-circuit, the function enters
   `START_CRIT_SECTION` and a loop using `LWLockAcquireOrWait` on
   `WALWriteLock` plus `WaitXLogInsertionsToFinish` group-commit
   piggybacking. [verified-by-code] `xlog.c:2832-2880`.

8. **`WaitXLogInsertionsToFinish(upto)`** iterates *all* WAL insertion
   locks, using their `insertingAt` indicators to ignore inserters
   working past `upto`. The deadlock-avoidance scheme from §4 above
   depends on this. [verified-by-code] `xlog.c:1545`.

9. **`XLOG_MARK_UNIMPORTANT` records do not update `lastImportantAt`.**
   The flag suppresses progress tracking so that "is there real WAL
   activity since the last checkpoint" can ignore housekeeping
   records. [from-comment] `xlog.c:365-372`, code at `xlog.c:968-973`.

10. **DELAY_CHKPT_IN_COMMIT in `xact.c`** is observed by the
    checkpoint code here. (Cross-ref to `xact.c:1469-1471` and the
    checkpoint orchestration in this file.) [inferred]

11. **`info_lck` is a spinlock; `WALBufMappingLock`, `WALWriteLock`,
    `ControlFileLock` are LWLocks.** [from-comment] `xlog.c:308-322`.

## Functions of note (≥3 ≤8)

### `XLogInsertRecord` — `xlog.c:784` [verified-by-code]

The hot insertion path called by `xloginsert.c:XLogInsert`. Handles
three classes via `WalInsertClass`:

- `WALINSERT_NORMAL` — single lock, reserve via
  `ReserveXLogInsertLocation`. Detects stale `RedoRecPtr` /
  changed `doPageWrites` (e.g. `runningBackups` just went non-zero)
  and bails returning `InvalidXLogRecPtr` so the caller re-assembles
  with FPIs. [verified-by-code] `xlog.c:858-907`.
- `WALINSERT_SPECIAL_SWITCH` — all 8 locks; uses `ReserveXLogSwitch`
  which may decide the record is unnecessary at a segment boundary
  (`inserted = false`, returns the segment-start LSN). [verified-by-code]
  `xlog.c:908-924`.
- `WALINSERT_SPECIAL_CHECKPOINT` — all 8 locks; updates `Insert->RedoRecPtr`
  to `StartPos` while holding all locks. [verified-by-code]
  `xlog.c:925-942`.

After reservation, CRC is finalized over the header
(`xlog.c:950-953`), then `CopyXLogRecordToWAL` writes the data
(`xlog.c:959-961`), and `lastImportantAt` is updated unless the
caller passed `XLOG_MARK_UNIMPORTANT`.

### `XLogFlush` — `xlog.c:2801` [verified-by-code]

Force flush to `record`. Recovery-path: redirect to
`UpdateMinRecoveryPoint`. Live path: piggyback inflight writes,
acquire `WALWriteLock` (or wait if someone else is doing the work —
group commit), call `XLogWrite` with a `Flush` request reaching at
least to `record`. The inner loop may flush *past* `record` if more
data accumulated, to amortize fsync.

### `XLogBackgroundFlush` — `xlog.c:3004` [verified-by-code]

Walwriter's flush function (see README §"Asynchronous Commit"). Looks
at `LogwrtResult.Write` and at the most recent async-commit LSN
(`asyncXactLSN`); decides whether to write+flush the page boundary,
the async commit, or just write changed buffers. Honors
`wal_writer_delay` / `wal_writer_flush_after`.

### `StartupXLOG` — `xlog.c:5846` [verified-by-code]

Crank that bootstraps the entire database. Reads control file, decides
between archive recovery / crash recovery / fresh start, finds the
redo starting point (checkpoint record), then delegates the replay
loop to `xlogrecovery.c:PerformWalRecovery`. After recovery: invokes
`CleanupAfterArchiveRecovery`, picks a new timeline if needed
(`XLogInitNewTimeline`), writes an end-of-recovery checkpoint, sets
`SharedRecoveryState = RECOVERY_STATE_DONE`. (Body is enormous; see
README §"Transaction Emulation during Recovery" for what other
subsystems do during this loop.)

### `RecoveryInProgress` — `xlog.c:6834` [verified-by-code]

The function every backend uses to gate WAL writes. Three-state local
cache (`LocalRecoveryInProgress`): once it observes `RECOVERY_STATE_DONE`,
it caches `false` and skips the shared read forever. [from-comment]
`xlog.c:227-231`.

### `XLogSetAsyncXactLSN` — `xlog.c:2630` [verified-by-code]

Used by async commits to advertise their commit LSN to the walwriter
(see README §"Asynchronous Commit"). Stored in `XLogCtl->asyncXactLSN`,
guarded by `info_lck`. Signals walwriter via latch when necessary.

### `WaitXLogInsertionsToFinish` — `xlog.c:1545` [verified-by-code]

Walks the eight WAL insertion locks, reads each lock's `insertingAt`,
returns the minimum LSN that all locks have *reached or passed*. The
caller (`XLogWrite` / `XLogFlush`) uses this to know when WAL pages
behind it are safe to write.

### `XLogFileInit` / `InstallXLogFileSegment` — `xlog.c:3431`, `3614` [verified-by-code]

Manage segment-file allocation. `XLogFileInit` writes a new file
(possibly zeroed if `wal_init_zero`), then `InstallXLogFileSegment`
renames it into place — atomic rename so the segno isn't visible
until the file is fully allocated.

## Cross-references

- `xloginsert.c` is the producer; calls `XLogInsertRecord`.
- `xlogrecovery.c` consumes `StartupXLOG`'s output via
  `PerformWalRecovery`.
- `xlogreader.c` is the decoder; `xlog.c` doesn't directly drive
  recovery replay but supplies the reader's read callbacks during
  startup.
- `checkpointer.c` calls into here for `CreateCheckPoint` (defined in
  this file — not deep-read above; see line ~7400+).
- `walwriter.c` is the consumer of `XLogBackgroundFlush`.
- `pg_control` is in `catalog/pg_control.h`; read/write via
  `Read/WriteControlFile`.
- `procarray.c`, `slot.c`, `walreceiver.c` — interact for hot standby
  bootstrapping inside `StartupXLOG`.
- `xact.c`'s `RecordTransactionCommit` calls `XLogFlush(XactLastRecEnd)`
  and `XLogSetAsyncXactLSN`.

## Open questions

- `XLogCtlData` is huge and the cache-line layout matters for
  performance; not deep-read in this pass. [unverified]
- `CreateCheckPoint` and `CreateRestartPoint` are defined in this file
  but were not opened here; they are central to recovery and need a
  follow-up pass. [unverified]
- The detailed semantics of `XLogWrite`'s sync-method switch (`fsync` vs
  `fdatasync` vs `open_datasync`) are not analyzed here.
  [unverified]
- The exact protocol by which `XLogBackgroundFlush` decides to flush
  through the latest async-commit LSN is described in the README but
  not re-derived from code. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 39
- `[from-comment]`: 14
- `[inferred]`: 1
- `[unverified]`: 4

## Synthesized by
<!-- backlinks:auto -->
- [architecture/wal.md](../../../../../architecture/wal.md)
- [subsystems/access-transam.md](../../../../../subsystems/access-transam.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new WAL record](../../../../../scenarios/add-new-wal-record.md)
- [Scenario — Bump CATALOG_VERSION_NO](../../../../../scenarios/bump-catversion.md)

<!-- scenarios:auto:end -->
