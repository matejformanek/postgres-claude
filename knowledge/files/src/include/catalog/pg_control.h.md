# pg_control.h

- **Source path:** `source/src/include/catalog/pg_control.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"The system control file `pg_control` is not a heap relation. However, we define it here so that the format is documented." Declares the on-disk `ControlFileData` struct, the `CheckPoint` record body, the `DBState` enum, and the XLOG-rmgr info-byte constants. [from-comment]

## What this header IS (not a CATALOG)

There is NO `CATALOG(...)` declaration in this file. `pg_control` is a single binary file at `$PGDATA/global/pg_control`, written atomically and protected by a CRC32C. This header is the on-disk format spec, parallel to (but unrelated to) the relational catalogs. [verified-by-code]

## Principal types declared

### `CheckPoint` — body of CheckPoint XLOG records

Embedded in `ControlFileData.checkPointCopy`. "Changing this struct requires a `PG_CONTROL_VERSION` bump." [from-comment]

Fields: `redo` (XLogRecPtr REDO start), `ThisTimeLineID`, `PrevTimeLineID`, `fullPageWrites` (bool), `wal_level` (int), `logicalDecodingEnabled` (bool), `nextXid` (FullTransactionId), `nextOid`, `nextMulti` (MultiXactId), `nextMultiOffset` (MultiXactOffset), `oldestXid` (TransactionId, cluster-wide minimum datfrozenxid), `oldestXidDB` (Oid), `oldestMulti`, `oldestMultiDB`, `time` (pg_time_t), `oldestCommitTsXid`, `newestCommitTsXid`, `oldestActiveXid` (only meaningful for online checkpoints when wal_level=replica), `dataChecksumState` (uint32). [verified-by-code]

### `DBState` — system status indicator

"Stored in pg_control; if you change it, you must bump `PG_CONTROL_VERSION`." [from-comment] Values: `DB_STARTUP=0`, `DB_SHUTDOWNED`, `DB_SHUTDOWNED_IN_RECOVERY`, `DB_SHUTDOWNING`, `DB_IN_CRASH_RECOVERY`, `DB_IN_ARCHIVE_RECOVERY`, `DB_IN_PRODUCTION`. **Integer values are on-disk.** [verified-by-code]

### `ControlFileData` — contents of pg_control

Fields, in order:

- `system_identifier` (uint64) — unique cluster id, matched against WAL files.
- `pg_control_version` (uint32) — `PG_CONTROL_VERSION` (= 1902 currently). Must stay at the same 8-byte offset from start of file for historical reasons.
- `catalog_version_no` (uint32) — see `catversion.h`.
- `state` (DBState).
- `time` (pg_time_t) — last pg_control update.
- `checkPoint` (XLogRecPtr) — last checkpoint record ptr.
- `checkPointCopy` (CheckPoint) — embedded copy of last checkpoint body.
- `unloggedLSN` (XLogRecPtr) — current fake LSN for unlogged rels.
- `minRecoveryPoint` (XLogRecPtr), `minRecoveryPointTLI` (TimeLineID) — archive-recovery floor.
- `backupStartPoint` (XLogRecPtr), `backupEndPoint` (XLogRecPtr), `backupEndRequired` (bool) — online-backup tracking.
- `wal_level` (int), `wal_log_hints` (bool), `MaxConnections` (int), `max_worker_processes` (int), `max_wal_senders` (int), `max_prepared_xacts` (int), `max_locks_per_xact` (int), `track_commit_timestamp` (bool) — settings recorded for hot-standby compatibility checks.
- `maxAlign` (uint32), `floatFormat` (double, == `FLOATFORMAT_VALUE` 1234567.0) — hardware-arch compatibility check.
- `blcksz`, `relseg_size`, `slru_pages_per_segment`, `xlog_blcksz`, `xlog_seg_size`, `nameDataLen`, `indexMaxKeys`, `toast_max_chunk_size`, `loblksize` (all uint32) — compile-time-configurable sizes.
- `float8ByVal` (bool).
- `data_checksum_version` (uint32) — zero if no checksums.
- `default_char_signedness` (bool) — signed-char default of the platform that ran initdb.
- `mock_authentication_nonce` (char[`MOCK_AUTH_NONCE_LEN`=32]) — cluster-unique nonce for failed SASL exchanges.
- `crc` (pg_crc32c) — "**MUST BE LAST!**" CRC of all preceding fields. [verified-by-code]

## Key macros

- `PG_CONTROL_VERSION 1902` — bump on any change to `ControlFileData`, `CheckPoint`, or `DBState`. [verified-by-code]
- `MOCK_AUTH_NONCE_LEN 32`. [verified-by-code]
- `PG_CONTROL_MAX_SAFE_SIZE 512` — atomic-disk-write limit. Active data must fit in one disk sector. [from-comment]
- `PG_CONTROL_FILE_SIZE 8192` — physical file size, kept constant across format changes so `ReadControlFile` returns a wrong-version error instead of a read error on incompatible files. [from-comment]
- `FLOATFORMAT_VALUE 1234567.0` — magic double used to detect floating-point format mismatch. [verified-by-code]
- XLOG rmgr info bytes: `XLOG_CHECKPOINT_SHUTDOWN` 0x00, `XLOG_CHECKPOINT_ONLINE` 0x10, `XLOG_NOOP` 0x20, `XLOG_NEXTOID` 0x30, `XLOG_SWITCH` 0x40, `XLOG_BACKUP_END` 0x50, `XLOG_PARAMETER_CHANGE` 0x60, `XLOG_RESTORE_POINT` 0x70, `XLOG_FPW_CHANGE` 0x80, `XLOG_END_OF_RECOVERY` 0x90, `XLOG_FPI_FOR_HINT` 0xA0, `XLOG_FPI` 0xB0, `XLOG_ASSIGN_LSN` 0xC0, `XLOG_OVERWRITE_CONTRECORD` 0xD0, `XLOG_CHECKPOINT_REDO` 0xE0, `XLOG_LOGICAL_DECODING_STATUS_CHANGE` 0xF0. **All are on-disk WAL record info bytes** — renumbering breaks WAL replay across versions. [verified-by-code]
- XLOG2 rmgr info bytes: `XLOG2_CHECKSUMS 0x00`. [verified-by-code]
- Two `StaticAssertDecl`s enforce `sizeof(ControlFileData) <= PG_CONTROL_MAX_SAFE_SIZE` and `<= PG_CONTROL_FILE_SIZE`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Consumer: `source/src/backend/access/transam/xlog.c` — `ReadControlFile`, `WriteControlFile`, `UpdateControlFile`. Subsystem doc: `knowledge/subsystems/wal-xlog.md` (when written).
- Consumer: `source/src/backend/access/transam/xlogrecovery.c` — checkpoint replay reads `checkPointCopy`.
- `catversion.h` — `catalog_version_no` field is initialized from `CATALOG_VERSION_NO` at initdb time.
- Companion idiom: `knowledge/idioms/wal-and-xlog.md`.

## Potential issues

- **[ISSUE-ONDISK: changing this struct silently corrupts clusters]** `pg_control.h:112-249` — Any field add/remove/reorder in `ControlFileData` requires bumping `PG_CONTROL_VERSION` (line 25). Same for `CheckPoint` (line 35) and `DBState` (line 97), both embedded/referenced from `ControlFileData`. Forgetting the bump means a new backend will silently read garbage from an old `global/pg_control`. The `StaticAssertDecl`s at lines 271-274 only catch size overflow, not format drift. [from-comment + inferred]
- **[ISSUE-ONDISK: XLOG info-byte renumbering breaks replay]** `pg_control.h:72-90` — The `XLOG_*` info-byte constants are written into WAL record headers; replay code dispatches on them. Renumbering across major versions would silently misdispatch redo callbacks on replay of pre-upgrade WAL. [inferred]
- **[ISSUE-ATOMICITY: 512-byte ceiling is hardware-defined]** `pg_control.h:251-257` — `PG_CONTROL_MAX_SAFE_SIZE` assumes 512-byte disk sectors. Modern 4K-sector drives may write `pg_control` atomically up to 4096 bytes, but the project intentionally keeps the conservative limit. New fields are expensive; consider whether the field truly must live in `pg_control`. [from-comment]

## Tally

`[verified-by-code]=12 [from-comment]=6 [inferred]=3`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Bump CATALOG_VERSION_NO](../../../../scenarios/bump-catversion.md)

<!-- scenarios:auto:end -->
