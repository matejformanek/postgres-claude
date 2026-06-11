# `src/bin/pg_waldump/pg_waldump.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~82
- **Source:** `source/src/bin/pg_waldump/pg_waldump.h`

Public header shared between `pg_waldump.c` and
`archive_waldump.c` (the tar-archive support added in PG18).
Declares `XLogDumpPrivate`, the per-process WAL-decoding state
passed via `XLogReaderState->private_data`, plus the four entry
points implemented in `archive_waldump.c`. [verified-by-code]

## API / entry points

- `struct XLogDumpPrivate` — fields:
  - Decoding control: `timeline`, `segsize`, `startptr`, `endptr`,
    `endptr_reached`, `decoding_started`.
  - Archive fields (PG18+): `archive_dir`, `archive_name`,
    `archive_fd`, `archive_fd_eof`, `archive_streamer`,
    `archive_read_buf`, `archive_read_buf_size`, `cur_file`,
    `archive_wal_htab`, `start_segno`, `end_segno`.
    [verified-by-code]
- `extern char *TmpWalSegDir` — global, set in
  `archive_waldump.c:setup_tmpwal_dir` on first need. [verified-by-code]
- `extern int open_file_in_directory(directory, fname)` —
  implemented in `pg_waldump.c:182`. [verified-by-code]
- `extern void init_archive_reader(...)`,
  `extern void free_archive_reader(...)`,
  `extern int read_archive_wal_page(...)`,
  `extern void free_archive_wal_entry(...)` — all implemented in
  `archive_waldump.c`. [verified-by-code]

## Notable invariants / details

- `cur_file` is a tricky shared pointer between the streamer
  callback in `archive_waldump.c` and `read_archive_wal_page`. The
  comment in the struct (line 44-51) calls out the hazard
  explicitly: it can become NULL inside a single `read_archive_file`
  call when a tar member trailer is seen.
  [verified-by-code]
- `archive_wal_htab` is a simplehash whose entries can MOVE on
  insert/delete; the comment at line 56-58 documents that
  `cur_file` must be revalidated after any insert.
  [verified-by-code]
- `start_segno`/`end_segno` are cached to avoid repeated
  `XLByteToSeg()` calls on every archive member. `end_segno`
  defaults to `UINT64_MAX` (line 65-66 in header docs).
  [verified-by-code]

## Potential issues

- `TmpWalSegDir` is process-global, which makes pg_waldump
  fundamentally single-instance for archive mode. Probably fine.
  [verified-by-code]
- `XLogDumpPrivate` field name `cur_file` is short and gives no
  hint as to "currently-being-read tar member". Workable.
  [verified-by-code]
