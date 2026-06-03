# dump.c

## Purpose

Invokes `pg_dumpall --globals-only` to capture roles/tablespaces from
the old cluster, then `pg_dump --format=custom --binary-upgrade` per
user database for schema (and statistics) migration. All dumps are
read back by `pg_restore` in `restore_schema()` (see `pg_upgrade.c`).

## Role in pg_upgrade

Phase between cluster start (`server.c:start_postmaster(&old_cluster)`)
and data-file transfer. Produces:

- `<dumpdir>/pg_upgrade_dump_globals.sql` — superuser/role/tblspc.
- `<dumpdir>/pg_upgrade_dump_<dboid>.custom` — per-db schema (binary
  format).

`--no-data` means relfilenode contents are *not* in the dump; those
come over via `file.c` later. The point of `--binary-upgrade` is that
pg_dump emits `SELECT
binary_upgrade.set_next_heap_relfilenode(...)` etc. so OIDs/
relfilenumbers from the old cluster are preserved.

## Key functions

- `generate_old_dump()` `dump.c:16` — only entry point.
  - Globals call: `exec_prog(UTILITY_LOG_FILE, NULL, true, true, ...)`
    line 23 — synchronous, exit-on-error.
  - Per-DB call: `parallel_exec_prog(...)` line 58 — fans out across
    `user_opts.jobs` workers (see `parallel.c`).
  - `reap_child(true)` loop at line 73 — joins all workers before
    returning.

## Wire surface — argv composition

Format string at line 24 and 59 builds the command for `system(3)` via
`exec_prog`. Components:

- Binary path: `"%s/pg_dumpall"` — `new_cluster.bindir` is shell-quoted
  with raw `\"...\"`, NOT through `appendShellString`. Relies on
  pg_upgrade trusting its own --new-bindir CLI flag.
- `cluster_conn_opts(&old_cluster)` (server.c:94) — already
  shell-quoted via `appendShellString` on sockdir and username.
- Per-db: `escaped_connstr.data` — built by `initPQExpBuffer` +
  `appendConnStrVal(db_name)` then run through `appendShellString`
  (lines 44-52). So a malicious database name in the OLD cluster
  cannot break out of the shell argument.
- `log_opts.dumpdir` — interpolated raw. Comes from `-o/-O` /
  `pg_upgrade_output.d` setup in option.c, not user-typed.

## State / globals

None. Reads `old_cluster`, `new_cluster`, `user_opts`, `log_opts`.

## Phase D notes

- [from-code] db_name is correctly run through both `appendConnStrVal`
  (libpq-style quoting) and `appendShellString` (shell-quoting). If an
  old cluster has a database named `foo"; rm -rf ~; #`, the dump still
  goes to the right place. `dump.c:46,51`.
- `--binary-upgrade` means the dump SQL contains `set_next_*` calls
  that hard-wire the new cluster's OID space to the old. If the dump
  file is tampered with between `generate_old_dump()` and
  `restore_schema()`, it could write arbitrary catalog rows.
  pg_upgrade explicitly does NOT validate dump output before piping
  to psql/pg_restore.
- `cluster_conn_opts(&old_cluster)` returns the old cluster's port
  + Unix-socket dir; no password handling because pg_upgrade requires
  trust authentication on both clusters during the upgrade
  (documented in pg_upgrade.sgml).

[ISSUE-trust-boundary: pg_dump output is implicitly trusted by the
subsequent pg_restore; tamper window exists between
generate_old_dump() and restore_schema() if log_opts.dumpdir is on
shared storage (maybe-low)] — `dump.c:55,66` writes file at
`<dumpdir>/pg_upgrade_dump_<oid>.custom`; pg_upgrade does not
checksum or re-read with a stored hash before invoking pg_restore.
This is theoretical: dumpdir is per-invocation under
`pg_upgrade_output.d/<timestamp>/` by default (option.c).

[ISSUE-info-disclosure: pg_dump log files in
log_opts.dumpdir/pg_upgrade_dump_<oid>.log capture pg_dump's own
error output including database-name-bearing messages; not scrubbed
on retention (maybe-low)] — files retained when `--retain` is set
(util.c:cleanup_output_dirs).
