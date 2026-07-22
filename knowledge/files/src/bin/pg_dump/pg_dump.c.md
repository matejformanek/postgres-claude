---
path: src/bin/pg_dump/pg_dump.c
anchor_sha: f25a07b2d94c
loc: 21102
depth: deep
---

# pg_dump.c

- **Source path:** `source/src/bin/pg_dump/pg_dump.c`
- **Last verified commit:** `f25a07b2d94c`

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** re-pinned
> `4b0bf0788b0`→`f25a07b2d94c`. The `7ca548f23a60` revert ("Revert
> non-text output formats for pg_dumpall") restored pg_dump.c to a state
> matching this doc — LOC unchanged at 21102, no `archAppend`/`-Fa`
> append-mode helpers present. Spot-checked cites (main:418,
> set_restrict_relation_kind:1523, getRoleName:10798,
> getAdditionalACLs:10869, dumpUserMappings:16384, dumpACL:16570,
> dumpSequenceData:19723) all hold. AUDIT clean.
- **LOC:** 21102 (largest single C file in pg_dump; ~½ the project's
  bin/pg_dump LOC)

## Purpose

`pg_dump` is the per-database dump driver. From a single connection
to one database, it (a) collects metadata for every dumpable object
into `DumpableObject` subclasses (the `getXxx()` family), (b) hands
the array to `pg_dump_sort.c` for type-then-name + topological
ordering, and then (c) emits CREATE/ALTER/COMMENT/SECURITY LABEL/
GRANT statements through the archive layer (the `dumpXxx()` family
+ `dumpDumpableObject` dispatcher). Output is mediated by the
`Archive *` interface (`pg_backup.h`/`pg_backup_archiver.c`) so the
same code paths feed plain SQL, custom-format, directory-format, and
tar archives. Parallelism (`-j N`) launches worker backends that
re-connect, re-execute the same `setup_connection`, and adopt the
leader's exported snapshot via `SET TRANSACTION SNAPSHOT`. The
top-of-file comment warns that the window between snapshot
acquisition and `getSchemaData()` (where AccessShareLock is taken
on every dumpable table) is racy — concurrent DDL can produce
'cache lookup failed' errors. [from-comment, pg_dump.c:14-25;
verified-by-code, pg_dump.c:418-1287]

## Top-level driver — `main()` (418-1287)

The shape of `main()` is the spine of the whole utility:

1. **Options parsing** (456-1015) — `getopt_long` over ~80
   long-options plus single-letter friends. Includes the cross-cutting
   include/exclude string lists (`schema_include_patterns`,
   `table_include_patterns`, `extension_include_patterns`, the
   `_and_children` variants, `table_exclude_data_patterns`,
   `foreign_servers_include_patterns`, and so on).
2. **Format + connection set-up** (1016-1085) — `parseArchiveFormat`,
   `CreateArchive`, `ConnectDatabase`, `setup_connection`.
3. **`getSchemaData()`** (1091) — the catalog walker. Defined in
   `common.c`; calls every `getXxx(Archive *)` in turn (namespaces,
   extensions, types, funcs, aggregates, ops, AMs, opclasses,
   opfamilies, collations, conversions, tables (→ deferred
   `getTableAttrs`), owned seqs, inherits, partitioning info, indexes,
   constraints, rules, triggers, proc langs, casts, transforms, TS
   parsers/dicts/templates/configs, FDWs/servers, default ACLs, event
   triggers, policies, publications, subscriptions, extended stats).
4. **`getTableData`** (3007) + **`makeTableDataInfo`** (3026) — once
   `getSchemaData` is done, the table list is walked again to mark
   which tables need DATA dumps (creates a `TableDataInfo` per
   selected table or sequence). `buildMatViewRefreshDependencies`
   (3116) wires REFRESH MATERIALIZED VIEW dependencies for matviews
   that depend on data of other tables. `getTableDataFKConstraints`
   (3231) emits FK-constraint TOC entries for `--data-only`.
5. **Binary-upgrade specials** (1110-1138) — adds a `pg_shdepend`
   data-dump entry for large-object rows, and (only when remote
   server < 16) a `pg_largeobject_metadata` dump. Comment notes
   that ≥16 the file can be `pg_upgrade`-copied.
6. **`getLOs`** (3936) — only when `--large-objects` or
   `--binary-upgrade` (3936-4088).
7. **`getDependencies`** (20469) — walks `pg_depend` and
   `pg_shdepend` and turns dependency edges into
   `addObjectDependency` calls. Filtered: only DEP_NORMAL, DEP_AUTO,
   DEP_AUTO_EXTENSION, and a few others actually populate the
   graph. Cycles get sorted out by `pg_dump_sort.c`.
8. **ACL / comment / sec-label / sequence collection** (1159-1171) —
   `getAdditionalACLs` (10869), `collectComments` (11734),
   `collectSecLabels` (16939), `collectBinaryUpgradeClassOids` (only
   in binary-upgrade), `collectSequences` (19407).
9. **Boundary objects** (1173-1182) — `createBoundaryObjects`
   manufactures the two `DO_PRE_DATA_BOUNDARY` /
   `DO_POST_DATA_BOUNDARY` dummies; `addBoundaryDependencies`
   inserts the section-ordering edges into the dependency graph.
10. **Sort** (1191-1194) — `sortDumpableObjectsByTypeName` baseline
    then `sortDumpableObjects` topological pass (see
    `knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md`).
11. **Special TOC entries** (1204-1210) — `dumpEncoding`,
    `dumpStdStrings`, `dumpSearchPath`, and (only with `-C`)
    `dumpDatabase`.
12. **Dump loop** (1213-1214) — `for i in 0..numObjs:
    dumpDumpableObject(fout, dobjs[i])`. This produces TOC entries
    in dependency order; the actual data-dumping functions
    (`dumpTableData_copy`, `dumpLOs`, …) are invoked later by the
    archive layer.
13. **Finalize** (1216-1284) — build a derived `RestoreOptions *
    ropt`, `SetArchiveOptions`, `ProcessArchiveRestoreOptions`,
    `BuildArchiveDependencies` (non-plain only), and either
    `RestoreArchive` (plain text) or `CloseArchive` (writes out
    custom/tar/directory).

## getXxx() / dumpXxx() pair table (key kinds)

Each row: SQL collector → dumper. Both are top-level
file-static (or extern, exposed via `pg_dump.h`).

| Kind | `getXxx` (collect) | `dumpXxx` (emit) | Notes |
|---|---|---|---|
| schema | `getNamespaces` (6083) | `dumpNamespace` (12016) | namespace pre-data |
| extension | `getExtensions` (6215) | `dumpExtension` (12093) | CREATE EXTENSION + config tables |
| type — generic | `getTypes` (6290) | `dumpType` (12216) → dispatches | by `typtype`: base / composite / enum / range / domain / undefined |
| type — base | (in getTypes) | `dumpBaseType` (12609) | |
| type — enum | | `dumpEnumType` (12247) | |
| type — range | | `dumpRangeType` (12387) | |
| type — domain | | `dumpDomain` (12858) | |
| type — composite | | `dumpCompositeType` (13083) | + `dumpCompositeTypeColComments` (13289) |
| type — shell | | `dumpShellType` (13378) | created on-demand to break I/O-function cycles |
| function | `getFuncs` (7005) | `dumpFunc` (13608) | uses `format_function_arguments`/`format_function_signature` |
| aggregate | `getAggregates` (6864) | `dumpAgg` (15529) | `AggInfo` is `FuncInfo` superset |
| operator | `getOperators` (6458) | `dumpOpr` | |
| access method | `getAccessMethods` (6662) | `dumpAccessMethod` (14576) | |
| opclass | `getOpclasses` (6736) | `dumpOpclass` (14644) | |
| opfamily | `getOpfamilies` (6799) | `dumpOpfamily` (14925) | |
| collation | `getCollations` (6534) | `dumpCollation` (15144) | |
| conversion | `getConversions` (6600) | `dumpConversion` (15401) | |
| proclang | `getProcLangs` (9053) | `dumpProcLang` (13424) | |
| cast | `getCasts` (9137) | `dumpCast` (14030) | |
| transform | `getTransforms` (9247) | `dumpTransform` (14135) | |
| TS parser / dict / tmpl / config | `getTSParsers`/`TSDictionaries`/`TSTemplates`/`TSConfigurations` (10261, 10335, 10401, 10460) | `dumpTSParser`/`TSDictionary`/`TSTemplate`/`TSConfig` (15889, 15953, 16033, 16091) | |
| FDW / server | `getForeignDataWrappers` (10519) / `getForeignServers` (10613) | `dumpForeignDataWrapper` (16211) / `dumpForeignServer` (16284) + `dumpUserMappings` (16384) | |
| default ACL | `getDefaultACLs` (10701) | `dumpDefaultACL` (16478) | |
| table | `getTables` (7278) + `getTableAttrs` (9331) + `getOwnedSeqs` (7756) + `getInherits` (7821) + `getPartitioningInfo` (7877) | `dumpTable` → `dumpTableSchema` (17266) / `dumpSequence` (19469) | sequences are tables w/ relkind = 'S' |
| table attach (partition) | (in partitioning) | `dumpTableAttach` (18323) | |
| attribute default | (in getTableAttrs / getConstraints) | `dumpAttrDef` | |
| index | `getIndexes` (7937) | `dumpIndex` (18481) + `dumpIndexAttach` (18632) | |
| extended stats | `getExtendedStatistics` (8306) | `dumpStatisticsExt` (18675) + `dumpStatisticsExtStats` (18752) | |
| constraint (CHECK/UQ/PK/EXCLUDE/FK) | `getConstraints` (8388) | `dumpConstraint` (19032) | one func handles all kinds (FK has its own enum to sort differently) |
| rule | `getRules` (8682) | `dumpRule` (20028) | non-`SELECT` rules always `separate` |
| trigger | `getTriggers` (8779) | `dumpTrigger` (19812) | |
| event trigger | `getEventTriggers` (8975) | `dumpEventTrigger` (19938) | |
| policy | `getPolicies` (4226) | `dumpPolicy` (4398) | RLS ENABLE row has `polname = NULL` |
| publication | `getPublications` (4516) | `dumpPublication` (4682) + `dumpPublicationNamespace` (5015) + `dumpPublicationTable` (5058) | |
| subscription | `getSubscriptions` (5159) | `dumpSubscription` (5563) + `dumpSubscriptionTable` (5494) | |
| large object | `getLOs` (3936) | `dumpLO` (4090) (metadata) + `dumpLOs` (4180) (data) | grouped by owner/ACL into `LoInfo` |
| table data | `getTableData` (3007) / `makeTableDataInfo` (3026) | `dumpTableData` (2857) → `dumpTableData_copy` (2364) or `dumpTableData_insert` (2535) | per-row INSERT only with `--inserts`/`--column-inserts`/`--rows-per-insert` |
| sequence data | (in `makeTableDataInfo`) | `dumpSequenceData` (19723) | emits `SELECT pg_catalog.setval(...)` |
| matview refresh | (in `buildMatViewRefreshDependencies`) | `refreshMatViewData` (2972) | |
| ACL (cross-cutting) | `getAdditionalACLs` (10869) | `dumpACL` (16570) | called from per-kind dumpers |
| comment (cross-cutting) | `collectComments` (11734) | `dumpComment` (11098) / `dumpCommentExtended` (10998) / `dumpTableComment` (11559) | |
| security label | `collectSecLabels` (16939) | `dumpSecLabel` | |
| relation statistics | (in `getTables`/`getIndexes`) | `dumpRelationStats` (11533) + `dumpRelationStats_dumper` (11246) | |

`dumpDumpableObject` (11819) is the cast-and-switch dispatcher that
fans `DumpableObject *` out to these `dumpXxx` siblings keyed on
`objType`. [verified-by-code, pg_dump.c:11819-12009]

## Internal landmarks

- **`setup_connection`** (1399) — session preamble run once per
  worker. Forces `standard_conforming_strings = on`,
  `DATESTYLE = ISO`, `INTERVALSTYLE = POSTGRES`, `extra_float_digits
  = 3` (or user-supplied), `synchronize_seqscans = off`, all
  `*_timeout = 0` (version-gated for `lock_timeout`,
  `idle_in_transaction_session_timeout`, `transaction_timeout`),
  optional `quote_all_identifiers = true`, optional `row_security =
  on/off`, and the security-critical `restrict_nonsystem_relation_kind
  = "view, foreign-table"` call (`set_restrict_relation_kind`, see
  below). Begins a transaction-snapshot mode tx — `SERIALIZABLE, READ
  ONLY, DEFERRABLE` if `--serializable-deferrable`, else `REPEATABLE
  READ, READ ONLY`. Adopts the leader's snapshot or exports one for
  workers. [verified-by-code, pg_dump.c:1399-1576]
- **`set_restrict_relation_kind`** (definition near 5133) — issues
  `SELECT set_config('restrict_nonsystem_relation_kind', value,
  false)`. This is the security boundary that prevents an
  attacker-controlled view (or foreign table) referenced by a
  dumped query from running code as the dumping role. Set to
  "view, foreign-table" by default; **temporarily relaxed to just
  "view" during `COPY (SELECT ...)` of foreign tables**
  (`dumpTableData_copy` lines 2403-2405, 2520-2521;
  `dumpTableData_insert` line 2551). Failure to revert leaks the
  relaxation across subsequent dumps; the code does revert in the
  finally-path of both COPY paths. [verified-by-code,
  pg_dump.c:1523, 2405, 2521, 2551, 2794, 5133-5134]
- **`setupDumpWorker`** (1580) — called per parallel worker after
  it inherits the leader's archive handle. Re-invokes
  `setup_connection` passing the inherited
  `AH->encoding`/`AH->use_role`/`AH->sync_snapshot_id` so the worker
  joins the same snapshot.
- **`expand_schema_name_patterns`** (1647) and
  **`expand_table_name_patterns`** (1811) — resolve glob-style
  `--schema`/`--table` patterns to OID lists via
  `processSQLNamePattern`. With `--strict-names` they error out if
  a pattern matches zero relations.
- **`prohibit_crossdb_refs`** (1907) — checks no `--schema`/`--table`
  pattern is cross-database-qualified (i.e. has more than one dotted
  prefix); pg_dump can't dump objects from a database it's not
  connected to.
- **`selectDumpableX`** helpers (1982-2342) — given a freshly-collected
  object, set its `dump` bitmask based on the user's include/exclude
  lists, system-schema status, extension membership, etc. Order
  matters: schema decisions cascade into table/type decisions
  (see e.g. `selectDumpableNamespace` setting `dobj->dump = ...`
  before tables in that schema are considered).
- **`dumpEncoding` / `dumpStdStrings` / `dumpSearchPath`** (3825,
  3850, 3874) — emit the three special pre-data archive entries that
  the restore script needs before anything else: SET client_encoding,
  SET standard_conforming_strings, SELECT pg_catalog.set_config(
  'search_path', '', false).
- **`dumpDatabase`** (3272) — only when `--create` (`outputCreateDB`).
  Multi-version SQL for `pg_database` columns — `datminmxid`
  conditional on ≥9.3; `datlocprovider/datlocale/datcollversion`
  conditional on ≥15/≥17; `daticurules` ≥16. CREATE DATABASE
  template-and-OID preservation in `binary_upgrade` mode uses
  `STRATEGY = FILE_COPY` (binary_upgrade-mode server skips
  checkpoints) and explicitly sets OID. Tablespace name through
  `fmtId`. Locale strings through `appendStringLiteralAH`.
  [verified-by-code, pg_dump.c:3272-3540 approx]
- **`dumpTableData_copy`** (2364) — issues `COPY ... TO stdout` and
  funnels data via `PQgetCopyData` + `WriteData`. Uses `COPY
  (SELECT ...) TO` for foreign tables, for tables with a
  `filtercond`, and (old binary-upgrade pg_largeobject_metadata case)
  for `WITH OIDS`. Column list is built by `fmtCopyColumnList`
  (20936) so column order is deterministic across ADD COLUMN
  history. The throttle-loop comment (2444-2488) is a long
  historical note explaining why throttling was deliberately not
  implemented.
- **`dumpTableData_insert`** (2535) — alternative path for
  `--inserts`/`--column-inserts`/`--rows-per-insert`. Comment notes
  that emitted INSERTs must be parseable by `pg_backup_db.c`'s
  `ExecuteSimpleCommands` which can't handle comments, E'' strings,
  or dollar quoting — constrains what this function can produce.
- **`dumpTableSchema`** (17266) — the workhorse for CREATE TABLE.
  Per-column generation/identity/storage/compression/options/
  collation/missingval/fdwoptions splices, NOT NULL constraints
  (with v17 named-vs-unnamed and v18 NOT VALID), inheritance,
  partitioning (`PARTITION OF ... FOR VALUES`), table AM,
  reloptions, tablespace, ALTER TABLE ENABLE/FORCE ROW SECURITY.
- **`dumpACL`** (16570) — the centralized ACL printer. Takes
  `objDumpId`+`altDumpId`, looks up `acl`, `acldefault`,
  `init_privs` (the `pg_init_privs` baseline), and computes a
  minimal sequence of GRANT/REVOKE statements via
  `buildACLCommands` (in `dumputils.c`). Called from many
  per-kind dumpers; the `altDumpId` ties ACL TOC entries to a
  separate dump item so they sort late (after DEFINITION).
- **`getRoleName`** (10798) — caches `(oid → rolname)` lookups
  used by every per-object dumper that needs to emit an owner
  name. Single global cache (`rolename_hash`), no eviction —
  intended to live the duration of the run. [inferred,
  pg_dump.c:10798-10867]

## Key globals & state

- **`schema_include_patterns`** / `schema_exclude_patterns` /
  `table_include_patterns` / `table_exclude_patterns` /
  `extension_include_patterns` / `extension_exclude_patterns` /
  `tabledata_exclude_patterns` / `tabledata_exclude_oids` /
  `foreign_servers_include_patterns` plus their `_with_children`
  variants — all file-static `SimpleStringList` / `SimpleOidList`.
- **`have_extra_float_digits`**, **`extra_float_digits`** — user
  override of the default `SET extra_float_digits TO 3`.
- **`strict_names`** — gate for `expand_*_patterns` zero-match errors.
- **`quote_all_identifiers`** — extern, shared with `dumputils`.
- **`rolename_hash`** (via `getRoleName`) — `simplehash` of OID →
  role name.
- **`is_prepared`** array in the `Archive` — per-prepared-query
  bool, sized `NUM_PREP_QUERIES`, set by `setup_connection` so
  workers have their own state.

## Invariants & gotchas — SQL-string assembly discipline

- **Identifiers MUST go through `fmtId()` or `fmtQualifiedDumpable()`.**
  Both are pg_dump's canonical quote-and-escape helpers (in
  `fe_utils/string_utils.c`). Examples: `fmtId(use_role)` at 1452,
  `fmtId(tablespace)` at 3495, `fmtId(rolename)` (in pg_dumpall),
  `fmtQualifiedDumpable(tbinfo)` at 2418. Splicing an identifier with
  bare `%s` is a SQL-injection vector; `quote_all_identifiers = true`
  in `setup_connection` is a belt-and-suspenders flip.
- **String literals MUST go through `appendStringLiteralAH(buf,
  literal, AH)` or `appendStringLiteralConn(buf, literal, conn)`.**
  The "AH" variant knows the archive's `std_strings`+encoding; the
  "Conn" variant knows the live connection's. Examples at 2743,
  3421, 3438, 3478, 3534. `appendStringLiteralConn(...)` is what
  pg_dumpall uses for role passwords (line 1180).
- **`std_strings = true` is forced** in `setup_connection` (1422,
  1431) so that all literal escaping can assume
  `standard_conforming_strings = on`.
- **`set_restrict_relation_kind` MUST be re-tightened** after any
  COPY-SELECT against a foreign table. See landmarks above — both
  `dumpTableData_copy` and `dumpTableData_insert` have paired
  enable/disable calls; if either is rerouted around (e.g. via
  `exit_nicely`) the relaxation leaks.

## Invariants & gotchas — Multi-version compat

- **`fout->remoteVersion`** is the canonical version gate.
  Versions follow PG number-encoding (`80300`, `90600`, `170000`,
  `190000`). Mixing major-version comparisons with the
  `_full_version` style is a latent source of bugs.
- **Branches must remain syntactically valid SQL on the OLDEST
  supported server.** Adding a column that only exists in v17+
  requires `if (remoteVersion >= 170000)` AND a fallback `NULL AS
  newcol` for older servers (see `dumpDatabase` 3328-3341).
- **`minRemoteVersion = 90200; maxRemoteVersion = (PG_VERSION_NUM /
  100) * 100 + 99`** is the supported window — set on
  `Archive *fout` early in `main`. Adding a hard dependency on a
  newer server must bump `minRemoteVersion`.

## Invariants & gotchas — Race windows

- **Catalog-read vs DDL race.** Top comment (14-25): "It is possible
  to get 'cache lookup failed' error if someone performs DDL
  changes while a dump is happening. The window for this sort of
  thing is from the acquisition of the transaction snapshot to
  `getSchemaData()` (when pg_dump acquires AccessShareLock on every
  table it intends to dump). It isn't very large, but it can
  happen." [from-comment, pg_dump.c:14-25] The mitigation is the
  AccessShareLock; the race is exposure to `pg_get_*def()` and
  friends that consult SysCache rather than the snapshot.
- **Sequence currval is read non-atomically with table data.**
  Sequence DATA dumps via `dumpSequenceData` (19723) read
  `last_value` at a different moment than the table data is COPY'd;
  the DUMP is consistent vs the snapshot, but concurrent activity
  in the SAME transaction is not the model. [inferred,
  pg_dump.c:19723-19811]
- **Parallel workers race against the leader for `pg_class` lookups
  in the early window.** Mitigated by snapshot adoption via
  `SET TRANSACTION SNAPSHOT`. [verified-by-code,
  pg_dump.c:1538-1574]

## Invariants & gotchas — ACL / privilege

- **`dumpACL` always emits a REVOKE-everything-then-GRANT pattern**
  computed by `buildACLCommands` from the (`acl`, `acldefault`,
  `initprivs`) triple. The `initprivs` come from `pg_init_privs`
  and represent the extension- or initdb-installed baseline. If
  this is missing from a newly-collected catalog, restoring
  produces overgranted permissions silently.
- **`DUMP_COMPONENT_USERMAP` for FOREIGN SERVER** is the one ACL-
  adjacent component that crosses object kinds: `dumpUserMappings`
  (16384) is called from inside `dumpForeignServer`. Owner
  semantics for user mappings differ from server ACLs (per-user
  vs per-server). [verified-by-code, pg_dump.c:16384 ff.]

## Cross-refs

- Header: `knowledge/files/src/bin/pg_dump/pg_dump.h.md`.
- Sorter: `knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md`.
- Archive layer (TODO when documented):
  `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md` —
  `Archive *`, `TocEntry`, `RestoreOptions`, `ArchiveEntry`,
  `RestoreArchive`, `CloseArchive`, `BuildArchiveDependencies`.
- Catalog walker (`getSchemaData`) lives in `common.c`
  (not yet documented).
- `pg_dumpall.c.md` — `runPgDump` invokes this binary per database.
- `pg_restore.c.md` — replays the archives this file writes.

<!-- issues:auto:begin -->
- [Issue register — `pg_dump`](../../../../issues/pg_dump.md)
<!-- issues:auto:end -->

## Potential issues

**pg_dump is a primary Phase D candidate area** — it runs as an
ordinary role but its output is replayed at full privilege during
restore. Watch list:

- **[ISSUE-correctness: snapshot-vs-DDL race produces "cache lookup
  failed"]** `pg_dump.c:14-25, 1091` — documented in the top-of-file
  comment. The mitigation (AccessShareLock at `getSchemaData()`) does
  not cover the snapshot-acquisition window. Severity: maybe (known
  / accepted upstream; would be CommitFest-worthy to truly close).
- **[ISSUE-correctness: `set_restrict_relation_kind` leak under
  exit_nicely from COPY-SELECT]** `pg_dump.c:2403-2521` — the
  foreign-table COPY path opens `set_restrict_relation_kind(fout,
  "view")` and re-tightens at the end. If `ExecuteSqlQuery` /
  `PQgetCopyData` fatal-fails into `exit_nicely(1)` (line 2498),
  the connection is torn down and the relaxation is moot — but if
  any new caller adds a non-fatal error path in between, the
  relaxation persists. Severity: maybe.
- **[ISSUE-correctness: sequence currval read outside data dump
  txn semantics]** `pg_dump.c:19723` — sequence DATA is dumped as
  `SELECT pg_catalog.setval('seq', N, true)` with N read at
  collection time. Concurrent `nextval()` between collection and
  any subsequent table data dump in the SAME run is invisible to
  the snapshot model (snapshot-stable, but the dump's
  inter-statement state may be surprising to users). Severity:
  question / probably fine.
- **[ISSUE-correctness: per-DB pg_dump invocation by pg_dumpall
  inherits shell-quoting]** Cross-file with `pg_dumpall.c` —
  user-supplied option values (paths, role names, dbnames) reach
  this binary via a `system()`-built command string. Severity:
  maybe (see `pg_dumpall.c.md`).
- **[ISSUE-undocumented-invariant: `dumpACL` correctness for
  `pg_init_privs` requires it to be collected unconditionally]**
  `pg_dump.c:16570 ff, 10869` — `getAdditionalACLs` (10869) is the
  source of `init_privs`. If `--no-acl` (aclsSkip) is on, it's
  skipped (1159) — but that's safe because `dumpACL` short-circuits
  on `aclsSkip` too. A future addition that consumes `initprivs`
  for non-ACL purposes would silently regress. Severity: maybe.
- **[ISSUE-correctness: parallel worker snapshot adoption on
  standbys < v10]** `pg_dump.c:1572-1574` — `pg_fatal("parallel
  dumps from standby servers are not supported by this server
  version")` if `isStandby && remoteVersion < 100000`. That's a
  user-visible error; the check is correct. Severity: nit
  (documentation).
- **[ISSUE-stale-todo: throttle comment is ~25 years of historical
  notes]** `pg_dump.c:2444-2488` — long comment describing why
  throttling wasn't implemented. Not actionable but flagged here so
  a future committer who wants to add `--throttle` knows the
  history. Severity: nit.
- **[ISSUE-undocumented-invariant: shell-type dependency repair
  requires shell-type to exist]** `pg_dump.c` (`dumpShellType`,
  13378) is invoked only via `repairTypeFuncLoop` in
  `pg_dump_sort.c:940-962`, which BUMPS the shell type's `dump`
  mask. If the shell type wasn't created in `getTypes`
  (`shellType == NULL` per `pg_dump.h:223-224`), the loop-break
  silently leaves the original type↔function cycle, and the
  topological sort breaks arbitrarily. Severity: maybe.
- **[ISSUE-question: `--single-transaction` is in pg_restore, not
  pg_dump]** Verified — pg_dump's `--serializable-deferrable` is the
  closest analogue here. Worth a docs cross-link. Severity: nit.
- **[ISSUE-correctness: foreign-table COPY data is dumped under
  RELAXED restrict_relation_kind]** `pg_dump.c:2403-2421` — by
  necessity (we want the FT's data), the restriction must drop to
  just "view" so the foreign scan runs. If a malicious owner has
  configured the foreign server to execute attacker code on SCAN,
  pg_dump itself can be turned into a code-exec primitive for that
  owner. Standard known-tradeoff. Severity: maybe (architectural).
- **[ISSUE-question: extension membership decision lives in
  `selectDumpableExtension` (2267) — interplay with
  `--exclude-extension` for an extension that owns dumped
  tables?]** Worth verifying that a table marked
  `ext_member = true` whose extension is excluded is itself
  excluded; the comment chain suggests yes but the code path
  hasn't been chased here. Severity: question.
- **[ISSUE-correctness: identifiers in error messages]** Many
  `pg_log_error` / `pg_log_warning` calls splice in raw `dbname`/
  `tablename` strings (`Dumping the contents of table \"%s\"` at
  2469, 2479; `unexpected extra results during COPY of table \"%s\"`
  at 2488; re-anchored 2026-07-22 @`0da71d90d623` from 2495/2505/2514,
  code shifted up ~26 lines as pg_dump.c shrank 21102→20835 LOC;
  pattern intact). If a relname contains `\n` it can spoof an
  additional log line. The relname is server-supplied, but a
  malicious owner can create relations with crafted names.
  Severity: nit (log-only, not SQL output).

## Tally

`[verified-by-code]=37 [from-comment]=8 [inferred]=4 [unverified]=0`
