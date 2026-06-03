# version.c

## Purpose

Per-version compatibility shims invoked by check.c during the
pre-upgrade analysis pass. Detects features that need user action
(reindex hash indexes, alter-extension updates, jsonb format check)
and writes remediation scripts under the upgrade output dir.

## Role in pg_upgrade

Called from `check.c::check_and_dump_old_cluster` and from the
data-type-usage scanner. Returns nothing; produces side-effect files
plus pg_log messages.

## Key functions

- `jsonb_9_4_check_applicable(cluster)` `version.c:21` — predicate
  hook for the data-type-usage check: returns true only for catalog
  versions before `JSONB_FORMAT_CHANGE_CAT_VER` on a 9.4 cluster.
- `protocol_negotiation_supported(cluster)` `version.c:36` — returns
  `major_version >= 1100`. Conservative — comment (line 37-46)
  explains we lock max_protocol_version=3.0 on anything pre-11
  because we only have major-version granularity and the Feb 2018
  minor-release added it.
- `old_9_6_invalidate_hash_indexes(cluster, check_mode)` `version.c:55`
  — iterates every database, finds hash indexes, in check_mode just
  reports them; in real mode writes `reindex_hash.sql` AND runs
  `UPDATE pg_index SET indisvalid = false` for the old cluster's hash
  indexes so the new cluster won't trust them post-upgrade.
- `process_extension_updates(dbinfo, res, arg)` `version.c:166`
  (static callback for UpgradeTask) — for each extension where
  `installed_version != default_version`, appends an `ALTER EXTENSION
  ... UPDATE;` line to the report file.
- `report_extension_updates(cluster)` `version.c:195` — schedules the
  query through task.c's `UpgradeTask` framework.

## State / globals

None. All work via passed `ClusterInfo *` and `os_info`.

## Phase D notes

[from-code] **Version-check default behavior:** `protocol_negotiation_
supported` returns `false` on anything pre-11. Default is to ASSUME
NOT SUPPORTED — fail-closed for the unknown case. This is the
correct direction for trust.

[from-code] **`get_pg_version()`** (called from exec.c, defined in
pg_upgrade.c) reads `PG_VERSION` file from PGDATA. If unreadable or
malformed, pg_upgrade exits with `pg_fatal`. Hence the per-version
dispatch in this file always has a valid major number to switch on.
Means there's no "fail open" version path.

[from-code] **Hash-index UPDATE** (line 119-128) runs an explicit
`UPDATE pg_catalog.pg_index SET indisvalid = false` against the OLD
cluster, mutating the cluster being upgraded. This is intentional
(comment line 118: "mark hash indexes as invalid"). If the upgrade
later aborts, the old cluster has been left with invalidated hash
indexes; user must rebuild them.

[ISSUE-state-transition: `old_9_6_invalidate_hash_indexes` writes
`indisvalid = false` to the OLD cluster's pg_index but does NOT
record a recovery action; if pg_upgrade fails after this point the
old cluster's hash indexes need a REINDEX (low; this is on the
9.6→10 path only, which is decade-old)] — `version.c:119`.

[from-code] **Output script paths.** `reindex_hash.sql` (line 60)
and `update_extensions.sql` (line 206) are written to the current
working directory (literal relative path), not `log_opts.basedir`.
This is intentional — these are meant to be run by the operator
after upgrade. The `fopen_priv` call uses umask-restricted
permissions but does not sanitize the working directory.

[ISSUE-info-disclosure: extension/index names from the old cluster
embedded in `reindex_hash.sql` / `update_extensions.sql`; written
into cwd (low)] — `version.c:108,186`. Public information already
via `\d`.

[ISSUE-stale-todo: `old_9_6_invalidate_hash_indexes` is per-version
dead code for clusters pg_upgrade now refuses to read — pg_upgrade
in current master refuses old clusters older than 9.2 (low)] —
`version.c:55`. Will eventually be retired when minimum supported
old version moves past 9.6.

[from-code] No `process_cb` here that touches `argv`/environment.
Pure SQL emission; trust boundary is the SQL connection.
