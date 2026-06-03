# pg_upgrade.c

## Purpose

The orchestrator. `main()` drives the entire upgrade pipeline:
parse args, check compatibility, dump the old cluster, restore into
the new, copy/link/clone the relation files, fix the xid/multi/oid
counters, and emit a delete-old-cluster script. ~1100 lines, no
phase-handler dispatch table — just a linear `main()` that hard-codes
the order.

The 38-line header comment (lines 11-38) is the load-bearing
invariant statement: which `pg_class.oid` /
`pg_class.relfilenode` / `pg_tablespace.oid` / `pg_type.oid` /
`pg_enum.oid` / `pg_authid.oid` / `pg_database.oid` values
**must** match between old and new clusters and why (composite types,
toast pointers, enum stored values, large-object metadata,
on-disk directory naming). Every other file in pg_upgrade enforces a
slice of these promises.

## Role in pg_upgrade pipeline

Owns the pipeline. The order in `main()` (lines 89-269) is:

1. `pg_logging_init` + `set_pglocale_pgservice`.
2. `umask(PG_MODE_MASK_OWNER)` — restrictive (0700) until new
   cluster perms are known. [verified-by-code line 103]
3. `parseCommandLine` (option.c).
4. `get_restricted_token()` — Windows: drop privileges if running
   as admin.
5. `adjust_data_dir` (×2) — resolve config-only dirs by running
   `postgres -C data_directory`.
6. `GetDataDirectoryCreatePerm(new_cluster.pgdata)` →
   `umask(pg_mode_mask)` — switch to 0700 or 0750 to match new
   cluster.
7. `make_outputdirs(new_cluster.pgdata)` — creates
   `pg_upgrade_output.d/<timestamp>/{log,dump}` INSIDE the new
   cluster's pgdata. Timestamp is `gettimeofday`-derived with
   millisecond precision.
8. `setup(argv0)` — `check_pghost_envvar`, default `new_cluster.bindir`
   to dirname(argv0), `verify_directories`, **probe stale
   postmaster.pid files** by attempting `start_postmaster`. If the
   old cluster starts → stale lock → stop it. If it doesn't → assume
   live server → enable `live_check` (only allowed in `--check`).
9. `output_check_banner` + `check_cluster_versions` +
   `get_sock_dir(×2)` + `check_cluster_compatibility`.
10. `check_and_dump_old_cluster` (check.c) — starts old postmaster
    (unless live_check), runs all compatibility checks, dumps the
    old cluster, stops old postmaster.
11. `start_postmaster(&new_cluster)` + `check_new_cluster` +
    `report_clusters_compatible`. In `--check` mode the program
    `exit(0)`s here (check.c line 813).
12. `set_locale_and_encoding` (line 465) — UPDATE template0 in new
    cluster with old template0's encoding/locale via libpq.
13. `prepare_new_cluster` (line 543) — `vacuumdb --all --analyze`
    then `--all --freeze` on the new cluster.
14. `stop_postmaster(false)`.
15. `copy_xact_xlog_xid` (line 773) — copy old `pg_xact` (or
    `pg_clog` for ≤9.6) into new; **multiple `pg_resetwal -f`
    runs** to set chkpnt_nxtxid, chkpnt_oldstxid, chkpnt_nxtepoch,
    commit-timestamp limits; convert or copy `pg_multixact/*`
    (multixact_rewrite.c if format change crossed); reset WAL
    archive.
16. `set_new_cluster_char_signedness` (line 428) — only if mismatch.
17. `start_postmaster(&new_cluster)`.
18. `prepare_new_globals` (line 573) — `set_frozenxids(false)` then
    psql-restore of `pg_upgrade_dump_globals.sql`. THIS IS WHERE
    `pg_authid` rows (incl. password hashes) are written into the
    new cluster.
19. `create_new_objects` (line 595) — parallel `pg_restore` per
    database. Template1 is special-cased first (single-threaded)
    because it cannot be processed concurrently with peers (gets
    transiently dropped during `--clean --create`). Other DBs use
    `parallel_exec_prog` with `txn_size = RESTORE_TRANSACTION_SIZE
    / user_opts.jobs` (floor 10).
20. `stop_postmaster(false)`.
21. **Point of no return** for `--link` / `--swap`:
    `disable_old_cluster` (controldata.c) renames old pg_control
    aside so the old cluster cannot be started again — protects
    against the user accidentally bringing it up and corrupting
    the now-shared-via-hardlink data files. [verified-by-code lines 184-186]
22. `transfer_all_new_tablespaces` (relfilenumber.c) — the file copy.
23. `pg_resetwal -o <chkpnt_nxtoid>` — restore OID counter.
24. If `migrate_logical_slots || sub_retain_dead_tuples`:
    restart new postmaster → `create_logical_replication_slots` /
    `create_conflict_detection_slot` → stop.
25. If `user_opts.do_sync`: `initdb --sync-only`.
26. `create_script_for_old_cluster_deletion` (check.c).
27. `issue_warnings_and_set_wal_level` (check.c) — restart new
    postmaster to write a final WAL record with `wal_level=replica`.

## Key functions

- `main()` line 89 — the pipeline above.
- `make_outputdirs(pgdata)` line 277 — builds
  `<pgdata>/pg_upgrade_output.d/YYYYMMDDTHHMMSS.NNN/{dump,log}`.
  Every `snprintf` is paired with a `>= MAXPGPATH` truncation check
  via `pg_fatal`. Opens `INTERNAL_LOG_FILE` and writes a
  separator banner into each of the four output_files.
- `setup(argv0)` line 361 — see step 8 above. Important quirk: if
  `--check` and the old cluster has a `postmaster.pid` AND
  `start_postmaster(report_and_exit_on_error=false)` fails, sets
  `user_opts.live_check = true`. So `live_check` is **inferred**,
  not explicitly requested via CLI. [verified-by-code lines 401-410]
- `set_locale_and_encoding()` line 465 — version-branched UPDATE on
  template0 in the new cluster. Three SQL variants by major version
  (≥1700 / ≥1500 / older) for the changing `datlocprovider` /
  `datlocale` / `daticulocale` columns.
- `prepare_new_cluster()` line 543 — vacuum freeze on new cluster.
- `prepare_new_globals()` line 573 — invokes psql with
  `EXEC_PSQL_ARGS` (= "--echo-queries --set ON_ERROR_STOP=on
  --no-psqlrc --dbname=template1") to load globals.sql.
- `create_new_objects()` line 595 — parallel pg_restore harness.
- `copy_subdir_files(old_subdir, new_subdir)` line 749 — uses
  shell `cp -Rf` / `xcopy` to copy `pg_xact`/`pg_clog`/
  `pg_multixact` dirs. The shell-command is a `pg_fatal`-on-truncate
  snprintf into `exec_prog`'s vformat.
- `copy_xact_xlog_xid()` line 773 — the xid/multixact migration. The
  long sequence of `pg_resetwal` calls (lines 786-902) is
  load-bearing for clusters carrying long transaction history.
- `set_frozenxids(minmxid_only)` line 927 — UPDATE
  `pg_database.datfrozenxid` / `.datminmxid` and `pg_class.relfrozenxid`
  / `.relminmxid` on every DB. Temporarily flips
  `datallowconn=true` on databases that disallow connections
  (template0), so it can connect and update pg_class.
- `create_logical_replication_slots()` line 1030 —
  `SELECT pg_create_logical_replication_slot(name, plugin, false,
  two_phase, failover)` per slot. Names escaped via
  `appendStringLiteralConn`.
- `create_conflict_detection_slot()` line 1090 — calls
  `binary_upgrade_create_conflict_detection_slot()`.

## State / globals

- `old_cluster`, `new_cluster` (type `ClusterInfo`) — defined here at
  lines 73-74, declared `extern` in pg_upgrade.h.
- `os_info` (type `OSInfo`) — defined at line 75.
- `output_files[]` (line 77) — list of log filenames written by the
  banner code in `make_outputdirs`.

## Phase D notes

[ISSUE-trust-boundary: pg_authid carryover via SQL restore of
GLOBALS_DUMP_FILE (medium)] — `prepare_new_globals()` (line 583)
runs the globals dump file through psql against the new
cluster. That file contains `ALTER ROLE ... PASSWORD '<scram-hash>'`
lines from pg_dumpall's globals output (see
src/bin/pg_dumpall/pg_dumpall.c). The hashes are SCRAM-SHA-256
(modern) or md5 (legacy), so the file is NOT plaintext-password.
BUT: it sits in `<new_pgdata>/pg_upgrade_output.d/<ts>/dump/`
between dump and restore, then is left there until
`cleanup_output_dirs()` at the very end (or RETAINED forever if
`-r/--retain` is passed OR the upgrade fails partway). On a cluster
configured with `data_directory_mode=0750`, the hash file is
group-readable. **No scrub of the dump file after restore.** Same
exposure as in pg_dump/pg_dumpall — see A2 corpus.

[ISSUE-trust-boundary: catalog values from the OLD cluster fully
trusted (medium)] — Multiple resetwal invocations use raw values
from `old_cluster.controldata`:
- `pg_resetwal -o %u` ← `chkpnt_nxtoid` (line 199)
- `pg_resetwal -f -u %u` ← `chkpnt_oldstxid` (line 787)
- `pg_resetwal -f -x %u` ← `chkpnt_nxtxid` (line 795)
- `pg_resetwal -f -e %u` ← `chkpnt_nxtepoch` (line 799)
- `pg_resetwal -f -c %u,%u` ← `chkpnt_nxtxid` twice (line 803)
- `pg_resetwal -O %" PRIu64 " -m %u,%u` ← `chkpnt_nxtmxoff`,
  `chkpnt_nxtmulti`, `chkpnt_oldstMulti` (line 829)

A maliciously-modified pg_control (or a corrupted old cluster) could
inject crazy values — but only the new cluster is affected, and
`pg_resetwal` itself validates ranges to some extent.

[ISSUE-state-transition: between `disable_old_cluster()` (line 186)
and `transfer_all_new_tablespaces` (line 188) the old cluster cannot
be started but the new one is not yet populated (low)] — A crash in
this window leaves both clusters in a transient state. The user
is told (line 818) "If pg_upgrade fails after this point, you must
re-initdb the new cluster before continuing." Documented behaviour.

[ISSUE-shell-injection: `copy_subdir_files` (line 749) invokes
shell `cp -Rf "%s" "%s"` / `xcopy ... "%s" "%s\"` with paths
sourced from `cluster->pgdata` (low)] — pgdata is operator-supplied
and not validated against shell metacharacters (`"`, `$`, backtick).
Quotes are doubled around each operand. A user-supplied PGDATA
containing a `"` or `$(...)` could be smuggled into the shell —
but only by the operator running pg_upgrade themselves, so this is
a footgun rather than an escalation. Same posture as
`exec_prog` (exec.c — separate batch).

[ISSUE-state-transition: stale `postmaster.pid` probe in `setup()`
silently flips `live_check=true` (line 409) when `--check` AND the
old server "won't start" via stale-pid probe (low)] — If the old
postmaster is wedged (won't respond, won't restart) the probe
infers "live server running" and silently downgrades the run. A
genuinely-corrupted old data dir might present the same shape, in
which case the inferred live_check is wrong and downstream checks
that depend on live-server behaviour misfire.

[ISSUE-undocumented-invariant: timestamp directory name
(`make_outputdirs` line 294) only millisecond-precision — running
pg_upgrade twice within the same millisecond produces a directory
collision and `pg_fatal` (very low)] — Operator footgun, not
exploitable.

## Potential issues

[ISSUE-correctness: `template1` special-cased BEFORE the loop in
`create_new_objects` (lines 619-656) but the loop is then re-run
(lines 658-708) and `break`s on the first non-template1 — meaning
the template1 single-threaded pass uses `--clean --create` and
loops only until found, while the parallel pass skips it cleanly]
— Confusing structure but correct. Worth a comment refactor.

[ISSUE-stale-todo: comment line 56-58 "At some point we might want
to make this user-controllable" re `RESTORE_TRANSACTION_SIZE 1000`]
— Aged TODO; -j scaling is in place but the base value is still
hardcoded.

[ISSUE-correctness: `pg_strdup(getenv("PGUSER"))` (option.c via
parseCommandLine) keeps env-var-derived user, but `os_info.user` is
serialized into `output_completion_banner` via `appendShellString`
(check.c line 853) — quoting is correct for shell] —
verified-by-code.
