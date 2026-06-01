# `src/backend/backup/basebackup.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1700 (largest in subsystem)
- **Source:** `source/src/backend/backup/basebackup.c`

## Purpose

Top-level driver for the `BASE_BACKUP` replication command. Walks the data
directory, decides what to include, computes checksums, and pushes bytes
through a chain of `bbsink` (basebackup sink) callbacks that wrap
compression / throttling / progress / target stages.
[from-comment] (`basebackup.c:3-4`)

## Spine

- `SendBaseBackup()` (`basebackup.c:992`) — walsender command entry; parses
  options, constructs the sink chain (server/blackhole/copystream + optional
  gzip/lz4/zstd + throttle + progress), calls `perform_base_backup`.
- `perform_base_backup()` (`basebackup.c:240`) — drives the backup: forces a
  checkpoint via `do_pg_backup_start`, builds tablespace list, two-pass send
  (`sizeonly=true` first to tally, then real send), finishes with
  `do_pg_backup_stop`. [verified-by-code]
- `sendDir()` (`basebackup.c:1191`) — recursive directory walker honoring
  `excludeDirContents[]` / `excludeFiles[]`. Calls `sendFile` per regular
  file, recurses for subdirectories.
- `sendFile()` (`basebackup.c:1576`) — opens a relation segment, optionally
  filters to `incremental_blocks[]` for incremental backups, runs page
  checksum verification (`verify_page_checksum`), and streams bytes to the
  sink.

## Notable constants / data

- `SINK_BUFFER_LENGTH = Max(32768, BLCKSZ)` (`basebackup.c:61`) — must be a
  multiple of block size; drives CopyData chunk size.
- `excludeDirContents[]` (`basebackup.c:157`) — `pg_stat_tmp`, `pg_replslot`,
  `pg_dynshmem`, `pg_notify`, `pg_serial`, `pg_snapshots`, `pg_subtrans`.
  These directories are recreated at startup so contents are skipped, but
  the directory itself is included (empty) to preserve permissions.
  [from-comment]

## Invariants / contracts

- Page checksum verification is best-effort: a single read may catch a torn
  page mid-write, so failed checksums trigger a re-read before being
  reported as failures (`verify_page_checksum` retry path).
- Incremental mode (`opt->incremental == true`) requires
  `IncrementalBackupInfo` built from the prior manifest; `sendFile` then
  walks only the blocks reported as changed.
- Two-pass design: the `sizeonly=true` pass computes the byte total so the
  progress sink can report a meaningful percentage; otherwise file growth
  during backup would invalidate the estimate.

## Cross-refs

- Outbound: `do_pg_backup_start` / `do_pg_backup_stop` in `access/xlog.c`;
  `backup_manifest.c` for manifest emission; all `basebackup_*.c` sinks.
- Inbound: walsender command dispatcher (`replication/walsender.c`).

## Tag tally

`[verified-by-code]` 2 / `[from-comment]` 4
