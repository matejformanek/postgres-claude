---
path: src/bin/pg_dump/pg_backup_db.c
anchor_sha: 4b0bf0788b0
loc: 619
depth: deep
---

# pg_backup_db.c

- **Source path:** `source/src/bin/pg_dump/pg_backup_db.c`
- **Lines:** 619
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_db.h` (the public surface), `connectdb.c`/`connectdb.h` (`ConnectDatabase`), `parallel.c`/`parallel.h` (`set_archive_cancel_info`), `pg_backup_archiver.h` (`ArchiveHandle`, `WORKER_*`, `OUTPUT_*`).

## Purpose

Connection lifecycle + SQL execution layer for both pg_dump (build the schema queries) and pg_restore (push restored SQL back). Covers:

1. Connecting / reconnecting / disconnecting (`ConnectDatabaseAhx`, `ReconnectToServer`, `DisconnectDatabase`).
2. Server-version + recovery-mode probe (`_check_database_version`).
3. SQL wrappers that error out on the wrong result (`ExecuteSqlStatement`, `ExecuteSqlQuery`, `ExecuteSqlQueryForSingleRow`).
4. The big multiplexer `ExecuteSqlCommandBuf` (called from `ahwrite` when restoring direct-to-DB) — routes to COPY mode, INSERT-stream parsing, or single statement exec.
5. Transaction primitives (`StartTransaction`, `CommitTransaction`) — both wrappers around `ExecuteSqlCommand`.
6. Blob ACL fan-out (`IssueCommandPerBlob`, `IssueACLPerBlob`, `DropLOIfExists`).

## Top-of-file comment
> Single line: "Implements the basic DB functions used by the archiver." [from-comment, pg_backup_db.c:5]

## Public surface

- `ConnectDatabaseAhx(Archive *, const ConnParams *, bool isReconnect)` (108) — open/re-open the libpq connection. Optionally prompts for password. Stores connection on AH; sets noticeProcessor; wires SIGINT cancel via `set_archive_cancel_info`.
- `ReconnectToServer(ArchiveHandle *, const char *dbname)` (72) — used when restore encounters a `\connect` / `CREATE DATABASE` and wants to talk to a new DB.
- `DisconnectDatabase(Archive *)` (163) — issues PQcancel if a query was running, then PQfinish.
- `GetConnection(Archive *)` (192).
- `ExecuteSqlStatement`, `ExecuteSqlQuery`, `ExecuteSqlQueryForSingleRow` (217-260).
- `ExecuteSqlCommandBuf` (383).
- `EndDBCopyMode` (438).
- `StartTransaction`, `CommitTransaction` (467, 475).
- `IssueCommandPerBlob` (490), `IssueACLPerBlob` (537), `DropLOIfExists` (611).

## Key flows

### Connection (`ConnectDatabaseAhx`, 108-157)

1. pg_fatal if already connected.
2. **Never prompt during reconnection** (line 121: `prompt_password = isReconnect ? TRI_NO : cparams->promptPassword`). [verified-by-code, pg_backup_db.c:120-121]
3. Password preference: saved-from-previous-connect > prompt > none. Uses `simple_prompt("Password: ", false)` (line 126) — fe_utils helper, **echo-off**. [verified-by-code, pg_backup_db.c:125-126]
4. Calls common-codebase `ConnectDatabase(...)` (line 128) — that returns the live PGconn or pg_fatals.
5. **First SQL emitted on every new connection:** `ALWAYS_SECURE_SEARCH_PATH_SQL` (line 135) — sets `search_path = ''` for the session; the comment "Start strict; later phases may override this" matches. This is a **defense-in-depth measure** against schema-confusion attacks during dump-driving queries. [from-comment, pg_backup_db.c:133]
6. If the connection actually used a password (`PQconnectionUsedPassword`), the password is captured into `AH->savedPassword` via `pg_strdup(PQpass(...))` — so reconnects (parallel workers cloning the AH) can reuse it without re-prompting. [verified-by-code, pg_backup_db.c:144-148]
7. Checks server version vs `minRemoteVersion`/`maxRemoteVersion`; if mismatch, prints to stderr and `exit(1)` (line 52-56).
8. Installs `notice_processor` (line 153) which pipes server NOTICEs into `pg_log_info`.
9. Installs cancel info via `set_archive_cancel_info(AH, conn)` (line 156) — registers the connection for SIGINT handler.

### Sql-execution dispatch (`ExecuteSqlCommandBuf`, 383-433)

Called from `ahwrite` when `RestoringToDB(AH)` (archiver.c:1903) is true. Three branches:

| `outputKind`        | Behavior                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------------- |
| `OUTPUT_COPYDATA`   | `PQputCopyData(conn, buf, bufLen)`. If pgCopyIn is false (libpq is not in COPY mode), drop data on the floor — explicitly documented as the "continue after a COPY error" path. |
| `OUTPUT_OTHERDATA`  | Stream into `ExecuteSimpleCommands(AH, buf, bufLen)` for INSERT/BLOB COMMENTS bufferloads.        |
| else (general SQL)  | If buf is NUL-terminated at `bufLen`, exec it directly; otherwise copy into a fresh `pg_malloc(bufLen+1)`, terminate, exec, free. |

[verified-by-code, pg_backup_db.c:383-433]

### `ExecuteSimpleCommands` (318-377) [the mini SQL lexer]

Stateful per-AH lexer that splits a buffer of streamed INSERT/COMMENT-ON commands into individual statements. State enum `sqlparseState` = `SQL_SCAN / SQL_IN_SINGLE_QUOTE / SQL_IN_DOUBLE_QUOTE`. Important assumption from the comment block (308-316):

> "We assume that INSERT data will not contain SQL comments, E'' literals, or dollar-quoted strings, so this is much simpler than a full SQL lexer."

**That assumption is owned by pg_dump's emission path**, not enforced by this lexer. If pg_dump ever emits an INSERT with an E'\\n' literal or a `--` comment line, this lexer's semicolon-detection becomes incorrect.

For single-quoted regions it honors backslash-escapes (`SQL_IN_SINGLE_QUOTE` branch, lines 360-368) **only when `std_strings` is false** — matches PG escaping semantics, but also means a buffer-boundary split inside an escape can mis-state-track since `backSlash` is preserved across calls via `AH->sqlparse.backSlash`. [verified-by-code, pg_backup_db.c:360-368]

### Error paths (`die_on_query_failure`, 207-214; `ExecuteSqlCommand`, 266-296)

`die_on_query_failure(AH, query)` calls `pg_log_error("query failed: %s", PQerrorMessage(conn))` then `pg_log_error_detail("Query was: %s", query)` then `exit(1)`. Note: **the full failing query is dumped to stderr** — that includes any literal values pg_dump put in (table names, role names, but also possibly column values in INSERT mode). On a TTY this is fine; in non-TTY logs or CI it can leak sensitive data into logs. `[maybe — phase D]` [verified-by-code, pg_backup_db.c:207-214]

`ExecuteSqlCommand` (266-296) switches on PGRES result:

- `PGRES_COMMAND_OK / PGRES_TUPLES_OK / PGRES_EMPTY_QUERY` → ok.
- `PGRES_COPY_IN` → sets `AH->pgCopyIn = true` (we're now in libpq COPY mode).
- anything else → `warn_or_exit_horribly(AH, "%s: %sCommand was: %s", desc, PQerrorMessage(conn), qry)` — so the same query-disclosure risk applies in the soft-fail path. [verified-by-code, pg_backup_db.c:288-292]

### Blob fan-out (`IssueCommandPerBlob`, `IssueACLPerBlob`)

`IssueCommandPerBlob` (490-526) walks a `te->defn` containing newline-separated blob OIDs, wrapping each in `cmdBegin <oid> cmdEnd;\n`. Also counts each emitted command against `--transaction-size` mode (lines 506-520).

`IssueACLPerBlob` (537-609) is more involved: it parses the ACL command text to find each `LARGE OBJECT <oid>` substring, splitting the GRANT/REVOKE into a prefix and suffix that get applied per-blob via `IssueCommandPerBlob`. The parsing handles `"`-quoted role names by ignoring content inside quotes. **Asserts:**
- `strcmp(blobte->desc, "BLOB METADATA") == 0` (line 549) — the dependency dumpId[0] must point at the BLOB METADATA entry.
- `isdigit(*en)` after `"LARGE OBJECT "` substring match (line 581) — i.e. it trusts that the blob OID is well-formed.

[verified-by-code, pg_backup_db.c:537-609]

### `DropLOIfExists` (611-619)

Emits `SELECT pg_catalog.lo_unlink(oid) FROM pg_catalog.pg_largeobject_metadata WHERE oid = '%u';\n`. The `%u` is OID — safe.

## Phase D notes

- **Password retention.** `AH->savedPassword` lives for the lifetime of the AH. On `DisconnectDatabase` it is NOT scrubbed. On `CloneArchive` (archiver.c:5219-5221) it is `pg_strdup`'d per-clone, so clones can reconnect without re-prompting. Process memory dumps will contain the password. `[maybe — phase D]`
- **Query disclosure on failure.** Both `die_on_query_failure` and `warn_or_exit_horribly` log the full SQL command. Acceptable trade-off for a developer/operator tool, but worth flagging in headless / CI environments where stderr is persisted. `[maybe — phase D]`
- **`PQputCopyData` size argument is `size_t bufLen`.** No integer-truncation issue (libpq takes int internally but it's the caller's job to chunk). `[fine]`
- **`ExecuteSimpleCommands` parser is fragile** to the documented assumptions (no `--` comment, no E-strings, no dollar-quoting). If a future change to pg_dump's INSERT emission breaks the assumption, the lexer mis-splits and `ExecuteSqlCommand` receives a partial / mis-terminated statement. The blast radius is "syntax error during restore" rather than injection, but in restore-to-superuser scenarios a partial statement followed by reinterpretation of the rest could be exploitable. `[maybe — phase D]` [from-comment, pg_backup_db.c:308-316]
- **`IssueACLPerBlob` trusts `blobte->desc == "BLOB METADATA"` and that the OID list is well-formed integers**. The `defn` text is asserted but not validated against `te->defn` having matching `"LARGE OBJECT "` markers. A corrupt archive could trip the `Assert(isdigit(...))` in a non-assertions build → undefined behavior. `[maybe — phase D]` [verified-by-code, pg_backup_db.c:581-595]
- **Cancel handling.** `DisconnectDatabase` sends `PQcancel` if `PQtransactionStatus == PQTRANS_ACTIVE`, then nulls `connCancel` before `PQfinish`. Race vs signal handler dereferencing `connCancel` is closed by the `set_archive_cancel_info(AH, NULL)` call (line 185). `[fine]`
- **Always-secure-search-path.** Setting `search_path = ''` immediately after connect is the right pattern; matches `ALWAYS_SECURE_SEARCH_PATH_SQL` used by pg_upgrade and others. `[fine]` [verified-by-code, pg_backup_db.c:133-135]

## Cross-references

- `set_archive_cancel_info` — `parallel.c` (registers SIGINT handler to call PQcancel).
- `ALWAYS_SECURE_SEARCH_PATH_SQL` — `common/connect.h`.
- `ConnectDatabase` — `connectdb.c` (shared with psql/pg_upgrade for connect-with-prompt logic).
- `notice_processor` (200-204) — installed via PQsetNoticeProcessor; routes server NOTICE/WARNING to pg_log_info.

## Open questions

- Is `simple_prompt` echo-off guaranteed on Windows when stdin is a file? `[unverified]`
- Does `PQputCopyEnd(conn, NULL)` (line 447) correctly reset pgCopyIn even on send-failure? Code pg_fatals on `<= 0`, so the failure path exits. [verified-by-code, pg_backup_db.c:447-450]

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1 [maybe]=4 [fine]=3`
