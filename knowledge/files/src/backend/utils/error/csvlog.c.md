# csvlog.c

- **Source path:** `source/src/backend/utils/error/csvlog.c`
- **Lines:** 262
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `error/elog.c` (the upstream that decides to call this), `error/jsonlog.c` (sibling format), `postmaster/syslogger.c` (writes the file when running under logging collector)

## Purpose

Formats an `ErrorData` into the comma-separated `csvlog` line format documented in `config.sgml`, then ships the bytes either directly to the syslogger file (if we *are* the syslogger) or through `write_pipe_chunks` to the syslogger pipe. Quote/escape uses the standard PostgreSQL CSV convention: quote = escape = `"`, fields are double-quoted, embedded `"` is doubled. [from-comment, csvlog.c:31-35, 57-60]

## Top-of-file comment (verbatim)

> "csvlog.c — CSV logging." Plus the function header: "write_csvlog — Generate and write CSV log entry. Constructs the error message, depending on the Errordata it gets, in a CSV format which is described in doc/src/sgml/config.sgml." [from-comment, csvlog.c:1-13, 56-61]

## Public surface

- `write_csvlog(ErrorData *edata)` (62) — the only public entry. Called by `send_message_to_server_log` (elog.c:3675) when `LOG_DESTINATION_CSVLOG` is set in `Log_destination`.

## Static helpers

- `appendCSVLiteral(buf, data)` (36) — write `data` as a quoted CSV string, doubling embedded `"`. NULL input → write nothing (empty field).

## CSV column order (load-bearing — consumers parse positionally)

1. log_time (timestamp with ms)
2. user_name
3. database_name
4. process_id
5. connection_from (`"host:port"`)
6. session_id (`%lx.%x` of MyStartTime + MyProcPid)
7. session_line_num (per-process counter, reset on PID change)
8. command_tag (PS display)
9. session_start_time
10. virtual_transaction_id (`procNumber/lxid`)
11. transaction_id (`GetTopTransactionIdIfAny()`)
12. error_severity (localized, via `error_severity` from elog.c)
13. sql_state_code (`unpack_sql_state` from elog.c)
14. message (errmsg)
15. detail (`detail_log` if set, otherwise `detail`)
16. hint
17. internal_query
18. internal_query_pos (only if internal_query non-null and >0)
19. context (suppressed if `edata->hide_ctx`)
20. user_query (suppressed via `check_log_of_query` if `edata->hide_stmt` or similar)
21. user_query_pos (cursorpos, only if user_query printed)
22. file_location (`funcname, filename:lineno`) — only if `Log_error_verbosity >= PGERROR_VERBOSE`
23. application_name
24. backend_type (`get_backend_type_for_log`)
25. leader_pid (only for parallel workers, when `MyProc->lockGroupLeader && leader->pid != MyProcPid`)
26. query_id (`pgstat_get_my_query_id()`)

Terminated with `\n`. [verified-by-code, csvlog.c:85-253]

## Key invariants

- **Line-number counter is static and per-process; reset when `MyProcPid` changes** (so EXEC_BACKEND children don't inherit the postmaster's counter). Also calls `reset_formatted_start_time()` on the same reset event. [verified-by-code, csvlog.c:69-84]
- **`MyBackendType == B_LOGGER` writes the file directly; otherwise the line is shipped via the pipe protocol.** This handles the case where the syslogger itself emits a log message — it cannot write into its own pipe without deadlocking. [verified-by-code, csvlog.c:256-259]
- **Empty fields are emitted as bare `,`**, not `""`. `appendCSVLiteral(NULL)` is the explicit branch that ensures this. [verified-by-code, csvlog.c:42-44]
- **Backend type emitted in column 24, leader PID in 25** — these were appended at the end to preserve backward compatibility with parsers reading earlier columns.
- **`vxid` field format must stay in sync with `lockfuncs.c`** (`pg_locks` view) — comment at line 152.

## Cross-references

- Format is documented in `doc/src/sgml/config.sgml`; consumed by `postgres_fdw` log shippers and a handful of monitoring tools (pgBadger, etc.).
- `write_pipe_chunks` lives in elog.c (3916) and uses the syslogger framing protocol.
- All the formatter helpers (`get_formatted_log_time`, `get_formatted_start_time`, `error_severity`, `unpack_sql_state`, `check_log_of_query`, `get_backend_type_for_log`) are in elog.c.

## Open questions

- None — the format is rigid by contract.

## Confidence tag tally

`[verified-by-code]=6 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=0`
