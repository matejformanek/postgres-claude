# `src/bin/pg_combinebackup/write_manifest.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~295
- **Source:** `source/src/bin/pg_combinebackup/write_manifest.c`

Streams a new `backup_manifest` JSON file out to disk as the
combined backup is constructed. Accumulates JSON text in an
internal StringInfo and flushes to the open fd whenever it grows
beyond 128 KiB. Maintains a SHA-256 checksum over the entire
manifest *up to* the final "Manifest-Checksum" line — that final
line is written without contributing to the checksum so the file
checksum is self-verifiable. [verified-by-code]

## API / entry points

- `create_manifest_writer(directory, system_identifier)` — allocates
  and initialises a `manifest_writer`, queues up the header
  (`PostgreSQL-Backup-Manifest-Version: 2`, system_identifier,
  opening `"Files": [`). Does NOT open the file yet — first open
  happens lazily inside `flush_manifest`. [verified-by-code]
- `add_file_to_manifest(mwriter, manifest_path, size, mtime,
  checksum_type, checksum_length, checksum_payload)` — appends one
  file entry. Handles JSON-escaping of valid UTF-8 paths and
  hex-encoding (as `Encoded-Path`) of any path that isn't valid UTF-8.
  [verified-by-code]
- `finalize_manifest(mwriter, first_wal_range)` — closes out the
  Files array, emits the WAL-Ranges array, flushes, then appends the
  Manifest-Checksum line, flushes again, and closes the file.
  [verified-by-code]

## Notable invariants / details

- `manifest_writer` (line 27): holds the pathname, fd (-1 until first
  flush), the in-memory `StringInfoData buf`, `first_file` boolean
  (for JSON comma vs newline separator), `still_checksumming`
  boolean, and a `pg_checksum_context` initialised to
  `CHECKSUM_TYPE_SHA256`. [verified-by-code]
- The 128 KiB flush threshold is hard-coded (line 116, 134).
  [verified-by-code]
- Header is written with format version `2` (line 60), matching the
  version policy in `load_manifest.c:247`. [verified-by-code]
- Non-UTF-8 paths use `Encoded-Path` with hex bytes (line 99-105),
  same convention as the server-side
  `backup/backup_manifest.c:AddFileToBackupManifest`. The comment on
  line 75 notes this duplicates the backend logic intentionally.
  [verified-by-code]
- Last-Modified uses `strftime("%Y-%m-%d %H:%M:%S %Z", gmtime(&mtime))`
  (line 112), so the timezone is "UTC" or "GMT" depending on libc.
  [verified-by-code]
- `escape_json` (line 194) duplicates the standard PG JSON escaping
  but is local rather than shared because frontend code can't easily
  reuse the backend's `escape_json`.
  Control characters < 0x20 become `\u%04x`, the canonical specials
  are escaped, and high bytes pass through verbatim.
  [verified-by-code]
- `hex_encode` (line 279) is a hand-rolled bin→hex pair-loop. Lower
  case digits. No NUL terminator written — the StringInfo `len` is
  bumped by `len*2`, and the trailing NUL is added separately by
  later `appendStringInfo` calls. [verified-by-code]
- Checksum stops including bytes once `finalize_manifest` sets
  `still_checksumming = false` (line 171). The final
  `flush_manifest` call therefore writes the Manifest-Checksum line
  without folding it into the SHA-256 state. [verified-by-code]
- File created with `O_CREAT | O_EXCL | PG_BINARY` (line 247) — an
  existing `backup_manifest` is fatal. [verified-by-code]

## Potential issues

- `Last-Modified` uses non-reentrant `gmtime()` (line 113). Fine for
  a single-threaded CLI; would be a bug in a threaded context.
  [verified-by-code]
- `escape_json` here is a duplicate of the same logic in the backend
  (`utils/adt/jsonfuncs.c` family). Drift between the two could
  produce manifests that round-trip differently. Currently both
  implementations follow the JSON spec; no known divergence.
  [verified-by-code] [ISSUE-doc-drift: local escape_json duplicates
  backend logic; no cross-reference comment (nit)]
- The lazy file-open inside `flush_manifest` means an EEXIST on the
  manifest path is only detected at first flush, which is *after*
  the writer has consumed the header bytes. Not visible to the user
  because the failure is still fatal, but the error happens later
  than necessary. [verified-by-code]
- `hex_encode` does not validate that `dst` has enough space.
  Callers use `enlargeStringInfo(buf, 2 * checksum_length)` before
  invoking it (line 125), but a future caller could trip a
  hard-to-debug overflow. [verified-by-code] [ISSUE-style: hex_encode
  has no length check on dst; relies on caller (nit)]
- The checksum stamped at the end is SHA-256 only. There is no way to
  request a stronger or weaker manifest checksum — the
  `--manifest-checksums` option affects per-file checksums, not the
  whole-manifest one. This matches backend behaviour but is worth
  documenting. [verified-by-code] [ISSUE-doc-drift:
  Manifest-Checksum algorithm is hard-coded SHA-256 regardless of
  --manifest-checksums (nit)]
- Line 177: `Assert(len == PG_SHA256_DIGEST_LENGTH)` — only fires in
  cassert builds. In release a wrong length silently corrupts the
  output. The pg_checksum_final API guarantees the length so this is
  safe in practice. [verified-by-code]
