---
path: src/bin/pg_dump/pg_restore.c
anchor_sha: 4b0bf0788b0
loc: 1331
depth: deep
---

# pg_restore.c

- **Source path:** `source/src/bin/pg_dump/pg_restore.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1331

## Purpose

CLI driver that reads a pg_dump archive (custom / directory / tar
format, NOT plain SQL — that's what `psql` is for) and either prints
its TOC, scripts the restore to stdout/file, or replays it into a
target database. Wraps the archive layer (`OpenArchive`,
`ProcessArchiveRestoreOptions`, `RestoreArchive`, `CloseArchive`)
defined in `pg_backup_archiver.c`. New since the pg_dumpall-can-emit-
archives change: detects a `toc.glo` marker file in a directory-format
input to switch into pg_dumpall-archive mode, which restores globals
+ each database from a `map.dat` + per-database archive files.
[from-comment, pg_restore.c:1-40, 22-25; verified-by-code,
pg_restore.c:521-630]

## Public surface

- `main(int argc, char **argv)` (84) — option parsing, mode
  selection, dispatch.
- All other functions in this file are file-static:
  `usage`, `read_restore_filters`, `file_exists_in_directory`,
  `restore_one_database`, `restore_global_objects`,
  `restore_all_databases`, `get_dbnames_list_to_restore`,
  `get_dbname_oid_list_from_mfile`. [verified-by-code,
  pg_restore.c:59-72]

## Top-level structure

1. **Parse opts → `RestoreOptions *opts`** (87-364): `getopt_long`
   into a `cmdopts[]` table mirroring pg_dump's option vocabulary
   (filters, jobs, schema/table/function/index/trigger include lists,
   `--clean`, `--create`, `--if-exists`, `--single-transaction`,
   `--transaction-size`, `--restrict-key`, `--exclude-database`).
2. **Validate mutually exclusive options** (382-463) via
   `check_mut_excl_opts`. Many combinations are forbidden — `-1` vs
   `-j N` (1462), `-C` vs `-1` (1458), `--data-only` vs `--no-data`,
   `--single-transaction` vs `--globals-only`, etc.
3. **Restrict-key handling** (397-410). If no `-d/--dbname` was
   given (i.e. scripting to stdout), generate or validate a
   `--restrict-key` token; pg_dump's output uses `\restrict <key>`
   to put psql into restricted mode so the dump's contents cannot
   smuggle psql meta-commands into the client side.
4. **Derived flags** (465-487): compute `dumpData`, `dumpSchema`,
   `dumpStatistics` from `(data_only, schema_only, statistics_only,
   no_*, with_statistics)`. Comment notes that any nonsensical
   combination is already excluded by step 2.
5. **Format detection** (495-516): `-F c|custom`/`d|directory`/`t|tar`;
   `p|plain` is rejected with "please use psql".
6. **pg_dumpall-archive detection** (521-614): if `inputFileSpec`
   exists AND contains a `toc.glo` file → enter dumpall mode.
   Validate that incompatible options (`--list`, `--use-list`,
   `--strict-names`, `--no-schema`, `--data-only`,
   `--statistics-only`, `--section`-excluding-pre-data,
   `--clean` + `--globals-only` together) weren't given.
   Implies `--if-exists` when `--clean` is on (554-558).
   Requires `-C/--create` (581-588) unless only doing globals.
7. **Else single-archive restore** (615-630): `restore_one_database`.
8. **Summary** (632-639): print "errors ignored on restore" warning
   if any TOC entries failed.

## Internal landmarks

- `restore_global_objects` (647) — opens the `toc.glo` custom-format
  archive, disables `noTocComments`, forces `numWorkers = 1` (parallel
  restore is not implemented for the globals archive), runs
  `RestoreArchive`. [verified-by-code, pg_restore.c:647-683]
- `restore_one_database` (692) — generic single-database driver.
  `OpenArchive` → install on-exit cleanup hook (or replace it on
  second-pass restores via `replace_on_exit_close_archive`, for
  pg_dumpall-archive mode that calls this once per DB) → optionally
  load a `-L`/`--use-list` TOC order via `SortTocFromFile` → either
  `PrintTOCSummary` (`-l`) or `ProcessArchiveRestoreOptions` +
  `RestoreArchive`. [verified-by-code, pg_restore.c:692-743]
- `get_dbnames_list_to_restore` (953) — connects to the source
  cluster (postgres or template1) to evaluate `--exclude-database`
  patterns via `processSQLNamePattern` against each `map.dat` entry.
  Marks excluded entries with `oid = InvalidOid` rather than removing
  them (used as a "skip" flag below). Uses
  `appendStringLiteralConn(db_lit, dbidname->str, conn)` to escape
  the dbname before splicing into the pattern query, so the encoding
  context matches the server. [verified-by-code,
  pg_restore.c:953-1040]
- `get_dbname_oid_list_from_mfile` (1050) — reads
  `<dumpdir>/map.dat` line by line, each line `<oid> <dbname>`.
  Strips trailing newline. Errors out on any line where dbname is
  empty or the oid isn't a valid OID. Builds a `DbOidName` flexible-
  array list. [verified-by-code, pg_restore.c:1050-1132]
- `restore_all_databases` (1145) — main dumpall-archive driver.
  Builds the dbname list, applies `--exclude-database`, then loops:
  per database, probe with a `ConnectDatabase` attempt to decide
  between "DB exists, skip CREATE" and "DB doesn't exist, use
  `createDB`". For each: build path
  `<root>/databases/<oid>.tar`, `.dmp`, or `.../<oid>/` (directory
  format), in that probe order, and call `restore_one_database(...,
  append_data=true)`. [verified-by-code, pg_restore.c:1145-1331]
- `read_restore_filters` (834) — reads include/exclude rules from
  a `--filter=FILENAME` file via the shared `filter_read_item`
  parser. Restricted to a subset of object types:
  - include allows function/index/schema/table/trigger.
  - exclude allows ONLY schema. Trying to use any other type with
    "exclude" exits with an error (884-913). This is a permission-
    boundary detail (the comment up in `pg_dump.c` for the dump-side
    filter is what mirrors this asymmetry).
- `file_exists_in_directory` (932) — tiny `stat`+`S_ISREG` helper
  used both for the `toc.glo`/`map.dat` detection and for finding
  per-DB archive files.

## Invariants & gotchas

- **Single-txn ↔ parallel jobs are mutually exclusive.** `if
  (opts->single_txn && numWorkers > 1) pg_fatal(...)` at
  `pg_restore.c:462`. The archive layer cannot multiplex one
  transaction across multiple worker connections.
  [verified-by-code, pg_restore.c:461-463]
- **`-C` requires creating a DB in autocommit mode.** Hence
  `--create` vs `--single-transaction` is forbidden
  (`check_mut_excl_opts` at 458). [verified-by-code,
  pg_restore.c:454-459]
- **`--if-exists` requires `--clean`** (489-491) — `--if-exists`
  modifies the DROP statements emitted by `--clean`; without
  `--clean`, no DROPs exist to be modified.
- **For pg_dumpall archives, `--clean` implicitly enables
  `--if-exists`** (554-558) — globals like roles/tablespaces may
  legitimately not exist in the target cluster yet. The implicit
  enable is logged but no opt-out.
- **`--section` MUST include `--pre-data` for dumpall archives**
  (572-574) — restoring data without first creating schema is
  guaranteed to fail.
- **`--exclude-database` only works on dumpall archives** (615-622)
  — single-archive restore has no notion of multiple databases.
  Same for `--globals-only` (624-626).
- **Parallel restore is not supported for the globals
  (`toc.glo`) archive.** `restore_global_objects` forces
  `AH->numWorkers = 1` regardless of `-j` (672). [verified-by-code,
  pg_restore.c:671-672]
- **Per-DB restore reuses `opts` from a fresh `original_opts`
  copy each iteration** (1156, 1256), because `pg_backup_archiver.c`
  may mutate `RestoreOptions` during a previous restore.
  [verified-by-code, pg_restore.c:1156-1159, 1251-1256]
- **`replace_on_exit_close_archive`** is the second-and-onward
  iteration's cleanup-hook replacement (713-714) — without it, the
  previous DB's `Archive *` would still be in the on-exit handler
  array, pointing to freed memory.
- **`map.dat` parser is strict.** Any line that doesn't begin with
  a digit is silently skipped (treated as comment), but any line
  that begins with a digit but has an invalid OID OR empty dbname
  triggers `pg_fatal`. [verified-by-code,
  pg_restore.c:1080-1113]
- **`PG_MAX_JOBS` cap on `-j`** (239) — same cap as pg_dump.
- **No `-R` honoured.** Listed as `case 'R': /* no-op, still
  accepted for backwards compatibility */` (267-269).

## Cross-refs

- Archive layer: `pg_backup_archiver.c` (`OpenArchive`,
  `RestoreArchive`, `ProcessArchiveRestoreOptions`,
  `PrintTOCSummary`, `SortTocFromFile`, `BuildArchiveDependencies`,
  `replace_on_exit_close_archive`).
- pg_dumpall side: `knowledge/files/src/bin/pg_dump/pg_dumpall.c.md`
  (`dumpDatabases` emits the `map.dat` / `toc.glo` / `databases/`
  layout that this file reads).
- Restrict-key origin:
  `knowledge/files/src/bin/pg_dump/pg_dump.c.md` (uses `\restrict
  <key>` / `\unrestrict <key>` to fence psql meta-commands).
- Filter file format: shared with `pg_dump`/`pg_dumpall` via
  `bin/pg_dump/filter.c`.

<!-- issues:auto:begin -->
- [Issue register — `pg_dump`](../../../../issues/pg_dump.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-correctness: per-DB connect-probe uses `ConnectDatabase`
  with `exit_on_error=false` but doesn't sanitize SQLSTATE]**
  `pg_restore.c:1285-1294` — the connect attempt to detect "DB
  exists" succeeds = use existing DB, fails = create. Any failure
  reason (auth, network, permission) is treated as "doesn't exist".
  On a permission failure against an existing DB this silently
  attempts a CREATE DATABASE, which then fails with a less
  diagnostic error. Severity: maybe.
- **[ISSUE-leak: `--exclude-database` skipped entries still live in
  `dbname_oid_list`]** `pg_restore.c:1027-1031, 1247-1249` — entries
  are marked with `oid = InvalidOid` rather than removed, and the
  per-DB loop skips them. Negligible memory cost but increases inner-
  loop iterations. Severity: nit.
- **[ISSUE-undocumented-invariant: probe order
  `.tar`→`.dmp`→`directory` is fixed]** `pg_restore.c:1265-1276` —
  the directory probe is the silent fallback (no
  `file_exists_in_directory` check before `snprintf`'ing the path).
  If a malformed dump has both `<oid>.tar` AND a `<oid>/` directory,
  the tar wins. No comment explains the precedence. Severity: nit.
- **[ISSUE-question: `restore_global_objects` overrides
  `txn_size = 0`]** `pg_restore.c:655` — silently zeros
  `--transaction-size` for globals even if the user asked for
  per-N commits. Probably intentional (globals fit in one txn) but
  uncommented. Severity: nit.
- **[ISSUE-question: `--restrict-key` rejected with `--dbname`]**
  `pg_restore.c:393-395` — when restoring directly to a database,
  the key serves no purpose (no psql involvement), so the rejection
  is fine. But there's no documented way to "verify the key matches
  the dump's `\restrict <key>`" — the key in pg_dump's output is
  trusted by the consuming psql side only. Severity: nit / question.

## Tally

`[verified-by-code]=18 [from-comment]=5 [inferred]=2 [unverified]=0`
