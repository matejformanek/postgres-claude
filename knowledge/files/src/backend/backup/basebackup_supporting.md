# `src/backend/backup/basebackup_*.c`

- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim

Group doc for the basebackup sink implementations and helpers, all reached
via walsender's `BASE_BACKUP` command (`walsender.c:2217 → SendBaseBackup`).

## Files

- `basebackup_sink.c` (3.0K) — the bbsink vtable and chain plumbing.
- `basebackup_copy.c` (12.4K) — sink that streams TAR via libpq COPY (the
  classic `pg_basebackup` over replication).
- `basebackup_server.c` (8.4K) — sink that writes to server-side files
  (target=server).
- `basebackup_gzip.c` (9.5K), `basebackup_lz4.c` (8.5K) — compressing
  sinks; pluggable layer.
- `basebackup_progress.c` (7.6K) — progress reporting plumbing for
  `pg_stat_progress_basebackup`.
- `basebackup_incremental.c` (34.9K) — handles `UPLOAD_MANIFEST` + the
  block-tracking infra (uses summarizer WAL data) to ship only changed
  blocks. Largest of the bunch and a candidate for its own deep read in
  the wal-summarizer pass.
