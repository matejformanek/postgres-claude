# pg_basebackup.c

## Purpose

The pg_basebackup tool — takes a base backup of a running PostgreSQL
cluster over the replication protocol (`BASE_BACKUP` command) and
writes it locally as either a plain extracted directory tree
(`--format=plain`, default) or as one tar per tablespace
(`--format=tar`). Optionally streams WAL in parallel via a forked
background process and can rewrite the output to be ready for
standby recovery (`-R`).

## Role in pg_basebackup pipeline

The orchestrator. Layout of responsibility:

- **`main()`** (line 2343) — parse args, validate, set up
  `cleanup_directories_atexit`, set umask, verify output dir, optionally
  create pg_wal symlink, call `BaseBackup()`.
- **`BaseBackup()`** (line 1740) — issue `BASE_BACKUP` SQL command to
  the server, fork the bg-WAL streamer, drive the COPY stream, write
  `backup_manifest`, durably rename, sync.
- **`StartLogStreamer()`** (line 616) — fork()s a child that runs
  `LogStreamerMain` → `ReceiveXlogStream` from receivelog.c with its own
  PGconn.
- **`CreateBackupStreamer()`** (line 1063) — assembles the astreamer
  pipeline for one archive (tablespace/main): writer → optional
  manifest-injector → optional recovery-injector → tar-parser → optional
  tar-archiver → optional decompressor. The pipeline is built in REVERSE
  order — outermost wrapped around innermost.

## Wire/protocol surface

Two server protocols:

1. **`BASE_BACKUP`** replication command. The server responds with:
   - First result: `(lsn, tli)` row — starting position.
   - Second result: per-tablespace metadata `(oid, location, size_kb)`.
   - Then either:
     - One CopyOut stream containing typed messages: `'n'` (new
       archive), `'d'` (data — `PqMsg_CopyData`), `'p'`
       (progress report), `'m'` (manifest) — parsed by
       `ReceiveArchiveStreamChunk` at line 1320 (v15+ protocol).
     - One tar CopyOut per tablespace plus an optional manifest
       CopyOut (legacy pre-v15 protocol).
   - Final result: `(end_lsn)` row.

2. **`START_REPLICATION`** — handled by receivelog.c via the bg child.

## Key functions

- `tablespace_list_append(arg)` line 321 — parses `-T OLDDIR=NEWDIR`
  with backslash escape for `=`. `pg_fatal` on bad input. Calls
  `canonicalize_path` on both halves.
- `verify_dir_is_empty_or_create(dirname, ...)` line 749 — wraps
  `pg_check_dir`. `pg_fatal` if exists-and-nonempty. Used for
  the data dir, the optional waldir, and each tablespace target dir.
- `CreateBackupStreamer(archive_name, spclocation, ...)` line 1063 —
  the streamer-chain builder. Critical decision tree:
  - `format == 'p'` → must parse → use `astreamer_extractor_new`
    (line 1151) — extracts tar into directory via
    `get_tablespace_mapping` callback.
  - `format == 't'` → write to `archive_filename` (or stdout if
    `basedir == "-"`); chain a compressor for client-side gzip / lz4 /
    zstd.
  - If `must_parse_archive` (= plain, or `inject_manifest`, or
    `spclocation==NULL && writerecoveryconf`) → prepend tar-parser. If
    target-format is tar, also prepend `astreamer_tar_archiver`.
  - For server-compressed tar in plain output: insert appropriate
    decompressor (lines 1252-1260).
- `ReceiveArchiveStream / ReceiveArchiveStreamChunk` (lines 1272, 1320)
  — v15+ COPY-CopyData dispatcher; runs `CreateBackupStreamer` per new
  archive marker, buffers or files-out the manifest.
- `ReceiveTarFile / ReceiveTarCopyChunk` (lines 1587, 1650) — pre-v15
  one-tar-per-tablespace path.
- `BaseBackup` line 1740 — the choreography: version checks, options
  build, `UPLOAD_MANIFEST` (incremental backup), `BASE_BACKUP` send,
  per-tablespace receive, manifest receive, end-LSN handshake with bg
  child via `bgpipe[1]`, `sync_pgdata` / `sync_dir_recurse`,
  `durable_rename(backup_manifest.tmp → backup_manifest)`.
- `LogStreamerMain` line 545 — forked child entry; creates
  `WalDirectoryMethod` (plain) or `WalTarMethod` (tar) and runs
  `ReceiveXlogStream`.
- `GetCopyDataString / GetCopyDataByte / GetCopyDataUInt64 /
  GetCopyDataEnd` (lines 1503-1561) — the in-message cursor primitives.
  Each one calls `ReportCopyDataParseError` (line 1571) → `pg_fatal`
  on bounds-check failure.
- `cleanup_directories_atexit` line 237 — on failure (`!success`), if
  not `--no-clean` and not a checksum error, `rmtree`s any directories
  we created or filled.

## State / globals

Huge global block at lines 131-195:

- Option globals: `basedir`, `format`, `label`, `tablespace_dirs`,
  `xlog_dir`, `writerecoveryconf`, `do_sync`, `maxrate`,
  `replication_slot`, `temp_replication_slot`, `backup_target`,
  `create_slot`, `no_slot`, `verify_checksums`, `manifest`,
  `manifest_force_encode`, `manifest_checksums`, `sync_method`.
- State: `success`, `made_new_pgdata`, `found_existing_pgdata`,
  `made_new_xlogdir`, `found_existing_xlogdir`,
  `made_tablespace_dirs`, `found_tablespace_dirs`,
  `checksum_failure`.
- BG handoff: `bgpipe[2]`, `bgchild`, `in_log_streamer`,
  `bgchild_exited` (sig_atomic_t), `xlogendptr`, `has_xlogendptr`.
- `recoveryconfcontents` (PQExpBuffer) — generated by
  `GenerateRecoveryConfig` (fe_utils/recovery_gen.c), passed into
  `astreamer_recovery_injector_new`.

## Phase D notes

[ISSUE-trust-boundary: server-controlled archive_name only sanitized for
empty / starts-with-dot / slash / backslash (path-traversal, low)] —
`ReceiveArchiveStreamChunk` line 1357: `if (archive_name[0] == '\0' ||
archive_name[0] == '.' || strchr(archive_name, '/') != NULL ||
strchr(archive_name, '\\') != NULL) pg_fatal(...)`. That covers leading-
dot files (no `.foo`), explicit `..`, both `/` and `\` path
separators. Does NOT block embedded NULs (string is already
NUL-terminated by `GetCopyDataString`), embedded control chars, or
overly-long names (MAXPGPATH check is implicit via the
`archive_filename` snprintf truncation at line 1173).
[verified-by-code]

[ISSUE-trust-boundary: server-controlled `spclocation` becomes an output
directory after `get_tablespace_mapping` is applied (path-traversal,
maybe)] — Line 1145-1150: if `spclocation == NULL` → write to
`basedir`. If not absolute → write to `basedir/spclocation` (line
1148). If absolute → run through user-supplied -T mapping table; if
no match, write to the server-supplied path AS-IS. A compromised
server can therefore name absolute paths like `/etc` and pg_basebackup
will `verify_dir_is_empty_or_create` them (line 2071) and then extract
into them. The user's `-T` is the only filter, and not having
a matching mapping is silent fall-through, not refusal. Mitigation:
the running user's filesystem permissions. [verified-by-code]

[ISSUE-trust-boundary: tar-parser depends on `astreamer_tar_parser`
honoring tar member-name sanitization; not done in pg_basebackup.c
itself (tar-parsing, see fe_utils/astreamer_tar.c)] — Inside the tar
parser, member names could include `..` or absolute paths. The
`astreamer_extractor` (called only in plain format) is responsible
for refusing those. This file's only check is on archive_name (the
outer wrapper), not on tar members. Cross-file analysis required.
[unverified — punt to fe_utils/astreamer_tar.c review]

[ISSUE-trust-boundary: server-driven progress messages contain a
uint64 totaldone (line 1444) and the server alone decides the
totalsize for percentage (line 2047, atoll of server response)
(dos, low)] — Untrusted ratios; worst case progress display jumps
or wraps. No file is created from this. [verified-by-code]

[ISSUE-state-transition: bgchild atexit can race with bgpipe write
in main process — on rare path SIGCHLD fires after we wrote
xlogend (state-transition, low)] — `bgchild_exited` is
sig_atomic_t; main checks `if (bgchild > 0)` then writes pipe at
line 2226. If bgchild already exited between the check and the
write, `write` returns EPIPE → pg_fatal. So race is fail-fast not
data-loss. [verified-by-code]

[ISSUE-state-transition: pg_wal symlink created BEFORE BaseBackup
runs (line 2858) so server failure during BASE_BACKUP leaves an
orphan symlink in the data dir; cleanup_directories_atexit removes
it via rmtree (path-traversal, low)] — `symlink(xlog_dir, linkloc)`.
If xlog_dir was a relative path or a path the attacker controls,
they could indirectly write to that location via the bg-WAL
receiver. `is_absolute_path` is NOT checked for `--waldir` in this
file (search for `xlog_dir` shows no validation). [verified-by-code]

[ISSUE-stale-todo: the "FIXME: we might send it ok, but get an error"
comment on the TIMELINE_HISTORY error path lives in `receivelog.c:541`,
NOT this file — mis-cited as pg_basebackup.c:542 at seed (2026-06-03).
No FIXME exists in pg_basebackup.c at seed anchor 4b0bf0788b0 or at
current. Re-anchored to receivelog.c:541 and its per-file doc on
2026-07-04.] [verified-by-code]

[ISSUE-tar-parsing: 8 GiB tar member size cap inherited from the
ustar header. Per-tablespace tar at format=t can exceed this if a
single tablespace contains a > 8 GiB file (tar-parsing, maybe)] —
Same class as A3's pg_dump finding. pg_basebackup's tar writer is
`astreamer_tar_archiver` (fe_utils), not walmethods.c's tar method.
Cross-file. [punt to fe_utils review]

[ISSUE-dos: server-compressed tar with client-side extraction passes
through `astreamer_*_decompressor_new` (lines 1254-1259) with no
ratio cap (dos, maybe)] — Compression-bomb risk: server sends a
small compressed stream that decompresses to terabytes. The
extractor writes to disk per member, so `ENOSPC` would eventually
stop us — but only after disk fills. [inferred]

[ISSUE-secret-scrub: `recoveryconfcontents` (PQExpBuffer) contains
the publisher connection string with embedded password (if any)
and is destroyed via `destroyPQExpBuffer` (line 2271) without
explicit_bzero (secret-scrub, low)] — `GenerateRecoveryConfig`
builds primary_conninfo that may include `password=...` from the
caller's command-line connection options. PQExpBuffer free path
just `pfree`s the data. [verified-by-code]

`umask(pg_mode_mask)` at line 2825 IS called after `GetConnection()`
populates the mask from server's `data_directory_mode`. So all
files created downstream inherit the server's data-dir mode. See
streamutil.c finding about trusting that value. [verified-by-code]

`atexit(cleanup_directories_atexit)` registered BEFORE arg parse
(line 2411) so even argument-parsing exit paths clean up. Sets
`success = true` only at the bottom of `main()` (line 2866).
[verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_basebackup`](../../../../issues/pg_basebackup.md)
<!-- issues:auto:end -->
