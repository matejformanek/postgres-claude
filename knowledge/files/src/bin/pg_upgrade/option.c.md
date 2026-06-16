# option.c

## Purpose

CLI option parsing for pg_upgrade. Five public entry points:
`parseCommandLine`, `adjust_data_dir`, `get_sock_dir`, and the
static `usage` and `check_required_directory`. ~550 lines, almost
entirely getopt_long boilerplate plus directory-resolution helpers.

## Role in pg_upgrade

First thing `main()` calls after `pg_logging_init`. Populates the
two `ClusterInfo` globals' early fields (`bindir`, `pgdata`,
`pgopts`, `port`) and the `user_opts` and `os_info` globals.
`adjust_data_dir` runs later (during `main`) to resolve a
config-only directory to the real data dir by exec'ing `postgres
-C data_directory`. `get_sock_dir` runs after
`check_cluster_versions` to pick the unix-socket directory.

## Key functions

- `parseCommandLine(argc, argv)` line 39 — the getopt_long loop.
  Long options table at lines 41-67. Short opts:
  `"b:B:cd:D:j:kNo:O:p:P:rs:U:v"`. Stores into `user_opts`,
  `old_cluster.*`, `new_cluster.*`, `log_opts`, `os_info`.

  Notable cases:
  - `-o` / `-O` (lines 149, 162) — APPEND to `old_pgopts` /
    `new_pgopts` via `psprintf("%s %s", old, new)`. Repeated `-o`
    accumulates. The string is later interpolated into pg_ctl
    `-o "..."`.
  - `-p` / `-P` (lines 175, 180) — port number via `atoi`; rejects
    `<= 0`.
  - `-U` (line 193) — overrides OS-derived user, sets
    `os_info.user_specified = true` for banner emission.
  - `--clone` / `--copy` / `--copy-file-range` / `--link` / `--swap`
    — all stored into `user_opts.transfer_mode` (mutually
    exclusive by last-wins semantics).
  - `--set-char-signedness signed|unsigned` (line 224) —
    `pg_strcasecmp`; everything else `pg_fatal`s.
  - `--sync-method` (line 214) — delegates validation to
    `parse_sync_method` (fe_utils/option_utils).
- `check_required_directory(dirpath, envVarName, useCwd,
  cmdLineOption, description, missingOk)` line 384 — falls through
  CLI → env → cwd → missingOk → `pg_fatal`. After resolution calls
  `canonicalize_path` to trim trailing separators (path is used as
  prefix for snprintf later).
- `adjust_data_dir(cluster)` line 429 — handles "config-only"
  directory layout (Debian-style separate config dir). Detection:
  `postgresql.conf` present AND `PG_VERSION` absent. If matched,
  popen()s `"%s/postgres" -D "%s" -C data_directory` and uses the
  first line of output as the real pgdata. `MAX_STRING=1024` buffer.
- `get_sock_dir(cluster)` line 499 — pre-Win32. In live_check mode
  on the old cluster, parses the live `postmaster.pid` to extract
  the listening port (LOCK_FILE_LINE_PORT) and unix-socket dir
  (LOCK_FILE_LINE_SOCKET_DIR) from the running postmaster — this
  can OVERWRITE the user-supplied old port and log a warning. On
  Win32, sockdir is unconditionally NULL.

## State / globals

- `user_opts` — defined here at line 30.
- `os_info.user`, `os_info.user_specified`, `os_info.progname` —
  populated during parse.
- `old_cluster.port`, `new_cluster.port` — defaulted from
  `PGPORTOLD`/`PGPORTNEW` env vars at lines 82-83.

## Environment variables

Read inside `parseCommandLine`:
- `PGPORTOLD` / `PGPORTNEW` — old/new cluster port defaults.
- `PGUSER` — overrides OS-derived user.
- `PGOPTIONS` — line 256: prefixed with
  `"-c default_transaction_read_only=false"` and re-set into the
  process env so all libpq connections suppress read-only.
- `PGBINOLD` / `PGBINNEW` / `PGDATAOLD` / `PGDATANEW` /
  `PGSOCKETDIR` — fallback values for the corresponding CLI flags
  (lines 268-277).

`check_pghost_envvar` (declared in pg_upgrade.h, lives in server.c)
is called separately from `main()->setup()` to clear `PGHOST` /
`PGHOSTADDR` / `PGPORT` from the env so libpq doesn't accidentally
target a third cluster.

## Phase D notes

[ISSUE-shell-injection: `-o` / `-O` accept arbitrary strings stored
in `old_pgopts` / `new_pgopts` and later spliced into pg_ctl `-o "%s"`
inside server.c::start_postmaster (medium)] — Operator footgun:
`pg_upgrade -o '-c shared_preload_libraries=evil.so'` is intended
behaviour. `pg_upgrade -o '"; touch /tmp/pwned; #'` is the same
footgun in shell-metachar form. Not exploitable across a trust
boundary since the caller of pg_upgrade is the operator; flag for
posterity.

[ISSUE-info-disclosure: `PGOPTIONS` env var is set into the process
env (line 261) and inherited by all subprocesses including
pg_ctl/psql/pg_restore/pg_dump (low)] — Includes whatever the user
had in PGOPTIONS prepended with the
`default_transaction_read_only=false` injection. If a user had
`PGOPTIONS=-c password=foo` (no PG option actually takes that, but
illustrating) it would leak into all child process command lines.
Not a real PG threat model but worth knowing.

[ISSUE-trust-boundary: `adjust_data_dir` (line 429) runs `postgres
-C data_directory` from `cluster->bindir` (low)] — `bindir` is
operator-controlled. The exec'd `postgres` binary then reads
`cluster->pgconfig/postgresql.conf` (also operator-controlled). If
either is from an untrusted source the operator was already
compromised. Standard trust posture.

[ISSUE-undocumented-invariant: `get_sock_dir` parses the live
`postmaster.pid` and may OVERWRITE the user-supplied
`old_cluster.port` (line 531) without checking that the new value
makes sense (low)] — A weird `postmaster.pid` (corrupt, attacker-
written) on the old cluster would silently change the port
pg_upgrade tries to connect to.

[ISSUE-correctness: `atoi(getenv("PGPORTOLD"))` at line 82 has no
error checking — non-numeric env value → 0, then the `-p` switch's
`<= 0` check happens only if user passes `-p`, not for the env
default (low)] — `start_postmaster` will fail later, but the
diagnostics will say "port 0", not "your env var is malformed."

[ISSUE-undocumented-invariant: `os_info.user` is allocated and
later transitively interpolated into `EXEC_PSQL_ARGS` /
`cluster_conn_opts` SQL contexts; checked-for-shell-quoting elsewhere
but not validated here for control characters (low)] —
`check_old_cluster_global_names` enforces no `\n` / `\r` in role
names (PG ≥19) but pg_upgrade itself doesn't sanitize what came
out of `-U` or `PGUSER`.

## Potential issues

[ISSUE-stale-todo: `FIX_DEFAULT_READ_ONLY` (line 27) is unconditionally
injected even when neither cluster has
`default_transaction_read_only=on` — wasteful but harmless] —
Defensible because pg_upgrade can't know the old cluster's setting
until it connects.

[ISSUE-dead-code: Windows-only block at lines 286-298 forbids
running pg_upgrade from inside the new cluster's data directory] —
Specific to `initdb --sync-only` lockfile race; possibly resolvable
with a smarter sync.

[ISSUE-correctness: pre-getopt early "--help" / "--version" handling
at lines 96-105 — happens BEFORE the `os_user_effective_id == 0`
root check (line 109), as the comment notes. Means root-running
get errors LATE not early. The comment is the only documentation of
the intentional ordering.]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
