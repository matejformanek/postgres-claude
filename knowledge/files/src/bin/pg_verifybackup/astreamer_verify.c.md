# `src/bin/pg_verifybackup/astreamer_verify.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~432
- **Source:** `source/src/bin/pg_verifybackup/astreamer_verify.c`

The terminal `astreamer` in the pg_verifybackup tar pipeline. Sits at
the end of `decompressor → tar_parser → verify_content` and is called
once per tar-archive-member with `(streamer, member, data, len,
context)`. Performs per-member header validation (cross-check against
manifest), incremental checksum computation (so we don't have to
re-read the tar after decompressing), and — for the control file only,
in manifest version ≥ 2 — buffers the bytes so we can validate
CRC and system_identifier at TRAILER time. [verified-by-code]

## API / entry points

- `astreamer_verify_content_new(next, context, archive_name, tblspc_oid)`
  — factory. Allocates `astreamer_verify` (a struct embedding `astreamer
  base`), installs ops, allocates `checksum_ctx` if not skipping. The
  `next` pointer is expected to be NULL (no downstream).
  [verified-by-code]
- `astreamer_verify_content(streamer, member, data, len, context)` —
  switch on `context` (ASTREAMER_MEMBER_HEADER / _CONTENTS / _TRAILER /
  ARCHIVE_TRAILER). Header → `member_verify_header`. Contents →
  `member_compute_checksum` if verifying, `member_copy_control_data` if
  buffering. Trailer → `member_verify_checksum`,
  `member_verify_control_data`, then `member_reset_info`.
  [verified-by-code]
- `astreamer_verify_finalize` — asserts no downstream
  (`Assert(bbs_next == NULL)`). [verified-by-code]
- `astreamer_verify_free` — frees `checksum_ctx` and streamer.
- `member_verify_header(streamer, member)` — only regular files
  considered. Constructs `pathname` (`"./<name>"` for the base archive,
  `"pg_tblspc/<oid>/<name>"` for tablespace archives), `canonicalize_path`s,
  checks ignore list, looks up in `manifest_files`, marks `matched`,
  compares size. Decides `verify_checksum` (skip_checksums off + manifest
  has a checksum) and `verify_control_data` (version != 1 + path ==
  XLOG_CONTROL_FILE). Initializes the checksum context.
  [verified-by-code]
- `member_compute_checksum` — accumulates bytes via `pg_checksum_update`,
  tracks `checksum_bytes` to cross-check size at trailer time.
  [verified-by-code]
- `member_verify_checksum` — at trailer, asserts bytes match size,
  computes final checksum, compares to manifest. [verified-by-code]
- `member_copy_control_data` — buffers into the streamer's
  `control_file` field up to `sizeof(ControlFileData)`. Tracks total
  bytes seen (`control_file_bytes`). [from-comment]
- `member_verify_control_data` — at trailer, error if
  `control_file_bytes != PG_CONTROL_FILE_SIZE`, CRC-check, version
  check, system_identifier check against `manifest->system_identifier`.
  All four checks call `report_fatal_error` (noreturn). [verified-by-code]
- `member_reset_info` — zero `mfile`, both verify flags, and the byte
  counters. [verified-by-code]

## Notable invariants / details

- `Assert(streamer->bbs_next == NULL)` in finalize (line 140): this
  must be the terminal stage. [verified-by-code]
- The `*((const astreamer_ops **) &streamer->base.bbs_ops)` cast
  (line 73) is the standard pattern for assigning ops to an embedded
  base struct via the const qualifier. [verified-by-code]
- The tablespace path construction at line 183-184 uses literal
  `"pg_tblspc"` rather than `PG_TBLSPC_DIR` macro. Drift risk if the
  macro ever diverges. [ISSUE-doc-drift: hardcoded "pg_tblspc" string
  (nit)]
- The control-file buffer is at most `sizeof(ControlFileData)` (smaller
  than `PG_CONTROL_FILE_SIZE`); excess bytes are counted but not
  retained, per the comment at lines 342-347. [from-comment]
- The control file CRC computation uses `offsetof(ControlFileData,
  crc)`, exactly matching backend `update_controlfile`. Same algorithm
  as `pg_controldata`. [verified-by-code]
- The non-`OidIsValid(tblspc_oid)` branch uses `"./%s"` to force
  `canonicalize_path` to treat absolute paths inside the tar header as
  relative. Important because tar headers can contain absolute paths
  in malformed backups. [from-comment]
- `checksum_ctx` is shared across all members for one streamer; reset
  via `pg_checksum_init` per member header. [verified-by-code]

## Potential issues

- `astreamer_verify.c:232-233` — if `pg_checksum_init` fails,
  `verify_checksum` is forced off and the file is silently uncheck.
  An error is reported, but `member_verify_checksum` won't be invoked.
  Manifest will register a file as `matched` but `bad` is not set —
  so `should_verify_checksum` returns false and downstream
  `report_extra_backup_files` won't catch it.
  [ISSUE-correctness: checksum_init failure leads to silent skip
  rather than treating file as bad (likely)]
- `astreamer_verify.c:148` — `pfree(streamer)` is called on the base
  struct pointer, but the allocation was `palloc0_object(astreamer_verify)`
  — palloc tracks size, so this is correct. [verified-by-code]
- `astreamer_verify.c:165` — `MAXPGPATH` buffer for `pathname`; if a
  tablespace OID + member name overflows, `snprintf` truncates silently.
  Subsequent hash lookup would just miss. [verified-by-code]
- `astreamer_verify.c:386-389` — `(int) mystreamer->control_file_bytes`
  cast for `report_fatal_error` formatting; comment at 380-385
  acknowledges the truncation risk but accepts it for format-string
  parity with pg_rewind. [from-comment]
- `astreamer_verify.c:182-186` — `OidIsValid(tblspc_oid)` decides
  prefix; an attacker who crafted a tar with `tblspc_oid = 0` (the
  "InvalidOid" value commonly used for base) and member names like
  `../etc/passwd` would have `canonicalize_path` strip the `./` and
  then `..` resolution would land outside the backup. But since this
  path is only used for hash lookup (not for filesystem access in this
  streamer), it would just produce "file not in manifest" errors.
  Still worth noting. [ISSUE-security: path-traversal in tar member
  names not blocked, but not exploited here (nit)]
- `astreamer_verify.c:294-305` — `checksum_bytes != m->size` at
  trailer is unlikely "but let's check anyway"; if the tar parser
  delivered short content for a manifest-recorded size, this is the
  catch-net. [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_verifybackup`](../../../../issues/pg_verifybackup.md)
<!-- issues:auto:end -->
