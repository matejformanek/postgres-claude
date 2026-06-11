# `src/bin/pg_combinebackup/backup_label.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~283
- **Source:** `source/src/bin/pg_combinebackup/backup_label.c`

Parses and rewrites the `backup_label` text file that lives at the
root of a base backup. Used by `pg_combinebackup` to: (a) validate
that a chain of base + incremental backups is internally consistent
(matching LSN/TLI handoff between adjacent backups), and (b) emit a
new `backup_label` for the combined output directory with the two
`INCREMENTAL FROM ...` lines stripped so it looks like a plain full
backup. [verified-by-code]

## API / entry points

- `parse_backup_label(filename, buf, start_tli, start_lsn,
  previous_tli, previous_lsn)` — line-by-line parse of the file
  contents in `buf` (a StringInfo). Recognises four key/value lines:
  `START WAL LOCATION`, `START TIMELINE`, `INCREMENTAL FROM LSN`,
  `INCREMENTAL FROM TLI`. The `INCREMENTAL FROM *` pair is optional
  but must appear together or not at all. All errors are fatal
  (`pg_fatal`). [verified-by-code]
- `write_backup_label(output_directory, buf, checksum_type, mwriter)`
  — writes a copy of `buf` to `<output_directory>/backup_label`,
  omitting any line that starts with `INCREMENTAL FROM LSN: ` or
  `INCREMENTAL FROM TLI: `, computes a checksum of the written bytes,
  and if `mwriter` is non-NULL adds the file to the manifest. Creates
  the output file with `O_CREAT|O_EXCL` so an existing file is fatal.
  [verified-by-code]

## Notable invariants / details

- `parse_lsn()` (line 240) temporarily writes a `\0` over the byte at
  `*e` to make the slice NUL-terminated for `sscanf`, then restores
  the original byte. This is safe because the caller always passes a
  buffer whose underlying StringInfo has the trailing `\0`-pad invariant
  preserved by `slurp_file()` in `pg_combinebackup.c:1375`.
  [verified-by-code]
- LSN parser format is `%X/%08X` — high half then a fixed
  zero-padded 8-hex-digit low half. The terminator for
  `START WAL LOCATION` is a space; for `INCREMENTAL FROM LSN` it is a
  newline. Asymmetric on purpose: `START WAL LOCATION: X/Y FILE foo`
  has additional fields after the LSN. [verified-by-code]
- `parse_tli()` requires the character after the TLI to be exactly
  `\n` — anything else is a parse failure (line 279). [verified-by-code]
- Both `start_tli==0` and `previous_tli==0` are treated as "invalid
  TLI". TLI 0 is never legal in PostgreSQL — TLI 1 is the bootstrap
  timeline. [verified-by-code]
- The `found` bitmask uses bits 1/2/4/8 for the four required
  fields; lines 105-114 enforce that both incremental fields appear
  or neither does. [verified-by-code]

## Potential issues

- Line 142: `pg_file_create_mode` is taken at the time of this
  `open()` call. `check_input_dir_permissions()` (in
  `pg_combinebackup.c:690`) is what sets the per-process group mode
  from the final input directory's stat. If `write_backup_label` ever
  gets reused outside `pg_combinebackup` without first calling
  `SetDataDirectoryCreatePerm`, the output file could have the wrong
  group bits. Currently only called from `pg_combinebackup`, so OK in
  practice. [inferred] [ISSUE-undocumented-invariant: write_backup_label
  caller must have already set pg_file_create_mode via
  SetDataDirectoryCreatePerm (nit)]
- Line 250: `sscanf("%X/%08X%n", ...)` happily accepts negative-looking
  uppercase hex like `FFFFFFFF/FFFFFFFF`. Probably fine since
  XLogRecPtr is uint64, but the asymmetry between `%X` (no width on
  the high half) and `%08X` (exactly 8 on the low half) means
  `12345/00000001 ` parses while `12345/1 ` does NOT (because of the
  `%08X` width constraint). This matches how the backend writes
  backup_label, so harmless in practice. [verified-by-code]
- The `INCREMENTAL FROM ...` strip in `write_backup_label` is
  purely string-prefix based. If a future field name began with the
  same prefix (e.g. hypothetical `INCREMENTAL FROM LSN AT TLI:`) it
  would be silently dropped. [unverified] [ISSUE-question: would a
  newly-added backup_label field with the INCREMENTAL FROM prefix be
  silently stripped? (maybe)]
