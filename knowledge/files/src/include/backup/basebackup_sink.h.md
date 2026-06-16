# `src/include/backup/basebackup_sink.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~302
- **Source:** `source/src/include/backup/basebackup_sink.h`

Defines the **`bbsink` abstraction** — the streaming-output chain
used by `pg_basebackup`. A base backup produces one archive per
tablespace plus an optional manifest; a chain of bbsinks pipelines
those bytes from the server through compressors / throttlers /
progress reporters and finally to the client (or to a server-side
file). Each link does one job; default callbacks forward to the
next. [from-comment]

## Core types

- `bbsink_state` — shared state for the whole backup:
  `tablespaces` (List), `tablespace_num` (current index),
  `bytes_done`, `bytes_total`, `bytes_total_is_valid`, `startptr`,
  `starttli`. Allocated once before `bbstate_begin_backup`; bbsinks
  retain a pointer and read but should not modify (caller updates).
  [from-comment]
- `bbsink` — common header for every sink: `bbs_ops` callback
  table, `bbs_buffer` / `bbs_buffer_length` (caller writes data into
  this, length must be a multiple of `BLCKSZ`), `bbs_next` (next
  sink in the chain), `bbs_state`. [from-comment]
- `bbsink_ops` — vtable. Required callbacks: `begin_backup`,
  `begin_archive`, `archive_contents`, `end_archive`,
  `begin_manifest`, `manifest_contents`, `end_manifest`,
  `end_backup`, `cleanup`. [verified-by-code]

## Lifecycle

1. `bbsink_begin_backup(sink, state, buffer_length)` — once per
   backup. Implementations allocate `bbs_buffer` here. Asserts
   `buffer_length % BLCKSZ == 0`. [verified-by-code]
2. Per archive: `bbsink_begin_archive(sink, archive_name)`, repeated
   `bbsink_archive_contents(sink, len)` (caller has copied `len`
   bytes into `bbs_buffer` first), `bbsink_end_archive(sink)`.
   [verified-by-code]
3. Per manifest (if any, after all archives):
   `bbsink_begin_manifest`, `bbsink_manifest_contents`,
   `bbsink_end_manifest`. [verified-by-code]
4. `bbsink_end_backup(sink, endptr, endtli)` — asserts
   `tablespace_num == list_length(tablespaces)`. [verified-by-code]
5. `bbsink_cleanup(sink)` — runs after `end_backup` on success, or
   on error to release transient resources. [from-comment]

## Forwarding helpers

`bbsink_forward_*` for each callback are extern functions a child
sink can drop straight into its ops vtable to forward to
`bbs_next`. [verified-by-code]

## Sink constructors

- `bbsink_copystream_new(send_to_client)` — terminal sink that
  writes the libpq COPY stream. [verified-by-code]
- `bbsink_gzip_new(next, spec)`,
  `bbsink_lz4_new(next, spec)`,
  `bbsink_zstd_new(next, spec)` — compression filters.
  [verified-by-code]
- `bbsink_progress_new(next, estimate_backup_size, incremental)` —
  drives `pg_stat_progress_basebackup`. [verified-by-code]
- `bbsink_server_new(next, pathname)` — terminal sink that writes
  to the server filesystem (the `--target=server` mode).
  [verified-by-code]
- `bbsink_throttle_new(next, maxrate)` — bandwidth limit.
  [verified-by-code]

## Progress hooks

- `basebackup_progress_wait_checkpoint()`,
  `basebackup_progress_estimate_backup_size()`,
  `basebackup_progress_wait_wal_archive(state)`,
  `basebackup_progress_transfer_wal()`,
  `basebackup_progress_done()` — phase markers for the backup
  driver to call so the progress sink can advance.
  [verified-by-code]

## Notable invariants

- `bbs_buffer_length` must be a multiple of `BLCKSZ`; asserted at
  `bbsink_begin_backup`. [verified-by-code]
- `bbsink_archive_contents`/`bbsink_manifest_contents` assert
  `0 < len <= bbs_buffer_length`. Calling with `len == 0` or with
  `len > buffer_length` is a programming error. [verified-by-code]
- The bbsink struct is conceptually immutable after creation: "no
  changes should be made to the contents of this struct" except
  via the pointed-to buffer/state. [from-comment]

## Potential issues

- header-level. The forward-decl plus typedef-on-same-name pattern
  (`struct bbsink; typedef struct bbsink bbsink;`) is correct C but
  causes some IDEs to flag "redefinition". Cosmetic.
  [ISSUE-style: typedef redundancy with struct forward decl (nit)]
- The contract that "`cleanup` runs after `end_backup` on success,
  or before destruction on error" depends on every implementer in
  every sink doing the right thing. No central enforcement.
  [ISSUE-undocumented-invariant: cleanup ordering relies on
  per-sink discipline (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `backup`](../../../../issues/backup.md)
<!-- issues:auto:end -->
