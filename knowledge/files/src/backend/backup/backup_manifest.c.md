# `src/backend/backup/backup_manifest.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~360 (11.6K)
- **Source:** `source/src/backend/backup/backup_manifest.c`
- **Depth:** skim

## Purpose

Generates the JSON `backup_manifest` file emitted by `BASE_BACKUP` —
per-file checksums + WAL range — used later by `pg_verifybackup` and as
input to `pg_basebackup --incremental` /
`pg_combinebackup`. [from-comment]

Streams JSON via repeated `AppendStringToManifest` (`:24`). Uses
`utils/json.h` for escaping. Manifest is itself fed through the bbsink
chain.
