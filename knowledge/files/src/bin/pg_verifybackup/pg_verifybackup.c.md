# `src/bin/pg_verifybackup/pg_verifybackup.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1407
- **Source:** `source/src/bin/pg_verifybackup/pg_verifybackup.c`

Verifies a pg_basebackup output (plain or tar format) against the
JSON `backup_manifest` file produced alongside it. Three layers of check:
(1) every file mentioned in the manifest exists on disk with the right
size, (2) every file has the recorded checksum (SHA-/CRC-/none-per-file),
(3) every WAL range listed in the manifest is replayable via `pg_waldump`.
For manifest version ≥ 2, also cross-checks `pg_control` (system identifier,
CRC, version). [verified-by-code]

## API / entry points

- `main` — argument parsing, hard-coded ignore list seeded with
  `backup_manifest`, `pg_wal`, `postgresql.auto.conf`, `recovery.signal`,
  `standby.signal` (line 184-188). Auto-detects plain-vs-tar by stat-ing
  `PG_VERSION` inside the backup directory unless `-F` is given.
  Dispatches to `verify_plain_backup_directory` or `verify_tar_backup`.
  Then `report_extra_backup_files` (manifest entries not seen on disk),
  `verify_backup_checksums` for plain backups (tar verifies inline),
  and `parse_required_wal` unless `-n / --no-parse-wal`.
  [verified-by-code]
- `parse_manifest_file(manifest_path)` — open, fstat, estimate hash
  table size (`statbuf.st_size / 100`), slurp-in-one if small enough
  or chunked-incremental otherwise (READ_CHUNK_SIZE = 128 KiB). The
  incremental path uses `json_parse_manifest_incremental_*` and ensures
  the *last* chunk is at least chunk_size/2 so the trailing checksum
  block isn't split. [from-comment]
- `verifybackup_*_cb` — JSON parse callbacks that populate
  `manifest_data`: version, system_identifier, per-file (insert into
  simplehash), per-WAL-range (doubly-linked list).
  [verified-by-code]
- `verify_plain_backup_directory` / `verify_plain_backup_file` —
  recursive directory walk; reports errors when files are present on
  disk but missing from the manifest, when sizes mismatch, or when
  control-file mismatch occurs (the latter only for manifest version
  != 1). [verified-by-code]
- `verify_control_file(path, manifest_sysid)` — load via
  `get_controlfile_by_exact_path`, error if CRC bad, version mismatch,
  or `system_identifier` ≠ manifest's. [verified-by-code]
- `verify_tar_backup` — two-pass: precheck each tar (recognize
  `base.*`, `pg_wal.*`, `<tblspc-oid>.tar*`, identify compression
  algorithm) into a `SimplePtrList`, then `verify_tar_file` per entry
  with the streamer pipeline `gzip|lz4|zstd-decompressor → tar-parser
  → astreamer_verify_content`. [verified-by-code]
- `precheck_tar_backup_file` — basename pattern match (`base`,
  `pg_wal`, or `<oid>`), then `parse_tar_compress_algorithm` on the
  suffix. WAL archives are short-circuited (skipped by content
  verification; pg_waldump handles them later). [verified-by-code]
- `verify_tar_file` — read in `READ_CHUNK_SIZE` blocks, feed to
  `astreamer_content(streamer, NULL, buffer, rc, ASTREAMER_UNKNOWN)`.
  [verified-by-code]
- `verify_backup_checksums` / `verify_file_checksum` — iterate hash,
  open each file, chunked read + `pg_checksum_update`, compare against
  `m->checksum_payload`. [verified-by-code]
- `parse_required_wal(context, pg_waldump_path, wal_path)` — for each
  WAL range, builds a `pg_waldump --quiet --path=... --timeline=...
  --start=... --end=...` command and invokes via `system(3)`. Failures
  are reported but iteration continues. [verified-by-code]
- `report_backup_error` / `report_fatal_error` — log + saw_any_error
  (or exit). `exit_on_error` causes the soft-error path to also exit.
  [verified-by-code]
- `should_ignore_relpath` — substring-prefix match against
  `ignore_list` with `/` boundary so `aa/bb` is not a prefix of `aa/bbb`
  but is of `aa/bb/cc`. [from-comment]
- `progress_report(finished)` — at most once per second, prints kB
  done/total + percent to stderr. [verified-by-code]

## Notable invariants / details

- The manifest is the trust root: any file present in the backup but
  not in the manifest is an error, and any file in the manifest but
  not on disk is also an error. The ignore list breaks that for known
  exceptions (5 baked-in entries plus user `-i RELATIVE_PATH`).
  [verified-by-code]
- Manifest version 1 (PG 13's first incremental support) had no
  system_identifier; verify_control_file is skipped for v1
  (line 748). [verified-by-code]
- For tar backups, the control-file CRC + system-identifier cross-check
  lives in `astreamer_verify.c` (`member_verify_control_data`), not
  here. [verified-by-code]
- `find_other_exec` for `pg_waldump` requires identical major version;
  versioning mismatch is fatal. Skipped if `-n`. [verified-by-code]
- Manifest size → hash-table size estimate: 100 bytes per line. Min
  256, max PG_UINT32_MAX. Skew acceptable per the comment block at
  line 31-42. [from-comment]
- Incremental JSON parsing: each chunk is fed into a sticky parser
  state; final chunk is signaled by `bytes_left == 0`. [verified-by-code]
- `precheck_tar_backup_file`'s OID extraction uses `strtoul`
  (line 954) with `OID_MAX` upper bound. A tar filename like
  `0` or `99999999999999.tar` is rejected. [verified-by-code]

## Potential issues

- `pg_verifybackup.c:1237` — `system(pg_waldump_cmd)` runs a constructed
  command line including `wal_path` from `-w / --wal-path` (or a
  computed path). The path comes from user CLI or from the backup
  directory listing; if either contains shell metacharacters they will
  be interpreted by /bin/sh. `canonicalize_path` runs on user input,
  but it does not strip shell metacharacters.
  [ISSUE-security: shell injection via crafted -w argument or crafted
  tablespace name inside a backup (likely)]
- `pg_verifybackup.c:1232-1235` — the `pg_waldump_cmd` format string
  uses `%s` for `pg_waldump_path` and `wal_path`. If `pg_waldump_path`
  comes from `find_other_exec` it's the binary the verifier resolved,
  so trusted. `wal_path` is user-controlled.
  [ISSUE-security: same root cause as above (likely)]
- `pg_verifybackup.c:198-203` — `-i` accepts arbitrary path including
  `..`. After `canonicalize_path` the string is appended to the ignore
  list verbatim. Lookups against this list use `should_ignore_relpath`
  which is prefix-bounded by `/`. Not exploitable but worth noting.
  [verified-by-code]
- `pg_verifybackup.c:248-249` — `context.backup_directory` is
  `canonicalize_path`'d but no further validation. If a user passes
  a path to a non-backup directory, the tool will iterate it and
  declare lots of files "present on disk but not in manifest".
  Working as designed. [verified-by-code]
- `pg_verifybackup.c:529-532` — `report_manifest_error` is
  `pg_noreturn` and exits 1; this is correct for a top-level
  fatal-on-parse-error policy but it means that even with
  `--exit-on-error` *off*, manifest parse problems still abort.
  Documented. [from-comment]
- `pg_verifybackup.c:954-967` — accepts an OID-named tar even if the
  OID corresponds to no actual tablespace; verification of the
  contents catches a mismatch via the manifest entries, but the
  metadata cross-check on the OID itself isn't performed.
  [ISSUE-correctness: OID-as-filename not cross-checked against
  catalog/tablespace (nit)]
- `pg_verifybackup.c:1188-1194` — `bytes_read != m->size` check is a
  belt-and-braces re-check; the primary size check is in
  `verify_plain_backup_file`. Useful only against concurrent file
  modification mid-checksum. [from-comment]
- `pg_verifybackup.c:1255-1264` — `report_backup_error` ignores
  `errno` in the `va_list` formatting; the underlying
  `pg_log_generic_v` handles `%m` only at the top of the format.
  No issue. [verified-by-code]
- `pg_verifybackup.c:430-431` — `Min(PG_UINT32_MAX, Max(estimate,
  256))` — `estimate` is `off_t` (potentially 64-bit). `Min(uint32,
  off_t)` works via the Min macro's implicit comparison. Fine on
  64-bit; on 32-bit hosts an off_t > UINT32_MAX backup manifest is
  unrealistic. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_verifybackup`](../../../../issues/pg_verifybackup.md)
<!-- issues:auto:end -->
