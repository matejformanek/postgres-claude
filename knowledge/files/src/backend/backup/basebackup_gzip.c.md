# `src/backend/backup/basebackup_gzip.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~310
- **Source:** `source/src/backend/backup/basebackup_gzip.c`

bbsink that gzips archive contents and manifest in-stream using zlib's
`deflate`. `bbsink_gzip_new(next, compress_spec)` allocates and pulls
compression level + window from `pg_compress_specification`. Sink ops
override `begin_archive` (init z_stream + write gz header), `archive_contents`
(deflate in chunks of `next->bbs_buffer_length`), `end_archive` (flush
+ deflateEnd). Whole-file enabled only when built `--with-zlib`
(`#ifdef HAVE_LIBZ`); otherwise `bbsink_gzip_new` ereports
`"gzip compression is not supported by this build"`. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
