# `src/include/backup/basebackup_incremental.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~56
- **Source:** `source/src/include/backup/basebackup_incremental.h`

Public API for incremental backup support (PG17+). Consumers build
an `IncrementalBackupInfo` from the prior manifest, then ask
"should this file be sent fully or incrementally?" per relation
segment via `GetFileBackupMethod`. [verified-by-code]

## Constants

- `INCREMENTAL_MAGIC = 0xd3ae1f0d` — leading uint32 magic written
  into every `INCREMENTAL.*` file on disk. Used by
  `pg_combinebackup` for sanity-checking. [verified-by-code]

## Types

- `FileBackupMethod` — `BACK_UP_FILE_FULLY` or
  `BACK_UP_FILE_INCREMENTALLY`. The driver in `basebackup.c`
  switches on this. [verified-by-code]
- `IncrementalBackupInfo` — opaque, owned by
  `basebackup_incremental.c`. [verified-by-code]

## API / entry points

- `CreateIncrementalBackupInfo(MemoryContext)` — allocator;
  initialises the incremental JSON parser. [verified-by-code]
- `AppendIncrementalManifestData(ib, data, len)` — stream chunks of
  the prior manifest received from the client. [verified-by-code]
- `FinalizeIncrementalManifest(ib)` — flush the last chunk through
  the JSON parser, free transient state. [verified-by-code]
- `PrepareForIncrementalBackup(ib, backup_state)` — match prior
  manifest's TLI ranges against this server's history, locate the
  required WAL summaries, load them into an in-memory block-ref
  table. Throws ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE if WAL
  summaries are missing. [verified-by-code]
- `GetIncrementalFilePath(dboid, spcoid, relfilenumber, forknum,
  segno)` — palloc'd path with `INCREMENTAL.` prefix on the leaf
  segment name. [verified-by-code]
- `GetFileBackupMethod(ib, path, dboid, spcoid, relfilenumber,
  forknum, segno, size, *num_blocks_required,
  relative_block_numbers[RELSEG_SIZE], *truncation_block_length)`
  — the core decision function. Outputs either FULL or the per-segment
  block list to send. [verified-by-code]
- `GetIncrementalFileSize(num_blocks_required)` and
  `GetIncrementalHeaderSize(num_blocks_required)` — size accounting,
  header rounded to BLCKSZ multiple when any blocks are stored.
  [verified-by-code]
