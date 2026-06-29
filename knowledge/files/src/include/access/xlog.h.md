# xlog.h

- **Source path:** `source/src/include/access/xlog.h`
- **Lines:** 344
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlog.c`, `xlogdefs.h`, `xlog_internal.h`,
  `xlogbackup.h`, `xlogrecord.h`, `xlogreader.h`, `xlogrecovery.h`.

## Purpose

The public façade of the WAL manager. GUC variable externs, enums for
sync method / archive mode / wal_level / wal_compression / recovery
state, checkpoint-request flag bits, the `CheckpointStatsData` struct,
and prototypes for `XLogInsertRecord`, `XLogFlush`, `StartupXLOG`,
`CreateCheckPoint`, `CreateRestartPoint`, `RecoveryInProgress`, the
control-file/data-checksum state machine, and base-backup entrypoints.
[from-comment] `xlog.h:1-9`.

## Top-of-file comment (verbatim)

```
xlog.h

PostgreSQL write-ahead log manager
```
[verified-by-code] `xlog.h:1-4`.

## Public surface (selection)

GUC externs: `wal_sync_method`, `wal_segment_size`,
`min/max/wal_keep_size_mb`, `XLOGbuffers`, `XLogArchiveTimeout`,
`wal_retrieve_retry_interval`, `XLogArchiveCommand`,
`EnableHotStandby`, `fullPageWrites`, `wal_log_hints`,
`wal_compression`, `wal_init_zero`, `wal_recycle`,
`wal_consistency_checking[_string]`, `log_checkpoints`,
`CommitDelay`, `CommitSiblings`, `track_wal_io_timing`,
`wal_decode_buffer_size`, `data_checksums`, `CheckPointSegments`,
`XLogArchiveMode`, `wal_level`, `XLogLogicalInfo`,
`ProcLastRecPtr`, `XactLastRecEnd`, `XactLastCommitEnd`,
`CheckpointStats`. [verified-by-code] `xlog.h:31-99, 195`.

Functions: `XLogInsertRecord`, `XLogFlush`, `XLogBackgroundFlush`,
`XLogNeedsFlush`, `XLogFileInit`, `XLogFileOpen`, `CheckXLogRemoved`,
`XLogGetLastRemovedSegno`, `XLogGetOldestSegno`,
`XLogSetAsyncXactLSN`, `XLogSet/GetReplicationSlotMinimumLSN`,
`xlog_redo`/`xlog2_redo`, `RecoveryInProgress`, `GetRecoveryState`,
`XLogInsertAllowed`, `Get{XLogInsertRecPtr,XLogInsertEndRecPtr,
XLogWriteRecPtr,SystemIdentifier,MockAuthenticationNonce}`,
data-checksum state-machine (`DataChecksums*`,
`SetDataChecksums*`), `BootStrapXLOG`, `LocalProcessControlFile`,
`StartupXLOG`, `ShutdownXLOG`, `CreateCheckPoint`,
`CreateRestartPoint`, `GetWALAvailability`, `XLogPutNextOid`,
`XLogRestorePoint`, `XLogAssignLSN`, `UpdateFullPageWrites`,
`GetFullPageWriteInfo`, `GetRedoRecPtr`, `GetInsertRecPtr`,
`GetFlushRecPtr`, `GetWALInsertionTimeLine[IfSet]`,
`GetLastImportantRecPtr`, `SetWalWriterSleeping`,
`WakeupCheckpointer`, `WALReadFromBuffers`. Plus 8 functions
exposed for `xlogrecovery.c` callbacks. Backup: `do_pg_backup_start`,
`do_pg_backup_stop`, `do_pg_abort_backup`, `get_backup_status`.
[verified-by-code] `xlog.h:213-331`.

## Key types / enums

- `WalSyncMethod` — `xlog.h:23-30`.
- `ArchiveMode` — `OFF`, `ON`, `ALWAYS`. `xlog.h:65-70`.
- `WalLevel` — `MINIMAL`, `REPLICA`, `LOGICAL`. `xlog.h:74-79`.
- `WalCompression` — `NONE`, `PGLZ`, `LZ4`, `ZSTD`. `xlog.h:82-88`.
- `RecoveryState` — `CRASH`, `ARCHIVE`, `DONE`. `xlog.h:91-96`.
- `CheckpointStatsData` — start/write/sync/sync_end/end timestamps,
  buffer/SLRU counts, segment counts, sync stats. `xlog.h:172-193`.
- `WALAvailability` — `INVALID_LSN`, `RESERVED`, `EXTENDED`,
  `UNRESERVED`, `REMOVED`. `xlog.h:200-208`.
- `SessionBackupState` — `NONE`, `RUNNING`. `xlog.h:318-322`.

## Key invariants and macros

1. **`XLogArchivingActive()` requires `wal_level >= REPLICA`.**
   Assertion in macro. [verified-by-code] `xlog.h:102-106`.

2. **`XLogIsNeeded() = (wal_level >= REPLICA)`.** When false,
   AMs may skip WAL for new relfilenumbers (see README §"Skipping
   WAL"). [verified-by-code] `xlog.h:112`.

3. **`XLogHintBitIsNeeded() = (wal_log_hints || DataChecksumsNeedWrite())`.**
   The README's "Writing Hints" rule. [verified-by-code] `xlog.h:123`.

4. **`XLogStandbyInfoActive()` is the gate for hot-standby
   metadata** (KnownAssignedXids, sinval). [verified-by-code]
   `xlog.h:126`.

5. **`XLogLogicalInfoActive()` may force logical info even at
   `wal_level = replica`** via the process-local `XLogLogicalInfo`
   flag. The flag is constant within an XID-bearing transaction
   once an XID has been assigned. [from-comment] `xlog.h:128-138`.

6. **Checkpoint flag bits** — `CHECKPOINT_IS_SHUTDOWN`,
   `_END_OF_RECOVERY`, `_FAST`, `_FORCE`, `_FLUSH_UNLOGGED`,
   `_WAIT`, `_REQUESTED`, `_CAUSE_XLOG`, `_CAUSE_TIME`.
   [verified-by-code] `xlog.h:151-162`.

7. **Per-record insert flags** — `XLOG_INCLUDE_ORIGIN`,
   `XLOG_MARK_UNIMPORTANT`. [verified-by-code] `xlog.h:167-168`.

## Cross-references

- `xlog.c` implements all the prototypes.
- `xlogrecovery.c` uses the recovery-callback subset.
- `xloginsert.c` is the producer-side façade over
  `XLogInsertRecord`.

## Open questions

- The `WALAvailability` return values are consumed by replication
  slot machinery (`replication/slot.c`); not analyzed here.
  [unverified]

## Confidence tag tally

- `[verified-by-code]`: 22
- `[from-comment]`: 2
- `[unverified]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [idioms/checkpoint-coordination.md](../../../../idioms/checkpoint-coordination.md)
- [idioms/wal-buffer-state.md](../../../../idioms/wal-buffer-state.md)
