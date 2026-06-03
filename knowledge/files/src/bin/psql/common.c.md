---
path: src/bin/psql/common.c
anchor_sha: 4b0bf0788b0
loc: 2710
depth: deep
---

# common.c

- **Source path:** `source/src/bin/psql/common.c`
- **Lines:** 2710
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common.h` (externs), `command.c` (the slash-command catalogue that drives this layer), `copy.c::handleCopy{In,Out}` (downstream of HandleCopyResult).

## Purpose

The query-execution waist of psql: every user-typed SQL statement, every internal lookup (`\d`, `\sf`, `\password`), and every `\watch` iteration funnels through `SendQuery` or `PSQLexec` here. Also owns the SIGINT longjmp protocol, the variable-substitution callback the flex lexer uses, and a fairly intricate pipeline-mode result accountant. [verified-by-code, common.c:1-2710]

## Role in psql

`MainLoop / startup.c → SendQuery / PSQLexec → ExecQueryAndProcessResults → PQsendQuery / PQsendQueryParams / PQsendPrepare / PQsendPipelineSync / PQsendFlushRequest → ResultLoop → PrintQueryResult → PrintQueryTuples / StoreQueryTuple / ExecQueryTuples / PrintResultInCrosstab / HandleCopyResult → fe_utils/print.c`.

## Key functions

### Output-stream plumbing (common.c:55-170)

- `openQueryOutputFile(fname, fout, is_pipe)` (55) — NULL/empty → stdout; `|cmd` → `popen`; otherwise `fopen`. Caller manages SIGPIPE based on `*is_pipe`.
- `SetupGOutput` / `CloseGOutput` (89, 109) — internal `\g <file>` helpers; track is_pipe and call `SetShellResultVariables(pclose(...))` for pipes.
- `setQFout(fname)` (143) — the `\o` and `-o` handler; replaces `pset.queryFout` after first verifying the new sink can be opened.

### Variable lexer callback — `psql_get_variable` (common.c:187)

Resolves `:foo` / `:'foo'` / `:"foo"` / `:{?foo}` references for the flex lexer. Returns a malloc'd string. Four quoting modes:
- `PQUOTE_PLAIN` (`:foo`) — raw value via `GetVariable` then `pg_strdup`.
- `PQUOTE_SQL_LITERAL` (`:'foo'`) — `PQescapeLiteral`. Requires `pset.db` else error.
- `PQUOTE_SQL_IDENT` (`:"foo"`) — `PQescapeIdentifier`. Requires `pset.db` else error.
- `PQUOTE_SHELL_ARG` (`:'foo'` in a backtick context) — `appendShellStringNoError`. Fails on embedded `\n` or `\r`. [verified-by-code, common.c:246-266]

If `passthrough` (the ConditionalStack) reports the current `\if` branch is inactive, returns NULL → suppresses substitution. [verified-by-code, common.c:194-196]

### SIGINT plumbing (common.c:304-328)

- `volatile sig_atomic_t sigint_interrupt_enabled` (default false).
- `sigjmp_buf sigint_interrupt_jmp`.
- `psql_cancel_callback` (308) — if `sigint_interrupt_enabled`, clear it and `siglongjmp(sigint_interrupt_jmp, 1)`; otherwise just set `cancel_pressed = true`. On WIN32 the longjmp arm is `#ifndef`-stripped — Windows handles Ctrl-C differently. [from-comment, common.c:300-303]
- `psql_setup_cancel_handler` (324) — install via `fe_utils/cancel::setup_cancel_handler`.

### Connection liveness (common.c:336-404)

- `ConnectionUp` — `PQstatus != CONNECTION_BAD`.
- `CheckConnection` — on dead conn, if non-interactive `exit(EXIT_BADCONN)`; if interactive, try `PQreset` and on failure stash old conn in `pset.dead_conn` (so `\connect` can still read its params). Calls `UnsyncVariables` on permanent loss. [verified-by-code]

### Result helpers (common.c:417-590)

- `AcceptResult` (417) — categorise `PQresultStatus`; on error, `pg_log_info` the message and call `CheckConnection`.
- `SetResultVariables` (478) — populate `ERROR`, `SQLSTATE`, `ROW_COUNT`, `LAST_ERROR_SQLSTATE`, `LAST_ERROR_MESSAGE` from a PGresult.
- `SetShellResultVariables` (518) — `SHELL_ERROR`, `SHELL_EXIT_CODE` from a `wait(2)`-style return.
- `SetPipelineVariables` (536) — `PIPELINE_SYNC_COUNT`, `PIPELINE_COMMAND_COUNT`, `PIPELINE_RESULT_COUNT`.
- `ClearOrSaveResult` (560) — if error, save into `pset.last_error_result` for `\errverbose`; else PQclear.

### `PSQLexec` (common.c:656)

The "back door" for internal queries. Subject to `ECHO_HIDDEN` (prints `/**** INTERNAL QUERY ****/`), bypasses `ECHO_QUERIES`. No transaction wrapping. Used by `\d`, `\sf`, `\password`, `lookup_object_oid`, etc. [verified-by-code, common.c:656-699]

### `PSQLexecWatch` (common.c:711)

`\watch`-specific. Calls `ExecQueryAndProcessResults(query, ..., is_watch=true, min_rows, opt, printQueryFout)`. Returns 1 / 0 / -1.

### `SendQuery` (common.c:1119)

The "front door". Lifecycle:
1. If `pset.singlestep`, print the query and wait for return-or-`x`. (common.c:1136-1151)
2. If `ECHO=queries`, echo. (common.c:1152-1156)
3. If logfile open, write `/******** QUERY *********/...`. (common.c:1158-1165)
4. **Implicit BEGIN.** If `PQTRANS_IDLE && !autocommit && !command_no_begin(query)`, issue `BEGIN`. `command_no_begin` (common.c:2266-2475) is a tiny lookahead parser that knows about transaction-control commands plus VACUUM/CLUSTER/CREATE DATABASE/CREATE INDEX CONCURRENTLY/etc. — exactly the keywords the backend's `PreventInTransactionBlock` rejects. [verified-by-code]
5. **ON_ERROR_ROLLBACK savepoint.** In INTRANS state with the option enabled, issue `SAVEPOINT pg_psql_temporary_savepoint`. (common.c:1188-1204)
6. **Dispatch.** Either `DescribeQuery(query, ...)` (for `\gdesc`) or `ExecQueryAndProcessResults`. (common.c:1206-1215)
7. **Savepoint cleanup.** Examine post-execution transaction status — `INERROR` → rollback to sp; `INTRANS && !svpt_gone` → release sp; `IDLE` → nothing; `ACTIVE`/`UNKNOWN` → log unexpected. (common.c:1220-1274)
8. **Timing print** if enabled. (common.c:1277-1278)
9. **Track `client_encoding` change.** If the server reported a different encoding after the query (e.g. user did `SET client_encoding`), update `pset.encoding`, `pset.popt.topt.encoding`, and the `ENCODING` variable. (common.c:1282-1290)
10. **`PrintNotifications`.** (common.c:1292)
11. **Cleanup** (common.c:1296-1338) — reset `pset.gfname`, restore `\g`-saved pset options, reset `\gset`/`\gdesc`/`\gexec`/`\crosstabview` triggers, `clean_extended_state` for `\bind` etc.

### `DescribeQuery` (common.c:1351)

`\gdesc` plumbing: PQprepare with `""` (unnamed statement), PQdescribePrepared, then SELECT against a VALUES list to format. Uses `PQescapeLiteral` for column names. [verified-by-code]

### `discardAbortedPipelineResults` (common.c:1467)

After a pipeline error, drain results until a `PGRES_PIPELINE_SYNC` or until counters say no more requested. Handles connection reset.

### `ExecQueryAndProcessResults` (common.c:1557)

Massive switch over `pset.send_mode`:
- `PSQL_SEND_QUERY` — `PQsendQuery` or `PQsendQueryParams` (if in a pipeline).
- `PSQL_SEND_EXTENDED_PARSE` / `_QUERY_PARAMS` / `_QUERY_PREPARED` / `_CLOSE` — `\parse`/`\bind*`/`\close_prepared`.
- `PSQL_SEND_START_PIPELINE_MODE` / `_END_PIPELINE_MODE` / `_PIPELINE_SYNC` — pipeline lifecycle.
- `PSQL_SEND_FLUSH` / `_FLUSH_REQUEST` / `_GET_RESULTS`.

Then a `PQgetResult` loop with chunked-mode handling (`PGRES_TUPLES_CHUNK`), COPY interception (`PGRES_COPY_OUT` / `_IN`), pipeline counter accounting, and cancel-pressed bailout. Returns 1 / 0 / -1. [verified-by-code, common.c:1557-2196]

Critical detail: COPY inside a pipeline is forbidden — psql calls `exit(EXIT_BADCONN)` if it happens (common.c:1895-1897). Comment explains the libpq sync-message ambiguity. [from-comment]

### `command_no_begin` (common.c:2266)

Multibyte-safe lookahead. Knows ABORT / BEGIN / START / COMMIT / END / ROLLBACK / PREPARE TRANSACTION / VACUUM / CLUSTER (without args) / CREATE [DATABASE|TABLESPACE|UNIQUE INDEX CONCURRENTLY] / ALTER SYSTEM / DROP/REINDEX [DATABASE|SYSTEM|TABLESPACE|TABLE CONCURRENTLY|INDEX CONCURRENTLY] / DISCARD ALL. The comment block at 2399-2403 is candid: "Note: these tests will match DROP SYSTEM and REINDEX TABLESPACE, which aren't really valid commands so we don't care much." [from-comment]

### Connection introspection (common.c:2481-2570)

- `is_superuser`, `standard_strings` — `PQparameterStatus` lookups.
- `session_username` — `session_authorization` parameter-status falling back to `PQuser`.
- `get_conninfo_value(keyword)` — copy a libpq conninfo option (caller frees).

### `expand_tilde` (common.c:2578)

`~` → `$HOME`; `~user` → `pw_dir`. No-op on WIN32. [verified-by-code]

### `uri_prefix_length` / `recognized_connection_string` (common.c:2636, 2706)

Detect `postgresql://` or `postgres://` URI prefixes. Both flagged with `XXX This is a duplicate of the eponymous libpq function`. [from-comment]

### `clean_extended_state` (common.c:2662)

After every query or new extended-protocol meta-command, free `pset.stmtName` and any `pset.bind_params[]`. Switch over `pset.send_mode`. [verified-by-code]

## State / globals

- `volatile sig_atomic_t sigint_interrupt_enabled` (304) — defined here.
- `sigjmp_buf sigint_interrupt_jmp` (306) — defined here.
- All other state goes through `pset` (defined in startup.c).

## Concurrency / signal handling

This file owns the SIGINT longjmp protocol. The contract:

- A blocking-read caller (`gets_interactive`, `gets_fromFile`, `simple_prompt_extended`, `handleCopyIn`'s `fread`/`fgets`) sets `sigint_interrupt_enabled = true` IMMEDIATELY before the read and clears it after.
- Some outer scope must have called `sigsetjmp(sigint_interrupt_jmp, 1)` recently enough that the saved context is still valid. Currently: `MainLoop` (mainloop.c:107) and `handleCopyIn` (copy.c:521).
- `psql_cancel_callback` SIGINT handler: if enabled, `siglongjmp`; else `cancel_pressed = true`. On WIN32 the longjmp arm is omitted. [from-comment, common.c:300-303]

`disable_sigpipe_trap` / `restore_sigpipe_trap` (from fe_utils) wrap any `popen` write-side: `SetupGOutput`, `\copy program`, `\watch` pager, `\w |prog`, `\o |prog`. [verified-by-code, common.c:97, 116]

## Phase D notes

- **`PSQLexec` echo of internal queries.** `ECHO_HIDDEN` writes the literal internal SQL to stdout AND to the logfile (common.c:667-680). `\password` does not use `PSQLexec` for the password change — it uses `PQchangePassword` (command.c:2593) — but the lookup of `CURRENT_USER` (`SELECT CURRENT_USER`) at command.c:2561 DOES go through `PSQLexec`. So `\password` with `ECHO_HIDDEN=on` logs the username lookup but not the password itself. [verified-by-code]
- **Logfile contents.** When `-L logfile` is set, `SendQuery` writes every user query into the logfile (common.c:1158-1165). This includes `CREATE USER … PASSWORD '…'` text. Same risk as PSQL_HISTORY but the logfile is `fopen(filename, "a")` with default umask — no chmod. [verified-by-code, startup.c:350; common.c:1158] [ISSUE-secret-scrub: -L logfile captures full text of queries including embedded PASSWORD literals; logfile permissions follow umask not 0600 (likely)]
- **Pipeline COPY abort exits the process.** common.c:1895-1897 calls `exit(EXIT_BADCONN)` — comment explains libpq's sync-vs-COPY ambiguity. Hard exit is heavy-handed but documented. [from-comment]
- **`psql_get_variable` PQUOTE_SHELL_ARG** uses `appendShellStringNoError` which fails on `\n`/`\r` and otherwise single-quote-wraps. Backtick-context variable expansion in scripts is therefore safe against argument-splitting but NOT against shell metacharacters inside the variable that the user's `\!`-targeted shell command then evaluates as part of larger context. The wrapping function does proper single-quote escape. [verified-by-code, common.c:246-266]
- **`PQescapeLiteral` / `PQescapeIdentifier`** require `pset.db`. If a `:'foo'` is referenced in a `-c` script BEFORE the connection is up — impossible in practice because connection happens before action processing in main — but if a connection drop happens mid-script and the next line uses `:'foo'`, the substitution returns NULL with `pg_log_error("cannot escape without active connection")`. [verified-by-code, common.c:216-220]
- **`StoreQueryTuple` `\gset` rejects hook-protected variables.** common.c:826-831 emits a warning and skips. This prevents `\gset` from clobbering `AUTOCOMMIT` or `PROMPT1`. Documented per the comment in EstablishVariableSpace. [verified-by-code, common.c:826]
- **`ExecQueryTuples` `\gexec`** sends each cell value through `SendQuery` (common.c:898) — so a hostile server can craft result rows containing arbitrary SQL that psql will then execute against itself. This is the documented purpose of `\gexec`; users should only run it against trusted result sets. [verified-by-code, common.c:862-920] [ISSUE-trust-boundary: `\gexec` is a documented "execute server-returned text as SQL" feature; the user is the trust boundary (nit, by-design)]
- **Asynchronous notifications.** `PrintNotifications` (common.c:741) writes the LISTEN payload (`notify->extra`) and pid to `pset.queryFout` — directly, no escaping. The payload is server-supplied text; it can contain ANSI escape sequences that a misbehaving terminal would interpret. Same risk class as any pg_log_error on server text. [verified-by-code, common.c:751-755] [ISSUE-trust-boundary: NOTIFY payload printed verbatim to terminal — terminal-escape injection (nit, by-design)]
- **`SetResultVariables` clears `LAST_ERROR_MESSAGE` only on failure** (common.c:478-505). On a successful query that follows an error, `LAST_ERROR_MESSAGE` retains its previous content — by design, but easy to misread in scripts. [verified-by-code]
- **`uri_prefix_length` / `recognized_connection_string`** are libpq duplicates per their own XXX comments. [from-comment] [ISSUE-stale-todo: XXX duplicate-of-libpq tags on common.c:2634, 2704 (nit)]

## Potential issues (compact)

- [ISSUE-secret-scrub: `-L logfile` captures CREATE USER … PASSWORD literals at default umask (likely)]
- [ISSUE-trust-boundary: `\gexec` runs server-returned text as SQL — documented feature, document it for users (nit, by-design)]
- [ISSUE-trust-boundary: NOTIFY payload printed unescaped to terminal (nit, by-design)]
- [ISSUE-undocumented-invariant: SIGINT longjmp protocol depends on every blocking read resetting `sigint_interrupt_enabled`; one missed reset = use-after-jmp (nit)]
- [ISSUE-stale-todo: XXX duplicate-of-libpq on uri_prefix_length / recognized_connection_string (nit)]

## Cross-references

- `mainloop.c` — primary caller of SendQuery; consumes `sigint_interrupt_jmp`.
- `command.c` — every backslash command ultimately drives either PSQLexec or SendQuery.
- `copy.c::handleCopy{In,Out}` — dispatched from HandleCopyResult.
- `fe_utils/cancel.h` — setup_cancel_handler, cancel_pressed, ResetCancelConn, SetCancelConn.
- `fe_utils/print.h` — printQuery, printQueryOpt, ClosePager, PageOutput.
- `startup.c` — defines `pset`, calls `psql_setup_cancel_handler`.

## Confidence tally

`[verified-by-code]=28 [from-comment]=6 [inferred]=1`
