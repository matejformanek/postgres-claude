# `src/bin/pg_combinebackup/load_manifest.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~315
- **Source:** `source/src/bin/pg_combinebackup/load_manifest.c`

Reads `backup_manifest` files (JSON) into in-memory `manifest_data`
structs holding a simplehash of `manifest_file` entries plus a linked
list of WAL ranges. Wraps `common/parse_manifest.c`'s callback-based
parser. Used by `pg_combinebackup` to look up file checksums in prior
backups and to copy the final backup's WAL ranges into the combined
manifest. [verified-by-code]

## API / entry points

- `load_backup_manifest(backup_directory)` — opens
  `<backup_directory>/backup_manifest`. Returns `NULL` (with a warning)
  if the file simply does not exist; any other I/O error or parse
  failure is fatal. [verified-by-code]
- `load_backup_manifests(n_backups, backup_directories)` — bulk
  variant; returns an array of `manifest_data *` of size `n_backups`,
  possibly containing NULLs. [verified-by-code]
- `manifest_files_*` — simplehash-generated hash table over
  `manifest_file` keyed by `pathname` (uses
  `common/hashfn_unstable.h:hash_string`). Declared in
  `load_manifest.h` (`SH_DECLARE`), defined here (`SH_DEFINE`).
  [verified-by-code]
- `combinebackup_*_cb` callbacks — installed into a
  `JsonManifestParseContext` and fed to `json_parse_manifest()` or
  the incremental variant. [verified-by-code]

## Notable invariants / details

- Reads the whole file in one shot if `<= 128 KiB`; otherwise feeds
  the parser incremental chunks via
  `json_parse_manifest_incremental_chunk()`. Chunk-sizing trick on
  line 191-194: when bytes_left lands in `(chunk, 2*chunk]`, the
  function splits the remaining bytes in half rather than taking a
  full chunk followed by a tiny tail; the comment explains this is
  so the final chunk is "sufficiently large" to contain the manifest
  checksum line intact. [verified-by-code]
- Hash table initial size estimate: `file_size / 100` (one entry per
  100 bytes), clamped to `>= 256` and `<= PG_UINT32_MAX` (line 137).
  [verified-by-code]
- `combinebackup_version_cb` (line 247) refuses manifest version 1:
  incremental backups require version 2. [verified-by-code]
- `combinebackup_per_file_cb` (line 280) refuses duplicate pathnames
  in the manifest as fatal — defends against an attacker-crafted
  manifest. [verified-by-code]
- `combinebackup_system_identifier_cb` only records the value; the
  actual cross-manifest validation happens in `pg_combinebackup.c:307`.
  The comment "Validation will be at the later stage" notes this.
  [verified-by-code]
- WAL ranges are appended in encounter order with both `prev` and
  `next` pointers maintained. [verified-by-code]
- `report_manifest_error` is `pg_noreturn` and calls `exit(1)`. The
  parser library expects this contract. [verified-by-code]

## Potential issues

- Line 137: `Min(PG_UINT32_MAX, Max(estimate, 256))`. `estimate` is
  `off_t` (signed). For a multi-TB manifest (theoretically) the
  cast to `uint32` could lose precision before the `Min`. In practice
  `backup_manifest` files are bounded by the number of files in the
  cluster — hundreds of thousands of entries × 100 bytes ≈ tens of
  MB at most — so this is not reachable in real life.
  [verified-by-code] [ISSUE-question: hash sizing math uses off_t→uint
  truncation; only matters at >4 GB manifest (nit)]
- Line 217: `pfree(buffer)` is called regardless of whether we took
  the single-shot path (small file) or the incremental path (large
  file). Both branches leave `buffer` set, so this is correct, but
  the dual ownership is non-obvious.
  [verified-by-code]
- The `system_identifier` check is enforced by the caller, not here
  (see `combinebackup_system_identifier_cb` comment at line 260
  "Validation will be at the later stage"). If a future refactor
  reuses `load_backup_manifest()` from a context that forgets to
  cross-check, a manifest with the wrong sysid would silently load.
  [verified-by-code] [ISSUE-undocumented-invariant: caller must
  validate system_identifier; not enforced in this file (maybe)]
- No upper bound on `manifest_version`. Future manifest format bumps
  beyond v2 will pass through here without complaint. If v3 changes
  semantics that combinebackup can't honour, callers see a confused
  manifest. [verified-by-code] [ISSUE-correctness: version_cb accepts
  any version >= 2 silently; future-format mismatch surfaces as later
  parse errors (likely)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_combinebackup`](../../../../issues/pg_combinebackup.md)
<!-- issues:auto:end -->
