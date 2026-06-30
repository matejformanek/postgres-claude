# check.c

- **Source path:** `source/src/bin/pg_upgrade/check.c`
- **Lines:** 2646
- **Last verified commit:** `02f699c14163` (re-verified + re-pinned
  2026-06-30 by pg-quality-auditor AUDIT mode after anchor-bump
  `4abf411e2328..02f699c14163`; triggering commit `cae90d747969`
  "Message and comment wording fixes" touched message/comment text only —
  no documented region shifted materially; a few cites drifted ±1 line.)

## Purpose

The pre-upgrade compatibility checker — **THE** security boundary
between old and new clusters. ~2650 lines, 40+ check functions
spanning data-type usage, encoding, role identity, prepared
transactions, replication slots, subscriptions, tablespaces,
on-disk format changes, and assorted cross-version trip-hazards.
Each check either passes silently (`check_ok()`), warns
(`pg_log(PG_WARNING, …)`), produces a report file under
`<pgdata>/pg_upgrade_output.d/<ts>/`, or fatally aborts with
`pg_fatal`.

Also owns the public driver functions `output_check_banner`,
`check_and_dump_old_cluster`, `check_new_cluster`,
`report_clusters_compatible`, `issue_warnings_and_set_wal_level`,
`output_completion_banner`, `check_cluster_versions`,
`check_cluster_compatibility`, and the deletion-script generator
`create_script_for_old_cluster_deletion`.

## Role in pg_upgrade

`pg_upgrade.c::main()` calls into this file at three points:

1. `output_check_banner()` (line 575) — header.
2. `check_cluster_versions()` (line 882) — major-version sanity:
   old must be ≥ 9.2, new must be current PG version exactly, no
   downgrades, binary version must match data-dir version.
3. `check_cluster_compatibility()` (line 937) — pg_control comparison
   via controldata.c.
4. `check_and_dump_old_cluster()` (line 593) — the big one. Starts
   old postmaster (unless live_check), runs all "checks against the
   old cluster" in order, optionally runs `generate_old_dump`,
   stops postmaster.
5. `check_new_cluster()` (line 742) — checks against the new
   cluster after it's been started.
6. `report_clusters_compatible()` (line 805) — emits "*Clusters are
   compatible*" and exits(0) if `--check` mode.
7. `issue_warnings_and_set_wal_level()` (line 824) — restarts new
   server so a real WAL record is written with `wal_level=replica`
   for standby rsync workflows.
8. `output_completion_banner()` (line 845) — final user-facing
   guidance, including vacuumdb commands.
9. `create_script_for_old_cluster_deletion(&fname)` (line 1012) —
   writes the `.sh` or `.bat`.

## Check inventory

### Data-type usage checks (table-driven, lines 103-322)

`DataTypesUsageChecks data_types_usage_checks[]` is an array of
structs with `{status, report_filename, base_query, report_text,
threshold_version, version_hook}`. Walked by
`check_for_data_types_usage` (line 468) via an UpgradeTask.

Entries:
- system-defined composite types in user tables (ALL_VERSIONS)
- `line` data type (≤903)
- `reg*` data types (regcollation, regconfig, regdictionary,
  regnamespace, regoper, regoperator, regproc, regprocedure) —
  ALL_VERSIONS. Comment notes regclass, regdatabase, regrole,
  regtype are OK because their referenced catalogs preserve OIDs.
- `aclitem` (≤1500) — internal format changed in 16.
- `unknown` columns (≤906) — no longer allowed.
- `sql_identifier` (≤1100) — storage switched from name to varchar
  in 12.
- `jsonb` (MANUAL_CHECK → `jsonb_9_4_check_applicable`) — format
  changed during 9.4 beta.
- `abstime` / `reltime` / `tinterval` (≤1100) — removed in 12.

### Old-cluster checks (`check_and_dump_old_cluster`, ordered)

Lines 593-738:
- `check_for_connection_status` — `datallowconn=t` for non-template0
  and `=f` for template0; `datconnlimit != -2`.
- `check_for_unsupported_encodings` — `PG_VALID_BE_ENCODING`.
- `check_old_cluster_global_names` (≤1800) — `\n` / `\r` in
  database / role / tablespace names; fatal if found (v19 forbids).
- `get_db_rel_and_slot_infos(&old_cluster)`.
- `init_tablespaces()` (tablespace.c).
- `get_loadable_libraries()` (function.c).
- `check_is_install_user` — must be bootstrap superuser
  (`pg_authid.oid = BOOTSTRAP_SUPERUSERID = 10`).
- `check_for_prepared_transactions` — must be empty.
- `check_for_isn_and_int8_passing_mismatch` — contrib/isn breakage
  if int8 pass-by-value changed.
- `check_old_cluster_for_valid_slots` (≥1700) — logical slot
  validity + caught-up.
- `get_subscription_info` + `check_old_cluster_subscription_state`
  (≥1700) — subrel state must be `i` or `r`; subscription must
  have a replication origin.
- `check_for_data_types_usage` (the table above).
- `check_for_unicode_update` — if `unicode_version()` changed
  between old and new, scan indexes / partitioned tables /
  matviews / check constraints for expressions involving Unicode-
  dependent functions/operators. Warn only.
- `check_for_user_defined_encoding_conversions` (≤1300) —
  PG14 changed conversion function signature.
- `check_for_user_defined_postfix_ops` (≤1300) — removed in 14.
- `check_for_incompatible_polymorphics` (≤1300) — anyarray →
  anycompatiblearray in 14.
- `check_for_tables_with_oids` (≤1100) — removed in 12.
- `check_for_not_null_inheritance` (≤1800) — pre-18 inherited
  not-null gaps.
- `check_for_gist_inet_ops` (≤1800) — btree_gist's
  gist_inet_ops/cidr_ops dump→restore opclass swap.
- `old_9_6_invalidate_hash_indexes(&old_cluster, true)` (≤906,
  check mode only).
- `check_for_pg_role_prefix` (≤905) — roles starting with `pg_`
  forbidden from 9.6.
- `generate_old_dump()` (dump.c) — only outside `--check` mode.

### New-cluster checks (`check_new_cluster`, ordered)

Lines 742-801:
- `get_db_rel_and_slot_infos(&new_cluster)`.
- `check_new_cluster_is_empty` — no user relations in any DB
  (pg_catalog OK).
- `check_loadable_libraries` (function.c).
- Mode-specific filesystem check: `check_file_clone` /
  `check_copy_file_range` / `check_hard_link` (file.c).
- `check_is_install_user(&new_cluster)` — additionally enforces
  EXACTLY ONE role (the install user). Comment line 1144: "other
  defined users might match users defined in the old cluster and
  generate an error during pg_dump restore."
- `check_for_prepared_transactions(&new_cluster)`.
- `check_for_new_tablespace_dir` (line 983) — tablespace dirs in
  the new cluster must not already exist; otherwise the global
  objects restore would fail.
- `check_new_cluster_replication_slots` (line 2205) — no existing
  logical slots; no `pg_conflict_detection` slot;
  `wal_level != 'minimal'`; `max_replication_slots` sufficient.
- `check_new_cluster_subscription_configuration` (line 2313) —
  `max_active_replication_origins >= old_cluster.nsubs`.

## Key functions (more detail)

- `check_is_install_user(cluster)` line 1110 — Connects to
  template1 as the configured user, runs `SELECT rolsuper, oid
  FROM pg_roles WHERE rolname = current_user AND rolname !~ '^pg_'`,
  expects exactly one row and `oid = BOOTSTRAP_SUPERUSERID` (10).
  Comment line 1117: "Can't use pg_authid because only superusers
  can view it." Then a count of non-`pg_*` roles. For the new
  cluster, only ONE row allowed.
- `create_script_for_old_cluster_deletion(&fname)` line 1012 —
  Refuses to generate the script if (a) new_pgdata is inside
  old_pgdata, or (b) any new_tablespace path is inside
  old_pgdata. Sets `*fname = NULL` in those cases and the
  completion banner tells the user to delete manually. The
  generated script `rmdir`s the old pgdata + each old tablespace's
  versioned subdir. On POSIX: `chmod S_IRWXU` so the script is
  executable only by owner.
- `check_for_unicode_update(cluster)` line 2071 — Only ≥1700.
  Compares `unicode_version()` on the cluster vs `PG_UNICODE_VERSION`
  compiled into the new pg_upgrade. If different, runs an
  elaborate CTE-based pg_node_tree-pattern-match query (lines
  2100-2168) over `pg_constraint.conbin`,
  `pg_index.indexprs/indpred`,
  `pg_partitioned_table.partexprs`, and `pg_rewrite.ev_action` for
  matviews. WARNING only (not fatal). [verified-by-code]
- `check_new_cluster_replication_slots()` line 2205 — Composite SQL
  that conditionally counts logical slots and the
  `pg_conflict_detection` slot. Enforces `wal_level ∈
  {replica, logical}` and `max_replication_slots ≥ nslots_on_old
  (+1 if retain_dead_tuples)`.
- `check_old_cluster_for_valid_slots()` line 2356 — Walks
  `old_cluster.dbarr.dbs[].slot_arr.slots[]` (populated by
  info.c). For each slot: if `invalid` → report; if `!live_check
  && !caught_up` → report; if name equals `pg_conflict_detection`
  → report (reserved from PG19). Writes
  `invalid_logical_slots.txt`. Fatal if any reports.
- `check_old_cluster_subscription_state()` line 2478 — Two
  queries: missing replication origin (subscription exists but
  no `pg_replication_origin` row named `pg_<sub_oid>`); subrel
  state outside `{i, r}` (rules out DATASYNC, SYNCDONE,
  FINISHEDCOPY).
- `check_old_cluster_global_names(cluster)` line 2585 — UNION over
  `pg_database.datname` / `pg_roles.rolname` /
  `pg_tablespace.spcname`; flag any with `\n` or `\r`. From v19
  forbidden. Fatal if any.

## State / globals

Reads everything: `old_cluster`, `new_cluster`, `user_opts`,
`log_opts`, `os_info`. Writes new fields onto the clusters
indirectly via the info.c task callbacks (rel_arr / slot_arr).
Maintains no module-private state.

## Phase D notes

[ISSUE-trust-boundary: every "old cluster" check connects via
libpq to a postmaster that pg_upgrade itself just started against
the old `$PGDATA` (high)] — `check_and_dump_old_cluster` runs
inside the start/stop fence (line 598/737). If the old data dir is
compromised (e.g. attacker-controlled `pg_class`, malicious
extensions in `shared_preload_libraries` via `pgopts`), the
backend that pg_upgrade talks to is running attacker code. The
checks operate on whatever the old backend returns. Trust model:
operator owns both clusters and the binaries; data-dir tampering is
out of scope.

[ISSUE-trust-boundary: `check_is_install_user` line 1117 NOTES the
limitation explicitly: "Can't use pg_authid because only superusers
can view it" (medium)] — `pg_authid` IS visible to the install
user, who is by definition `BOOTSTRAP_SUPERUSERID`. The query uses
`pg_roles` (a view that masks rolpassword) instead. This means
**pg_upgrade does NOT inspect role password hashes at all** — they
flow purely via the pg_dumpall globals dump. No scrubbing of the
globals.sql file after restore.

[ISSUE-trust-boundary: SQL queries against old cluster are sometimes
hardcoded as `current_database()` / `current_user` with no
client-side filtering (medium)] — Acceptable when the SQL is itself
read-only and the server-side authentication establishes identity.
But any `executeQueryOrDie` that does an UPDATE (e.g. the
`set_frozenxids` in pg_upgrade.c) flows through this same channel.

[ISSUE-trust-boundary: `check_loadable_libraries` (declared in
pg_upgrade.h, in function.c) attempts to `LOAD '<libname>'` on the
new cluster for every library named in the old cluster's
`pg_proc.prosrc` etc. (medium)] — If an old cluster has a
malicious `pg_proc` entry referencing `/tmp/evil.so`, the new
cluster will try to LOAD it. The new cluster's binary actually
LOADs the .so to verify availability — if the path resolves and
the .so exists, _PG_init runs IN the new cluster's backend. Real
trust-boundary risk: a tampered old catalog → arbitrary code in
the new cluster. See function.c (separate batch) for details.

[ISSUE-state-transition: `setup()` in pg_upgrade.c silently flips
`live_check=true` when `--check` AND old postmaster.pid exists
AND the stale-pid restart probe fails — `check_and_dump_old_cluster`
then skips `start_postmaster(&old_cluster, true)` (line 598) (low)] —
Already noted in pg_upgrade.c doc; relevant here because all
old-cluster checks then talk to the live production server. The
live server's data is presumed trusted (the operator started it),
but `check_old_cluster_for_valid_slots` explicitly weakens to skip
the caught-up check under live_check (info.c line 696).

[ISSUE-undocumented-invariant: `check_for_unicode_update` is
WARNING-only (line 2184) (medium)] — A cluster with indexes that
will silently corrupt due to ICU/Unicode version mismatch can pass
pg_upgrade and start the new cluster, with the operator having
acknowledged a warning that may scroll past. Other checks fatally
abort; this one's "warning" status is defensible but visible from
a security standpoint as a "fail-open" check.

[ISSUE-undocumented-invariant: no check that the new cluster's
`shared_preload_libraries` matches or is a subset of the old (low)] —
The library-availability check (`check_loadable_libraries`) covers
"can the new server load them" but not "should they be loaded
during normal operation." An operator who removes a library from
`shared_preload_libraries` between old and new will succeed at
pg_upgrade and then break replicas / triggers / extensions.

[ISSUE-correctness: `check_for_new_tablespace_dir` line 998
`if (stat(...) == 0 || errno != ENOENT)` — covers both "exists"
and "stat failed for non-ENOENT reason" with the same fatal
message "new cluster tablespace directory already exists" (low)] —
A permission-denied stat (EACCES) emits the wrong error.

[ISSUE-correctness: `create_script_for_old_cluster_deletion` line
1030 compares paths with `path_is_prefix_of_path` after
`canonicalize_path`. Symlinks in either path are NOT resolved —
a symlinked new pgdata pointing inside old pgdata could bypass the
"don't create script" guard (low)] — Operator-controlled paths; not
exploitable across a trust boundary.

[ISSUE-info-disclosure: every report file (`*.txt`) is written
under `log_opts.basedir` with `fopen_priv` (= `fopen`) — mode
defaults to umask which was set to `pg_mode_mask` from
`GetDataDirectoryCreatePerm` (low)] — Files inherit the data-dir
permission posture. If `data_directory_mode=0750`, reports are
group-readable. Reports list relation names, slot names,
subscription names — naming info but not data.

[ISSUE-stale-todo: `check_old_cluster_subscription_state` does NOT
validate that the dump-globals.sql contains
`CREATE SUBSCRIPTION ... CONNECTION '...'` strings with no
credentials embedded (low)] — pg_dumpall is responsible for
suppressing the password in the connection string; pg_upgrade
trusts that. See pg_dumpall corpus doc.

## Negative space — checks that are absent

These would be defensible additions per Phase D analysis:

1. **No check that `pg_authid.rolpassword` hashes use the same algorithm
   class** between old and new. If the operator-configured
   `password_encryption` on the new cluster differs from how
   passwords were originally set, the SCRAM hashes carry over
   verbatim (correct) but mismatched md5 vs scram across replicas
   becomes a runtime surprise.

2. **No check on `pg_largeobject_metadata.lomacl` content beyond
   the aclitem-format gate.** The aclitem format change is gated
   (≥1600), but the entries themselves are trusted verbatim. A
   tampered `lomacl` value could grant unintended privileges on
   large objects after upgrade.

3. **No check that the `shared_preload_libraries` GUC in the new
   cluster's postgresql.conf** matches the old's. `function.c`
   verifies extensions are LOADable but not whether they're
   PRELOADed for normal operation.

4. **No check on `pg_proc.prosecdef` security-definer functions**
   for the `current_user` they'll inherit on the new cluster. If
   the install user OID is preserved but the OID happens to be
   reused for a different identity (impossible under
   BOOTSTRAP_SUPERUSERID=10 invariant, but defensible to assert).

5. **`unicode_version_changed` is WARNING-only** (already flagged).
   Promoting it to FATAL would be safer but a UX regression for
   minor-Unicode-version-bump upgrades.

## Potential issues

[ISSUE-dead-code: `check_for_pg_role_prefix` (line 1879) only
applies to upgrades from ≤905; given we are now several major
versions past, the path is rarely exercised but kept for old-
version support.]

[ISSUE-stale-todo: comment at line 110 "The cutoff OID here should
match the source cluster's value of FirstNormalObjectId. We
hardcode it rather than using that C #define..." — note line 113-114
suggests "Eventually we may need a test on the source cluster's
version to select the correct value." That eventuality has not
arrived.]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
