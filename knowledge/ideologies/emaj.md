# emaj — logical "undo" / time-travel for committed data, built entirely in PL/pgSQL as per-table shadow log tables + AFTER-row log triggers, with rollback that replays the log in reverse

> Produced by `pg-extension-anthropologist`. Repo: `dalibo/emaj` @ `master`.
> All `file:line` cites point into that repo (raw.githubusercontent.com), **not** `source/`.
> Fetched 2026-07-19.

## Domain & purpose

E-Maj ("Enregistrement des Mises A Jour" — update recording) does two things core
Postgres has no idiom for: **log every INSERT/UPDATE/DELETE/TRUNCATE on a chosen
set of tables, and then logically *cancel* (rollback) those changes back to a named
point in time** without restoring a physical backup or stopping the cluster
(`README.md:18-31`) `[from-README]`. It is savepoints-for-committed-data:
"efficiently cancel these changes if needed, and reset a tables set to a predefined
stable state" (`README.md:20-21`) `[from-README]`. The unit of protection is a
**tables group**; within a group you set **marks** (named restore points) and later
`emaj_rollback_group('grp','mark')` to undo everything after that mark.

The reason to document it: core Postgres WAL is a *physical redo* log — it can roll
a cluster forward to a consistent state during crash recovery / PITR, but it is not
logically replayable *backwards*, and once a transaction commits its effects are
permanent (MVCC dead tuples are garbage, not an undo image). E-Maj reconstructs a
logical UNDO log in user space, per row, via triggers, because the engine offers no
such thing. And it does so with **zero C**: the entire framework is PL/pgSQL and SQL.

## How it hooks into PG

- **No C module.** `emaj.control` has no `module_pathname`; it declares only
  `schema = 'emaj'`, `superuser = true`, `relocatable = false`, and
  `requires = 'dblink, btree_gist'` (`emaj.control:4-10`) `[verified-by-code]`. The
  whole extension body is `sql/emaj--devel.sql` — ~15,700 lines, 216 functions all
  `LANGUAGE plpgsql`/`LANGUAGE sql`, and a grep for `LANGUAGE c` / `$libdir` / `.so`
  returns nothing (`emaj--devel.sql`, whole file) `[verified-by-code]`. A framework
  this large with no compiled component is itself the headline divergence.
- **Per-table log triggers.** For each protected table `_create_tbl` builds an
  `AFTER INSERT OR UPDATE OR DELETE ... FOR EACH ROW` trigger `emaj_log_trg` plus a
  `BEFORE TRUNCATE ... FOR EACH STATEMENT` trigger `emaj_trunc_trg`
  (`emaj--devel.sql:3475-3482`) `[verified-by-code]`.
- **SECURITY DEFINER everywhere.** Log function, trigger functions, and the
  worker functions are `SECURITY DEFINER SET search_path = pg_catalog, pg_temp`
  (e.g. `_create_tbl` at `emaj--devel.sql:3316-3317`, the generated log function at
  `:3473`, `_truncate_trigger_fnct` at `:2197-2198`) so unprivileged application
  roles can write emaj's internal tables while emaj objects stay owned by
  `emaj_adm` `[verified-by-code]`.
- **Event triggers** protect emaj's own objects from DDL (see divergence 4).
- **dblink** is a hard prerequisite used as an *autonomous-transaction* channel: a
  rollback is one big transaction, and dblink lets `_rlbk_session_exec` write
  progress rows that commit independently so the operation can be monitored
  (`emaj.control:10`; `emaj--devel.sql:906-910`, progress writes at `:10276-10281`)
  `[verified-by-code]`. `btree_gist` supports the GiST exclusion/range indexing on
  emaj's time-range bookkeeping.

## Where it diverges from core idioms

**1. Undo-in-userspace instead of engine-owned WAL.** Core has redo-only physical
WAL and MVCC (dead tuples, not an undo image). E-Maj keeps, per protected table, a
**shadow log table** created as `CREATE TABLE <log> (LIKE <app_table>, emaj_verb,
emaj_tuple, emaj_gid, emaj_changed, emaj_txid, emaj_user, ...)`
(`emaj--devel.sql:3401-3410`) `[verified-by-code]`. The log function writes `OLD` on
DELETE, `OLD` on UPDATE, `NEW` on INSERT, and *both* `OLD` and `NEW` on UPDATE, each
tagged with `emaj_verb` ∈ {INS,UPD,DEL,TRU} and `emaj_tuple` ∈ {OLD,NEW}
(`emaj--devel.sql:3460-3471`) `[verified-by-code]`. This is a hand-rolled write-ahead
UNDO log at the row level, in ordinary heap tables that are themselves WAL-logged by
core — E-Maj rides core's redo to make its undo durable.

**2. Trigger-based CDC with a global monotonic ordering sequence.** Every log row
gets `emaj_gid BIGINT DEFAULT nextval('emaj.emaj_global_seq')`
(`emaj--devel.sql:3404`), a single database-wide sequence deliberately created with
no cache / no cycle so that `nextval` values are strictly time-ordered across *all*
log tables — the comment is explicit that this ordering is used for rollback "So
this order is not based on system time that can be unsafe"
(`emaj--devel.sql:214-221`) `[verified-by-code/from-comment]`. Core's own change
stream (logical decoding) reads WAL; E-Maj instead materializes an ordered CDC feed
in user tables keyed by one shared sequence.

**3. Logical rollback = replay the log table in reverse, bounded by a global-seq
window.** `_rlbk_tbl` is the heart. Given `(minGlobalSeq, maxGlobalSeq]` it:
(a) builds a temp table of the distinct primary keys touched in that window with
their earliest `emaj_gid` (`emaj--devel.sql:4954-4959`); (b) `DELETE`s every current
app-table row for those PKs — removing rows inserted or updated in the window
(`:4963-4964`); (c) re-`INSERT`s the pre-image by selecting the `emaj_tuple = 'OLD'`
rows from the log table for those same keys and window (`:4972-4980`)
`[verified-by-code]`. So an inserted row is deleted, and a deleted/updated row is
restored from its logged OLD image — undo by replaying the log backwards, entirely
in SQL. The window bound is the global sequence value captured at the target mark,
not a timestamp.

- **Unlogged vs logged rollback.** For an *unlogged* rollback the log triggers are
  disabled and the replayed-away log rows are physically deleted by `_delete_log_tbl`
  (`emaj--devel.sql:4996-5012`, only called "for unlogged rollbacks", `:5000`)
  `[verified-by-code]`. A *logged* rollback keeps triggers enabled (the rollback's own
  DELETE/INSERT are themselves logged) so the rollback is itself rollback-able — it
  sets a mark before and after and records the target in
  `mark_logged_rlbk_target_mark` (`emaj--devel.sql:454`, `rlbk_is_logged` at
  `:526`; `_rlbk_tbl` header note `:4917`) `[verified-by-code]`. This "undo that can
  be undone" has no analog in core.

**4. Catalog-emulation via emaj's own bookkeeping tables, protected by event
triggers.** There is no core catalog relationship binding a log table to its app
table; E-Maj keeps that mapping itself in `emaj_relation` (schema, tblseq, group,
`rel_kind`, log schema/table/sequence/function, a `rel_time_range` int8range)
(`emaj--devel.sql:339-378`) `[verified-by-code]`, groups in `emaj_group`
(`group_is_rollbackable`, `group_is_logging`, `emaj--devel.sql:295-297`), marks in
`emaj_mark` (`emaj--devel.sql:443-459`), and per-mark snapshots in `emaj_sequence` /
`emaj_table` / `emaj_seq_hole`. Because these relationships live only in emaj's
tables, a stray `DROP`/`ALTER` would silently corrupt them — so E-Maj installs
**event triggers** to defend its invariants: `emaj_sql_drop_trg` (on `sql_drop`)
raises an exception on any attempt to drop a protected app table/sequence/schema, a
log table/sequence/function, an emaj trigger, or the PK of a rollbackable table
(`emaj--devel.sql:14754-14895`, created at `:15408-15411`) `[verified-by-code]`; and
`emaj_table_rewrite_trg` (on `table_rewrite`) blocks any ALTER that rewrites a
protected app table or a log table (`emaj--devel.sql:14905-14946`, created at
`:15416-15418`) `[verified-by-code]`. A third, `emaj_protection_trg`, guards the emaj
schema/extension itself. E-Maj thus polices referential integrity that core would
enforce with real catalog dependencies.

**5. Sequences are snapshotted by value, not rolled back by log.** Sequences are
non-transactional, so there is no log of `nextval` calls to replay. Instead
`_set_mark_groups_exec` records each application sequence's full state
(`sequ_last_val`, increment, min/max, cache, is_cycled, is_called) into
`emaj_sequence` at mark time (`emaj--devel.sql:8097-8109`; table at `:466-481`)
`[verified-by-code]`. Rollback then diffs current-vs-mark state and emits a single
`ALTER SEQUENCE` to restore it: `_rlbk_seq` → `_build_alter_seq`
(`emaj--devel.sql:5034-5077`, `5079-5093`) `[verified-by-code]`. Log *sequences* are
never rolled back; the gap left by deleted log rows is instead recorded in
`emaj_seq_hole` so statistics stay accurate (`emaj--devel.sql:5014-5028`,
`500-507`) `[verified-by-code]`.

## Notable design decisions (cited)

- **The generated log function is per-table string-built PL/pgSQL.** `_create_tbl`
  assembles the trigger function body by concatenation and `EXECUTE`s the
  `CREATE FUNCTION` (`emaj--devel.sql:3455-3473`); it increments the table's own log
  sequence at entry and relies on the log table's `emaj_gid DEFAULT nextval(global_seq)`
  for global ordering (`:3457-3459`) `[verified-by-code]`.
- **Triggers toggle between DISABLED / ENABLE ALWAYS depending on group state.** In a
  logging group the log + truncate triggers are set `ENABLE ALWAYS` so they fire even
  under `session_replication_role = replica` during rollback; in an idle group they
  are `DISABLE`d until `emaj_start_group` (`emaj--devel.sql:3483-3495`)
  `[verified-by-code]`. Unlogged rollback additionally flips
  `SET session_replication_role = 'replica'` around the replay to suppress app
  triggers/FK actions (`emaj--devel.sql:4941-4943`, `4985-4987`) `[verified-by-code]`.
- **TRUNCATE is logged by copying the whole table into the log.** `_truncate_trigger_fnct`
  writes a `TRU`/`''` marker row, then `INSERT INTO <log> SELECT *, 'TRU','OLD' FROM
  ONLY <table>` before the truncate proceeds, and bumps the log sequence by the row
  count (`emaj--devel.sql:2213-2234`) `[verified-by-code]` — so even TRUNCATE is
  reversible, which core TRUNCATE (WAL-logged as a relfilenode swap, no per-row image)
  is not.
- **Marks pin a global-sequence position, not a clock.** A mark stores only
  `mark_time_id` referencing `emaj_time_stamp` (`emaj--devel.sql:443-459`); the
  rollback window `(minGlobalSeq, maxGlobalSeq]` is derived from `time_last_emaj_gid`
  at that time_id (`emaj--devel.sql:10258-10264`, `10320-10331`) `[verified-by-code]`.
- **The mark also snapshots table stats + log-sequence high-water mark** into
  `emaj_table` (reltuples, relpages, `tbl_log_seq_last_val`) so change counts between
  marks can be computed cheaply (`emaj--devel.sql:8152-8161`, table at `:486-496`)
  `[verified-by-code]`.
- **`emaj_rollback_group` is a thin wrapper** over `_rlbk_groups(..., isLoggedRlbk =>
  FALSE, ...)`; the logged variant flips one boolean (`emaj--devel.sql:8925-8937`)
  `[verified-by-code]`.
- **Rollback is planned then executed in steps.** `_rlbk_groups` /
  `_rlbk_session_exec` drive a plan of typed steps (`RLBK_TABLE`, `DELETE_LOG`,
  `RLBK_SEQUENCES`, `DIS_LOG_TRG`, `DROP_FK`/`ADD_FK`, `DIS_APP_TRG`, ...) stored in
  `emaj_rlbk_plan`, supporting multi-session parallel rollback via UNLOGGED (not TEMP)
  scratch tables usable under 2PC (`emaj--devel.sql:10265-10344`, `4948-4952`)
  `[verified-by-code]`.

## Links into corpus

- `[[temporal_tables]]` — the sibling "core feature core lacks, rebuilt from
  triggers" ideology: temporal_tables reconstructs SQL:2011 system-versioning via a C
  BEFORE-trigger that SPI-inserts prior row images into a history table. Same
  shadow-history-table-via-trigger shape, but temporal_tables is C over the public
  trigger/SPI API while E-Maj is 100% PL/pgSQL and adds *reverse replay* (undo), which
  temporal_tables does not.
- `[[pg_ivm]]` — also maintains a derived shadow table from AFTER-triggers; contrast
  the direction (incremental *forward* materialized-view maintenance vs E-Maj's
  *backward* undo replay).
- `[[pg_dirtyread]]` / `[[pg_squeeze]]` / `[[pg_repack]]` — other extensions that
  reach around MVCC/storage semantics core keeps closed.
- `[[knowledge/subsystems/access-transam]]` and `[[knowledge/idioms/wal-record-construction]]`
  — the redo-only physical WAL that E-Maj's userspace UNDO log exists to work around;
  E-Maj's log tables are themselves WAL-logged by this subsystem.
- `[[knowledge/idioms/trigger-firing-order]]`, `[[knowledge/idioms/event-trigger-firing]]`,
  `[[knowledge/idioms/ddl-deparse-via-event-triggers]]` — the AFTER-row/BEFORE-TRUNCATE
  log triggers and the `sql_drop` / `table_rewrite` event triggers that police emaj's
  objects.
- `[[knowledge/subsystems/contrib-dblink]]` — the autonomous-transaction channel emaj
  requires for rollback-progress monitoring.

Core concepts referenced in prose without wiki links: `session_replication_role`,
`ALTER SEQUENCE`, `SECURITY DEFINER`, `pg_event_trigger_dropped_objects()`,
`pg_event_trigger_table_rewrite_oid()`.

## Sources

Fetched 2026-07-19 (branch `master`):

- `https://raw.githubusercontent.com/dalibo/emaj/master/emaj.control` → HTTP 200
  (10 lines; no `module_pathname`, `requires = dblink, btree_gist`).
- `https://raw.githubusercontent.com/dalibo/emaj/master/META.json` → HTTP 200
  (abstract/tags: "trigger-based logging", "logical rollback", "flashback", CDC).
- `https://raw.githubusercontent.com/dalibo/emaj/master/README.md` → HTTP 200
  (78 lines; objectives, cancel-changes semantics).
- `https://raw.githubusercontent.com/dalibo/emaj/master/sql/emaj--devel.sql` →
  HTTP 200 (15,727 lines; the entire extension body — deep-read the log-table +
  trigger creation `_create_tbl`, the generated log function, `_truncate_trigger_fnct`,
  `_rlbk_tbl` / `_delete_log_tbl` / `_rlbk_seq` / `_build_alter_seq`,
  `_set_mark_groups_exec`, `_rlbk_session_exec`, the two protection event-trigger
  functions, and the catalog-emulation tables `emaj_group` / `emaj_relation` /
  `emaj_mark` / `emaj_sequence` / `emaj_table` / `emaj_seq_hole`). Grep-verified
  zero `LANGUAGE c` / `$libdir` / `.so` occurrences.

No 404 gaps; the four manifest paths all returned 200.
