# walmethods.c

## Purpose

Implements the two pluggable WAL writers behind `walmethods.h`:

- `WalDirectoryMethod` — one file per WAL segment in a directory, with
  optional gzip or lz4 compression (used by `pg_receivewal` and by
  `pg_basebackup`'s plain-format WAL stream).
- `WalTarMethod` — one tar (optionally `.tar.gz`) containing all
  received segments. Used by `pg_basebackup --format=t` for the WAL
  stream; does NOT support all the operations `pg_receivewal` would
  need (the header comment makes this explicit).

## Role in pg_basebackup

End of the WAL receive pipeline. `receivelog.c` calls
`wwmethod->ops->open_for_write / write / sync / close / finish /
free` without knowing which method is in play.

## Wire/protocol surface

None directly. Consumes raw bytes from `receivelog.c` after the WAL
header has been stripped. Writes them to disk through libc / zlib /
lz4 / lz4frame.

## Key functions — directory method

- `dir_open_for_write` (line 116) — `open(O_WRONLY|O_CREAT, pg_file_create_mode)`,
  then optionally wraps fd in `gzdopen()` or initializes LZ4 frame
  context with `LZ4F_compressBegin`. Padding with `pg_pwrite_zeros`
  for uncompressed (line 225). `fsync_fname` + `fsync_parent_path`
  if `sync` flag is set (line 254-255).
- `dir_write` (line 303) — branches on `compression_algorithm`: zlib
  `gzwrite`, LZ4 `LZ4F_compressUpdate` in `LZ4_IN_SIZE` (4096) chunks,
  or raw `write(fd, ...)`. Detects short writes and falls back to
  `ENOSPC` when errno=0 (the "no disk space" idiom). `currpos`
  advances by raw uncompressed count (line 366: "Our caller keeps
  track of the uncompressed size").
- `dir_close` (line 384) — finalize compressor (`LZ4F_compressEnd`,
  `gzclose`), then either `durable_rename(.partial → final)` for
  `CLOSE_NORMAL+temp_suffix`, `unlink` for `CLOSE_UNLINK`, or
  `fsync_fname + fsync_parent_path` for `CLOSE_NO_RENAME`.
- `dir_sync` (line 513) — `gzflush(Z_SYNC_FLUSH)` or `LZ4F_flush`,
  then `fsync(fd)`.
- `dir_existsfile` (line 583) — just `open(O_RDONLY)`.
- `dir_finish` (line 607) — `fsync_fname(basedir, isdir=true)`.

## Key functions — tar method

- `tar_open_for_write` (line 836) — opens the tar file on first
  member (lazy). Initializes zlib if compressed (`deflateInit2` with
  `15+16` for gzip). Refuses concurrent open: "tar files can't have
  more than one open file" (line 891). Writes a placeholder
  `tarCreateHeader` with size 0; size is patched on close. If
  `pad_to_size`, pads the file body now (uncompressed) or defers
  to `tar_close` (compressed).
- `tar_write` (line 764) — direct `write(fd)` or zlib
  `deflate`-via-`tar_write_compressed_data`. No support for lz4 or
  zstd in tar method.
- `tar_close` (line 1041) — patches the header's size+name+checksum,
  pads to TAR_BLOCK_SIZE multiple, `lseek`s back, overwrites header,
  `lseek SEEK_END`. `pg_fatal` if final fsync fails (line 1206).
- `tar_finish` (line 1226) — writes the two empty 512-byte blocks
  marking tar EOF, flushes zlib `Z_FINISH`, closes fd, then
  `fsync_fname / fsync_parent_path` of the tarfile.

## State / globals

No file-scope statics. Each method allocates a method struct
(`DirectoryMethodData` or `TarMethodData`) that embeds the
`WalWriteMethod` base.

`TarMethodData.currentfile` enforces the single-open invariant.

## Phase D notes

[ISSUE-tar-parsing: tar method silently inherits ustar's 11-octal-digit
size field; segments larger than 8 GiB (octal 077777777777 = 8589934591)
would overflow the size field (dos, low)] — Same class of issue as
pg_dump's tar format (A3 finding). For WAL segments, this can only
matter if `WalSegSz` were > 8 GiB, which `IsValidWalSegSize` rejects
(streamutil.c:330 caps at 1 GiB). So this is *currently* not
reachable, but the latent invariant — "tar method can only handle
members ≤ 8 GiB" — is not asserted anywhere. [verified-by-code]

[ISSUE-dos: no compression-ratio guard on incoming WAL data
(dos, low)] — `dir_write` for gzip uses `gzwrite` and trusts the
caller to limit input. Receivelog feeds `WalSegSz` bytes per
segment, capped at 1 GiB. Output size is bounded by zlib's worst-
case expansion ratio (~0.04% overhead) so not a real bomb. But the
LZ4 path `lz4bufsize = LZ4F_compressBound(LZ4_IN_SIZE, NULL)` (line
189) only sizes for the per-chunk compressed output, not whole-file.
[verified-by-code]

[ISSUE-undocumented-invariant: `tarChecksum` of header written WITHOUT
verifying the path is valid (line 902 `tarCreateHeader(..., tmppath,
NULL, ...)`) — receivelog only passes server-derived
`XLogFileName` output as `tmppath` (path-traversal, low)] — Since
the WAL filename comes from `XLogFileName(walfile_name, tli, segno,
WalSegSz)` (receivelog.c:99), the format `XXXXXXXX...XXXXXXXX` is
fixed and contains no `/` or `..`. So path-traversal not reachable
from a server's segment numbering. [verified-by-code]

[ISSUE-state-transition: tar_close patches the header in place
without re-validating; if some other code seeked the tar fd
between tar_write and tar_close, the patch lands at the wrong
offset (state-transition, low)] — Line 1150 does `lseek(fd,
tf->ofs_start, SEEK_SET)`. `ofs_start` was captured in
`tar_open_for_write` (line 930). No re-check that anything else
hasn't moved the fd. Single-open invariant + receivelog's strict
linear ordering make this safe today. [verified-by-code]

[ISSUE-undocumented-invariant: tar method's `existsfile` always
returns false (line 1219); resumption via existing tar archive is
not supported] — Comment is explicit ("We only deal with new
tarfiles"). Means `pg_receivewal` cannot use tar method.
[verified-by-code]

`tar_finish` fsync-on-close gates the durability story. If
`wwmethod->sync` is false, the resulting tar may not survive a crash.
That matches pg_basebackup's `--no-sync` flag semantics. [verified-by-code]

Tar method uses `S_IRUSR | S_IWUSR` (0600) hardcoded in
`tarCreateHeader` call at line 902 — does not consult
`pg_file_create_mode`. So mode set by server's
`data_directory_mode` (streamutil.c) is ignored for WAL-in-tar.
[verified-by-code]
