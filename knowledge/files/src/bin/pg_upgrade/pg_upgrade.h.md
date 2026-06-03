# pg_upgrade.h

## Purpose

The single central header for pg_upgrade. Defines every cross-module
typedef (`ClusterInfo`, `DbInfo`, `RelInfo`, `FileNameMap`,
`ControlData`, `LogicalSlotInfo`, `UpgradeTask`), every transfer mode
enum, every public function across `check.c` / `controldata.c` /
`dump.c` / `exec.c` / `file.c` / `function.c` / `info.c` / `option.c` /
`relfilenumber.c` / `server.c` / `tablespace.c` / `util.c` /
`version.c` / `multixact_rewrite.c` / `parallel.c` / `task.c`. Also
declares the four globals (`log_opts`, `user_opts`, `old_cluster`,
`new_cluster`, `os_info`) that pg_upgrade uses in lieu of a context
struct.

Every other .c file in pg_upgrade includes only this header (plus
`postgres_fe.h`); there is no per-module header.

## Role in pg_upgrade

The data-model spine. The orchestrator in `pg_upgrade.c` keeps state
in two `ClusterInfo` globals (old/new). Each phase populates more of
this struct from catalog queries (`info.c`), pg_controldata
(`controldata.c`), or filesystem scans (`tablespace.c`). The header
defines the shape; every other file fills in or reads back fields.

## Key types

- `ClusterInfo` (line 294) — per-cluster aggregate: `pgdata`,
  `pgconfig`, `bindir`, `pgopts`, `sockdir`, `port`, `major_version`,
  `bin_version`, `tablespaces[]`, `controldata`, `template0`,
  `dbarr`, `nsubs`, `sub_retain_dead_tuples`,
  `tablespace_suffix`. Two globals: `old_cluster` and `new_cluster`.
- `ControlData` (line 236) — a private copy of pg_controldata fields
  pg_upgrade cares about, NOT the backend's `ControlFileData`.
  Comment: "we use our own structure to avoid pg_control version
  issues between releases." Includes `chkpnt_nxtxid`,
  `chkpnt_nxtmulti`, `chkpnt_nxtmxoff`, `chkpnt_oldstMulti`,
  `cat_ver` (catversion), `default_char_signedness`,
  `data_checksum_version`. [verified-by-code]
- `DbInfo` (line 203) — per-database: `db_oid`, `db_name`,
  `db_tablespace` (MAXPGPATH), `rel_arr`, `slot_arr`.
- `RelInfo` (line 144) — per-relation: `nspname`, `relname`,
  `reloid`, `relfilenumber`, `indtable` (if index, owning table
  OID), `toastheap` (if toast, owning table OID), `tablespace`.
  Pointer-sharing flags `nsp_alloc` / `tblsp_alloc` for the
  string-interning trick in `info.c::process_rel_infos`. [verified-by-code]
- `FileNameMap` (line 187) — one entry per relation file to transfer:
  `old_tablespace`/`new_tablespace` (+ suffixes), `db_oid`,
  `relfilenumber`, plus `nspname`/`relname` for logging.
- `LogicalSlotInfo` (line 167) — per-slot: name, plugin, two_phase,
  caught_up, invalid, failover.
- `DbLocaleInfo` (line 216) — template0 collation info copied to new
  cluster.
- `transferMode` enum (line 266) — `CLONE`, `COPY`,
  `COPY_FILE_RANGE`, `LINK`, `SWAP`.
- `UserOpts` (line 339) — parsed CLI: `check`, `live_check`,
  `do_sync`, `transfer_mode`, `jobs`, `socketdir`, `sync_method`,
  `do_statistics`, `char_signedness` (-1 / 1 / 0).
- `LogOpts` (line 322) — `internal` FILE pointer, `verbose`,
  `retain`, `rootdir`/`basedir`/`dumpdir`/`logdir`, `isatty`.
- `OSInfo` (line 363) — `progname`, `user` (database superuser),
  `user_specified`, `libraries[]`, `running_cluster` pointer.
- `UpgradeTask` (line 526) — opaque, defined in `task.c`. Built
  incrementally via `upgrade_task_create()` /
  `upgrade_task_add_step()` / `upgrade_task_run()` — runs a list of
  query+callback steps once per user database.

## Catalog version landmarks

Hard-coded `cat_ver` constants gating format conversions:

- `VISIBILITY_MAP_FROZEN_BIT_CAT_VER 201603011` — 9.6 VM all-frozen
  bit. Triggers `rewriteVisibilityMap` in relfilenumber.c.
- `MULTIXACT_FORMATCHANGE_CAT_VER 201301231` — 9.3 multixact format
  change.
- `MULTIXACTOFFSET_FORMATCHANGE_CAT_VER 202512091` — v19 widens
  MultiXactOffset to 64-bit. Triggers `rewrite_multixacts` in
  pg_upgrade.c.
- `LARGE_OBJECT_SIZE_PG_CONTROL_VER 942` — large_object_size added
  to pg_control.
- `JSONB_FORMAT_CHANGE_CAT_VER 201409291` — 9.4 beta JSONB change.
- `DEFAULT_CHAR_SIGNEDNESS_CAT_VER 202502212` — pg_control gains
  `default_char_signedness`.

## Constants

- `DEF_PGUPORT 50432` (line 20) — private-range default. Both old
  and new postmasters started by pg_upgrade listen here unless
  overridden by `-p` / `-P` / `PGPORTOLD` / `PGPORTNEW`. Lives in
  IANA private-port range to avoid colliding with the production
  PG on 5432.
- `MAX_STRING 1024`, `QUERY_ALLOC 8192` — buffer sizes.
- `MESSAGE_WIDTH 62` — column for "ok"/"fail" alignment.
- `GET_MAJOR_VERSION(v) ((v) / 100)` — convert PG_VERSION_NUM to
  major (e.g. 160000 → 1600). All version gates use this idiom.
- `BASE_OUTPUTDIR "pg_upgrade_output.d"` — under the **new**
  cluster's pgdata. Phase D note below.
- `GLOBALS_DUMP_FILE "pg_upgrade_dump_globals.sql"` — the
  pg_dumpall-globals output, which carries `pg_authid` rows
  including hashed passwords.

## Platform branches

Win32 deviates in:

- `pg_mv_file` → `pgrename` (vs `rename`).
- `PATH_SEPARATOR` `\` vs `/`.
- `RM_CMD` / `RMDIR_CMD` for the generated `delete_old_cluster`
  script — `.bat` body with `@DEL /q` / `@RMDIR /s/q` vs POSIX
  `rm -f` / `rm -rf`.
- `SERVER_START_LOG_FILE` is a separate file on Windows because
  postmaster holds the log open across pg_ctl exit (long comment
  lines 51-65).

## Phase D notes

[ISSUE-info-disclosure: `BASE_OUTPUTDIR` "pg_upgrade_output.d" is
created INSIDE the new cluster's `$PGDATA` (line 39 + use in
pg_upgrade.c:289) with mode `pg_dir_create_mode` derived from data-dir
permissions (low)] — Every dump artifact lives there, including
`pg_upgrade_dump_globals.sql` (pg_authid hashes). On a cluster
configured for group-readable data dir
(`GetDataDirectoryCreatePerm` may yield 0750), the
globals-dump file is also group-readable. The pg_dump output IS the
secret store; pg_upgrade just inherits the directory mode. Not a new
vulnerability — same posture as production `$PGDATA`.

[ISSUE-trust-boundary: `FileNameMap.relfilenumber` is sourced from
the old cluster's `pg_class.relfilenode` and used directly to
construct destination paths (medium)] — see also relfilenumber.c
notes. A compromised old cluster's `pg_class` could in principle
inject crafted relfilenumbers; the integer parse in
`relfilenumber.c::parse_relfilenumber` only rejects file**names**
during `--swap`, not the catalog-supplied value here.

[ISSUE-undocumented-invariant: `chkpnt_nxtmxoff` widened to `uint64`
in v19 (line 245) but `chkpnt_nxtxid` / `chkpnt_nxtmulti` still
`uint32` — wraparound semantics not asserted (low)] —
`MULTIXACTOFFSET_FORMATCHANGE_CAT_VER` gates a rewrite. The
xid/multi 32-bit fields are still subject to wraparound; the new
cluster receives the old xid counter via `pg_resetwal -x` and must
not be older than it. No explicit check here that
`new_cluster.controldata.chkpnt_nxtxid <
old_cluster.controldata.chkpnt_nxtxid` is feasible (i.e. that the
new initdb didn't somehow allocate beyond the old).

[ISSUE-undocumented-invariant: `MAX_STRING 1024` used as scratch
buffer for `popen()` output in `adjust_data_dir` (line 22 +
option.c:434) — silently truncates a too-long `postgres -C
data_directory` output (low)] — Resulting `pgdata` could be a prefix
of the real path, which then fails downstream with a less-clear
"directory does not exist".

## Potential issues

[ISSUE-stale-todo: `fopen_priv` macro (line 439) "is no longer
different from fopen()"] — historical fossil. All call sites could
just use `fopen` directly. Not a bug, but a 100+ call site grep target
for cleanup.
