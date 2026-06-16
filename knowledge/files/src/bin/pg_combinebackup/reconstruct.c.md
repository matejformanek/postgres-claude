# `src/bin/pg_combinebackup/reconstruct.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~791
- **Source:** `source/src/bin/pg_combinebackup/reconstruct.c`

The heart of `pg_combinebackup`: given an `INCREMENTAL.foo` file and
a chain of prior backups, reconstructs a complete (full) version of
`foo`. Walks the backup chain newest-to-oldest, building two arrays
(`sourcemap[]`, `offsetmap[]`) of length `block_length` that tell the
writer, for each output block, which file to read it from and at
what offset. Special-cases a "shortcut" path where the file in the
oldest full backup is itself sufficient (no newer block touched it
AND its length matches `truncation_block_length`), in which case we
just `copy_file()` it. [verified-by-code]

## API / entry points

- `reconstruct_from_incremental_file(input_filename, output_filename,
  relative_path, bare_file_name, n_prior_backups, prior_backup_dirs,
  manifests, manifest_path, checksum_type, &checksum_length,
  &checksum_payload, copy_method, debug, dry_run)` — only public
  entry. [verified-by-code]

## Notable invariants / details

- An `rfile` (line 37) is `{filename, fd, header_length, num_blocks,
  relative_block_numbers[], truncation_block_length,
  num_blocks_read, highest_offset_read}`. A *full* file is recognised
  by `header_length == 0`. [verified-by-code]
- Incremental file format (read in `make_incremental_rfile`, line
  455):
  - 4-byte `magic` (must equal `INCREMENTAL_MAGIC` from
    `backup/basebackup_incremental.h`).
  - 4-byte `num_blocks`, must be `<= RELSEG_SIZE` (default 131072).
  - 4-byte `truncation_block_length`, also bounded by `RELSEG_SIZE`.
  - `num_blocks * sizeof(BlockNumber)` array of relative block
    numbers.
  - Header padded up to a multiple of BLCKSZ only when `num_blocks
    > 0` (line 501). Empty incremental files are NOT padded.
    [verified-by-code]
- `find_reconstructed_block_length` (line 438): output length =
  `max(truncation_block_length, max(relative_block_numbers) + 1)`.
  Past-truncation blocks present in the incremental extend the file.
  [verified-by-code]
- The walk-back loop (line 165): for each older backup, look for the
  file as `<dir>/<relative><name>` first; if missing, look for
  `<dir>/<relative>INCREMENTAL.<name>`. The first full file found
  terminates the loop (line 257 `break`). [verified-by-code]
- Zero-fill: if `sourcemap[b]` is still NULL after the walk and
  `b < truncation_block_length`, the block is assumed to have been a
  never-written extension, and the writer fills it with zeros (line
  663-676). The comment is candid that this is unverifiable: a
  zero-filled never-written block looks identical to an unmodified
  block of zero data. [verified-by-code]
- Checksum reuse path (line 289): if we're going to do a full copy
  AND a manifest exists for the source backup AND it has a checksum
  of the requested type, we skip recomputing — just copy the bytes
  out of the manifest entry. [verified-by-code]
- `copy_file_range` branch (line 688): use kernel-side range copy
  per block when `--copy-file-range` is requested. If checksumming
  is on, we still have to re-read the block via `read_block` to feed
  the checksum (line 720). [verified-by-code]
- `write_reconstructed_file` opens the output with `O_RDWR | O_CREAT
  | O_EXCL`; `O_EXCL` ensures we never silently clobber an existing
  output file. [verified-by-code]
- Memory cleanup (line 362-377) closes all source FDs and frees
  per-rfile allocations. [verified-by-code]

## Potential issues

- Line 466: `pg_fatal("file \"%s\" has bad incremental magic
  number (0x%x, expected 0x%x)" ...)` — the magic is read as
  `unsigned magic` (4 bytes) but printed with `%x` (which expects
  `unsigned int`). On any sane platform this is fine but technically
  `unsigned` and `unsigned int` are the same type so OK.
  [verified-by-code]
- Line 538: `read_bytes` declares `rb` as `int` and stores
  `read(fd, buf, length)`. With a `length > INT_MAX` the cast would
  be lossy; `length` is `unsigned`, so a value above INT_MAX silently
  truncates. Since `num_blocks <= RELSEG_SIZE` (131072) and each
  entry is 4 bytes, the maximum legitimate read is ~512 KiB — well
  below INT_MAX. [verified-by-code]
- Line 663-676: the zero-fill assumption — "this block must have
  been an uninitialised extension" — is documented in the comment
  but cannot be cryptographically verified. If a real block of data
  was somehow lost from every backup in the chain, the reconstructed
  file would silently contain zeros. The manifest checksum would
  then be wrong relative to the *original* but consistent with the
  reconstructed file. This is an inherent limitation of incremental
  backup, not a bug in this code. [verified-by-code]
  [ISSUE-undocumented-invariant: missing-block-→-zero-fill is
  unverifiable; documented in comment but no manifest-based audit
  (maybe)]
- Line 297-318: when the manifest file exists but the entry for
  the file we're copying is missing, we emit a warning and proceed
  to recompute. Continuing is probably correct (the file may have
  been generated outside the manifest), but a hostile manifest could
  exploit this to make us recompute large files unnecessarily.
  Low impact. [verified-by-code]
- Line 339: `pg_fatal("full backup contains unexpected incremental
  file \"%s\"", source[0]->filename)` — the error message refers to
  the file in the FIRST (oldest) backup as "the full backup", but if
  the user has misordered backups on the command line, the actual
  first backup may not be a true full backup. The check at
  `check_backup_label_files` would have already rejected this case,
  so the message is only reachable via races.
  [verified-by-code]
- Line 313: `*checksum_payload = pg_malloc(*checksum_length)` —
  allocated, copied from manifest, but never freed at the call-site
  inside `pg_combinebackup.c:1162` (which `pfree`s it). Lifetime is
  scoped to one directory entry. Fine. [verified-by-code]
- Line 723: in the copy_file_range path, `pg_checksum_update` is
  passed `BLCKSZ` even when the actual read may have been short.
  But `read_block` already pg_fatals on a short read, so we never
  reach checksum_update with a partial buffer.
  [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_combinebackup`](../../../../issues/pg_combinebackup.md)
<!-- issues:auto:end -->
