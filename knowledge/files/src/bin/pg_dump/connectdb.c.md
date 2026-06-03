---
path: src/bin/pg_dump/connectdb.c
anchor_sha: 4b0bf0788b0
loc: 295
depth: deep
---

# connectdb.c

- **Source path:** `source/src/bin/pg_dump/connectdb.c`
- **Lines:** 295
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `connectdb.h` (declares the two extern functions), `pg_dumpall.c` (primary caller — opens one connection per database in the cluster), `pg_restore.c` (also calls `ConnectDatabase`), `fe_utils/string_utils.c` (`appendConnStrVal`), `common/connect.h` (`ALWAYS_SECURE_SEARCH_PATH_SQL`).

## Purpose

Two front-end utilities shared by pg_dumpall (and pg_restore in -d mode):

1. `ConnectDatabase` — wrap `PQconnectdbParams` with libpq-style connection-string parsing, optional password prompting / retry, server-version check, and forced `SET search_path = pg_catalog` via `ALWAYS_SECURE_SEARCH_PATH_SQL`.
2. `executeQuery` — `PQexec` wrapper that pg_fatals on failure.

`constructConnStr` (static) builds a child-process-safe connection string with `dbname`, `password`, and `fallback_application_name` stripped. [verified-by-code, connectdb.c:39-295]

## Public surface

- `ConnectDatabase(dbname, connection_string, pghost, pgport, pguser, prompt_password, fail_on_error, progname, **connstr, *server_version, *password, *override_dbname)` (39) — returns `PGconn *`. [verified-by-code, connectdb.c:39-231]
- `executeQuery(conn, query)` (278) — pg_fatals if the result is not `PGRES_TUPLES_OK`; PQfinishes the conn first. Useful only for SELECT-shaped commands. [verified-by-code, connectdb.c:277-295]

## Static helpers

- `constructConnStr(**keywords, **values)` (245) — builds `"k1='v1' k2='v2' …"` by appending `appendConnStrVal(buf, values[i])` which is the standard libpq quote-and-escape routine. Skips `dbname`, `password`, `fallback_application_name`. [verified-by-code, connectdb.c:244-270]

## Connection-build flow

The function builds two parallel `const char **keywords` / `const char **values` arrays, then feeds them to `PQconnectdbParams(keywords, values, /*expand_dbname=*/true)`. Order of population (connectdb.c:79-151):

1. If `connection_string` is non-NULL: parse with `PQconninfoParse`; pg_fatal on parse failure; copy every option **except `dbname`** into the arrays. Explicit comment: "Explicitly discard any dbname value in the connection string; otherwise, `PQconnectdbParams()` would interpret that value as being itself a connection string." [from-comment, connectdb.c:73-78]
2. Append host/port/user/password if non-NULL.
3. Append `dbname` (the per-DB iteration variable).
4. Append `override_dbname` if non-NULL — this OVERWRITES the prior `dbname` slot key but at a different index, so the array contains TWO `dbname` entries. `PQconnectdbParams` consumes them left-to-right; the last one wins. [verified-by-code, connectdb.c:136-147]
5. Append `fallback_application_name = progname`.

The do/while loop re-runs the whole build if the first `PQconnectdbParams` returned `CONNECTION_BAD && PQconnectionNeedsPassword && !password && prompt_password != TRI_NO`. [verified-by-code, connectdb.c:62-168]

## Version check

`PQparameterStatus(conn, "server_version")` (199) AND `PQserverVersion(conn)` (203) — both are queried; the textual one is used only for error messages. Allows backends back to 9.2; rejects servers newer than our major. [verified-by-code, connectdb.c:198-226]

After the version check passes, `executeQuery(conn, ALWAYS_SECURE_SEARCH_PATH_SQL)` forces `SELECT pg_catalog.set_config('search_path', '', false)` on the new session before anyone else gets to issue a query. [verified-by-code, connectdb.c:228]

## Phase D — surfaces of concern

- **Password preservation across retry.** The retry loop keeps the prompted `password` in scope, so a wrong-password followed by SIGINT-then-retry does not re-prompt. The password is also returned via the caller's `char *password` out-parameter when not NULL (pg_dumpall reuses it across databases). The function does NOT scrub the password buffer after `PQconnectdbParams` consumes it. [verified-by-code, connectdb.c:53-167; pg_dumpall.c:170-?] [maybe]
- **Hostile `dbname` from server-returned DB list.** The caller (pg_dumpall) reads the list of databases from `pg_database` and passes each name as `dbname`. The name is fed verbatim to `PQconnectdbParams`, which performs its own quoting — there is no shell metacharacter concern here. But `PQconnectdbParams(..., expand_dbname=true)` means if `dbname` itself parses as `key=val key=val ...` libpq will interpret it as a connection string. **In `ConnectDatabase`, `expand_dbname=true` is hard-coded (line 154).** A database with a name like `host=evil port=1234 dbname=foo` could in principle redirect the next per-DB connection — except that libpq only triggers expansion when there's a `=` in the value AND the value doesn't begin with a recognized URI scheme. [verified-by-code, connectdb.c:154] [likely — Phase D, see ISSUE register]
- **`override_dbname` shadows but doesn't replace.** Both keys are written; libpq is documented as "last entry wins", but the array thus has duplicates, which a future libpq strict-mode could reject. [verified-by-code, connectdb.c:136-147] [maybe]
- **`constructConnStr` reuses parsed-and-trusted values.** The connstr handed to a child process is built from the SAME `values[]` array that libpq already accepted. `appendConnStrVal` does the standard backslash-escape-and-single-quote. No unquoted interpolation. [verified-by-code, connectdb.c:244-270] [no concern]
- **`ALWAYS_SECURE_SEARCH_PATH_SQL` is fixed text** — not built from user input. [verified-by-code, connectdb.c:228] [no concern]

## Cross-references

- Callers: `pg_dumpall.c::dumpDatabases()`, `pg_restore.c::main()` (only when `-d`/`-C` used). The pg_dump binary itself uses a different connect routine in `pg_backup_db.c`.
- See also: `knowledge/files/src/bin/pg_dump/connectdb.h.md` for the prototype block.

## Confidence tag tally
`[verified-by-code]=10 [from-comment]=2 [maybe]=2 [likely]=1`
