# `src/bin/pg_combinebackup/backup_label.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~30
- **Source:** `source/src/bin/pg_combinebackup/backup_label.h`

Public header for `backup_label.c`. Declares
`parse_backup_label()` and `write_backup_label()`. Uses a forward
declaration of `struct manifest_writer` to avoid pulling in
`write_manifest.h`. [verified-by-code]

## API / entry points

- `parse_backup_label` — see `backup_label.c.md`. [verified-by-code]
- `write_backup_label` — see `backup_label.c.md`. [verified-by-code]

## Notable invariants / details

- Includes `access/xlogdefs.h` for `TimeLineID` / `XLogRecPtr`,
  `common/checksum_helper.h` for `pg_checksum_type`, and
  `lib/stringinfo.h` for `StringInfo`. [verified-by-code]
- Header copy-paste error in the leading comment: says "Read and
  manipulate backup label files" identical to the `.c` file's banner,
  which is fine. [verified-by-code]

## Potential issues

- None notable for a 30-line forwarder header.
