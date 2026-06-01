# `src/backend/backup/basebackup_zstd.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~300
- **Source:** `source/src/backend/backup/basebackup_zstd.c`

bbsink wrapping `zstd` via streaming API (`ZSTD_compressStream2`).
Gated by `#ifdef USE_ZSTD`. Supports compression `level`, `workers`
(threaded compression via `ZSTD_c_nbWorkers`), and `long` mode (large
window). All options come from `pg_compress_specification`. Ops follow
the same gzip/lz4 pattern (header / contents / end_archive flush).
ereports on build without zstd. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
