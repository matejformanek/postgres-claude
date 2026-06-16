# `src/bin/pg_verifybackup/pg_verifybackup.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~111
- **Source:** `source/src/bin/pg_verifybackup/pg_verifybackup.h`

Shared types and helpers between `pg_verifybackup.c` and
`astreamer_verify.c`. Defines:

- `manifest_file` — one file as recorded in the manifest: pathname,
  size, checksum_type/length/payload, plus mutable `matched` and `bad`
  flags used during verification. [verified-by-code]
- The `manifest_files_*` simplehash (declared + defined here, with a
  custom raw allocator `pg_malloc0`). Key is `const char *`,
  hash is `hash_string`, equality is `strcmp`. [verified-by-code]
- `manifest_wal_range` — TLI + start/end LSN, doubly linked. The
  doubly-linked-list shape matters for `parse_required_wal`'s simple
  forward traversal. [verified-by-code]
- `manifest_data` — version, system_identifier, files hash,
  first/last WAL range pointers. [verified-by-code]
- `verifier_context` — manifest, backup_directory, ignore_list,
  format ('p' or 't'), skip_checksums flag, exit_on_error flag,
  saw_any_error flag. The "did we see any error" flag drives the
  process exit status. [verified-by-code]
- `should_verify_checksum(m)` macro — `m->matched && !m->bad &&
  m->checksum_type != CHECKSUM_TYPE_NONE`. [verified-by-code]

## API / entry points

- `extern void report_backup_error(verifier_context *context,
  const char *fmt, ...)` — log + mark error + maybe exit; the
  non-noreturn variant.
- `pg_noreturn extern void report_fatal_error(const char *fmt, ...)`
  — log + exit 1.
- `extern bool should_ignore_relpath(verifier_context *context,
  const char *relpath)` — used by both files and by
  `astreamer_verify`.
- `extern astreamer *astreamer_verify_content_new(astreamer *next,
  verifier_context *context, char *archive_name, Oid tblspc_oid)`
  — factory for the tar-content verifier in the streamer pipeline.

## Notable invariants / details

- `SH_PREFIX = manifest_files`, `SH_KEY_TYPE = const char *`, key
  comparison via strcmp. The simplehash insert returns an existing
  entry; duplicate insert is treated as a fatal manifest error
  upstream in `verifybackup_per_file_cb`. [verified-by-code]
- `SH_RAW_ALLOCATOR = pg_malloc0` because frontend code doesn't have
  palloc-context support for simplehash. [verified-by-code]
- The doubly-linked `manifest_wal_range` carries a `prev` pointer set
  on insert but never used in the verifier (forward-only traversal in
  `parse_required_wal`). Kept for future symmetric uses or backwards
  iteration. [verified-by-code] [ISSUE-stale-todo: prev pointer
  unused (nit)]
- The exit-on-error toggle is per-context, not per-call; once set it
  stays for the run. [verified-by-code]

## Potential issues

- `pg_verifybackup.h:32` — `const char *pathname` is owned by the JSON
  parser (it's the manifest line). Lifetime is from manifest parse to
  end of run; if the parser ever freed pathnames mid-run, the hash
  would dangle. Currently parser keeps them alive. [from-comment]
- `pg_verifybackup.h:99-101` — `report_backup_error` is declared with
  `pg_attribute_printf(2, 3)` but NOT `pg_noreturn`; the implementation
  may or may not exit depending on `context->exit_on_error`. Callers
  must not assume control transfer. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_verifybackup`](../../../../issues/pg_verifybackup.md)
<!-- issues:auto:end -->
