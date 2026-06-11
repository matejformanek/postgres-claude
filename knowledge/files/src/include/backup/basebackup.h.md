# `src/include/backup/basebackup.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~42
- **Source:** `source/src/include/backup/basebackup.h`

Public exports of `basebackup.c`. Tiny header — exposes only
`SendBaseBackup`, the `tablespaceinfo` shape, and rate bounds.
[verified-by-code]

## Types

- `tablespaceinfo` — `{ Oid oid, char *path, char *rpath, int64 size
  }`. `path == NULL` denotes PGDATA itself; `rpath` is the relative
  path within PGDATA, else NULL. `size == -1` means "not known yet".
  [from-comment]

## API / entry points

- `SendBaseBackup(BaseBackupCmd *cmd, IncrementalBackupInfo *ib)` —
  top-level entry called from walsender when the client issues
  `BASE_BACKUP`. `ib` is non-NULL when the client supplied a prior
  manifest (incremental backup). [verified-by-code]

## Notable invariants

- `MAX_RATE_LOWER = 32` kB/s, `MAX_RATE_UPPER = 1048576` kB/s
  (1 GB/s) define the legal range for the `MAX_RATE` option of the
  `BASE_BACKUP` replication command. [verified-by-code]
- `struct IncrementalBackupInfo` is a forward-declared opaque
  pointer here; the real definition is in
  `basebackup_incremental.c`. [verified-by-code]
