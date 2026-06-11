# `src/include/backup/backup_manifest.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~54
- **Source:** `source/src/include/backup/backup_manifest.h`

API for incrementally constructing a backup manifest as files are
streamed to the sink. The manifest itself is an SHA-checksummed JSON
document held in a `BufFile` while being written, then forwarded to
the sink via `SendBackupManifest`. [verified-by-code]

## Types

- `backup_manifest_option` — tri-state `MANIFEST_OPTION_YES /
  _NO / _FORCE_ENCODE`. `FORCE_ENCODE` forces hex encoding of file
  paths even when not strictly needed (test hook). [verified-by-code]
- `backup_manifest_info` — `BufFile *buffile`, `pg_checksum_type
  checksum_type`, `pg_cryptohash_ctx *manifest_ctx`, `uint64
  manifest_size`, `bool force_encode`, `bool first_file`, `bool
  still_checksumming`. The `BufFile` is the on-disk staging area
  for the manifest body; the cryptohash is computed as bytes are
  appended; once the manifest's own trailing checksum line is being
  written, `still_checksumming` flips false to break the
  self-reference. [verified-by-code]

## API / entry points

- `InitializeBackupManifest(manifest, want_manifest, checksum_type)`
  — opens a `BufFile`, picks the checksum, writes the manifest
  preamble. If `want_manifest == MANIFEST_OPTION_NO` the manifest is
  not produced (other entry points become no-ops). [verified-by-code]
- `AddFileToBackupManifest(manifest, spcoid, pathname, size, mtime,
  checksum_ctx)` — append one file record. [verified-by-code]
- `AddWALInfoToBackupManifest(manifest, startptr, starttli, endptr,
  endtli)` — append the WAL-range section once the backup's
  start/stop LSN are known. [verified-by-code]
- `SendBackupManifest(manifest, sink)` — drive the BufFile through
  the sink's `begin_manifest` / `manifest_contents` / `end_manifest`
  callbacks. [verified-by-code]
- `FreeBackupManifest(manifest)` — close the BufFile and free
  cryptohash. [inferred]

## Notable invariants

- Manifest contents are checksummed as written; the trailing
  `Manifest-Checksum` field references everything BEFORE itself,
  enforced by toggling `still_checksumming`. [from-comment]
- The `force_encode` knob exists so the regression tests can exercise
  the hex-encoded-path branch on systems whose filenames are all
  plain ASCII. [inferred]
