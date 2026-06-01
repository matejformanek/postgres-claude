# `src/backend/backup/basebackup_lz4.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~280
- **Source:** `source/src/backend/backup/basebackup_lz4.c`

bbsink wrapping `lz4frame` (frame format, not raw block). Gated by
`#ifdef USE_LZ4`. Ops mirror gzip: header on `begin_archive`, frame
compression on `archive_contents` (using `LZ4F_compressUpdate`), trailer
on `end_archive`. `compresslevel` taken from `pg_compress_specification`.
Falls back to ereport on build without LZ4. [from-comment]
