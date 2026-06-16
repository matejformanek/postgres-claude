# `src/bin/pg_combinebackup/copy_file.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~339
- **Source:** `source/src/bin/pg_combinebackup/copy_file.c`

Implements the per-file copy operation used by `pg_combinebackup` to
materialise files in the combined output directory. Dispatches over
five strategies (`COPY`, `CLONE`, `COPY_FILE_RANGE`, `LINK`, and on
Windows `COPYFILE`), each with an optional pass that re-reads the
source to compute a checksum. Supports dry-run mode (open + close
source only, no I/O). [verified-by-code]

## API / entry points

- `copy_file(src, dst, checksum_ctx, copy_method, dry_run)` — sole
  public entry. Picks an implementation based on `copy_method`,
  emits a debug log line, then calls the implementation.
  [verified-by-code]

## Notable invariants / details

- `COPY_METHOD_COPY` is the only strategy that streams bytes through
  user-space (`copy_file_blocks`) and therefore computes the checksum
  while writing. The cloning, hard-link, copy_file_range, and Windows
  CopyFile paths all delegate to a separate `checksum_file()` pass
  that re-opens and re-reads the source if a checksum is requested.
  [verified-by-code]
- Buffer size for streamed copy and checksum is `50 * BLCKSZ` =
  400 KiB on default builds (line 145, 180). [verified-by-code]
- `copy_file_clone()` (line 226) prefers macOS's
  `copyfile(..., COPYFILE_CLONE_FORCE)` when available and falls back
  to Linux's `ioctl(FICLONE)`. On FICLONE failure it unlinks the
  partially-created destination before fatalling. [verified-by-code]
- `copy_file_by_range()` (line 272) loops on Linux's
  `copy_file_range(2)` until it returns 0, using `SSIZE_MAX` as the
  per-call request size. [verified-by-code]
- `copy_file_link()` (line 328) uses `link(2)`, which gives a hard
  link, not a symlink. The user-visible warning about "modifications
  to the output directory might destructively modify input
  directories" lives in `pg_combinebackup.c:444`, not here.
  [verified-by-code]
- Dry-run mode (line 64) opens the source read-only as a permission
  smoke-test, then closes and emits one of the "would copy..." debug
  lines. Note the source is opened twice in dry-run + checksum
  combinations, which is harmless. [verified-by-code]
- On Windows, if the user explicitly selected `COPY` it gets
  silently upgraded to `COPYFILE` (line 81). The comment says this
  is because CopyFile is universally available; there is no way to
  opt out on Windows. [verified-by-code]

## Potential issues

- Line 263 and others: clone, link, and copy_file_range paths
  re-read the source from disk to compute the checksum. This doubles
  disk I/O for any of these "cheap" strategies whenever the user also
  asks for `--manifest-checksums=SHA*`. Probably accepted (the
  documentation in the help text doesn't promise otherwise), but
  worth knowing. [verified-by-code] [ISSUE-undocumented-invariant:
  clone/link/copy_file_range strategies double-read source when
  checksum is requested (nit)]
- Line 217-218: on the streamed copy path, `src_fd`/`dest_fd` are
  closed without their return value checked. The clone path checks
  neither close either. Other PG client tools (e.g. `backup_label.c`)
  *do* check close-on-write, because some filesystems delay errors
  until close. Output errors on `dest_fd` could go undetected here.
  [verified-by-code] [ISSUE-correctness: write-side close() not
  checked on copy_file_blocks dest_fd; missed late-error report
  (likely)]
- Line 290: `copy_file_range` with `SSIZE_MAX` is fine on Linux but
  the man page warns that very large counts may be clamped silently;
  here the do/while handles short returns correctly. [verified-by-code]
- Line 244: when `FICLONE` fails the code uses `strerror(save_errno)`
  manually rather than `%m`, presumably because the subsequent
  `pg_fatal` call would otherwise interpret a different errno after
  the `unlink()`. Worth a comment but works. [verified-by-code]
- The Windows `copy_file_copyfile` (line 308) passes `true` as the
  third arg (`bFailIfExists`), which is the safe choice — but if
  partial output ever needs to be overwritten on restart, this would
  prevent it. The dry-run cleanup logic in `pg_combinebackup.c`
  removes the output directory entirely on failure so this is fine.
  [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_combinebackup`](../../../../issues/pg_combinebackup.md)
<!-- issues:auto:end -->
