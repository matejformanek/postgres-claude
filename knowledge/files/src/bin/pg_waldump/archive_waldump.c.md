# `src/bin/pg_waldump/archive_waldump.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~856
- **Source:** `source/src/bin/pg_waldump/archive_waldump.c`

PG18 addition: lets `pg_waldump` decode WAL directly from a tar
archive (optionally gzip/lz4/zstd compressed) produced by
`pg_receivewal` or `pg_basebackup`. Uses the
`fe_utils/astreamer.h` streaming framework — a chain of streamers
that decompresses, parses the tar, and finally hands each tar
member's bytes to a custom `astreamer_waldump` that buffers WAL
segments in a hash table. Out-of-order members are spilled to a
temp dir so the decoder can pick them up later. [verified-by-code]

## API / entry points

- `init_archive_reader(privateInfo, compression)` — opens the
  archive, sets up the astreamer chain (decompressor →
  tar_parser → astreamer_waldump), reads until at least one WAL
  segment with `XLogLongPageHeaderData` worth of data is buffered,
  extracts `segsize`, computes `start_segno`/`end_segno`, then
  prunes any already-buffered segments that fall outside the
  range. [verified-by-code]
- `free_archive_reader(privateInfo)` — tears down the streamer
  chain, destroys all hash entries, closes the archive fd.
  [verified-by-code]
- `read_archive_wal_page(privateInfo, targetPagePtr, count,
  readBuff)` — used as the `page_read` callback by
  `TarWALDumpReadPage`. Locates the right segment in the hash,
  copies bytes out of its buffer (or pulls more from the streamer
  if the buffer doesn't yet cover the requested range), pg_fatals
  on EOF before completion. [verified-by-code]
- `free_archive_wal_entry(fname, privateInfo)` — destroys the buffer
  and removes the entry from the hash; deletes the temp file too if
  the entry was spilled. Carefully revalidates `cur_file` because
  `ArchivedWAL_delete_item` may move other entries. [verified-by-code]

## Notable invariants / details

- `ArchivedWALFile` (line 63): the hash entry. Each segment has its
  own `StringInfo buf` (rationale in comment lines 44-61: the
  archive streamer's chunks straddle segment boundaries, so
  per-segment buffers make slicing trivial).
  Total `read_len` is tracked separately from `buf->len` because
  after spilling the buffer is reset but read_len stays accurate.
  [verified-by-code]
- `READ_ANY_WAL` macro (line 38): `start_segno == 0` means "haven't
  decided yet — accept all", used during the pre-startup phase
  before `segsize` is known. [verified-by-code]
- `get_archive_wal_entry` (line 463): when looking up a segment that
  isn't loaded, first spills any unrelated entries to disk to
  conserve memory (line 487-510), then drives the streamer
  forward. The do-not-spill conditions are: (a) already spilled,
  (b) is `cur_file`. [verified-by-code]
- Temp directory location: `TMPDIR` env var if set, else the
  archive's own waldir; created via `mkdtemp` with template
  `waldump_tmp-XXXXXX`. atexit cleanup is installed in
  `pg_waldump.c:1415`. [verified-by-code]
- `member_is_wal_file` (line 808): only regular files whose
  basename matches `IsXLogFileName` and are either at the archive
  root or under `XLOGDIR` (i.e. `pg_wal/`). [verified-by-code]
- Archive member tar paths are canonicalised by prepending `./`
  then calling `canonicalize_path` (line 828-829) — defensive against
  `..` segments. [verified-by-code]
- Duplicate WAL members in the archive are warned and ignored
  rather than fatal'd (line 741), to be tolerant of slightly
  bizarre archive layouts. [verified-by-code]
- `astreamer_waldump_finalize`/`free` assert
  `bbs_next == NULL` — this streamer is always the terminal node in
  the chain. [verified-by-code]

## Potential issues

- Line 367 / 371: `pg_fatal` on short WAL within archive uses the
  arithmetic `count - nbytes` for the bytes-read count; ok in
  practice but the value can be 0 (e.g. when the segment is
  immediately truncated), producing "read 0 of N bytes" which is
  technically correct but a touch confusing. [verified-by-code]
- Line 545: `read(archive_fd, buf, archive_read_buf_size)` — the
  return value is `int`, but for very large reads (the buffer is
  fixed 128 KiB, so this is fine in practice). [verified-by-code]
- Line 614: `prepare_tmp_write` does `chmod(fpath,
  pg_file_create_mode)` AFTER `fopen`. There's a small window where
  the file has default umask permissions. Since this is a temp
  file owned by the user, low risk. [verified-by-code] [ISSUE-
  security: TOCTOU window between fopen and chmod on temp file;
  low impact for user-owned temp dir (nit)]
- Line 644: `fwrite(buf->data, buf->len, 1, file)` with `nmemb=1`
  means a short write returns 0, and the only way to detect a
  partial-write error is via errno. The fallback sets errno to
  ENOSPC if it's 0, which is fine but loses the real cause.
  [verified-by-code]
- Line 624-628: `chmod` is `#ifndef WIN32`. The temp file on
  Windows therefore inherits default ACLs. Probably fine but
  worth noting if a user has unusual umask on Unix.
  [verified-by-code]
- The hash table's `SH_RAW_ALLOCATOR pg_malloc0` (line 85) means
  entries are heap-allocated; the destroy loop in
  `free_archive_reader` only frees the `buf` StringInfo, then
  `ArchivedWAL_destroy` frees the table itself. The `fname` field
  (the key, line 67) is a `pnstrdup`-allocated copy owned by the
  hash entry; we should `pfree` it but I don't see that happening.
  Looking at `free_archive_wal_entry` (line 405-451) and
  `ArchivedWAL_destroy` — neither frees `fname`.
  [verified-by-code] [ISSUE-leak: hash key fname (pnstrdup'd at
  line 842) is never pfree'd; minor leak per WAL segment processed
  (likely)]
- Line 545-558: there's no checking that the read returns < buffer
  size; partial reads are passed straight to `astreamer_content`
  which is correct because the streamer is byte-oriented.
  [verified-by-code]
- The 8-entry initial hash size (line 174) is arbitrary; a large
  archive with many spilled segments will reallocate the table
  multiple times. Cheap relative to disk I/O.
  [verified-by-code]
- If `read_archive_wal_page` is called for the same LSN twice
  AFTER `decoding_started = true`, the entry has been freed
  already and we'll re-fault into the archive. The comment in
  `TarWALDumpReadPage` (`pg_waldump.c:519`) addresses this by
  freeing only after we've moved past the previous segment.
  [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_waldump`](../../../../issues/pg_waldump.md)
<!-- issues:auto:end -->
