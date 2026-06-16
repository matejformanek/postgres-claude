# file.c

## Purpose

The actual data-migration path. Three mutually-exclusive transfer
modes for each relfilenode in the cluster (and tablespaces), plus a
visibility-map rewriter for the catversion-201603011 VM-format change,
plus three probe functions used at start of `--check` to fail fast if
the chosen transfer mode won't work.

## Role in pg_upgrade

Invoked once per relation file by `transfer.c::transfer_relfile`. The
chosen `user_opts.transfer_mode` (TRANSFER_MODE_COPY /
COPY_FILE_RANGE / LINK / CLONE / SWAP) routes to one of `copyFile`,
`copyFileByRange`, `linkFile`, or `cloneFile`. The visibility-map
rewriter is invoked separately when the old cluster's catversion is
pre-201603011.

## Key functions

- `cloneFile(src, dst, schemaName, relName)` `file.c:39` — CoW clone.
  Platform fork:
  - macOS: `copyfile(src, dst, NULL, COPYFILE_CLONE_FORCE)`.
  - Linux: `open(src, O_RDONLY|PG_BINARY)` + `open(dst,
    O_RDWR|O_CREAT|O_EXCL|PG_BINARY, pg_file_create_mode)` +
    `ioctl(dest_fd, FICLONE, src_fd)`. On ioctl failure, `unlink(dst)`
    then `pg_fatal`. Lines 50-67.
  - Other: empty stub (linker would fail; check_file_clone catches).
- `copyFile(src, dst, schemaName, relName)` `file.c:82` — vanilla
  read/write loop with `50 * BLCKSZ` chunks (line 100). On non-Windows:
  `open(src, O_RDONLY|PG_BINARY)` + `open(dst, O_RDWR|O_CREAT|O_EXCL
  |PG_BINARY, pg_file_create_mode)` + read/write loop. Sets `errno =
  0` before each write and infers `ENOSPC` if write returns short
  without setting errno (lines 116-124). On Windows: `CopyFile()`
  with the "fail-if-exists" flag.
- `copyFileByRange(src, dst, schemaName, relName)` `file.c:151` —
  Linux/BSD `copy_file_range(2)` loop with `SSIZE_MAX` per call.
  Open/create same way as copyFile.
- `linkFile(src, dst, schemaName, relName)` `file.c:190` — single
  `link(2)` call. No ownership/permission preservation needed (hard
  link aliases the inode).
- `rewriteVisibilityMap(fromfile, tofile, schemaName, relName)`
  `file.c:216` — translates one-bit-per-page → two-bit-per-page VM
  format. Reads BLCKSZ-aligned pages, requires full reads (line 263
  fatals on partial), allocates `PGIOAlignedBlock` buffers (lines
  221-222), recomputes `pd_checksum` if the new cluster has
  checksums enabled (line 334).
- `check_file_clone()`, `check_copy_file_range()`,
  `check_hard_link(transfer_mode)` `file.c:360,400,437` — probe
  functions. Each tries the operation on `<old>/PG_VERSION` →
  `<new>/PG_VERSION.<modename>test`, then `unlink`s the test file.
  `pg_fatal` with a mode-specific hint if it fails (e.g.
  "must be on the same file system" for link mode line 449).

## State / globals

None. All functions are stateless.

## Phase D notes — the THREE modes

[verified-by-code] Open-pattern audit:

- `O_RDONLY | PG_BINARY` on the source (lines 50, 90, 159, 232) — no
  `O_NOFOLLOW`.
- `O_RDWR | O_CREAT | O_EXCL | PG_BINARY` on the destination (lines
  54, 94, 163, 240, 381, 418). `O_EXCL` means an attacker cannot
  pre-create the destination file as a symlink to confuse the writer.
  Per-mode behavior on EEXIST is `pg_fatal`.
- `pg_file_create_mode` is used uniformly for permissions; matches
  the umask the new cluster's initdb established.
- No `fchmod` / `fchown` calls — the new file gets initdb's mode/uid
  and that's it.

**Path-traversal on relfilenumber input?** [from-code] The `src`/`dst`
strings are built in `transfer.c` from `cluster->pgdata` +
tablespace path + `relfilenumber + suffix`. relfilenumber is from
the OLD cluster's catalog (pg_class.relfilenode), which is a uint32
formatted as a decimal. No user-controllable component reaches this
function. The strings come in fully formed.

**Symlink hazard per mode:**

1. **copy mode** — source open is `O_RDONLY`, kernel follows symlinks
   normally. If the OLD cluster's PGDATA has a symlink-replaced data
   file pointing to `/etc/shadow`, copyFile() would copy that into
   the new cluster's data dir under the relfilenode name. But the
   old cluster's PGDATA must already be a postmaster's PGDATA, which
   `initdb` set up; the symlink-injection would need superuser
   shell access to the OLD cluster's filesystem, in which case the
   attacker can just edit pg_class. Same trust boundary.
2. **link mode (hard link)** — `link(2)` does NOT follow symlinks on
   the target name (creates a new directory entry); but it DOES
   resolve them on the source name. So a symlink-replaced source
   file gets hard-linked to the symlink target's inode. Same trust
   boundary as above.
3. **clone mode (FICLONE / copyfile COPYFILE_CLONE_FORCE)** — both
   syscalls follow symlinks. Same trust boundary.

[ISSUE-undocumented-invariant: link mode does NOT use O_NOFOLLOW or
`linkat(... AT_SYMLINK_NOFOLLOW)`, so a symlink-replaced source in
PGDATA aliases to the linktarget (low; requires pre-existing root or
PGDATA write)] — `file.c:193`.

[from-comment] **Link-mode danger is documented elsewhere** — see
`pg_upgrade.sgml` and the `disable_old_cluster()` warning in
controldata.c:782 ("Because 'link' mode was used, the old cluster
cannot be safely started"). file.c itself enforces nothing; the
operator must heed the warning.

[from-code] **Checksum recomputation on VM rewrite** (line 334):
`if (new_cluster.controldata.data_checksum_version !=
PG_DATA_CHECKSUM_OFF) pg_checksum_page(...)`. The OLD cluster's
checksum is *not* verified before reading — pg_upgrade trusts the
old cluster's pages.

[ISSUE-correctness: copyFileByRange has no progress check and may
loop forever if `copy_file_range` returns SSIZE_MAX but actually
copied less (low)] — `file.c:170`. In practice `copy_file_range`
returns the actual bytes copied; the loop terminates on `nbytes
<= 0`. If the syscall is buggy and returns >0 but doesn't advance
file offsets, infinite loop. Modern kernels are fine.

[ISSUE-trust-boundary: source-file content from the old cluster is
written byte-for-byte to the new cluster with no validation
(by-design; tagged for completeness)] — file.c:117 in copyFile,
file.c:193 in linkFile (the file IS the data), file.c:170 in
copyFileByRange, file.c:59 in cloneFile. Visibility-map rewrite
(file.c:216) is the ONLY function that inspects content; all others
are bytewise.

[ISSUE-state-transition: clone-mode `unlink(dst)` after ioctl
failure (file.c:63) leaves the file system in a half-state — if
unlink fails too, future runs of pg_upgrade hit the O_EXCL guard
(low)] — Only after a kernel-level FICLONE failure; rare.

[from-code] **Probe functions** (`check_file_clone` etc.) write to
`<new>/PG_VERSION.<mode>test`, which is in the new cluster's data
dir. If the new cluster's PGDATA permission isn't writable by the
pg_upgrade user, these abort with `pg_fatal` before any data is
copied. Good fail-fast.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
