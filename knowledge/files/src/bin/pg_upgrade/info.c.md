# info.c

## Purpose

Gathers catalog metadata from both clusters: list of databases, list
of relations per database, list of logical replication slots,
template0 locale, and subscription count. Produces the `DbInfo` /
`RelInfo` / `LogicalSlotInfo` arrays that the rest of pg_upgrade
consumes. Also generates the per-relation `FileNameMap` array that
relfilenumber.c walks to copy/link files.

## Role in pg_upgrade

Called after both clusters' postmasters are up:
1. `check.c::check_and_dump_old_cluster()` → `get_db_rel_and_slot_infos(&old_cluster)`.
2. `check.c::check_new_cluster()` → `get_db_rel_and_slot_infos(&new_cluster)`.
3. `pg_upgrade.c::create_new_objects()` (post-restore) calls it again
   on the new cluster to refresh, because objects have changed.
4. `relfilenumber.c::transfer_all_new_dbs` calls `gen_db_file_maps`
   per-database to build the file map.

Also: `get_subscription_info(&old_cluster)` is called from
`check_and_dump_old_cluster` (for ≥1700) to populate
`old_cluster.nsubs` and `old_cluster.sub_retain_dead_tuples`.

## Key functions

- `gen_db_file_maps(old_db, new_db, *nmaps, old_pgdata, new_pgdata)`
  line 44 — merge-walk two relation arrays (sorted by OID) to build
  the FileNameMap. Unmatched old rels → `pg_fatal`. Unmatched new
  rels in `pg_toast` namespace → silently ignored (the new server
  may have created a TOAST table that wasn't needed). Name mismatch
  on same OID → WARNING but not fatal in the loop (sets
  `all_matched=false` then `pg_fatal`s after the loop). [verified-by-code lines 73-150]
- `create_rel_filename_map(...)` line 163 — fills a single FileNameMap
  row. Tablespace selection: empty old tablespace → use
  `old_pgdata + "/base"`; non-empty → use tablespace path +
  `tablespace_suffix`. Same for new. Asserts via comments that
  "DB oid and relfilenumbers are preserved between old and new
  cluster" (line 198).
- `report_unmatched_relation(rel, db, is_new_db)` line 213 —
  diagnostic helper. Walks the rel array to find the parent table
  of an unmatched index or toast table for the error message.
- `get_db_rel_and_slot_infos(cluster)` line 279 — top-level entry.
  Builds an `UpgradeTask`, adds the rel-infos query, conditionally
  adds the logical-slot query (old cluster only, ≥1700), and runs
  the task against every connectable database in `cluster->dbarr`.
  Calls `get_template0_info` and `get_db_infos` first to populate
  the db array.
- `get_template0_info(cluster)` line 332 — three SQL variants by
  major version (≥1700 with `datlocale`, ≥1500 with `daticulocale`,
  older with hardcoded 'c' provider). Connects to `template1` to
  query.
- `get_db_infos(cluster)` line 397 — populates `cluster->dbarr`
  from `pg_database` with a JOIN to `pg_tablespace`. Skips
  `datallowconn = false` databases (line 425). Handles in-place
  tablespaces (relative paths) by prefixing `cluster->pgdata`.
- `get_rel_infos_query()` line 479 — builds the
  per-database CTE-based query that returns all user heaps,
  materialized views, their toast tables, and their valid indexes,
  ordered by OID. Includes `pg_largeobject` always (system table
  with user data) and `pg_largeobject_metadata` for old ≥1600 (aclitem
  format changed in 16). Adds RELKIND_SEQUENCE to the relkind
  filter ONLY when `transfer_mode == TRANSFER_MODE_SWAP` (line 514).
  Excludes orphan temp schemas. Uses `FirstNormalObjectId` (16384)
  as the user-OID cutoff.
- `process_rel_infos(dbinfo, res, arg)` line 578 — callback
  invoked once per database by the UpgradeTask. Allocates
  `RelInfo[ntups]`. Implements the **string-interning trick**:
  if the current `nspname` matches the previous one, reuse the
  pointer (`nsp_alloc=false`); same for `tablespace`. Saves
  memory on clusters with thousands of relations in few schemas.
  [verified-by-code lines 614-660]
- `get_old_cluster_logical_slot_infos_query(cluster)` line 678 —
  three SQL variants:
  - `live_check`: `caught_up=FALSE` always (cannot verify on a
    running server, new WAL keeps arriving).
  - ≥1900: optimised CTE using
    `binary_upgrade_check_logical_slot_pending_wal` on the slot
    with min `confirmed_flush_lsn` and max as cutoff — checks at
    most one slot per database.
  - ≤1800: per-slot
    `binary_upgrade_logical_slot_has_caught_up(slot_name)`.
- `process_old_cluster_logical_slot_infos(dbinfo, res, arg)`
  line 774 — fills `dbinfo->slot_arr` with `LogicalSlotInfo[]`.
- `count_old_cluster_logical_slots()` line 825 — sums `nslots`
  across all DBs.
- `get_subscription_info(cluster)` line 841 — sets
  `cluster->nsubs` and `cluster->sub_retain_dead_tuples`. The
  `subretaindeadtuples` column exists from ≥1900 only.

## State / globals

Reads `old_cluster` / `new_cluster` / `user_opts.transfer_mode` /
`log_opts.verbose` / `os_info.running_cluster`. Writes back into
`cluster->dbarr`, `cluster->template0`, `cluster->nsubs`,
`cluster->sub_retain_dead_tuples`.

`os_info.running_cluster` is consulted in `process_rel_infos` line
642 to prefix in-place tablespace paths with the **currently
running** cluster's pgdata. Set by `server.c::start_postmaster`.

## Phase D notes

[ISSUE-trust-boundary: catalog data from the OLD cluster is parsed
without sanitization and used to compose file paths (high)] —
`process_rel_infos` reads `relname`, `nspname`, `relfilenode`,
`spclocation` directly from `pg_class` / `pg_namespace` /
`pg_tablespace` of the old cluster. These values flow into:
- `FileNameMap.relfilenumber` (raw uint32, used in
  `transfer_relfile` to build paths like `<base>/<dboid>/%u`).
- `FileNameMap.nspname` / `.relname` — used in log messages only.
- `dbinfos[].db_tablespace` (line 452) — for **in-place tablespaces**
  this is `snprintf("%s/%s", cluster->pgdata, spcloc)` — a relative
  spcloc with `../../etc/passwd` would compose a path outside
  `pgdata`. The catalog `pg_tablespace_location()` for in-place
  tablespaces returns a relative subpath, but there's no validation
  here that it stays within pgdata. **A compromised pg_tablespace
  row with `spclocation='../../somewhere'` could redirect file
  operations.** Low practical impact because (a) pgdata is owned by
  the postgres user already, (b) transfer file ops are mode 0600.
  But the trust boundary is real.

[ISSUE-trust-boundary: `os_info.running_cluster->pgdata` used as
prefix for in-place tablespace paths (line 642), but the
"running_cluster" can be either old or new (medium)] — When the old
cluster is running this composes paths under `old_pgdata`; when
the new cluster is running, under `new_pgdata`. There's no
cross-check that the catalog row matches the cluster currently
running. If both clusters share in-place tablespace names but
different actual locations, paths might be mis-resolved.

[ISSUE-trust-boundary: `slot_info->plugin` (output plugin name) is
restored verbatim via `appendStringLiteralConn` in
`create_logical_replication_slots` (pg_upgrade.c line 1060) (medium)]
— A compromised old cluster could have a slot pointing to an
attacker-supplied plugin name. After upgrade, the new cluster will
try to load that plugin from disk when the slot is used (which
requires the .so to exist on disk). Realistic threat: insider with
write access to old cluster catalog plants a slot referencing
`/tmp/evil` — but the .so would still have to exist as a
`shared_preload_libraries`-loadable file. Not a direct RCE, but a
named exposure.

[ISSUE-info-disclosure: rel-infos query (line 499) excludes
namespaces in `('pg_catalog','information_schema','binary_upgrade','pg_toast')`
plus `pg_temp_*` and `pg_toast_temp_*` — but the
exclusion is paired with the OID-cutoff (>= FirstNormalObjectId).
A user could in theory create a `pg_temp_attacker` schema (allowed
syntactically), and their objects would be filtered (low)] —
verified-by-code, defense-in-depth as the comment notes.

[ISSUE-undocumented-invariant: `process_rel_infos` (line 597)
allocates `relinfos[ntups]` but only fills `num_rels` of them
(`num_rels = 0; for(...) curr = &relinfos[num_rels++]` and never
skips) — `num_rels` always equals `ntups` (low)] — Dead
defensiveness; refactor candidate.

[ISSUE-correctness: `gen_db_file_maps` returns even if `all_matched
== false` (line 149) but immediately `pg_fatal`s — so the function
never returns with partial maps. Comment line 76: "we'll abort, but
first print as much info as we can". Behaviour matches comment.]

## Potential issues

[ISSUE-stale-todo: comment at line 477 "the result is assumed to
be sorted by OID. This allows later processing to match up old and
new databases efficiently" — actually used by `gen_db_file_maps` for
RELS within a DB, not DBs themselves. Wording is slightly off.]

[ISSUE-correctness: subscription query (line 850) uses `count(*)`
returning a string then `atoi`s — fine, but if the new server is
unreachable mid-query the failure mode is `executeQueryOrDie ` ergo
`pg_fatal`.]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
