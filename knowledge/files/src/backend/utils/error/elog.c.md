# elog.c

- **Source path:** `source/src/backend/utils/error/elog.c`
- **Lines:** 4273
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/utils/elog.h` (the macro surface: `ereport`, `elog`, `errmsg`, `PG_TRY` etc., error level constants); `error/assert.c` (Assert handler); `error/csvlog.c`, `error/jsonlog.c` (alternate output formats); `utils/mmgr/mcxt.c` (ErrorContext memory); `tcop/postgres.c` (the topmost `PG_TRY` / longjmp catcher); `postmaster/syslogger.c` (pipe consumer)
- **Pair with skill:** `.claude/skills/error-handling/` (ereport vs elog idioms)

## Purpose

The whole PostgreSQL error/log reporting machinery. Three intertwined responsibilities:

1. **Error-frame state machine.** `errstart` opens a frame on the `errordata[]` stack, then `errmsg/errcode/errdetail/...` populate it, then `errfinish` either logs the message (LOG/INFO/NOTICE/WARNING/DEBUG*) or `longjmp`s out of an `ERROR` (via `PG_RE_THROW`), or `proc_exit`s on FATAL, or `abort()`s on PANIC. The macros in elog.h compile-time-decide between `errstart_cold` (for elevel ≥ ERROR) and `errstart` (for warning-or-less).
2. **Output routing.** `EmitErrorReport` → `send_message_to_server_log` (formats with log_line_prefix, optionally calls `write_csvlog` / `write_jsonlog` / `write_syslog` / `write_eventlog` / `write_console`) and `send_message_to_frontend` (libpq protocol). Routing decided by `Log_destination` (bitmask) and `whereToSendOutput`.
3. **Recursion / exhaustion handling.** Re-entrant calls during message construction get a stack frame (depth ≤ `ERRORDATA_STACK_SIZE = 5`); actual recursion (an error inside elog itself) is detected by `recursion_depth > 2` (`in_error_recursion_trouble`), at which point the code stops translating, resets `ErrorContext`, and bulldozes through with un-localized text.

## Top-of-file comment (verbatim, key passages)

> "Because of the extremely high rate at which log messages can be generated, we need to be mindful of the performance cost of obtaining any information that may be logged. Also, it's important to keep in mind that this code may get called from within an aborted transaction, in which case operations such as syscache lookups are unsafe." [from-comment, elog.c:6-10]
>
> "We need to be robust about recursive-error scenarios... First, distinguish between re-entrant use and actual recursion. It is possible for an error or warning message to be emitted while the parameters for an error message are being computed... We handle this by providing a (small) stack of ErrorData records... Second, actual recursion will occur if an error is reported by one of the elog.c routines or something they call. By far the most probable scenario of this sort is 'out of memory'; and it's also the nastiest to handle because we'd likely also run out of memory while trying to report this error! Our escape hatch for this case is to reset the ErrorContext to empty before trying to process the inner error. Since ErrorContext is guaranteed to have at least 8K of space in it (see mcxt.c), we should be able to process an 'out of memory' message successfully." [from-comment, elog.c:12-43]

## Public surface (selected — full list in headers)

### Macro-driven entry (defined in elog.h, dispatched here)
- `errstart(elevel, domain)` (355) / `errstart_cold` (339) — open frame; return false to short-circuit if message would be dropped.
- `errfinish(filename, lineno, funcname)` (486) — close frame: emit, then for ERROR `PG_RE_THROW`, for FATAL `proc_exit(1)`, for PANIC `abort()`.
- `errsave_start` / `errsave_finish` (651, 703) — "soft errors": if context is `ErrorSaveContext`, set its `error_occurred` flag instead of throwing.

### Field setters (all return `int` 0 so they can chain inside `ereport(level, errcode(...), errmsg(...))`)
- `errcode(sqlerrcode)` (875), `errcode_for_file_access` (898), `errcode_for_socket_access` (977).
- `errmsg`, `errmsg_internal`, `errmsg_plural` (1094, 1349, 1372). `errmsg` runs the format string through `gettext()`; `errmsg_internal` does not (use for "internal" messages we don't translate).
- `errdetail`, `errdetail_internal`, `errdetail_log`, `errdetail_log_plural`, `errdetail_plural` (1395, 1422, 1443, 1464, 1487). `errdetail_log` is the *server-log-only* variant — when both `detail_log` and `detail` are set, csv/json log uses `detail_log` and the client gets `detail`.
- `errhint`, `errhint_internal`, `errhint_plural` (1509, 1531, 1552).
- `errcontext_msg`, `set_errcontext_domain` (1578, 1604) — used by error-context callback functions.
- `errhidestmt`, `errhidecontext`, `errposition`, `internalerrposition`, `internalerrquery` (1624-1725).
- `err_generic_string(field, str)` (1725) — sets `schema_name`/`table_name`/`column_name`/`datatype_name`/`constraint_name`.
- `errbacktrace()` (1116) — request a backtrace be captured for this error.

### Error frame manipulation
- `CopyErrorData()` (1942), `FreeErrorData` (2014), `FreeErrorDataContents` (2026), `FlushErrorState` (2063), `ThrowErrorData` (2091), `ReThrowError` (2150), `pg_re_throw` (2200), `EmitErrorReport` (1883), `GetErrorContextStack` (2255), `geterrcode`/`geterrposition`/`getinternalerrposition` (1774, 1791, 1808), `format_elog_string` (1850), `pre_format_elog_string` (1841), `message_level_is_interesting` (285), `in_error_recursion_trouble` (306).

### Setup / sinks
- `DebugFileOpen` (2307) — open `OutputFileName` as stderr replacement.
- `check_log_min_messages`/`assign_log_min_messages` (2363/2591), `check_backtrace_functions`/`assign_backtrace_functions` (2608/2669), `check_log_destination`/`assign_log_destination` (2678/2742) — GUC plumbing.
- `assign_syslog_ident` (2751), `assign_syslog_facility` (2783); `write_syslog` (2808), `write_eventlog` (2934), `write_console` (3028) — platform sinks.
- `get_formatted_log_time` (3106), `reset_formatted_start_time`, `get_formatted_start_time` (3144, 3156), `check_log_of_query` (3180), `get_backend_type_for_log` (3203) — shared formatting helpers used by csvlog.c / jsonlog.c.
- `process_log_prefix_padding` (3230), `log_line_prefix` (3261), `log_status_format` (3270) — `%`-escape format engine for `log_line_prefix`.
- `unpack_sql_state(sql_state)` (3655) — 32-bit packed SQLSTATE → 5-char ASCII.
- `send_message_to_server_log` (3675) — the canonical stderr-format writer; calls `write_pipe_chunks` if running under syslogger, else `write_console`. Routes to csv/json sinks when those bits set in `Log_destination`.
- `write_pipe_chunks` (3916) — syslogger pipe protocol (PIPE_CHUNK_SIZE framing).
- `err_sendstring` (3967), `send_message_to_frontend` (3979) — libpq protocol writer.
- `error_severity(elevel)` (4157) — `DEBUG`/`LOG`/`INFO`/`NOTICE`/`WARNING`/`ERROR`/`FATAL`/`PANIC` string mapping.
- `write_stderr`, `vwrite_stderr` (4229, 4244) — last-resort stderr writer used before init or after teardown.

## Key types / state

- `ErrorData` — defined in `elog.h`; fields include elevel, output_to_server, output_to_client, hide_stmt, hide_ctx, domain, context_domain, sqlerrcode, message, detail, detail_log, hint, context, message_id, schema_name/table_name/column_name/datatype_name/constraint_name, cursorpos, internalpos, internalquery, saved_errno, filename, lineno, funcname, backtrace, assoc_context.
- `static ErrorData errordata[ERRORDATA_STACK_SIZE = 5]` (156) — the re-entrancy stack; `errordata_stack_depth` (158) is the top index, `recursion_depth` (160) counts true recursion.
- `ErrorContextCallback *error_context_stack` (100) — `extern`; macro `PG_RE_THROW()` etc. unwind via this and via `PG_exception_stack` (102, the `sigjmp_buf*`).
- `emit_log_hook` (111) — extensible hook called *after* the message has been formatted but before it goes to a sink. **Does not see messages suppressed by `log_min_messages`.**
- `saved_timeval`, `formatted_log_time`, `formatted_start_time` (166-171) — memoized formatted timestamps shared with csvlog/jsonlog so a single ereport produces a single timestamp across all sinks.

## Key invariants (load-bearing)

- **`CritSectionCount > 0` → ERROR is promoted to PANIC.** Set in `errstart` line 372. The whole "critical section" abstraction is enforced here. [verified-by-code]
- **`PG_exception_stack == NULL || ExitOnAnyError || proc_exit_inprogress` → ERROR is promoted to FATAL.** Three cases: in postmaster or early startup (no setjmp installed), initdb's --bootstrap mode, or already exiting. [verified-by-code, elog.c:387-393]
- **A stacked higher-severity error must not be downgraded** — `errstart` walks the existing stack and takes `Max(elevel, errordata[i].elevel)` (line 403-405).
- **`errfinish` does not return for ERROR/FATAL/PANIC.** ERROR → `PG_RE_THROW` (siglongjmp). FATAL → `proc_exit(1)`. PANIC → `abort()`. [verified-by-code, elog.c:551, 608, 621]
- **All error-frame work happens in `ErrorContext`** (switched at elog.c:505). `ErrorContext` has a reserved 8 KB so OOM can be reported. [from-comment]
- **`InterruptHoldoffCount`, `QueryCancelHoldoffCount`, `CritSectionCount` are reset to 0 before `PG_RE_THROW`** (lines 540-543). This is why a `PG_TRY/PG_CATCH` block must re-establish any holdoff state it needs.
- **`pg_re_throw` with no outer setjmp = FATAL, not undefined behavior.** Lines 2206-2236 detect this case, mutate `edata->elevel` to FATAL, clear `error_context_stack`, and call `errfinish` again. [verified-by-code]
- **`PG_TRY/PG_CATCH/PG_END_TRY` requires `FlushErrorState()` or `PG_RE_THROW()` in CATCH.** Forgetting both leaves `errordata_stack_depth >= 0`, causing future `errstart` calls to misbehave; `FlushErrorState` explicitly resets to -1 (line 2071).
- **`error_context_stack` callbacks run with no special protection.** If a callback errors, it just opens a new frame (and the inner error wins if it's ≥ ERROR). [from-comment, elog.c:514-518]
- **Hook order in `send_message_to_server_log`:** `emit_log_hook` first (can short-circuit), then platform sinks per `Log_destination` mask, then csv/json sinks, then frontend. The hook does NOT see messages dropped by `log_min_messages`. [from-comment, elog.c:104-109]
- **`is_log_level_output(elevel, log_min_level)`** has special-case treatment for LOG (sorts between ERROR and FATAL for the *server log* test) and WARNING_CLIENT_ONLY/FATAL_CLIENT_ONLY (never sent to log, regardless of log_min_messages). [verified-by-code, elog.c:213-237]
- **`ClientAuthInProgress` overrides client_min_messages**: during authentication, only `>= ERROR` goes to the client (security + many clients can't handle NOTICE during auth). [from-comment, elog.c:262-269]
- **Soft errors via `errsave`**: if the caller passed an `ErrorSaveContext` node and only wants notification (`!details_wanted`), `errsave_start` returns false WITHOUT opening a frame — so the field-setter macros following must compile-time-detect this. The macro in elog.h wraps everything in `if (errsave_start(...)) { ... errsave_finish(...); }`. [verified-by-code]

## Error level promotion ladder (in `errstart`, elog.c:362-405)

1. CritSectionCount > 0 → ERROR/FATAL → PANIC.
2. elevel == ERROR AND (no PG_exception_stack OR ExitOnAnyError OR proc_exit_inprogress) → FATAL.
3. Existing stacked error of higher severity → promote to its level.

This ordering is asymmetric: a FATAL inside a CRIT becomes PANIC; an ERROR with no handler becomes FATAL but does NOT become PANIC unless CRIT is also active.

## Most-confusing single thing

**`errstart` returns `bool`, and that return value silently short-circuits the entire field-setter chain.** The `ereport(level, errcode(...), errmsg(...), errdetail(...))` macro expands to roughly `if (errstart(level, TEXTDOMAIN)) { errcode(...), errmsg(...), errdetail(...), errfinish(...); }`. If `errstart` returns false (because `elevel < ERROR && !output_to_server && !output_to_client`), **none of the `errmsg`/`errdetail` calls run at all** — which means any side effects in arguments to those functions (function calls in the format args, `errcode_for_file_access()` etc.) also don't run. This is intentional ("no point computing a message we won't emit") and is fronted by `message_level_is_interesting` (line 285) for callers that want to guard expensive pre-computation, but it surprises every newcomer who tries to put a debugging assertion or counter inside an `errdetail(some_function(...))` and finds it silently absent at LOG severity. The cold attribute on `errstart_cold` (line 338) and the per-elevel dispatch in the elog.h macro further obscure the path. **If you ever wonder "why didn't my errdetail run?" — it's this.** [verified-by-code, elog.c:407-415 plus elog.h macro expansion]

## Cross-references

- The `PG_TRY` / `PG_CATCH` / `PG_END_TRY` / `PG_RE_THROW` macros are defined in elog.h around `PG_exception_stack` and `sigsetjmp`. Topmost `sigsetjmp` is installed in `PostgresMain` (tcop/postgres.c) — its catch reinitializes per-query state.
- `ErrorContext` is created in `mcxt.c::MemoryContextInit`; the 8 KB reserve is allocated by `AllocSetContextCreateInternal` for that one context.
- csvlog.c and jsonlog.c reuse `get_formatted_log_time`, `get_formatted_start_time`, `error_severity`, `unpack_sql_state`, `check_log_of_query`, `get_backend_type_for_log`, `write_pipe_chunks` from this file.
- Syslogger pipe consumer: `postmaster/syslogger.c::process_pipe_input` parses the chunks `write_pipe_chunks` emits.
- Error-handling idiom guidance: `.claude/skills/error-handling/SKILL.md`.

## Open questions

- Whether `emit_log_hook` is allowed to throw. Most extensions assume not, but the code calls it without a `PG_TRY` (the comment at line 105 only warns about message suppression). [unverified]
- Behaviour of nested FATAL inside ShutdownPostgres `before_shmem_exit` callback — the `proc_exit_inprogress` flag promotes ERROR→FATAL but ordering against the outer FATAL's `proc_exit(1)` is delicate. [unverified]
- Exact interaction between `pg_re_throw`'s "promote ERROR to FATAL without setjmp" path and `ExitOnAnyError` (initdb mode) — both lead to FATAL but via different code paths. [unverified — low risk]

## Confidence tag tally

`[verified-by-code]=18 [from-comment]=11 [from-readme]=0 [inferred]=0 [unverified]=3`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/error-handling.md](../../../../../idioms/error-handling.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/error-context-callbacks.md](../../../../../idioms/error-context-callbacks.md)

