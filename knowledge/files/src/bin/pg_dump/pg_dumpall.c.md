---
path: src/bin/pg_dump/pg_dumpall.c
anchor_sha: f25a07b2d94c
loc: 1892
depth: deep
---

# pg_dumpall.c

- **Source path:** `source/src/bin/pg_dump/pg_dumpall.c`
- **Last verified commit:** `f25a07b2d94c`
- **LOC:** 1892

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** upstream
> commit `7ca548f23a60` ("Revert non-text output formats for pg_dumpall")
> reverted the PG18-cycle feature that taught `pg_dumpall` to emit
> custom/directory/tar archives. The file is back to **text-only output**
> (file banner, `pg_dumpall.c:8-9`: "pg_dumpall forces all pg_dump output
> to be text"). This doc was previously pinned at `4b0bf0788b0` (LOC 2441)
> and described the now-removed archive machinery (`toc.glo`, `map.dat`,
> `archDumpFormat`, `parseDumpFormat`, `createDumpId`,
> `check_for_invalid_global_names`, hand-built `ArchiveEntry`s) — all of
> which are GONE at this anchor (−549 LOC). Rewritten to match.

## Purpose

CLI driver that dumps **cluster-wide state** as a single SQL text stream:
roles (`pg_authid` / `pg_roles`), tablespaces, role memberships, role GUC
privileges, per-role config (`ALTER ROLE … SET`), and every connectable
database in the cluster. It writes globals directly to `OPF`
(stdout or `-f` file) and `fork+exec`s `pg_dump` per database via
`system()`, concatenating each DB's plain-text dump into the same stream.
There is no archive/directory mode — `pg_dumpall` output is always plain
SQL. [from-comment, pg_dumpall.c:1-13]

## Public surface

- `main(int argc, char *argv[])` (128).
- Everything else is file-static (prototypes listed at lines 58-78).

## Top-level driver structure

1. **Locate `pg_dump`** via `find_other_exec` (230), comparing its
   `--version` output against `PGDUMP_VERSIONSTR` (35). Hard fail if the
   binary is missing or a different major version (238-243).
2. **Parse opts** (248-387) via `getopt_long`. Most non-cluster pg_dump
   opts are appended to a shared `pgdumpopts` PQExpBuffer (string-valued
   ones via `appendShellString`) that gets handed to every spawned
   `pg_dump`. A second block (453-500) appends the boolean long-options.
3. **Option-conflict validation** (398-440): `--exclude-database` vs the
   `*-only` modes; `-g`/`-r`/`-t` mutual exclusion; `--if-exists`
   requires `--clean`; `--clean` vs `--data-only`.
4. **Generate / validate the restrict key** (505-510) — `generate_restrict_key`
   if none supplied; fatal on invalid.
5. **Choose source DB** for the catalog connection: explicit `-l` dbname,
   else `postgres` → `template1` fallback (517-543).
6. **`expand_dbname_patterns`** (548) — resolve any `--exclude-database`
   wildcards into concrete names.
7. **Open output channel** (554-562): `fopen(filename, PG_BINARY_W)` for
   `-f`, else `OPF = stdout`. (No archive directory is ever created.)
8. **Session set-up** (567-599): set client encoding if `-E`,
   `SET standard_conforming_strings = on`, `setFmtEncoding`, `SET ROLE`
   if `--role`, `SET quote_all_identifiers = true` if asked.
9. **Header + restrict** (601-629): banner, optional `dumpTimestamp`,
   `\restrict <key>` (blocks psql meta-commands in the restored stream),
   `SET default_transaction_read_only = off`, replicate
   `client_encoding` + `standard_conforming_strings`.
10. **Globals** (631-671), gated `!data_only && !statistics_only &&
    !no_schema`: if `--clean`, `dropDBs` + `dropTablespaces` + `dropRoles`
    (in that order, with the `*-only` guards). Then `dumpRoles`,
    `dumpRoleMembership`, `dumpRoleGUCPrivs` (≥15 via `server_version >=
    150000 && !skip_acls`, 664), `dumpTablespaces`.
11. **`\unrestrict <key>`** (677), so pg_dump's per-DB output (which emits
    its own `\restrict`) takes over.
12. **`dumpDatabases`** (679-680) — unless a `*-only` mode is active.
13. **Close** (682-695): `PQfinish`, completion banner, `fclose` + optional
    `fsync_fname` for `-f`. [verified-by-code, pg_dumpall.c:128-698]

## Internal landmarks

- **`dropRoles`** (781), **`dumpRoles`** (828) — multi-version SQL. The
  role query branches on `server_version`:
  - `>= 90600`: full column set + filter `WHERE rolname !~ '^pg_'`
    (since v9.6 introduced the `pg_*` reserved-role pattern).
  - `>= 90500`: same set without the filter (BYPASSRLS first appears).
  - older: synthesises `false as rolbypassrls`.
  All three orderings end with `ORDER BY 2` (rolname). [verified-by-code,
  pg_dumpall.c:852-883]
- **`dumpRoles` builds CREATE ROLE + ALTER ROLE …** — CREATE first so an
  existing role produces a benign error and ALTER then sets all the flags.
  Roles whose name starts with `"pg_"` are skipped in the loop with a
  `continue` (913-917). For binary-upgrade dumps the OID is pinned via
  `binary_upgrade_set_next_pg_authid_oid` (922-926) and the CREATE may be
  suppressed for the currently-connected role (938). The role PASSWORD is
  `appendStringLiteralConn`'d (983-986) — the encoding-aware quoting
  helper, so passwords with unusual chars round-trip; `--no-role-passwords`
  skips it entirely.
- **`dumpRoleMembership`** (1036) — also multi-version-branched
  (`dump_grantors` / `i_grantor` locals at 1044/1048). Emits `GRANT … TO
  …` with optional `WITH ADMIN OPTION`, `WITH INHERIT`, `WITH SET FALSE`,
  `GRANTED BY <grantor>` when the server tracks them.
- **`dumpRoleGUCPrivs`** (1297) — `pg_database_role_settings`-based
  emission of per-DB-per-role `ALTER ROLE x IN DATABASE y SET p = v`.
  Only called when `server_version >= 150000` (main:664).
- **`dropTablespaces`** (1352), **`dumpTablespaces`** (1387) — emit
  DROP/CREATE TABLESPACE + ACLs + comments + sec labels; binary-upgrade
  OID pinning at 1425-1428.
- **`dropDBs`** (1491) — drops every `datallowconn` DB except `template1`
  and `postgres` (which `pg_dumpall` won't drop, to avoid disconnecting
  the restore script).
- **`dumpUserConfig`** (1538) — per-role `ALTER ROLE x SET p = v`.
- **`expand_dbname_patterns`** (1580) — runs `processSQLNamePattern` for
  `--exclude-database` wildcards.
- **`dumpDatabases`** (1633) — orchestrates per-DB invocation. The DB
  query orders `ORDER BY (datname <> 'template1'), datname` — template1
  first, then alphabetical (1649-1653); comment (1638-1648) explains the
  drop-postgres-while-connected hazard.
  - Skips `!datallowconn` and `datconnlimit = -2` rows in SQL; skips
    `template0` unconditionally in the loop (1666).
  - For `template1` / `postgres` (assumed to exist): if `--clean`, pass
    `--clean --create`; else `create_opts = ""` and emit a `\connect
    <dbname>` (1690-1700). Other DBs get `--create` (1702).
  - `runPgDump` per DB; any nonzero exit is fatal (1707-1709).
- **`runPgDump`** (1701) — assembles the pg_dump command string:
  `printfPQExpBuffer(&cmd, "\"%s\" %s %s", pg_dump_bin, pgdumpopts->data,
  create_opts)` (1710-1711), then appends `-Fa` (undocumented
  plain-append) when writing to a file or `-Fp` for stdout (1718-1720),
  then the `appendShellString`-quoted connection string with `dbname=`
  (1730-1732), and `system()`s it (1735). Returns the exit code.
  [verified-by-code, pg_dumpall.c:1701-1740 @`0da71d90d623`; re-anchored
  2026-07-22 from 1729-1769, code shifted up ~28 lines]
- **`buildShSecLabels`** (1783) — emits SECURITY LABEL rows for shared
  catalogs.
- **`executeCommand`** (1802), **`dumpTimestamp`** (1826),
  **`read_dumpall_filters`** (1845) — small helpers.

## Globals & state

- `pg_dump_bin[MAXPGPATH]` (80) — absolute path of the pg_dump binary
  located at startup.
- `pgdumpopts` (81) — shared option-buffer assembled during `getopt`
  parsing; concatenated into every `runPgDump` command.
- `connstr` (82) — connection-string stem reused for each per-DB pg_dump.
- `output_clean` (83) — drives DROP emission.
- `server_version` (109) — file-static int set by `ConnectDatabase`; gates
  every multi-version SQL branch.
- `role_catalog[10]` (115) — `pg_authid` or `pg_roles` depending on
  `--no-role-passwords` (447-450).
- `OPF` (119) — output FILE (stdout or `-f` file).
- `filename` (120) — `-f` target, NULL for stdout.
- `restrict_key` (125) — psql restrict-key, generated or `--restrict-key`.

## Invariants & gotchas

- **pg_dumpall output is always plain text.** The file banner
  (pg_dumpall.c:8-9) states it forces pg_dump to text because it splices
  pg_dump output into its own text stream. There is no `-F`/`--format`
  option here (it lives in pg_dump). [verified-by-code, pg_dumpall.c:8-9,
  130-191]
- **pg_dump and pg_dumpall MUST be the same version.** `find_other_exec`
  compares `pg_dump --version` against `PGDUMP_VERSIONSTR = "pg_dump
  (PostgreSQL) " PG_VERSION "\n"`. A mismatch fatal-fails before any
  catalog work. [verified-by-code, pg_dumpall.c:35, 230-243]
- **pg_dump (per-DB) inherits options via a SHELL-quoted string, not an
  arg-array.** `runPgDump` builds a command for `system()` using
  `appendShellString`-quoted values. Any option value with shell
  metacharacters depends on `appendShellString` for correct quoting; worth
  re-auditing if a new option is added. [verified-by-code,
  pg_dumpall.c:265-380 (per-opt append), 1729-1769]
- **template1 is dumped first** to avoid "drop postgres while connected to
  postgres" deadlocks in restore. Changing this order silently breaks
  `--clean` restores. [from-comment, pg_dumpall.c:1638-1648]
- **template0 is hardcoded-skipped** even if `datallowconn` is true (1666)
  — it's the bootstrap source and must not be dumped.
- **Roles whose name starts with `"pg_"` are skipped at `dumpRoles`
  time** (913-917). The query already filters on ≥9.6 (861); this is a
  belt-and-suspenders re-check for older servers.
- **`--no-role-passwords` switches the role catalog to `pg_roles`** (447-450)
  — the only way to dump roles between clusters with different MD5/SCRAM
  histories. With passwords on, the `rolpassword` literal is appended
  verbatim (983-986), so the target must accept the same format.
- **Text-mode global SQL is wrapped in `\restrict <key>` … `\unrestrict
  <key>`** (613, 677). Restore-time psql sees that pair before any
  `\connect dbname` line and refuses to execute meta-commands (e.g. `\!`
  shell-out) the dump's contents might carry. The unrestrict is emitted
  JUST BEFORE the per-DB sections, because pg_dump itself emits its own
  restrict/unrestrict pair per DB. [verified-by-code, pg_dumpall.c:605-613,
  673-677]
- **No `\connect postgres` is emitted before globals.** Comment (615-620)
  explains the old `\connect postgres` was removed because it broke
  installations without a `postgres` database; globals apply to whatever
  DB the restore is connected to.
- **`server_version` gates every multi-version SQL branch.** If a code
  path runs before `ConnectDatabase` (rare), it reads 0 and skips all
  version-conditional SQL. [verified-by-code, pg_dumpall.c:109, 517-534]
- **No transaction-snapshot mode for globals.** Unlike `pg_dump`,
  `pg_dumpall` queries roles/tablespaces/memberships as separate
  transactions with no shared snapshot; concurrent role create/drop
  between the role query and the membership query can produce inconsistent
  output. The per-DB `pg_dump` children DO take their own snapshots.
  [inferred, pg_dumpall.c:579-599]

## Cross-refs

- Spawnee: `pg_dump`. Every `runPgDump` invocation is a fresh process
  inheriting `pgdumpopts`, always invoked with `-Fp`/`-Fa` (plain text).
- Consumer: `knowledge/files/src/bin/pg_dump/pg_restore.c.md` — but note
  that with the revert, pg_dumpall no longer produces an archive directory
  for pg_restore to consume; the text stream is replayed via psql.
- Role/tablespace SQL is parallel-developed with the backend's `pg_authid`
  / `pg_tablespace` catalog evolution; multi-version branches at 852, and
  inside `dumpRoleMembership`/`dumpTablespaces`.

<!-- issues:auto:begin -->
- [Issue register — `pg_dump`](../../../../issues/pg_dump.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-correctness: no transaction snapshot for globals]**
  `pg_dumpall.c:579-599` — globals (roles, tablespaces, role memberships,
  role-GUC privs) are queried as separate transactions with no shared
  snapshot. A concurrent `CREATE ROLE a; GRANT a TO b;` interleaved with
  the dump's role-listing → membership query can leave the dump
  referencing role `a` in `b`'s GRANT without a CREATE for `a`; the restore
  then fails. The per-DB `pg_dump` does use transaction-snapshot mode; the
  globals step does not. Severity: maybe (the window is small).
- **[ISSUE-correctness: shell-command assembly for runPgDump]**
  `pg_dumpall.c:265-380, 1729-1769` — each string-valued `case` appends an
  option via `appendShellString` to a shared buffer, then `runPgDump`
  concatenates that buffer into a `system()` command. Correctness rests on
  `appendShellString` being airtight across platforms; Windows quoting is
  subtler. Worth double-checking if a future option takes a user-supplied
  path with backslashes or exclamation marks. Severity: maybe.
- **[ISSUE-undocumented-invariant: pg_dump_bin path quoting]**
  `pg_dumpall.c:1738` — formats `"\"%s\" %s %s"` (pg_dump path quoted, but
  the option spread isn't). A pg_dump path containing double-quotes would
  break; vanishingly unlikely. Severity: nit.
- **[ISSUE-question: undocumented `-Fa` plain-append mode]**
  `pg_dumpall.c:1718` (re-anchored 2026-07-22 @`0da71d90d623` from
  1745-1746; `runPgDump` def shifted 1729→1701, `-Fa` append 1745→1718)
  — when writing to a file, `runPgDump` passes the
  "undocumented plain-append pg_dump format" `-Fa`. This is the internal
  hand-off that lets the child pg_dump append to the same text file
  pg_dumpall is writing. Not user-facing; worth a comment cross-ref to the
  pg_dump side that implements `archAppend`. Severity: nit.

## Tally

`[verified-by-code]=17 [from-comment]=6 [inferred]=1 [unverified]=0`
