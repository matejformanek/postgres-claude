# `src/bin/pg_combinebackup/pg_combinebackup.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1376
- **Source:** `source/src/bin/pg_combinebackup/pg_combinebackup.c`

CLI entry point for `pg_combinebackup` (introduced PG17 alongside
incremental backup). Takes N input backup directories (one full +
N-1 incrementals, in chronological order) and an `-o` output
directory; recursively walks the latest backup, copying non-incremental
files straight through and feeding `INCREMENTAL.*` files into
`reconstruct_from_incremental_file()`. Optionally writes a fresh
`backup_manifest` to the output directory. [verified-by-code]

## API / entry points

- `main(argc, argv)` — getopt loop, then orchestration:
  1. Read PG_VERSION of the final backup, sanity-check.
  2. `check_control_files()` — read pg_control of every backup,
     validate identical `system_identifier`, identical pg_control
     version. Warn (don't fail) if `data_checksum_version`
     differs between backups. [verified-by-code]
  3. `check_backup_label_files()` — walk backups newest-to-oldest
     and confirm each one's `INCREMENTAL FROM (lsn, tli)` matches
     the previous backup's `START WAL LOCATION` / `START TIMELINE`.
     Returns the last-backup buffer for later
     `write_backup_label()`. [verified-by-code]
  4. `load_backup_manifests()` over prior_backup_dirs (note: this
     is `argv + optind`, which actually includes all backups
     including the final one — see "issues"). [verified-by-code]
  5. Cross-check that every manifest's system_identifier matches
     pg_control's. [verified-by-code]
  6. `scan_for_existing_tablespaces()` on the final backup's
     `pg_tblspc`. [verified-by-code]
  7. Atomic cleanup install: `atexit(cleanup_directories_atexit)`.
     [verified-by-code]
  8. Create output dirs (main + per-tablespace), open manifest
     writer, write rewritten `backup_label`, then
     `process_directory_recursively` for the main data dir and
     each tablespace. [verified-by-code]
  9. `finalize_manifest`, optionally `sync_pgdata`, then
     `reset_directory_cleanup_list` so atexit() leaves the output
     alone, then `exit(0)`. [verified-by-code]

## Notable invariants / details

- Three copy modes via `--copy`, `--clone`, `--copy-file-range`, plus
  `-k/--link`. Default is `COPY`. Platform availability is checked
  at startup (line 249-276). [verified-by-code]
- `--no-manifest` implies `--manifest-checksums=NONE` (line 242).
  [verified-by-code]
- `--manifest-checksums` accepts SHA224/256/384/512 / CRC32C / NONE
  via `pg_checksum_parse_type` (line 203). Default `CRC32C` (line
  173). [verified-by-code]
- `pg_file_create_mode` and `pg_dir_create_mode` are set by
  `check_input_dir_permissions()` (line 690) calling
  `SetDataDirectoryCreatePerm(st.st_mode)` on the final input dir.
  This propagates `group_access` behaviour from the source backup
  to the output. [verified-by-code]
- Tablespace mapping (line 455): user passes
  `-T OLDDIR=NEWDIR`; backslash escapes `\=` for literal equals.
  Both sides must be absolute paths. Mappings keyed by the readlink
  target of the symlink in the final backup's `pg_tblspc/<oid>`.
  In-place tablespaces (PG-15+) don't need a mapping; their old/new
  dirs are computed automatically. [verified-by-code]
- Directory classification (line 887): only files under `base/`,
  `global`, and `pg_tblspc/*` (or a tablespace dir, signalled by
  `OidIsValid(tsoid)`) are considered "incremental-eligible". Files
  under any other directory (config, pg_xact, pg_multixact, etc.)
  with an `INCREMENTAL.` prefix are copied verbatim, so a user who
  creates an unfortunately-named config file isn't broken.
  [verified-by-code]
- `is_pg_wal` paths skip checksumming because the backup manifest
  doesn't list WAL files (line 903). [verified-by-code]
- Atexit-based cleanup removes the entire output tree on any
  uncaught failure, but only the dirs created during this run
  (those tracked in `cleanup_dir_list`). Already-existing-and-empty
  output directories get their contents removed but not the dir
  itself (`rmtopdir == false`, line 755). [verified-by-code]
- `--link` mode (`-k`) warns at the end (line 444) that modifying
  the output directory may corrupt the input — because hard links
  share inodes. [verified-by-code]
- Server version check: refuses pre-v10 (line 281). The actual
  feature gating for incremental backup is at v17, but here the
  check is only "modern enough to have understandable layout".
  [verified-by-code]
- `parse_oid` (line 808): rejects 0 explicitly (`oid < 1`), and
  rejects leading-zero parses by way of `strtoul` + check.
  [verified-by-code]

## Potential issues

- Line 298-301: `prior_backup_dirs = argv + optind;` covers
  ALL backups (length `n_backups`), but
  `load_backup_manifests(n_backups, prior_backup_dirs)` then loads
  manifests for every backup including the final one. `n_prior_backups
  = argc - optind - 1` is the count *not including* the final
  backup. The naming is therefore misleading: `prior_backup_dirs`
  is treated as "all backups" everywhere except in the loop in
  `reconstruct.c:181` where the index is bounded by
  `n_prior_backups`. Workable but a footgun for future maintainers.
  [verified-by-code] [ISSUE-style: prior_backup_dirs naming
  inconsistent with its length n_backups (nit)]
- Line 1272-1280: `readlink()` target size is `MAXPGPATH`. If the
  symlink target is exactly MAXPGPATH bytes we treat it as too long,
  which is correct, but the message could be more specific.
  [verified-by-code]
- Line 567-570 comment "XXX. It's actually not required that
  start_lsn == check_lsn..." — known TODO acknowledging a slightly
  too-strict consistency check between adjacent backup labels. A
  WAL switchpoint after the start of an earlier backup is currently
  rejected as "starts at LSN ... but expected ...". [verified-by-code]
  [ISSUE-stale-todo: XXX comment at line 567 flags overly-strict
  cross-backup LSN check (maybe)]
- Line 674-678: when only some backups in the chain have
  data_checksums enabled, we emit a warning telling the user to
  "disable, and optionally reenable, checksums on the output
  directory". This means the resulting cluster's pg_control would
  claim checksums-on while reconstructed pages may have stale
  per-page checksums from the no-checksum backup. The warning
  *recommends* user action but doesn't enforce it. A naive user
  may start the cluster with corrupt per-page checksums and get
  CRC errors on first read. [verified-by-code] [ISSUE-security:
  inconsistent data_checksum_version across backups is warned but
  not blocked; can produce a cluster with bad page checksums
  (likely)]
- Line 1083-1102: when manifest entry is missing for a file in the
  source directory, we emit `pg_log_warning` and proceed to
  recompute the checksum from scratch. This silently allows a
  corrupted manifest to result in a combined backup whose manifest
  is "fixed up" — useful for repair, but means
  `pg_combinebackup` cannot be used to validate manifest integrity.
  [verified-by-code] [ISSUE-undocumented-invariant: missing manifest
  entry is warned but tolerated; combinebackup is not a manifest
  verifier (nit)]
- Line 1124-1129: `pg_checksum_final` is called only when
  `checksum_ctx.type != CHECKSUM_TYPE_NONE && !opt->dry_run`. If
  dry_run is true but the user requested checksums, the manifest
  entry written further down (line 1133) gets `checksum_length=0,
  checksum_payload=NULL`. Currently `mwriter` is also NULL in
  dry_run (line 346-358), so the manifest write is skipped — but
  the coupling is subtle. [verified-by-code]
- Line 1162: `pfree(checksum_payload)` is called unconditionally
  but `checksum_payload` may point to memory owned by the manifest
  hash table (line 1100, where it's borrowed from
  `mfile->checksum_payload`). Freeing borrowed memory would be a
  double-free. Looking carefully: in the reuse path
  `checksum_payload` is assigned `mfile->checksum_payload` (line
  1100), the variable isn't re-malloced after, then it's pfree'd at
  1162. This appears to be a real bug — pfree against
  hash-owned memory. [verified-by-code] [ISSUE-correctness: line
  1100 borrows checksum_payload from manifest_file, line 1162
  pfree's it; possible double-free or freeing of hash-owned memory
  (likely)]
- Line 1376: trailing `\0` invariant in `slurp_file` writes past
  `buf->len` by one byte; this is the standard StringInfo trailing
  NUL but the comment notes the manual maintenance.
  [verified-by-code]
- Tablespace mapping table lookup (line 1291-1300) is O(n) per
  tablespace. With many tablespaces this is fine; backup
  directories rarely have more than a handful. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_combinebackup`](../../../../issues/pg_combinebackup.md)
<!-- issues:auto:end -->
