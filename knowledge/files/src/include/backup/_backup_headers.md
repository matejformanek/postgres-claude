# `src/include/backup/` (combined)

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/include/backup/`

- `backup_manifest.h` — `manifest_info`, `InitializeBackupManifest`,
  `AddFileToBackupManifest`, `AddWALInfoToBackupManifest`,
  `SendBackupManifest`. Built incrementally during the backup.
- `basebackup.h` — top-level `SendBaseBackup(BaseBackupCmd *cmd,
  IncrementalBackupInfo *ib)` plus `BASE_BACKUP` option flags.
- `basebackup_incremental.h` — `IncrementalBackupInfo` opaque,
  `CreateIncrementalBackupInfo`, `IngestManifest`,
  `IngestWalSummaries`, `GetIncrementalBackupBlocks`. Drives the
  manifest-driven block-selection logic in `sendFile`.
- `basebackup_sink.h` — the `bbsink` / `bbsink_ops` interface every
  sink implements. Lists every callback (`begin_backup`, `begin_archive`,
  `archive_contents`, `end_archive`, `begin_manifest`, `manifest_contents`,
  `end_manifest`, `end_backup`, `cleanup`) plus the `bbsink_forward_*`
  default-pass-through helpers. `bbsink_state` shared structure.
- `basebackup_target.h` — `BaseBackupTargetHandle`,
  `BaseBackupAddTarget(name, check_detail, get_sink)` (extension API),
  `BaseBackupGetTargetHandle`, `BaseBackupGetSink`.
- `walsummary.h` — `WalSummaryFile`, `GetWalSummaries`,
  `FilterWalSummaries`, `WalSummariesAreComplete`,
  `OpenWalSummaryFile`, `ReadWalSummary`, `WriteWalSummary`.
