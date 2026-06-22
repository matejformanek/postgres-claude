# Issues — `pg_dump` (src/bin/pg_dump/)

Per-subsystem issue register for pg_dump, pg_dumpall, pg_restore, and
the archive-format layer. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent docs:** `knowledge/files/src/bin/pg_dump/*` (36 docs).

**Source:** 80 entries surfaced 2026-06-03 by the A3 pg_dump
parallel sweep (4 general-purpose agents reading the 36 files under
`src/bin/pg_dump/`). Each is mirrored in the corresponding per-file
doc's `## Potential issues` block.

pg_dump is a **Phase D candidate area** because of its position
across the privilege boundary: runs as a (possibly non-superuser)
role and emits SQL that pg_restore typically replays at full privilege.
Issues below are grouped by Phase D pattern.

---

## P0 — Phase D candidates (likely / confirmed severity)

### Archive-format trust model — "trust the source"

The headline finding from B2. There is essentially no defense against
a maliciously-crafted archive file being replayed by pg_restore as
superuser: `_printTocEntry` writes `te->defn` verbatim into the SQL
stream; format backends are length-prefix-only without semantic
validation; the `\restrict` / `\unrestrict` framing addresses
**malicious server response to dump queries**, NOT malicious archive
content.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_backup_archiver.c | correctness | likely | `_printTocEntry` writes `te->defn` verbatim into restore SQL stream — no validation of archive-supplied SQL | open | knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md |
| 2026-06-03 | pg_backup_archiver.c | correctness | likely | `processSearchPathEntry` stashes verbatim defn for emission — attacker-controlled `SET search_path` at restore time | open | knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md |
| 2026-06-03 | pg_backup_archiver.c | correctness | likely | `ReadToc` unbounded `deps[]` doubling — OOM-able from a hostile archive | open | knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md |
| 2026-06-03 | pg_backup_archiver.h | correctness | maybe | `offSize` field is an unbounded byte (DoS bounded by file size) | open | knowledge/files/src/bin/pg_dump/pg_backup_archiver.h.md |
| 2026-06-03 | pg_backup_archiver.h | correctness | maybe | `K_VERS_MAX` envelope lets attacker pick old-version code paths | open | knowledge/files/src/bin/pg_dump/pg_backup_archiver.h.md |
| 2026-06-03 | pg_backup_custom.c | correctness | likely | `_PrintTocData` linear scan lets hostile archive populate `dataPos`/`dataState` of arbitrary other TEs via side-effect | open | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md |
| 2026-06-03 | pg_backup_custom.c | correctness | likely | `_CustomReadFunc` does `pg_malloc(blkLen)` of an attacker-chosen int-widened-to-size_t | open | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md |
| 2026-06-03 | pg_backup_custom.c | correctness | likely | `_skipData` non-seekable malloc of attacker-chosen block size | open | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md |
| 2026-06-03 | pg_backup_custom.c | correctness | likely | `_skipData` seekable `fseeko(negative)` from attacker offset | open | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md |
| 2026-06-03 | pg_backup_custom.c | correctness | likely | `_readBlockHeader` `blkType` not validated centrally | open | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md |
| 2026-06-03 | pg_backup_custom.c | correctness | maybe | compression-algo byte from header is trusted | open | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md |
| 2026-06-03 | pg_backup_custom.c | correctness | maybe | no per-block upper-bound | open | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md |
| 2026-06-03 | pg_backup_directory.c | correctness | likely | Path-traversal: `te->filename` from TOC flows through `setFilePath` blindly | open | knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md |
| 2026-06-03 | pg_backup_directory.c | correctness | likely | Path-traversal: `lofname` parsed by `_LoadLOs` from `blobs_N.toc` | open | knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md |
| 2026-06-03 | pg_backup_directory.c | correctness | likely | No `O_NOFOLLOW` — restore follows symlinks placed by attacker | open | knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md |
| 2026-06-03 | pg_backup_tar.c | correctness | maybe | `read_tar_number` 12-octal-digit size header → DoS via 64 GiB padding-skip loop | open | knowledge/files/src/bin/pg_dump/pg_backup_tar.c.md |
| 2026-06-03 | pg_backup_null.c | question | maybe | Could a hostile `dataDumper` emit raw SQL meta-commands via WriteData (gated by `\restrict` framing) | open | knowledge/files/src/bin/pg_dump/pg_backup_null.c.md |

**Phase D pitch — hardening layers:**
1. Reject archives whose `dump_version` doesn't match pg_restore's own
   (currently warned but allowed).
2. Reject `..` and absolute paths in directory-format filenames.
3. Cap individual data-block sizes in custom and tar formats.
4. Validate `blkType` and compression-algo bytes in custom format.
5. Add a "trusted" / "untrusted" archive mode flag (similar to libpq's
   `host=` vs `hostaddr=` boundary).

### pg_dumpall — server-controlled DB name → libpq connection string

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | connectdb.c:154 | correctness | likely | Hard-coded `expand_dbname=true` combined with `datname` from server's `pg_database` table — if a hostile cluster has a DB named `host=evil port=1234 dbname=foo`, libpq's expansion could redirect the next per-DB connection | open | knowledge/files/src/bin/pg_dump/connectdb.c.md |
| 2026-06-03 | pg_dumpall.c | correctness | likely | No transaction snapshot for globals — race window between role/membership/GUC reads | open | knowledge/files/src/bin/pg_dump/pg_dumpall.c.md |
| 2026-06-03 | pg_dumpall.c | correctness | likely | Shell-command assembly — pg_dump invocations via `system()`; depends on `appendShellString` correctness | open | knowledge/files/src/bin/pg_dump/pg_dumpall.c.md |
| 2026-06-03 | pg_dumpall.c | undocumented-invariant | maybe | `pg_dump_bin` quoting | open | knowledge/files/src/bin/pg_dump/pg_dumpall.c.md |

**Phase D pitch**: this is the highest-priority pg_dumpall lead. The
`expand_dbname` semantics need verification against libpq's actual
`conninfo_uri_parse_options` rules; if confirmed exploitable, that's
a real privilege-escalation primitive against pg_dumpall (which is
usually run as superuser).

### `restrict_nonsystem_relation_kind` — the central security boundary

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_dump.c | correctness | likely | `restrict_nonsystem_relation_kind` temporarily relaxed to `"view"` (omitting `foreign-table`) in 3 places during foreign-table COPY → owner-controlled FDW can be a code-exec primitive against the dumper. Mis-revert = privilege escalation against subsequent dump work in same connection | open | knowledge/files/src/bin/pg_dump/pg_dump.c.md |
| 2026-06-03 | pg_dump.c | question | maybe | Sequence currval semantics — concurrent activity not handled | open | knowledge/files/src/bin/pg_dump/pg_dump.c.md |

### `pg_init_privs` baseline

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_dump.c | undocumented-invariant | likely | `pg_init_privs` baseline must be collected for `dumpACL` — missing it = overgranted permissions silently in restored object | open | knowledge/files/src/bin/pg_dump/pg_dump.c.md |
| 2026-06-03 | pg_backup_archiver.c | correctness | likely | `savedPassword` lives across `DisconnectDatabase` and is `pg_strdup`'d per parallel clone — N copies in memory during parallel restore; no scrub | open | knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md |
| 2026-06-03 | pg_backup_db.c | correctness | likely | `savedPassword` retention in AH; no scrub-on-teardown | open | knowledge/files/src/bin/pg_dump/pg_backup_db.c.md |
| 2026-06-03 | pg_backup_db.c | leak | likely | Full SQL query disclosure on `die_on_query_failure`/`warn_or_exit_horribly` (server-side data in error message) | open | knowledge/files/src/bin/pg_dump/pg_backup_db.c.md |
| 2026-06-03 | pg_backup.h | leak | likely | `ConnParams` credential retention; no clearance discipline | open | knowledge/files/src/bin/pg_dump/pg_backup.h.md |
| 2026-06-03 | pg_backup.h | leak | likely | `restrict_key` stored plaintext in archive | open | knowledge/files/src/bin/pg_dump/pg_backup.h.md |
| 2026-06-03 | pg_backup.h | correctness | maybe | `superuser` field is a privilege-escalation vector if attacker controls archive | open | knowledge/files/src/bin/pg_dump/pg_backup.h.md |

### Compression — decompression-bomb DoS (universal across all 3 backends)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | compress_gzip.c | correctness | maybe | No input/output size ratio bound on inflate loop | open | knowledge/files/src/bin/pg_dump/compress_gzip.c.md |
| 2026-06-03 | compress_lz4.c | correctness | maybe | Relies on LZ4 library v1.9+ for frame-size overflow checks; negative LZ4 levels silently treated as default | open | knowledge/files/src/bin/pg_dump/compress_lz4.c.md |
| 2026-06-03 | compress_zstd.c | correctness | maybe | `Zstd_open_write` uses raw `sprintf` into `MAXPGPATH` stack buffer (siblings use `psprintf`); `Zstd_eof` inconsistency with `LZ4Stream_eof` (doesn't drain internal buffers) | open | knowledge/files/src/bin/pg_dump/compress_zstd.c.md |
| 2026-06-03 | compress_io.c | correctness | maybe | Hostile archive with out-of-range algorithm enum → NULL fn-pointer dispatch (only saved by every backend stub being unconditionally compiled in) | open | knowledge/files/src/bin/pg_dump/compress_io.c.md |

### Tar format — fragile but constrained

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_backup_tar.h | correctness | maybe | 12-byte octal-ASCII file-size field caps at 8 GiB-1 — pg_dump tar archives of larger members would silently truncate | open | knowledge/files/src/bin/pg_dump/pg_backup_tar.h.md |

---

## P1 — Undocumented invariants / cross-file coupling (medium severity)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | dumputils.c | undocumented-invariant | likely | Callers in pg_dump.c must pre-quote `name`/`subname` arguments to `buildACLCommands`/`buildDefaultACLCommands` | open | knowledge/files/src/bin/pg_dump/dumputils.c.md |
| 2026-06-03 | dumputils.c | undocumented-invariant | maybe | `shseclabel` catalog name interpolated raw via `%s` | open | knowledge/files/src/bin/pg_dump/dumputils.c.md |
| 2026-06-03 | dumputils.c | doc-drift | maybe | GUC list quote-extensions hard-coded; excludes extension GUCs | open | knowledge/files/src/bin/pg_dump/dumputils.c.md |
| 2026-06-03 | pg_dump.h | undocumented-invariant | maybe | Subclass layout convention not stated | open | knowledge/files/src/bin/pg_dump/pg_dump.h.md |
| 2026-06-03 | pg_dump.h | doc-drift | maybe | `DumpComponents` 32-bit vs `_ALL = 0xFFFF` (16-bit literal but 32-bit type) | open | knowledge/files/src/bin/pg_dump/pg_dump.h.md |
| 2026-06-03 | pg_dump_sort.c | correctness | maybe | Catalog-corruption silent tie — no warning when two objects have identical (typname, namespace) | open | knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md |
| 2026-06-03 | pg_dump_sort.c | undocumented-invariant | maybe | `repairDependencyLoop` pattern-match ordering matters but isn't documented | open | knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md |
| 2026-06-03 | pg_dump_sort.c | question | maybe | Arbitrary edge-break fallback when no shape-match — silent | open | knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md |
| 2026-06-03 | common.c | correctness | maybe | `flagInhTables` silent-drop `if (child == NULL) continue;` at line 303 | open | knowledge/files/src/bin/pg_dump/common.c.md |
| 2026-06-03 | common.c | correctness | maybe | `flagInhIndexes` silent-drop, same shape, line 410 | open | knowledge/files/src/bin/pg_dump/common.c.md |
| 2026-06-03 | filter.c | correctness | maybe | Pattern returned raw, quoting deferred to consumer | open | knowledge/files/src/bin/pg_dump/filter.c.md |
| 2026-06-03 | filter.c | correctness | maybe | Unknown backslash-escape silently swallowed (lines 270-278) | open | knowledge/files/src/bin/pg_dump/filter.c.md |
| 2026-06-03 | parallel.c | correctness | maybe | `sscanf` "junk after id" check is assert-only at lines 1149/1158 | open | knowledge/files/src/bin/pg_dump/parallel.c.md |
| 2026-06-03 | parallel.c | undocumented-invariant | maybe | Windows pgpipe TCP-loopback race — known limitation | open | knowledge/files/src/bin/pg_dump/parallel.c.md |
| 2026-06-03 | parallel.h | correctness | maybe | `PG_MAX_JOBS = INT_MAX` on Unix — no soft cap | open | knowledge/files/src/bin/pg_dump/parallel.h.md |
| 2026-06-03 | pg_backup_db.c | correctness | maybe | `ExecuteSimpleCommands` parser assumes no E-strings, dollar-quoting, or `--` comments | open | knowledge/files/src/bin/pg_dump/pg_backup_db.c.md |
| 2026-06-03 | pg_backup_db.c | correctness | maybe | `IssueACLPerBlob` trusts `LARGE OBJECT <digits>` parse | open | knowledge/files/src/bin/pg_dump/pg_backup_db.c.md |
| 2026-06-03 | pg_backup_directory.c | correctness | maybe | `MAXPGPATH` snprintf truncation in `_StartLO` | open | knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md |
| 2026-06-03 | pg_backup_directory.c | question | maybe | `create_or_open_dir` empty-vs-non-empty dir behavior unverified | open | knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md |
| 2026-06-03 | pg_backup_archiver.c | undocumented-invariant | likely | Parallel-mode `clone->ropt->txn_size = 0` override (correct but subtle invariant — workers must commit per-statement) | open | knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md |
| 2026-06-03 | pg_restore.c | correctness | maybe | Connect-probe SQLSTATE-agnostic | open | knowledge/files/src/bin/pg_dump/pg_restore.c.md |
| 2026-06-03 | pg_restore.c | leak | maybe | Skipped DB entries kept in list | open | knowledge/files/src/bin/pg_dump/pg_restore.c.md |
| 2026-06-03 | pg_restore.c | undocumented-invariant | maybe | Probe order tar→dmp→dir | open | knowledge/files/src/bin/pg_dump/pg_restore.c.md |
| 2026-06-03 | pg_restore.c | question | maybe | `txn_size = 0` override | open | knowledge/files/src/bin/pg_dump/pg_restore.c.md |
| 2026-06-03 | pg_restore.c | question | maybe | restrict-key verification | open | knowledge/files/src/bin/pg_dump/pg_restore.c.md |
| 2026-06-22 | pg_dump.c:2495,2505,2514 | correctness | nit | Raw server-supplied `dbname`/`tablename` spliced into `pg_fatal`/`pg_log_warning`; a relname containing `\n` can spoof an extra log line (log-only, not SQL output) | open | knowledge/files/src/bin/pg_dump/pg_dump.c.md §Potential issues |
| 2026-06-22 | pg_dumpall.c:1745-1746 | question | nit | `runPgDump` passes the undocumented `-Fa` plain-append pg_dump format when writing to a file — internal hand-off worth a cross-ref to the pg_dump side implementing `archAppend` | open | knowledge/files/src/bin/pg_dump/pg_dumpall.c.md §Potential issues |
| 2026-06-22 | pg_restore.c:440-445 | style | nit | The three-way `dumpData`/`dumpSchema`/`dumpStatistics` boolean expressions each pack several precedence rules into one, relying on the earlier conflict checks (380-433); correct but hard to audit in isolation | open | knowledge/files/src/bin/pg_dump/pg_restore.c.md §Potential issues |

---

## P2 — Stale TODOs

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_dump.c | stale-todo | nit | Throttle stale comment | open | knowledge/files/src/bin/pg_dump/pg_dump.c.md |
| 2026-06-03 | pg_dump.h | stale-todo | nit | `SubscriptionInfo` binary-upgrade XXX | open | knowledge/files/src/bin/pg_dump/pg_dump.h.md |
| 2026-06-03 | pg_dump_sort.c | stale-todo | nit | Matview multi-loop "stopgap" | open | knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md |
| 2026-06-03 | pg_dumpall.c | stale-todo | nit | simplehash usage audit | open | knowledge/files/src/bin/pg_dump/pg_dumpall.c.md |
| 2026-06-03 | pg_dumpall.c | question | nit | pg_dumpall has no `--no-globals` | open | knowledge/files/src/bin/pg_dump/pg_dumpall.c.md |

---

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| _(none yet)_ | | | | | |

---

## Cross-cutting observations from the sweep

1. **pg_dump's SQL-assembly discipline is solid** — `fmtId()` + `appendStringLiteralAH/Conn` + `quote_all_identifiers=true` belt-and-suspenders + forced `standard_conforming_strings=on`. The 16 callsites in `dumputils.c` audited correct. **The residual risk is the caller contract** (pg_dump.c must pre-quote args to ACL builders).

2. **The structural problem isn't in pg_dump — it's in pg_restore.** Archive-format trust model is "trust the source." `_printTocEntry` writes `te->defn` verbatim to the SQL stream that gets replayed as superuser. The `\restrict` framing addresses malicious server response during dump, not malicious archive content during restore. Phase D fuzzing target #1 (custom format) and #2 (directory format path-traversal).

3. **pg_dumpall connect-per-DB with server-supplied `datname`** is the highest-priority Phase D lead for pg_dumpall — `expand_dbname=true` + hostile cluster could redirect connections.

4. **`restrict_nonsystem_relation_kind` is the central security boundary** that prevents an attacker-controlled view or foreign table from running code as the dumping role. It's relaxed in 3 places for foreign-table COPY; mis-revert is privilege escalation.

5. **Password handling is uneven** — `savedPassword` is `pg_strdup`'d per parallel clone; N copies in memory during parallel restore; no scrub-on-teardown. Same pattern as libpq's PGconn credential lifetime (see `knowledge/issues/libpq.md`).

6. **Multi-version SQL is pervasive** — every catalog query branches on `fout->remoteVersion`. Supported window: `[minRemoteVersion=90200, maxRemoteVersion=current+99]`. Adding new columns requires `NULL AS newcol` fallbacks for older servers.

7. **Section-boundary anchors** (`DO_PRE_DATA_BOUNDARY` / `DO_POST_DATA_BOUNDARY`) are dummy objects threaded via `addBoundaryDependencies` to enforce pre-data → data → post-data order across all 48 object kinds. Compile-time guard: `StaticAssertDecl(lengthof(dbObjectTypePriority) == NUM_DUMPABLE_OBJECT_TYPES, ...)` in `pg_dump_sort.c:157`.

8. **The pg_dumpall-archive format** (recent refactor) is detected at restore by `toc.glo` presence; it changes pg_restore semantics significantly (forced `--if-exists` with `--clean`, no `--list`/`--use-list`/`--strict-names`/`--no-schema`). Worth a separate spine doc.

9. **Parallel-restore worker safety is good but rests on subtle invariants** — leader builds the read-side data structures before workers exist; workers mutate only clone state + report via exit codes. `CloneArchive` flat memcpy + selective NULL-out is the contract; `clone->ropt->txn_size = 0` override is a hard-to-spot invariant.

10. **Decompression-bomb DoS is universal** across all 3 compression backends (gzip / lz4 / zstd). None bound output size against input. Phase D candidate but lower priority than the archive-format trust model.

## Notes

This register is smaller than libpq's (80 vs 227) because pg_dump's
SQL-assembly discipline largely works as designed. The real attack
surface is **structural**: pg_restore's archive trust model, plus
pg_dumpall's server-driven dbname handling. Both are concrete enough
to brainstorm hardening patches against.

For the Phase D launch, the candidate patches that emerge from this
register (combined with libpq's):

1. **Doc-only**: wire-protocol "do not change" + archive-format trust
   warning patch series.
2. **Defensive**: `pg_restore --trusted=<source>` flag that gates the
   verbatim `te->defn` emission; reject paths with `..` in directory
   format; cap data-block sizes in custom format.
3. **Architectural**: pg_dumpall `expand_dbname` audit + libpq
   credential clearance discipline (cross-register with `libpq.md`).
