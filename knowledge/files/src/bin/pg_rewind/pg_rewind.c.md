# pg_rewind.c

**Source:** `source/src/bin/pg_rewind/pg_rewind.c` (1216 lines)

## Purpose

Top-level driver for `pg_rewind`. Resynchronizes a target PostgreSQL
data directory with a (diverged) source by:

1. Parsing options, choosing source (libpq vs local).
2. Reading both control files; ensuring target was cleanly shut down
   (optionally invoking single-user `postgres` in recovery mode).
3. Finding the common-ancestor timeline and the divergence LSN.
4. Reading target WAL from the last common checkpoint to extract the
   set of changed blocks.
5. Asking `filemap.c` to decide a per-file action.
6. Executing the actions (the "point of no return") against the
   target — copying / truncating / removing files and writing a
   `backup_label` plus a rewritten `pg_control`.

Header file: `pg_rewind.h` (54 lines). [verified-by-code]

## Role in pg_rewind

`pg_rewind.c` is the orchestration spine — every other source file
(`filemap.c`, `parsexlog.c`, `timeline.c`, `libpq_source.c`,
`local_source.c`, `file_ops.c`) is a service called from here. The
trust boundary is established in `main()` at line 311 with
`PQconnectdb(connstr_source)` and never re-validated thereafter: the
`source` vtable is used to fetch a control file (line 349), traverse
files (line 484), and stream chunks from `perform_rewind()`.

## Key functions

- `main(argc, argv)` — `pg_rewind.c:120-555`. Argument parsing,
  root-check (`geteuid() == 0` rejected, `pg_rewind.c:281`), umask
  setup, source-vtable selection, control-file digest of both sides,
  timeline diff, WAL parse, action decision, `perform_rewind()`,
  `sync_target_dir()`, optional `WriteRecoveryConfig()`.
  [verified-by-code]
- `perform_rewind(filemap, source, chkptrec, chkpttli, chkptredo)` —
  `pg_rewind.c:563-741`. The "point of no return". For each entry:
  - If `target_pages_to_overwrite` bitmap is non-empty, queue a
    BLCKSZ range fetch per dirty block (lines 588-601).
  - Dispatch on `entry->action`: NONE / COPY (queue full-file) /
    TRUNCATE (`truncate_target_file`) / COPY_TAIL (queue range from
    target_size to source_size) / REMOVE (`remove_target`) / CREATE
    (`create_target`) / UNDECIDED (fatal).
  - `source->finish_fetch()` drains queued requests.
  - Re-fetches `XLOG_CONTROL_FILE` from the source **after** all
    other I/O, into `ControlFile_source_after`, so
    `minRecoveryPoint` is up-to-date (lines 645-650).
  - Sanity: if source was local, fail if `pg_control` changed mid-run
    (lines 660-665). The XXX comment admits this is asymmetric vs.
    the libpq case.
  - Writes a fresh `backup_label` via `createBackupLabel()`.
  - Computes `endrec`/`endtli` for the new `pg_control`:
    standby → `minRecoveryPoint`; production → live
    `pg_current_wal_insert_lsn()`; local source → checkpoint.
  - `update_controlfile()` writes the rewritten control file with
    `state = DB_IN_ARCHIVE_RECOVERY`.
  [verified-by-code]
- `sanityChecks()` — `pg_rewind.c:743-790`. system_identifier match,
  pg_control version match, checksums OR `wal_log_hints`, target
  must be `DB_SHUTDOWNED` or `DB_SHUTDOWNED_IN_RECOVERY`, local
  source must also be shut down. NOTE: `backup_label` presence is
  a `TODO` (line 748). [verified-by-code]
- `findCommonAncestorTimeline()` — `pg_rewind.c:929-964`. Linear
  scan over the two history arrays; bails out at first
  `tli`-or-`begin` mismatch. [verified-by-code]
- `createBackupLabel()` — `pg_rewind.c:971-1009`. Writes a synthetic
  `backup_label` with `BACKUP METHOD: pg_rewind`,
  `BACKUP FROM: standby`. NOTE: the LABEL line is intentionally
  omitted (line 1000). The buffer is 1000 bytes and `pg_fatal`s on
  overflow. [verified-by-code]
- `digestControlFile()` — `pg_rewind.c:1033-1058`. Validates
  control-file size, copies into a `ControlFileData`, sets
  `WalSegSz` global, validates it via `IsValidWalSegSize`, then runs
  `checkControlFile()` which verifies the CRC32C. [verified-by-code]
- `getRestoreCommand(argv0)` — `pg_rewind.c:1066-1132`. Builds a
  shell command like `"<postgres> -D <datadir> -C restore_command"`
  using `appendShellString()` (proper quoting), invokes via
  `pipe_read_line()`, strips CRLF. Empty result is fatal.
  [verified-by-code]
- `ensureCleanShutdown(argv0)` — `pg_rewind.c:1139-1208`. Locates
  the matching `postgres` binary via `find_other_exec`, then
  `system()`-invokes it in single-user mode with stdin redirected
  from `/dev/null` so it does crash recovery and exits.
  [verified-by-code]
- `getTimelineHistory(tli, is_source, *nentries)` —
  `pg_rewind.c:866-921`. Reads timeline-history file via the source
  vtable or from local target, parses via
  `rewind_parseTimeLineHistory()`. [verified-by-code]
- `progress_report(finished)` — rate-limited to once per second
  unless `finished`. [verified-by-code]
- `disconnect_atexit()` — `PQfinish(conn)` on exit. [verified-by-code]

## State / globals

- `datadir_target` (extern in `pg_rewind.h`), `datadir_source` /
  `connstr_source` (static here). [verified-by-code]
- `ControlFile_target`, `ControlFile_source`,
  `ControlFile_source_after` — three full control-file copies.
- `conn` (static `PGconn *`) — the source connection.
- `source` (static `rewind_source *`) — the active source vtable.
- `restore_command` (static `char *`) — populated by
  `getRestoreCommand()` only when `--restore-target-wal`.
- `restore_wal`, `no_ensure_shutdown`, `writerecoveryconf`,
  `config_file`, `debug` — option flags.
- `targetHistory` / `targetNentries` — exported through `pg_rewind.h`
  so `parsexlog.c` can interpret timeline IDs while reading WAL.

## Phase D notes

**Source-trust shape (compared to A4 `pg_basebackup`):** very similar
in spirit but the wire format is **different** and arguably more
trusting in some ways and less trusting in others.

- pg_basebackup receives a tar stream the server constructs (file
  paths + sizes + modes); pg_rewind receives a server-side **SQL
  result set** built by `pg_ls_dir()` + `pg_stat_file()` +
  `pg_read_binary_file()` (see `libpq_source.c`). The trust shape is
  the same: server-named paths, server-claimed sizes, server-supplied
  bytes — all written into the target datadir.
- pg_rewind does NOT honor server-supplied file modes (it always
  uses `pg_file_create_mode` from `umask(pg_mode_mask)` at line 297).
  This is a hardening difference vs `pg_basebackup` which honors
  server-supplied modes in tar headers.
- pg_rewind DOES honor server-supplied symlink targets in
  `pg_tblspc/*` (the libpq SQL pulls `pg_tablespace_location()`); the
  target of `symlink()` is unvalidated server bytes
  (`file_ops.c:285`).

**No `simple_prompt()` callsite.** `connstr_source` is passed
straight to `PQconnectdb` at line 311. Password handling is whatever
libpq normally does (`PGPASSWORD`, `~/.pgpass`, interactive only via
the underlying libpq prompt if the connection string mandates one).
The connection string is then later passed through
`GetDbnameFromConnectionOptions(connstr_source)` and used by
`GenerateRecoveryConfig(conn, NULL, ...)` to write `primary_conninfo`
— so a password embedded in `connstr_source` could end up in the
recovery config file unless `GenerateRecoveryConfig` scrubs it.

**`--no-ensure-shutdown`** skips the single-user-mode crash-recovery
step (line 338-347). If the user passes this and the target was not
cleanly shut down, the subsequent `sanityChecks()` will fail with
"target server must be shut down cleanly" (line 779). So the option
is mostly a "trust me, I already ran crash recovery" knob, not a
silent corruption vector.

**Crash mid-rewind = inconsistent target.** Line 531 comment ("This
is the point of no return.") is honest: there is no rewind marker
file. If pg_rewind is killed between (a) the first overwriting write
and (b) the final `update_controlfile()`, the target has an arbitrary
mix of old + new bytes and `pg_control.state` is still
`DB_SHUTDOWNED` or `DB_SHUTDOWNED_IN_RECOVERY`. Re-running pg_rewind
might fix it; running `postgres` on it will likely corrupt further.

**Local-source modification check is asymmetric.** Line 656-665
fatals if the local source's `pg_control` changed between start and
end, but allows arbitrary file changes during the run. The XXX
comment ("the logic handles a libpq source that's modified
concurrently, why not a local datadir?") acknowledges the asymmetry.

**`getRestoreCommand` runs `postgres -C`.** This shells out to the
locally-installed `postgres` binary; if a malicious target datadir
contains a `postgresql.conf` with command injection in
`restore_command`, the value comes back through `pipe_read_line()`
and is then later passed to `parsexlog.c` `XLogReader` as the
restore command. The injection would have already required write
access to the target datadir, but it widens the blast radius.

**Logical decoding slots:** `filemap.c` excludes the entire
`pg_replslot/` directory from both source and target (see
`excludeDirContents[]` at filemap.c:130). After a rewind the user
must re-create slots manually; this is documented behavior, not a
bug.

## Potential issues

- `[ISSUE-state-transition: no marker file or atomic switch; a crash between first overwrite and final update_controlfile() leaves the target in an inconsistent state with pg_control still claiming a clean shutdown (medium)]`
- `[ISSUE-secret-scrub: connstr_source (which may contain password=...) is held in memory the entire run and is passed verbatim to GetDbnameFromConnectionOptions and may end up in primary_conninfo via GenerateRecoveryConfig. No explicit scrub or warn-on-cleartext (maybe)]`
- `[ISSUE-trust-boundary: local-source pg_control change is fatal, but mid-run modification of any other local-source file is silently tolerated (filemap was built from a stale snapshot). The XXX at pg_rewind.c:656-659 acknowledges this (low)]`
- `[ISSUE-stale-todo: pg_rewind.c:748 "TODO Check that there's no backup_label in either cluster" — sanityChecks does not check despite the comment; filemap.c excludeFiles only suppresses copying not the existence-check (low)]`
- `[ISSUE-undocumented-invariant: ensureCleanShutdown invokes postgres in single-user mode by passing template1 on stdin via /dev/null; if the cluster has a custom locale or auth that makes single-user fail, the failure path exits with a generic error and the user must retry with --no-ensure-shutdown (low)]`
- `[ISSUE-wire-protocol: pg_current_wal_insert_lsn() is read after copying files for a live primary, so the target replays past that LSN. If the source crashes between the file copy and this query, pg_rewind aborts; if the source advances WAL by a record between the file copy and this query that touches files we already copied, those changes are caught only by WAL replay (assumed full_page_writes=on, checked at libpq_source.c:139-141) (low)]`
- `[ISSUE-trust-boundary: server-controlled symlink target (source_link_target) flows into symlink(2) at file_ops.c:285 with no validation that the target is absolute, points outside the data dir, or is not a relative path that escapes via .. (low)]`
- `[ISSUE-dead-code: createBackupLabel deliberately omits the LABEL: line (pg_rewind.c:1000 comment "omit LABEL: line"). This may confuse tools that parse backup_label expecting a LABEL line (low)]`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Bump CATALOG_VERSION_NO](../../../../scenarios/bump-catversion.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_rewind`](../../../../issues/pg_rewind.md)
<!-- issues:auto:end -->
