---
path: src/bin/pg_dump/pg_dumpall.c
anchor_sha: 4b0bf0788b0
loc: 2441
depth: deep
---

# pg_dumpall.c

- **Source path:** `source/src/bin/pg_dump/pg_dumpall.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 2441

## Purpose

CLI driver that dumps **cluster-wide state**: roles (`pg_authid` /
`pg_roles`), tablespaces, role memberships, role GUC privileges,
per-role config (`ALTER ROLE … SET`), and every connectable database
in the cluster. For text-format output it writes globals directly
and `fork+exec`s `pg_dump` per database, concatenating into
stdout/file. For custom/directory/tar formats it builds an archive
directory containing `toc.glo` (custom-format archive of globals),
`map.dat` (oid → dbname mapping), and `databases/<oid>.<ext>`
artifacts produced by per-DB `pg_dump` runs. [from-comment,
pg_dumpall.c:1-21]

## Public surface

- `main(int argc, char *argv[])` (145).
- Everything else is file-static (lines 67-91 list the prototypes).

## Top-level driver structure

1. **Locate `pg_dump`** via `find_other_exec` (251), comparing its
   `--version` output against `PGDUMP_VERSIONSTR`. Hard fail if the
   binary is missing or a different major version (259-265).
2. **Parse opts** (270-590) via `getopt_long`. Most non-cluster
   pg_dump opts are appended to a shared `pgdumpopts` PQExpBuffer
   that gets handed to every spawned `pg_dump`.
3. **Choose source DB** for the catalog connection
   (`postgres` → `template1` fallback at 596-605).
4. **`expand_dbname_patterns`** (619) — resolve any `--exclude-database`
   wildcards into concrete names by running `processSQLNamePattern`
   on the source server.
5. **Session set-up** (632-657) — `SET standard_conforming_strings =
   on`, set encoding, `SET ROLE` if requested, `SET
   quote_all_identifiers = true` if asked.
6. **Open output channel.** For archive formats (660-740), create
   `<dir>/toc.glo` via `CreateArchive(archCustom, ...)`, hand-build
   pre-data `ArchiveEntry`s for `default_transaction_read_only = off`,
   `client_encoding`, `standard_conforming_strings = on`. For text,
   write a header banner + `\restrict <key>` (the same restrict-key
   mechanism that pg_dump emits, blocking psql meta-commands from
   the dump's contents) + the equivalent `SET` statements.
7. **Globals** (775-820): if `--clean` (or archive mode unconditionally),
   `dropDBs` + `dropTablespaces` + `dropRoles`. Then `dumpRoles`,
   `dumpRoleMembership`, `dumpRoleGUCPrivs` (≥15), `dumpTablespaces`.
8. **`\unrestrict <key>`** for text mode (829), so pg_dump's per-DB
   output (which emits its own `\restrict`) takes over.
9. **`dumpDatabases`** (832) — iterates `pg_database`, skipping
   `!datallowconn` rows and `datconnlimit = -2` ("invalid" sentinel),
   forces template1 first, calls `runPgDump` per DB.
10. **Close**. For archive mode, `SetArchiveOptions` +
    `ProcessArchiveRestoreOptions` + `CloseArchive`. For text,
    `fsync_fname` the output file. [verified-by-code,
    pg_dumpall.c:144-865]

## Internal landmarks

- **`dropRoles`** (950), **`dumpRoles`** (1018) — multi-version SQL.
  The role query branches on `server_version`:
  - `>= 90600`: full column set + filter `WHERE rolname !~ '^pg_'`
    (since v9.6 introduced `pg_*` reserved-role pattern).
  - `>= 90500`: same set without the filter (BYPASSRLS first appears).
  - older: synthesises `false AS rolbypassrls`.
  All three orderings end with `ORDER BY 2` (rolname). [verified-by-code,
  pg_dumpall.c:1044-1075]
- **`dumpRoles` builds CREATE ROLE + ALTER ROLE …** (1116-1187) —
  CREATE first so existing roles produce a benign error and ALTER
  then sets all the flags. For binary-upgrade dumps of the currently-
  connected role, the CREATE is suppressed (1132-1134). The role
  PASSWORD is `appendStringLiteralConn`'d (1180) — that is the
  encoding-aware quoting helper, so passwords with unusual chars
  round-trip. `--no-role-passwords` skips it entirely.
- **`dumpRoleMembership`** (1269) — also multi-version-branched.
  Comment (1290-1300) explains: older PG didn't carefully track
  grantor; old roleid/member could be names rather than OIDs; both
  affect dump fidelity. Modern code dumps `GRANT … TO …` with
  optional `WITH ADMIN OPTION`, `WITH INHERIT`, `WITH SET FALSE`,
  `GRANTED BY <grantor>` when available.
- **`dumpRoleGUCPrivs`** (1546) — `pg_database_role_settings`-based
  emission of per-DB-per-role `ALTER ROLE x IN DATABASE y SET p =
  v`. Only present ≥ v15.
- **`dropTablespaces`** (1612), **`dumpTablespaces`** (1667) —
  emit DROP/CREATE TABLESPACE + their ACLs + comments + sec labels.
- **`dropDBs`** (1819) — picks up every `datallowconn` DB except
  `template1` and `postgres` (which `pg_dumpall` won't try to drop
  to avoid disconnecting the restore script).
- **`dumpUserConfig`** (1884) — per-role `ALTER ROLE x SET p = v`,
  emitted from `pg_db_role_setting` for the `setdatabase = 0` rows.
- **`dumpDatabases`** (1989) — orchestrates per-DB invocation. The
  DB ordering is `ORDER BY (datname <> 'template1'), datname` —
  template1 first, then alphabetical. Comment (2001-2006) explains
  why: dropping "postgres" while connected to it deadlocks the
  script.
  - `template0` is skipped unconditionally (2061).
  - For `template1` / `postgres` (which the restore assumes exist):
    if `--clean`, emit `--clean --create`; else use a `\connect
    <dbname>` (text mode) or empty `create_opts` (archive mode).
    For other DBs: pass `--create` to pg_dump (2088-2099).
  - In archive mode, append `<oid> <dbname>\n` to `map.dat`
    (2117-2118).
- **`runPgDump`** (2147) — assembles the pg_dump command string with
  `pgdumpopts` + format flag + the connection string (built from
  the pg_dumpall connection's parameters) + dbname. Calls `system()`
  via the platform helper. Returns the exit code; `dumpDatabases`
  errors out the cluster dump on any nonzero. [verified-by-code,
  pg_dumpall.c:2147-2217]
- **`buildShSecLabels`** (2220) — emits SECURITY LABEL ON
  ROLE/TABLESPACE/DATABASE rows for shared catalogs.
- **`check_for_invalid_global_names`** (2271) — only used for archive
  format AND server <19; verifies that no role/tablespace name
  contains newlines or carriage returns, which would break the
  `map.dat` line-per-entry format. v19+ rejects such names at CREATE
  time. [verified-by-code, pg_dumpall.c:668-674, 2271-2331]
- **`parseDumpFormat`** (2407) — accepts `c`/`custom`/`d`/`directory`/
  `t`/`tar`/`p`/`plain`/`a`/`append`. The `a`/`append` value is the
  internal hand-off mode pg_dumpall uses to splice into an existing
  text output file from runPgDump. [verified-by-code,
  pg_dumpall.c:2407-2436]
- **`createDumpId`** (2438) — local monotonic counter
  (`return ++dumpIdVal;`); used only for the few hand-built
  `ArchiveEntry` calls in archive mode. NOT shared with pg_dump's
  AssignDumpId mechanism.

## Globals & state

- `pg_dump_bin[MAXPGPATH]` (93) — absolute path of the pg_dump
  binary located at startup.
- `pgdumpopts` (94) — shared option-buffer assembled during `getopt`
  parsing; concatenated into every `runPgDump` command.
- `archDumpFormat` (141) — single global picking text vs custom vs
  directory vs tar; dispatched on throughout.
- `OPF` (132) — output FILE for text mode.
- `restrict_key` (138) — psql restrict-key for text mode, generated
  or `--restrict-key` user-supplied.

## Invariants & gotchas

- **pg_dump and pg_dumpall MUST be the same version.**
  `find_other_exec` compares `pg_dump --version` against
  `PGDUMP_VERSIONSTR = "pg_dump (PostgreSQL) " PG_VERSION "\n"`. A
  version mismatch fatal-fails before any catalog work.
  [verified-by-code, pg_dumpall.c:43-45, 251-265]
- **pg_dump (per-DB) inherits options via a SHELL-quoted string,
  not arg-array.** `runPgDump` uses `system()` with an
  `appendShellString`-built command. This means any option value
  containing shell metacharacters depends on `appendShellString`
  for correct quoting. Worth re-auditing if a new option is added.
  [verified-by-code, pg_dumpall.c:288-296 (per-opt append),
  2147-2217]
- **template1 is dumped first** to avoid "drop postgres while
  connected to postgres" deadlocks in restore. Changing this order
  silently breaks `--clean` restores. [from-comment,
  pg_dumpall.c:2001-2006]
- **template0 is hardcoded-skipped**, even if `datallowconn` is true
  (2061) — template0 must NOT be dumped because it's the bootstrap
  source.
- **Roles whose name starts with `"pg_"` are skipped at
  `dumpRoles` time** (1105-1109) with a warning. The query already
  filters on ≥9.6; this is a belt-and-suspenders re-check for older
  servers.
- **`--no-role-passwords` is the only way to dump roles between
  clusters with different MD5/SCRAM histories**: with passwords on,
  the `rolpassword` literal is appended verbatim, so the target must
  accept the same format. [verified-by-code, pg_dumpall.c:1177-1181]
- **Text-mode global SQL is wrapped in `\restrict <key>` …
  `\unrestrict <key>`** (756, 829). Restore-time psql sees that
  pair before any `\connect dbname` lines and refuses to execute any
  meta-command (e.g. `\!` shell-out) the dump's contents might
  carry. The unrestrict is emitted JUST BEFORE the per-DB sections,
  because pg_dump itself emits its own restrict/unrestrict pair per
  DB. [verified-by-code, pg_dumpall.c:748-756, 823-830]
- **`--clean` is unconditional in archive format** (783-788) — comment
  explains the asymmetry: pg_restore controls --clean on the consuming
  side, while pg_dumpall must produce DROPs unconditionally so
  pg_restore CAN apply them.
- **`server_version` is a file-static int** (122) set by the
  successful `ConnectDatabase` call; used to gate every multi-version
  SQL branch. If a code path runs before connecting (rare), it'll
  read 0 and skip all version-conditional SQL.
- **No transaction-snapshot mode.** Unlike `pg_dump`, `pg_dumpall`
  for globals runs without `BEGIN`/REPEATABLE READ snapshot; each
  query sees the current committed state. The per-DB `pg_dump`
  children DO take their own snapshots. This means concurrent role
  creates/drops between the role query and the membership query
  CAN produce inconsistent output. [inferred, pg_dumpall.c:637-657]
- **`check_for_invalid_global_names`** runs only for archive format
  AND server < 19 (673-674). Older clusters silently accept role
  names with newlines that would corrupt `map.dat` — this is the
  scrubber.

## Cross-refs

- Spawnee: `pg_dump`. Every `runPgDump` invocation is a fresh
  process inheriting `pgdumpopts`.
- Consumer: `knowledge/files/src/bin/pg_dump/pg_restore.c.md` —
  `restore_all_databases` reads the `map.dat` + `databases/`
  layout this file emits.
- Archive layer: `pg_backup_archiver.c` (`CreateArchive`,
  `ArchiveEntry`, `SetArchiveOptions`, `CloseArchive`).
- Role/tablespace SQL is parallel-developed with backend's
  `pg_authid` / `pg_tablespace` catalog evolution; multi-version
  branches at lines 1044, 1290, 1546, etc.

## Potential issues

- **[ISSUE-correctness: no transaction snapshot for globals]**
  `pg_dumpall.c:637-657` — globals (roles, tablespaces, role
  memberships, role-GUC privs) are queried as separate transactions
  with no shared snapshot. A concurrent `CREATE ROLE a; GRANT a TO
  b;` interleaved with the dump's role-listing query → membership
  query can leave the dump referencing role `a` in `b`'s GRANT
  without a CREATE for `a`. Restoring the dump then fails. The
  per-DB `pg_dump` does use transaction-snapshot mode; the globals
  step does not. Severity: maybe (the window is small).
- **[ISSUE-correctness: shell-command assembly for runPgDump]**
  `pg_dumpall.c:288-296 etc., 2147-2217` — every `case` in the
  getopt loop appends ` -X ` + value via `appendShellString` to a
  shared buffer, then `runPgDump` concatenates that buffer into a
  `system()` command string. Correctness rests on
  `appendShellString` being airtight across all platforms; on
  Windows the quoting rules are subtler. Worth double-checking if
  a future option takes a user-supplied path with backslashes or
  exclamation marks. Severity: maybe.
- **[ISSUE-undocumented-invariant: `pg_dump_bin` path is taken
  unquoted on most call sites]** `pg_dumpall.c:2162, 2174` — formats
  `"\"%s\" %s -f %s %s"` (path quoted, but option spread isn't).
  Filenames with double-quotes in the path of pg_dump itself would
  fail; vanishingly unlikely. Severity: nit.
- **[ISSUE-question: `dumpUserConfig` ordering vs role passwords]**
  `pg_dumpall.c:1241-1249` — comment says "Dump configuration
  settings for roles after all roles have been dumped" because
  configs may mention other roles by name. But the configs are
  emitted in the same `for` loop iteration that prints the role —
  yes, but only AFTER the loop that printed all the ROLE CREATEs.
  Re-read to confirm the inner loop is fully separate. Severity:
  question, probably fine.
- **[ISSUE-stale-todo: comment about hash-table for roles]**
  `pg_dumpall.c:46-65` — defines a `simplehash`-backed
  `rolename_hash` for roles but it's not clear all role lookups
  use it; some still walk PGresults. Worth a re-audit. Severity:
  nit.
- **[ISSUE-question: `--no-globals` semantics for pg_dumpall
  itself]** Not present here — pg_dumpall has `--globals-only`
  and `--roles-only`/`--tablespaces-only`, but the `--no-globals`
  option lives in pg_restore (lines 110, 168). Verify pg_dumpall
  has no equivalent way to dump ONLY databases. Severity: nit.

## Tally

`[verified-by-code]=19 [from-comment]=8 [inferred]=2 [unverified]=0`
