---
path: src/common/file_utils.c
anchor_sha: 4b0bf0788b0
loc: 750
depth: read
---

# file_utils.c

- **Source path:** `source/src/common/file_utils.c`
- **Lines:** 750
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/file_utils.h`, `storage/fd.c` (backend walkdir cousin), `port/pg_iovec.h`.

## Purpose

Frontend file-system utilities used by **every PG tool that has to make changes durable**: `sync_pgdata` (initdb + pg_basebackup full-tree fsync), `sync_dir_recurse` (single-dir variant), `durable_rename` (atomic-replace with fsync), `fsync_fname`/`fsync_parent_path`, `pre_sync_fname` (sync_file_range/posix_fadvise hint), and the cross-built `get_dirent_type` / `pg_pwritev_with_retry` / `pg_pwrite_zeros` / `compute_remaining_iovec`. [from-comment, file_utils.c:1-13]

## Role in PG

Frontend file-utility hub. Backend has a parallel implementation in `storage/file/fd.c` — same algorithm, different error-reporting (ereport vs pg_log_error/exit). The vectored I/O helpers are shared verbatim between frontend and backend.

## Key functions

- `sync_pgdata(pg_data, serverVersion, sync_method, sync_data_files)` (98-228) — the cluster-wide fsync. Handles `pg_xlog`→`pg_wal` rename for pre-10 clusters, detects whether `pg_wal` is a symlink, then dispatches on `sync_method`:
  - `SYNCFS`: `syncfs(pg_data)`, plus `syncfs(pg_tblspc/<each>)` for tablespaces, plus `syncfs(pg_wal)` if it's a symlink. One syscall per filesystem. [verified-by-code, file_utils.c:130-186]
  - `FSYNC`: a `walkdir(pg_data, pre_sync_fname, false, exclude)` to hint the kernel, then `walkdir(pg_data, fsync_fname, false, exclude)` to do the work, plus separate `walkdir`s for `pg_wal` (if symlink) and `pg_tblspc` (with `process_symlinks=true`). `exclude_dir` skips `base/` when `sync_data_files=false` (pg_basebackup --no-sync-data-files case). [verified-by-code, file_utils.c:188-226]
- `walkdir(path, action, process_symlinks, exclude_dir)` (289-349) — recursive `opendir`/`readdir`. `process_symlinks` is consulted only at the top level via `get_dirent_type(...process_symlinks...)`; **subdir recursion always passes `false`** (intentional — comment at line 277-280). After each subdir walk, `(*action)(path, true)` fsyncs the directory itself. [verified-by-code, file_utils.c:289-349]
- `pre_sync_fname(fname, isdir)` (358-390) — opens read-only, calls `sync_file_range(SYNC_FILE_RANGE_WRITE)` if available, else `posix_fadvise(POSIX_FADV_DONTNEED)`. Errors only logged (best-effort hint). [verified-by-code, file_utils.c:358-390]
- `fsync_fname(fname, isdir)` (399-447) — opens RDWR for files, RDONLY for dirs. `fsync` failure is fatal (`exit(EXIT_FAILURE)`) unless it's a directory with EBADF/EINVAL (some OSes can't fsync dirs). [verified-by-code, file_utils.c:399-447]
- `durable_rename(oldfile, newfile)` (482-536) — fsync source, optionally open+fsync existing target, `rename()`, fsync new name, fsync parent dir. **Five fsyncs per rename in the worst case.** [verified-by-code, file_utils.c:482-536]
- `fsync_parent_path(fname)` (455-475) — fsync of `dirname(fname)`. [verified-by-code, file_utils.c:455-475]
- `get_dirent_type(path, *de, look_through_symlinks, elevel)` (546-611) — BSD `d_type` fast path; falls back to `stat`/`lstat`. The `look_through_symlinks` flag picks `stat` (follow) vs `lstat` (don't follow). [verified-by-code, file_utils.c:546-611, by file structure]
- `pg_pwritev_with_retry(fd, iov, iovcnt, offset)` (658-697) — copies `iov` into a local `iov_copy[PG_IOV_MAX]` so the retry loop can mutate without disturbing the caller's array. Loops while `compute_remaining_iovec` says more bytes pending. [verified-by-code, file_utils.c:658-697]
- `pg_pwrite_zeros(fd, size, offset)` (708-750) — uses a static `PGIOAlignedBlock zbuffer = {0}` (one BLCKSZ block) referenced from up to PG_IOV_MAX `iovec`s per syscall. The same zero page is reused for every IOV. [verified-by-code, file_utils.c:708-750]

## State / globals

- `static const PGIOAlignedBlock zbuffer` inside `pg_pwrite_zeros` (line 711) — one BLCKSZ of zeros for vectored zero-writing. `unconstify` is required because POSIX `writev` takes a non-const buffer pointer even when not modifying. [verified-by-code, file_utils.c:711-712]

## Phase D notes

- **No `O_NOFOLLOW`.** `pre_sync_fname` and `fsync_fname` both `open()` without `O_NOFOLLOW` (lines 364, 423). A symlink at the bottom of the walk that points outside PGDATA would be followed during the fsync pass. **But** `walkdir`'s symlink discipline (line 277-280, `process_symlinks` is only honored at the top level) means symlinks **encountered during recursion** are skipped by the dirent-type check — they never reach `open`. The exposure is: top-level `pg_wal` and entries directly under `pg_tblspc`. Those are documented PG-supported symlinks. [verified-by-code, file_utils.c:277-280,289-349] [maybe — Phase D]
- **walkdir errors are non-fatal mid-pass.** `opendir` failure logs an error and returns silently; `readdir` mid-walk error logs and continues. So a `sync_pgdata` that hit a transient EIO somewhere in the tree exits cleanly — the caller has no way to know not everything was fsynced. **Important for crash safety**: a missed fsync may be the difference between "WAL replayable" and "data loss". [verified-by-code, file_utils.c:301-340] [ISSUE-correctness: sync_pgdata's walkdir treats per-file fsync errors as non-fatal in pre_sync but fatal in fsync_fname; opendir/readdir errors silently degrade coverage either way (maybe-high)]
- **`durable_rename` opens the target if it exists** (line 497) to fsync it before the rename. If the target is a symlink to something not openable RDWR (e.g. a device, an unreadable file), we hit the `errno != ENOENT` branch at line 500 and bail with an error — without ever attempting the rename. [verified-by-code, file_utils.c:497-505] [maybe]
- **`pre_sync_fname` swallows `EACCES`** (line 368) — unreadable files in a walkdir don't error out the hint pass. The follow-up `fsync_fname` will see the same EACCES, hit the same branch at line 426 (skip), and continue. Net effect: a chmod'd-to-nothing file under PGDATA gets silently skipped by `sync_pgdata`. [verified-by-code, file_utils.c:368-369,426-427] [maybe]
- **`pg_pwritev_with_retry` overwrites caller's iov.** Wait — it doesn't: line 661 introduces `iov_copy[PG_IOV_MAX]` and the comment at 687-693 makes the swap explicit. Good. [verified-by-code, file_utils.c:661-694]
- **The static `zbuffer` is shared across threads** (frontend tools are single-threaded; backend uses a different copy via `fd.c`). No concurrency hazard in current code. [verified-by-code, file_utils.c:711-712]
- **`durable_rename` does not handle the case where source and target are on different filesystems.** `rename(2)` returns EXDEV and we log and bail. No fallback copy. [verified-by-code, file_utils.c:518-523]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=18 [maybe]=4`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
