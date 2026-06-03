# server.c

## Purpose

Starts and stops the old and new postmasters under controlled
conditions (no TCP, restricted socket dir, fsync/full_page_writes off
on the new cluster), and provides the `PGconn *` helpers
`connectToServer` / `executeQueryOrDie` used by check.c / info.c /
function.c / version.c.

## Role in pg_upgrade

Called from `pg_upgrade.c::main()`:
1. `start_postmaster(&old_cluster, true)` — read schema/state.
2. `stop_postmaster(false)` after dump.
3. `start_postmaster(&new_cluster, true)` — restore + adjust catalogs.
4. `stop_postmaster(false)` at end.

`atexit(stop_postmaster_atexit)` (line 173, registered on first
`start_postmaster`) ensures the postmaster is stopped on abnormal
exit.

## Key functions

- `connectToServer(cluster, db_name)` `server.c:28` — wraps
  `get_db_conn` and immediately runs `ALWAYS_SECURE_SEARCH_PATH_SQL`
  (line 43). Fatal on `CONNECTION_BAD`.
- `get_db_conn(cluster, db_name)` `server.c:57` — builds a
  conninfo string via `appendPQExpBufferStr`/`appendConnStrVal`.
  Fields: `dbname`, `user` (from `os_info.user`), `port`, optional
  `host` (sockdir), optional `max_protocol_version=3.0` for pre-11
  clusters (via `protocol_negotiation_supported` in version.c).
- `cluster_conn_opts(cluster)` `server.c:94` — returns a STATIC buffer
  holding shell-quoted `--host '...' --port N --username '...'` for
  passing to psql/pg_dump/pg_dumpall command lines. **Not** reentrant.
  Uses `appendShellString` for sockdir + user.
- `executeQueryOrDie(conn, fmt, ...)` `server.c:124` — `vsnprintf`
  into a static `query[QUERY_ALLOC]` buffer, then `PQexec`. Static
  buffer means this is not reentrant either; not a problem in
  pg_upgrade's single-threaded flow.
- `start_postmaster(cluster, report_and_exit_on_error)` `server.c:161`
  — composes the `pg_ctl -w -l <serverlog> -D <pgdata> -o "..."
  start` command, hands it to `exec_prog`. Postgres-specific options
  set in `-o`:
  - `-p <port>` (line 212).
  - `-b` (no autovac, no logical-replication launcher).
  - `-c listen_addresses=''` + `-c unix_socket_permissions=0700`
    (line 182) — TCP off, restrictive socket perms.
  - `-c unix_socket_directories='<sockdir>'` (or
    `unix_socket_directory` pre-9.2; line 189).
  - For the new cluster only: `-c synchronous_commit=off -c fsync=off
    -c full_page_writes=off` (line 205).
  - `cluster->pgopts` from `--old-options/-o` / `--new-options/-O`
    appended raw.
- `stop_postmaster(in_atexit)` `server.c:294` — `pg_ctl -w -D
  <pgdata> -o "<pgopts>" -m fast/smart stop` via `exec_prog`. Uses
  `-m smart` on a clean shutdown so any in-flight pg_upgrade queries
  drain.
- `check_pghost_envvar()` `server.c:321` — refuses to run if `PGHOST`
  or `PGHOSTADDR` env vars point to a non-local host.

## State / globals

`os_info.running_cluster` (set when start succeeds; cleared on stop)
— used by the atexit hook to know which cluster to stop.
Static-buffer reentrancy hazards: `cluster_conn_opts` (line 96 static
`PQExpBuffer`), `executeQueryOrDie` (line 126 static `char query[]`).

## Phase D notes

[from-code] **No password handling.** `get_db_conn` does not loop on
`PQconnectionNeedsPassword`. Setup script must use trust auth on the
postmaster's `pg_hba.conf`, which is the documented prerequisite.
This also means there are no password strings to scrub from process
memory.

[from-code] **Postmaster lock-file races.** `start_postmaster` does
NOT explicitly check `postmaster.pid` before invoking pg_ctl. That
check happens earlier in `check.c::check_cluster_compatibility` via
`pid_lock_file_exists` (exec.c:234) which warns + tries to play the
WAL. By the time `start_postmaster` runs the pid file should be
gone, but pg_ctl itself will refuse if it still exists.

[from-code] **Sockdir choice** (line 188-191): version-conditional
GUC name (`unix_socket_directory` ≤ 9.2 vs `unix_socket_directories`
later). Sockdir comes from `option.c::adjust_data_dir` and is
typically `/tmp` or a user-specified `-s` path — embedded in the
single-quoted `-c GUC='value'` form. A sockdir containing `'`
characters would break out of the quoting. [ISSUE-shell-injection:
sockdir embedded in `-c unix_socket_directories='%s'` is single-quote-
wrapped without escaping (maybe-low)] — `server.c:189`. Sockdir is
caller-supplied via `-s`/`--socketdir` CLI flag, so this is a
self-injection vector only.

[from-code] **PGOPTIONS passthrough** — `cluster->pgopts` (from
`--old-options`/`--new-options` CLI flag) is interpolated raw at
line 217 into the `-o "..."` argument of pg_ctl. The double-quoted
context means embedded `"` would terminate the arg early; this is
documented as a CLI option for the user's own configuration tuning.

[ISSUE-info-disclosure: full pg_ctl command line including
pgoptions is logged via `exec_prog` → `pg_log(PG_VERBOSE, "%s",
cmd)` in exec.c:119 (low)] — Only when `-v`/`--verbose` set; goes to
stdout+log.

[from-code] **`check_pghost_envvar`** (line 321) enumerates libpq env
vars via `PQconndefaults()` to find PGHOST/PGHOSTADDR strings; any
non-local value is fatal. Defense against accidentally talking to a
remote server during upgrade (e.g. via PGSERVICE).

[ISSUE-trust-boundary: `executeQueryOrDie`'s error path
(`server.c:141`) pg_log's `PQerrorMessage(conn)` to stdout — server
error text leaks to terminal/log (maybe-low for secret-scrub)] —
Standard libpq behavior; not unique to pg_upgrade.

[ISSUE-state-transition: if `start_postmaster` returns success but
the connection check immediately after (line 259) fails, we
`pg_fatal` while the postmaster is still alive. The atexit hook
(set at line 173) will eventually run and shut it down, so no leak
(verified)] — `os_info.running_cluster` is set BEFORE the
connectivity check (line 251), so the hook covers this window.
