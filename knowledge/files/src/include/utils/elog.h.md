# elog.h

- **Source path:** `source/src/include/utils/elog.h`
- **Lines:** 535
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `backend/utils/error/elog.c` (implementation), `utils/errcodes.h` (SQLSTATE table)
- **Pair with skill:** `.claude/skills/error-handling/`

## Purpose

The compile-time surface of the error reporting subsystem: error-level constants, SQLSTATE encoding, `ereport`/`elog`/`errsave`/`ereturn` macros, `PG_TRY` / `PG_CATCH` / `PG_FINALLY` / `PG_RE_THROW` macros, the `ErrorContextCallback` struct and stack-of-callbacks API, and prototypes for every `errxxx()` field setter implemented in elog.c. **Every C source file that reports errors includes this file.** [verified-by-code]

## Top-of-file comment

> "POSTGRES error reporting/logging definitions." [from-comment, elog.h:3-5]

## Error level constants (the priority ladder)

```
LOG_NEVER = 0   (suppress always)
DEBUG5    = 10  ... DEBUG1 = 14
LOG       = 15  (server log only by default; sorts BETWEEN ERROR and FATAL for log routing — see is_log_level_output)
LOG_SERVER_ONLY = COMMERROR = 16
INFO            = 17  (always to client, default not to server log)
NOTICE          = 18
WARNING         = PGWARNING = 19
WARNING_CLIENT_ONLY = 20  (never to server log)
ERROR           = PGERROR  = 21
FATAL           = 22
FATAL_CLIENT_ONLY = 23
PANIC           = 24
```
[verified-by-code, elog.h:26-58]

`PGWARNING` and `PGERROR` are aliases for the rare case where a third-party header defines `WARNING` / `ERROR` (e.g. on Windows). [from-comment, elog.h:60-65]

## SQLSTATE encoding

`MAKE_SQLSTATE(ch1,ch2,ch3,ch4,ch5)` packs five 6-bit characters into a 32-bit int. `ERRCODE_TO_CATEGORY(ec)` and `ERRCODE_IS_CATEGORY(ec)` derive the SQLSTATE category. Actual error code constants live in `utils/errcodes.h` (generated from `errcodes.txt`). [verified-by-code, elog.h:68-81]

## The `ereport` macro family

```
ereport(elevel, ...)               → ereport_domain(elevel, TEXTDOMAIN, ...)
ereport_domain(elevel, domain, ...) →
    if ((elevel >= ERROR ? errstart_cold(elevel, domain) : errstart(elevel, domain)))
        ..., errfinish(__FILE__, __LINE__, __func__);
    if (elevel >= ERROR) pg_unreachable();
```
[verified-by-code, elog.h:143-167]

Key properties:
- **Compile-time dispatch to `errstart_cold` when `elevel` is a constant `>= ERROR`** — lets the compiler treat the call as cold and tighten the hot path. Requires `HAVE_PG_INTEGER_CONSTANT_P` (gcc/clang `__builtin_constant_p`).
- **`pg_unreachable()` after the call for constant `elevel >= ERROR`** — signals the compiler that control does not return.
- **`pg_prevent_errno_in_scope()`** declares a dummy local that shadows `errno` to catch the trap of writing `errmsg("...%m...", errno)` (the `%m` already reads errno itself).
- **`elog(elevel, ...)` is a thin wrapper:** `ereport(elevel, errmsg_internal(__VA_ARGS__))`. So `elog` is `ereport` with a non-translatable format and no other fields. [verified-by-code, elog.h:242-243]

## The `errsave`/`ereturn` (soft-error) family

```
errsave(context, ...) - if context is an ErrorSaveContext node, record details into it
                        and return normally; otherwise behave as ereport(ERROR, ...).
ereturn(context, dummy_value, ...) - errsave(...) + return dummy_value;
```
[from-comment, elog.h:247-296]

Soft errors are how PG implements `CAST ... AS ... ON ERROR` and similar non-throwing parse paths. The receiving function checks `context->error_occurred` after the call.

## `ErrorContextCallback` and the callback stack

```
typedef struct ErrorContextCallback {
    struct ErrorContextCallback *previous;
    void  (*callback) (void *arg);
    void  *arg;
} ErrorContextCallback;
extern PGDLLIMPORT ErrorContextCallback *error_context_stack;
```
[verified-by-code, elog.h:311-318]

Callbacks are pushed onto `error_context_stack` (manually, as locals) and popped before returning. `errfinish` walks the stack calling each callback's `callback(arg)`, which is expected to invoke `errcontext()` to append a context line.

## `PG_TRY` / `PG_CATCH` / `PG_FINALLY` / `PG_RE_THROW`

Defined later in the header (around line 380+). Built on `sigsetjmp` writing to a per-block `sigjmp_buf` and chaining onto `PG_exception_stack`. Key semantic notes from the comments at lines 321-372:
- **Only catches `ereport(ERROR)`**; `FATAL` blows straight through to `proc_exit`.
- **CATCH must end with either `PG_RE_THROW()` or a (sub)transaction abort.** Otherwise the system is left in an inconsistent state.
- **`PG_FINALLY` and `PG_CATCH` are mutually exclusive within a single `PG_TRY`.**
- **Cleanup of non-process-local resources should use `PG_ENSURE_ERROR_CLEANUP`** (storage/ipc.h), not raw `PG_CATCH`, because FATAL bypasses CATCH.

## Field setters (return int 0 so they chain inside ereport)

`errcode`, `errcode_for_file_access`, `errcode_for_socket_access`, `errmsg`, `errmsg_internal`, `errmsg_plural`, `errdetail`, `errdetail_internal`, `errdetail_log`, `errdetail_log_plural`, `errdetail_plural`, `errhint`, `errhint_internal`, `errhint_plural`, `errcontext_msg` + `set_errcontext_domain` (combined via the `errcontext` macro), `errhidestmt`, `errhidecontext`, `errbacktrace`, `errposition`, `internalerrposition`, `internalerrquery`, `err_generic_string`. Read-back: `geterrcode`, `geterrposition`, `getinternalerrposition`. [verified-by-code, elog.h:177-234]

## Key invariants

- **`errstart`'s `bool` return drives short-circuit of the entire setter chain.** If `errstart` returns false, no `errmsg`/`errdetail` runs. (See the `MOST CONFUSING THING` block in elog.c.md.) [verified-by-code, elog.h:147-150 — the `?:` in ereport_domain]
- **`pg_prevent_errno_in_scope` is in scope for the duration of the ereport.** On Linux it declares `int __errno_location` as a local — any code that calls `errno` inside the ereport will see this local instead, producing a compile error. Designed to catch the `errmsg("...%m...", errno)` antipattern. [from-comment, elog.h:84-98]
- **`elog` is `ereport` + `errmsg_internal`** — important: it is NOT translated. Use `ereport(LEVEL, errmsg(...))` if the message should be localized.
- **`errcontext` is a macro, not a function** — it expands to `set_errcontext_domain(TEXTDOMAIN), errcontext_msg`, so the comma operator means callers must write `errcontext("...")` syntactically as if it were a function but it's actually two calls. [from-comment, elog.h:206-214]
- **`PG_RE_THROW` does NOT return** to the CATCH block; it `siglongjmp`s to the next outer setjmp on `PG_exception_stack`.

## Cross-references

- All level constants flow into `elog.c::is_log_level_output` and `should_output_to_server`/`_to_client`.
- `errcodes.h` is generated by `src/backend/utils/generate-errcodes.pl` from `src/backend/utils/errcodes.txt`.
- `PG_TRY`/`PG_CATCH` semantics + `pg_re_throw` failure mode documented in detail at `knowledge/files/src/backend/utils/error/elog.c.md`.
- Skill: `.claude/skills/error-handling/` for the ereport/elog idiom guide.

## Open questions

- Whether `errsave` correctly propagates messages through `ThrowErrorData` for the case where a soft error is later upgraded to a hard one. [unverified]

## Confidence tag tally

`[verified-by-code]=8 [from-comment]=6 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/error-handling.md](../../../../idioms/error-handling.md)