# `src/bin/pg_combinebackup/load_manifest.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~68
- **Source:** `source/src/bin/pg_combinebackup/load_manifest.h`

Public header for `load_manifest.c`. Declares `manifest_file`,
`manifest_wal_range`, `manifest_data` structs and the
simplehash-generated `manifest_files_*` API via `SH_DECLARE`.
[verified-by-code]

## API / entry points

- `struct manifest_file` — `pathname`, `size`, `checksum_type`,
  `checksum_length`, `checksum_payload`. Note `pathname` is the hash
  key; the comment on `manifest_files_*` says `SH_KEY pathname` in
  `load_manifest.c:50`. [verified-by-code]
- `struct manifest_wal_range` — TLI, start/end LSN, `next`/`prev`
  pointers for the doubly-linked list. [verified-by-code]
- `struct manifest_data` — `system_identifier`, `files` (hash),
  `first_wal_range`/`last_wal_range`. [verified-by-code]
- `load_backup_manifest`, `load_backup_manifests` —
  see `load_manifest.c.md`. [verified-by-code]
- simplehash declarations via `SH_PREFIX manifest_files`,
  `SH_ELEMENT_TYPE manifest_file`, `SH_KEY_TYPE const char *`,
  `SH_DECLARE`. [verified-by-code]

## Notable invariants / details

- `manifest_file::status` (line 24) is the hash-table status word
  required by simplehash; it is not a semantic field.
  [verified-by-code]
- `checksum_payload` is owned by the parser's palloc context; not
  freed in `load_manifest.c`. The pointer survives because the parser
  uses `palloc` against the process's CurrentMemoryContext.
  [inferred]

## Potential issues

- `SH_RAW_ALLOCATOR pg_malloc0` (line 36) means the hash table is
  allocated with `pg_malloc0` rather than via a MemoryContext.
  Combined with the fact that frontend code generally relies on
  process exit for cleanup, this is fine. [verified-by-code]
