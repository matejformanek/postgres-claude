# `src/bin/pg_checksums/pg_checksums.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~668
- **Source:** `source/src/bin/pg_checksums/pg_checksums.c`

Offline cluster-wide data-checksum tool. Three modes: `--check` (default,
verify pd_checksum on every relation block), `--enable` (compute and write
the checksum into each block), `--disable` (just flip the control-file flag).
The cluster MUST be cleanly shut down (`DB_SHUTDOWNED` or
`DB_SHUTDOWNED_IN_RECOVERY`) — running the tool on a live cluster, or even
starting the postmaster mid-run, leads to torn-page corruption that
checksums can't detect. [verified-by-code] [from-comment]

## API / entry points

- `main` — argument parsing; reads PG_VERSION + pg_control, validates
  cluster shutdown state and block size, then either two-pass scans
  (sizeonly first if `-P`) `global/`, `base/`, `pg_tblspc/` or just toggles
  the control file. Updates `data_checksum_version` and calls
  `update_controlfile` last. [verified-by-code]
- `scan_directory(basedir, subdir, sizeonly)` — recurses into the data
  directory. Special-cases `pg_tblspc/<oid>` by stat-ing
  `TABLESPACE_VERSION_DIRECTORY` and recursing into that, so symlinks are
  resolved. Skips `pg_internal.init` (prefix match), `PG_VERSION`,
  `pg_filenode.map`, `pg_control`, `.DS_Store`, `pgsql_tmp*` and the
  `PG_TEMP_FILE_PREFIX` files. [verified-by-code]
- `scan_file(fn, segmentno)` — opens the relfile, reads it BLCKSZ at a
  time, recomputes `pg_checksum_page(buf, blockno + segmentno*RELSEG_SIZE)`,
  in `--check` mode compares against `pd_checksum`, in `--enable` mode
  rewrites only blocks where the checksum differs. `PageIsNew` blocks are
  silently skipped (no checksum yet by design). [verified-by-code]
- `skipfile(fn)` — exclusion list against the per-cluster skip list (matches
  what `basebackup.c` excludes). [from-comment]
- `progress_report(finished)` — at most once per second, prints
  `current/total MB (pct)` to stderr; CR-terminated if TTY else newline.
  [verified-by-code]

## Notable invariants / details

- The cluster must be cleanly shut down: lines 584-586 reject any other
  `ControlFile->state`. There is no protection against a postmaster being
  started concurrently with pg_checksums after the check, per the comment
  at line 581-583. [from-comment] [ISSUE-undocumented-invariant:
  no advisory lock against concurrent postmaster (maybe)]
- Block-size and `pg_control_version` must match exactly (lines 568-577).
  Major-version of PG_VERSION must equal `PG_MAJORVERSION_NUM` (line 555).
  [verified-by-code]
- `--enable` checks the file again before rewriting (line 245-246) so
  re-running after partial completion only touches blocks that differ.
  [verified-by-code]
- Filename parsing at lines 355-368: cuts off at `.` for segment number and
  `_` for fork; `segmentno == 0` after `atoi` is fatal because a real
  segment-0 file is named without `.0`. [verified-by-code]
- `-f / --filenode` filter only applies to `--check`; enforced at line 542.
  [verified-by-code]
- After mode changes, `update_controlfile` is called last; if `do_sync`
  is true the data directory is fsynced first. The order matters — if we
  set `data_checksum_version` in pg_control before all blocks are written,
  a crash leaves a "checksums enabled" cluster with stale blocks.
  [from-comment]
- Filename canonicalization risk: `strncmp(de->d_name, PG_TEMP_FILE_PREFIX,
  strlen(PG_TEMP_FILE_PREFIX))` (line 321) is a prefix match; if PG ever
  introduced a non-temp file beginning with the same prefix it would be
  silently skipped. [verified-by-code] [ISSUE-correctness: prefix-only
  skip is fragile (nit)]

## Potential issues

- `pg_checksums.c:580-586` — only the postmaster cleanly-shutdown check;
  no advisory lockfile is taken. If an operator starts the postmaster
  while the tool is mid-`--enable`, blocks written by both writers race.
  [ISSUE-correctness: no concurrent-postmaster guard (likely)]
- `pg_checksums.c:254-258` — `lseek(...SEEK_CUR)` then `write` for the
  checksum-only rewrite; if the write returns short on a partial filesystem
  (e.g. NFS) the block ends up garbled but pg_checksums treats only
  non-positive returns as fatal. The check at 259-267 does handle
  `w != BLCKSZ` correctly. [verified-by-code]
- `pg_checksums.c:339-343` — `lstat` is used (correctly) on directory
  entries; tablespace symlinks are intentionally treated as directories
  by also matching `S_ISLNK` and recursing. [verified-by-code]
- `pg_checksums.c:108-117` — the exclusion list is in sync-with-comment
  with `basebackup.c`. Drift risk if backup logic changes.
  [ISSUE-doc-drift: keep exclusion list in sync with basebackup.c (nit)]
- `pg_checksums.c:226` — `pg_checksum_page(buf, blockno + segmentno *
  RELSEG_SIZE)` uses the global block number; this assumes RELSEG_SIZE
  matches the build-time constant. There's no on-disk check for that
  (block size IS checked above). [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `bin-singletons`](../../../../issues/bin-singletons.md)
<!-- issues:auto:end -->
