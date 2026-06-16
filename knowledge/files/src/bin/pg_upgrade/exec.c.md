# exec.c

## Purpose

Subprocess shell for pg_upgrade. Centralizes every external-program
invocation through `exec_prog()` (logs the command, runs it via
`system(3)`, captures stdout+stderr to a per-call log file) and
verifies that the requested old/new bindir contains the binaries
pg_upgrade needs at the expected major version.

## Role in pg_upgrade

Sits beneath `server.c` (start/stop postmaster), `dump.c` (dump
pg_dumpall/pg_dump), `parallel.c` (`parallel_exec_prog` ultimately
calls `exec_prog` in the child), and the various per-version helpers.
Called once at top of `pg_upgrade.c:main()` via `verify_directories()`.

## Key functions

- `get_bin_version(cluster)` `exec.c:34` — runs `"<bindir>/pg_ctl"
  --version` via `popen("r")`, parses `%*s %*s %d.%d`, stores
  `cluster->bin_version` as `v1*10000 + v2*100` (pre-10) or
  `v1*10000` (10+).
- `exec_prog(log_filename, opt_log_file, report_error, exit_on_error,
  fmt, ...)` `exec.c:86` — THE command runner. Format-prints into a
  fixed 2*MAXPGPATH buffer, appends ` >> "<log_file>" 2>&1`, logs
  `"command: %s"` to the log file then calls `system(cmd)`.
- `pid_lock_file_exists(datadir)` `exec.c:234` — `open(<datadir>/
  postmaster.pid, O_RDONLY)`; tolerates ENOENT/ENOTDIR.
- `verify_directories()` `exec.c:264` — POSIX `access(".", R|W|X)`
  test for current dir then calls `check_bin_dir` + `check_data_dir`
  for both clusters.
- `check_data_dir(cluster)` `exec.c:342` — `stat()` of `base/`,
  `global/`, `pg_multixact/`, `pg_subtrans/`, `PG_TBLSPC_DIR`,
  `pg_twophase`, version-conditional `pg_xlog`/`pg_wal` and
  `pg_clog`/`pg_xact`.
- `check_bin_dir(cluster, check_versions)` `exec.c:384` — `stat()` +
  per-binary `check_exec` calls for postgres, pg_controldata, pg_ctl,
  pg_resetwal (pre-10: pg_resetxlog); plus for the new cluster:
  initdb, pg_dump, pg_dumpall, pg_restore, psql, vacuumdb.
- `check_exec(dir, program, check_version)` `exec.c:430` — `validate_exec`
  + `pipe_read_line("<path> -V")` + string-equality check of the
  version banner against `"<prog> (PostgreSQL) " PG_VERSION`.

## Shell-injection surface

The format string in `exec_prog` is built by *callers* — every caller
in the tree (dump.c, server.c, function.c, check.c, …) passes a
`printf` template. The dangerous arguments are:

- `bindir` (from `-b`/`-B` CLI option, NOT user-controllable at run
  time once pg_upgrade starts). Quoted as `\"%s/<prog>\"`.
- `pgdata` (from `-d`/`-D` CLI option). Same quoting.
- `sockdir` (computed `/tmp/...`).
- `db_name` (from old cluster's `pg_database`) — caller in dump.c
  passes it through `appendShellString` (see dump.c).
- log file path is interpolated with `\"%s\"` quoting; if `log_opts.
  logdir` contained a `"` character it would corrupt the redirect.
  But logdir is auto-created under `pg_upgrade_output.d/` and not
  user-supplied as a path.

## State / globals

Static `mainThreadId` (Windows-only, line 99) — tracks which thread
gets the "print command before output" path. No other state.

## Phase D notes

[from-code] **No `execve`-style argv array.** Every external call goes
through `system(3)`, so quoting bugs in the format strings ARE
shell-injection bugs. The defense is that every caller using
user-supplied strings runs them through `appendShellString` first
(verified by inspection of dump.c, server.c, parallel.c calls).

[from-code] **Buffer cap is MAXCMDLEN = 2 * MAXPGPATH** (line 93).
`pg_fatal("command too long")` if exceeded. This is at line 113 and
117. Means a multi-page connect string from `cluster_conn_opts` plus
the per-call extras can still hit the cap if path lengths are near
MAXPGPATH; truncation is detected.

[from-code] **stderr is merged into the log file via `2>&1`** (line
115). Errors from pg_dump, pg_ctl, psql etc. all flow into per-call
log files under `log_opts.logdir`. The log file itself is opened with
`fopen(log_file, "a")` line 139, no privilege-drop. If a malicious
old cluster causes pg_dump to emit secrets in stderr, those will sit
in the upgrade log.

[ISSUE-shell-injection: `system(cmd)` with caller-built format
strings (mitigated by callers using `appendShellString` (maybe-low))]
— `exec.c:187`. Audit invariant: every `exec_prog`/`parallel_exec_prog`
caller that interpolates non-CLI-frozen data must shell-escape it.
Checked sites: dump.c (db_name shell-escaped), server.c (sockdir +
user shell-escaped via cluster_conn_opts), function.c (no exec_prog
calls), check.c (numerous; would need a separate audit).

[ISSUE-secret-scrub: stderr from pg_dump/psql captured to log file is
never scrubbed (maybe-medium)] — `exec.c:115` builds `>> "<log>" 2>&1`.
pg_dump's connection-error messages can include connection strings
(host/user/dbname). Log files persist under `log_opts.logdir` after a
failed run unless `cleanup_output_dirs()` (util.c:63) runs.

[ISSUE-info-disclosure: pg_log(PG_VERBOSE, "%s", cmd) on line 119
prints the full command line including any libpq env-var pass-through
to stdout when -v is set (maybe-low)] — Not normally enabled.

[from-code] **Windows special-case** (lines 121-167, 209-222) — log
file is closed before `system()` to avoid share violations; retries
opening with up to 4× 1s sleeps if pg_ctl-start kept it open.

[ISSUE-correctness: `popen()` return-status check in `get_bin_version`
only catches non-zero exit, not signals (maybe-low)] — `exec.c:50`
uses `pclose(output)` then `wait_result_to_str(rc)` for the error
message; rc != 0 covers signaled child but a SIGPIPE during fgets
won't reach this check.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
