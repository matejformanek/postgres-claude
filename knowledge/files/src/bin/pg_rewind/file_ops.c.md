# file_ops.c

## Purpose

The local-FS write layer of `pg_rewind` — opens, writes, truncates,
removes, and `mkdir`/`symlink`/`rmdir`s files inside the target
`datadir_target`. Also provides read helpers `slurpFile` and
`traverse_datadir` used during the inventory pass.

Every mutating function checks `path_is_safe_for_extraction(path)`
first and honours the global `dry_run` flag (set by `--dry-run`).

## Role in pg_rewind

The bottom of the write stack. The high-level flow is:

1. Source (libpq or local) → enumerates files on the source.
2. Filemap layer → decides per-file `FILE_ACTION_*`.
3. `create_target()` / `remove_target()` / `truncate_target_file()` /
   `write_target_range()` here → apply the action to disk.

After all writes, `pg_rewind.c` calls `sync_target_dir()` once, which
delegates to `sync_pgdata()` (two-pass fsync of the whole data dir).

## Key functions

- `open_target_file(path, trunc)` (`source/src/bin/pg_rewind/file_ops.c:46-72`).
  Reuses the static `dstfd` if the same path is already open and `!trunc`
  — micro-optimisation for sequential `write_target_range` calls into the
  same relfile. Opens with `O_WRONLY | O_CREAT | PG_BINARY` and
  `pg_file_create_mode` (0600 by default, 0640 in group mode).
- `write_target_range(buf, begin, size)` (`:90-129`). `lseek` to `begin`,
  loop-write until done; bumps `fetch_done` for the progress reporter.
  On `write < 0` with `errno == 0`, fabricates `ENOSPC` (defensive against
  buggy `write` returns).
- `remove_target_file(path, missing_ok)` (`:189-209`). `unlink`; treats
  `ENOENT` as success when `missing_ok`.
- `truncate_target_file(path, newsize)` (`:211-235`). Opens, `ftruncate`,
  closes. Comment passes `pg_file_create_mode` to a non-`O_CREAT` `open`
  — harmless but odd ([from-comment] [inferred]).
- `create_target()` / `remove_target()` (`:158-183`, `:132-156`). Dispatch
  by `file_entry_t::source_type` / `target_type` to the per-type helpers
  (regular files are not created here — they go through `open_target_file`).
- `create_target_symlink(path, link)` (`:273-288`). `symlink(link, dstpath)`.
  The link **target** content is whatever the source reported — no
  validation that it's a relative path or stays inside `datadir_target`.
- `sync_target_dir()` (`:316-323`). Delegates to `sync_pgdata` with
  `sync_method` (controls `fsync` vs `syncfs`).
- `slurpFile(datadir, path, *filesize)` (`:336-378`). Reads whole file
  into a `pg_malloc`'d, NUL-terminated buffer. Used for things like
  `PG_VERSION`, control file, history files.
- `traverse_datadir(datadir, callback)` / `recurse_dir` (`:384-491`).
  DFS over the data directory; skips `.`/`..`; tolerates `ENOENT` on
  `lstat` (file disappeared mid-scan, expected on running source);
  on `S_ISLNK` reads target via `readlink` and recurses only if the
  parent is `pg_tblspc` or path equals `pg_wal` (`:478-480`).

## State / globals

- `static int dstfd = -1`, `static char dstpath[MAXPGPATH]` (`:31-32`) —
  single "currently open target file" cache; reset to -1 on close.
- Relies on globals from `pg_rewind.h`: `dry_run`, `do_sync`, `datadir_target`,
  `sync_method`, `fetch_done`.

## Phase D notes

### Path safety — `path_is_safe_for_extraction`

Every mutating entry point validates `path` via
`path_is_safe_for_extraction()` (definition at
`source/src/port/path.c:636-645`). That helper runs `canonicalize_path`
on a stack-local copy and then `path_is_relative_and_below_cwd` —
rejecting absolute paths and any `..` components after canonicalisation.
This blocks the obvious `..//etc/passwd` style traversal.

What it does **NOT** block:

- **Symlink races.** The target file at `<datadir_target>/<path>` is
  opened with plain `open()` — no `O_NOFOLLOW`. If the target's
  data_dir already contains a symlink at `<path>` (planted by a
  prior local attacker, or pre-existing inside `pg_tblspc`), the
  `O_WRONLY | O_CREAT` here will follow it and clobber the symlink
  target. Same for `unlink`, `symlink`, `rmdir`.
- **TOCTOU between validation and open.** `path_is_safe_for_extraction`
  validates the relative path string, not the result of opening it.

### Per-file: does `file_ops.c` use `O_NOFOLLOW`?

**No.** Searched the file: zero occurrences. `open_target_file`
(`:65-68`) uses `O_WRONLY | O_CREAT | PG_BINARY`. `truncate_target_file`
(`:225`) uses `O_WRONLY`. `slurpFile` (`:348`) uses `O_RDONLY | PG_BINARY`.

### Symlink creation trust

`create_target_symlink(path, link)` (`:285`) calls `symlink(link, dstpath)`
where `link` is `entry->source_link_target` — i.e. the literal bytes the
source reported via libpq or via local `readlink`. There is no check that
`link` is a relative path or doesn't escape the data dir. The on-disk
contract is whatever the source said. For `pg_tblspc/*` this is expected
(tablespaces legitimately point outside), but for `pg_wal` or anywhere
else, an attacker controlling the source could plant a symlink pointing
into `/etc` and later writes through that path would write into `/etc`.

### Race vs concurrent target

The target Postgres must be cleanly shut down before pg_rewind runs
([from-README] — pg_rewind.sgml). If the operator violates that, the
running backend could be reading files this code is rewriting. No
locking is taken on the target dir.

### sync semantics

`sync_target_dir` runs once at end, after all writes. If pg_rewind
crashes mid-run, the target is in an undefined state until either
`pg_rewind` is re-run successfully or recovery from elsewhere is
performed. This is documented in pg_rewind.sgml ([from-comment]).

## Potential issues

- `[ISSUE-trust-boundary: open_target_file lacks O_NOFOLLOW — a
  pre-existing symlink at <datadir_target>/<path> is followed and
  written through (maybe)]` (`:65-68`). Mitigated by the requirement
  that the target be a stopped PG cluster owned by the same OS user,
  but is a hardening gap. Same concern for `truncate_target_file`
  (`:225`), `remove_target_file` (`:201`), `create_target_symlink`
  (`:285`), `remove_target_symlink` (`:302`), `remove_target_dir`
  (`:268`).
- `[ISSUE-trust-boundary: create_target_symlink writes attacker-
  influenced link target without validation (maybe)]` (`:285`). The
  link content comes from the source. For sources outside `pg_tblspc`
  this is suspicious; even within `pg_tblspc` an absolute path is
  trusted blindly.
- `[ISSUE-stale-todo: "TODO: But complain if we're processing the
  target dir!" on ENOENT during traversal (low)]` (`:437`). The
  ENOENT-tolerance is correct for the source dir scan but should
  be an error on the target.
- `[ISSUE-undocumented-invariant: dstfd cache key compares
  &dstpath[strlen(datadir_target) + 1] which assumes datadir_target
  has no trailing slash (low)]` (`:58`). If somebody set
  `datadir_target = "/foo/"`, the `strlen + 1` skips past the file
  separator incorrectly and the cache hit logic breaks. Probably
  prevented by argv parsing in `pg_rewind.c` but not enforced here.
- `[ISSUE-correctness: write_target_range fabricates ENOSPC when
  write returns < 0 with errno == 0 (low)]` (`:118-119`). Defensive,
  but masks the real cause. Modern Linux always sets errno on a
  failed `write`; this branch is essentially dead but kept for
  paranoid portability.
- `[ISSUE-path-traversal: symlink targets in pg_tblspc are followed
  recursively without checking they stay within the target's
  tablespace area (maybe)]` (`:478-480`). `recurse_dir` follows any
  symlink whose parent is `pg_tblspc` or whose path is `pg_wal`. A
  malicious source could report symlinks here that, when later
  created on the target, point into the source's filesystem and
  then be traversed by a *subsequent* pg_rewind run.
