# Error handling in PostgreSQL backend code

Reporting and recovery for the per-backend C code. Frontend libpq has its own
conventions; this file covers `src/backend/`.

Anchors (cite these directly when extending):
- `source/src/include/utils/elog.h` (the API)
- `source/src/backend/utils/error/elog.c` (the engine)
- Docs chapter "Error Message Reporting": <https://www.postgresql.org/docs/current/error-message-reporting.html> [from-docs]
- Style guide: <https://www.postgresql.org/docs/current/error-style-guide.html> [from-docs]
- Wiki: <https://wiki.postgresql.org/wiki/Error_messages> [from-wiki]

## The two entry points: ereport vs elog

`ereport(elevel, ...)` is the new-style API; `elog(elevel, fmt, ...)` is a thin
macro shorthand. `elog` expands to `ereport(elevel, errmsg_internal(__VA_ARGS__))`
[verified-by-code] (`elog.h:242`).

Practical split:
- **`ereport`** — user-facing errors. Carries an SQLSTATE (`errcode()`), a
  translatable primary message (`errmsg()`), and optional detail/hint/context.
- **`elog`** — "should never happen" internal errors, debug, log. The message
  goes through `errmsg_internal()` which means **not translated** (no `gettext`
  marker) and SQLSTATE defaults to `ERRCODE_INTERNAL_ERROR` for elevel ≥ ERROR
  [from-comment] (`elog.h:108-112`, lines 242-243).

Style guide: use `elog` only for cases that "should never happen" — i.e. internal
inconsistencies — and `ereport` for everything the user might see [from-docs].

## Elevel ladder

From `elog.h:26-58` [verified-by-code]:

| Level | Numeric | Meaning |
|---|---|---|
| `DEBUG5..DEBUG1` | 10..14 | Decreasing detail; `DEBUG1` is the GUC-debug level |
| `LOG` | 15 | Server log, not sent to client by default |
| `LOG_SERVER_ONLY` / `COMMERROR` | 16 | Same as LOG, never to client |
| `INFO` | 17 | Always to client, not to server log by default |
| `NOTICE` | 18 | To client, expected events (e.g. SERIAL creating sequence) |
| `WARNING` | 19 | To client + log; unexpected but non-fatal |
| `WARNING_CLIENT_ONLY` | 20 | Like WARNING but never to log |
| `ERROR` | 21 | Abort current transaction; longjmp out |
| `FATAL` | 22 | Abort the backend process |
| `FATAL_CLIENT_ONLY` | 23 | Fatal but no client message |
| `PANIC` | 24 | Take down all backends (postmaster restarts the cluster) |

Above `WARNING` the call **does not return**. The macro tells the compiler via
`pg_unreachable()` when elevel is a compile-time constant ≥ ERROR
[from-comment] (`elog.h:133-140`).

NOTICE vs WARNING distinction: NOTICE = expected, WARNING = unexpected
[from-comment] (`elog.h:44-49`).

## What ereport actually does on ERROR

`ereport(ERROR, ...)` does **not return**. It `longjmp`s to the nearest
`sigsetjmp` installed by `PG_TRY` or, if there is none, to the top-level loop
in `PostgresMain` which aborts the transaction. The exception stack lives in
the global `PG_exception_stack` [verified-by-code] (`elog.h:388-424`).

The longjmp is why C-level resource cleanup in PG is dominated by memory
contexts and resource owners, not by explicit `goto cleanup`. See
`knowledge/idioms/memory-contexts.md` and `ResourceOwner` (separate idiom).

## The auxiliary errxxx() functions

All of these return `int` so they can be chained inside the `ereport(...)`
varargs [verified-by-code] (`elog.h:177-225`):

- `errcode(ERRCODE_*)` — sets SQLSTATE. Defined in `utils/errcodes.h` (generated
  from `src/backend/utils/errcodes.txt`). Default for `elevel >= ERROR` is
  `ERRCODE_INTERNAL_ERROR`; for WARNING `ERRCODE_WARNING`; otherwise
  `ERRCODE_SUCCESSFUL_COMPLETION` [from-comment] (`elog.h:108-112`).
- `errcode_for_file_access()` / `errcode_for_socket_access()` — convert
  current `errno` to the appropriate SQLSTATE.
- `errmsg(fmt, ...)` — primary message, **translated** via `gettext`.
- `errmsg_internal(fmt, ...)` — primary message, **not translated**. Use for
  "can't happen" conditions and elog's expansion.
- `errmsg_plural(sing, plur, n, ...)` — `ngettext`-aware plural form.
- `errdetail(fmt, ...)` — secondary message; full sentences, translated.
- `errdetail_internal`, `errdetail_log`, `errdetail_log_plural`,
  `errdetail_plural` — variants for log-only or untranslated detail.
- `errhint(fmt, ...)` — actionable suggestion to the user.
- `errcontext(fmt, ...)` — wraps the call stack message (typically called from
  an `ErrorContextCallback`, not inline). Sets context domain to caller's
  TEXTDOMAIN before formatting [from-comment] (`elog.h:206-214`).
- `errposition(int)` — cursor position into the user's query string.
- `errhidestmt(bool)` / `errhidecontext(bool)` — suppress STATEMENT/CONTEXT log.
- `errbacktrace()` — attach a stack backtrace to this report.

## Message style (mandatory)

From the official style guide [from-docs] and reinforced by the wiki [from-wiki]:

- **`errmsg`**: no leading capital (unless the first word is a proper noun or
  SQL keyword), **no trailing period**, no newlines. Single-line phrase.
- **`errdetail` / `errhint` / `errcontext`**: full sentences. Each sentence
  starts with a capital letter, ends with a period.
- Quote user-supplied identifiers with `\"%s\"`.
- Don't include the SQLSTATE in the message text — `errcode()` carries it.
- Don't include "ERROR:" or the severity — the logger prepends it.
- Don't use contractions ("can't" → "cannot") in user-visible messages.
- Avoid assembling sentences from fragments; that breaks translation. Use
  separate `errmsg`/`errdetail` calls.

Canonical example [verified-by-code] (`copyfrom.c:823-827`):

```c
ereport(ERROR,
        (errcode(ERRCODE_WRONG_OBJECT_TYPE),
         errmsg("cannot copy to view \"%s\"",
                RelationGetRelationName(cstate->rel)),
         errhint("To enable copying to a view, provide an INSTEAD OF INSERT trigger.")));
```

Note the outer parens — pre-v12 they were required; now optional but most code
keeps them [from-comment] (`elog.h:114-116`).

## Translation (gettext)

`errmsg`, `errdetail`, `errhint`, `errcontext_msg` route their format string
through `gettext` so it ends up in `postgres.pot` for translators. The
extraction tool finds calls by name. Therefore:

- Format string must be a **string literal**, not a variable, or extraction
  fails [inferred from gettext conventions, common PG review point].
- Build the variable parts as printf args, not by concatenating into the format.
- Use `errmsg_internal` (and friends) to opt out of translation when the message
  is for developers (e.g. `elog(ERROR, "cache lookup failed for relation %u", oid)`).

## SQLSTATE / ERRCODE_*

The `ERRCODE_*` constants are produced from `src/backend/utils/errcodes.txt` at
build time. The macro `MAKE_SQLSTATE('2','2','0','0','3')` packs the 5-char
SQLSTATE into a 30-bit int via `PGSIXBIT` [verified-by-code] (`elog.h:69-74`).
Category-only codes (last three chars `000`) are matched by `ERRCODE_IS_CATEGORY`
[verified-by-code] (`elog.h:77-78`).

Pick the most specific code available. The categories follow the SQL standard
(class 22 = data exception, class 23 = integrity constraint, class 42 = syntax
or access rule, class XX = internal error, etc.).

## ErrorContextCallback — the CONTEXT: line

To attach "while processing function X / line Y" context to whatever error
occurs in a region of code:

```c
ErrorContextCallback cb;
cb.callback = my_cb;
cb.arg      = state;
cb.previous = error_context_stack;
error_context_stack = &cb;
/* ... do work that might ereport(ERROR) ... */
error_context_stack = cb.previous;     /* pop on normal exit */
```

The callback typically calls `errcontext("...")` to append a line.
`error_context_stack` is automatically saved/restored by `PG_TRY` and reset to
its pre-callback value before the catch block runs [verified-by-code]
(`elog.h:311-318`, `388-419`).

## PG_TRY / PG_CATCH / PG_FINALLY

```c
PG_TRY();
{
    /* code that might ereport(ERROR) */
}
PG_CATCH();
{
    /* must either PG_RE_THROW() or roll back a (sub)transaction */
}
PG_END_TRY();
```

Mechanics: `PG_TRY` installs a new `sigjmp_buf` on `PG_exception_stack` and
saves `error_context_stack`. The longjmp triggered by `ereport(ERROR)` lands in
the `CATCH` branch with both stacks restored [verified-by-code]
(`elog.h:388-419`).

Critical rules from the header comment [from-comment] (`elog.h:322-385`):

1. **`PG_CATCH` must either `PG_RE_THROW()` or abort the (sub)transaction.**
   If you swallow the error without abort, the system is left inconsistent.
2. **`PG_FINALLY` always runs and rethrows.** Use it when the cleanup is the
   same for success and error. Cannot be combined with `PG_CATCH` in one block.
3. **`FATAL` is NOT caught.** Control exits straight through `proc_exit()`.
   Use the `PG_ENSURE_ERROR_CLEANUP` macros from `storage/ipc.h` if you need
   to release non-process-local resources on FATAL.
4. **Modified locals must be `volatile`.** Any local variable that is modified
   inside `PG_TRY` and read inside `PG_CATCH` must be declared `volatile`, or
   the compiler may optimize the modification away. `gcc -Wclobbered` is
   unreliable for catching this.
5. **The catch block should be minimal.** Errors inside `PG_CATCH` will
   recurse on the error stack, which has a hard limit (5 frames,
   `ERRORDATA_STACK_SIZE` in `elog.c:154`) before PANIC [verified-by-code].

Most code does **not** use `PG_TRY`. The normal path is: let the ERROR
propagate, and let `AbortTransaction()` (or `AbortSubTransaction()`) do
cleanup via memory contexts and ResourceOwners. `PG_TRY` is for narrow cases:
SPI re-entry, PL/* languages catching backend errors, code that holds a
non-PG resource (e.g. a Python interpreter handle) that can't be cleaned up
by xact abort.

## Soft errors: errsave / ereturn

For input-parsing paths (e.g. type input functions) that want to report a
problem without aborting the transaction. `errsave(context, ...)`:
- If `context` is NULL or not an `ErrorSaveContext`, behaves exactly like
  `ereport(ERROR, ...)`.
- If `context` is a real `ErrorSaveContext`, the info is recorded on the node
  and control returns normally. Caller must check the node and clean up
  [verified-by-code] (`elog.h:246-280`).

`ereturn(context, dummy_value, ...)` = `errsave(...)` plus `return dummy_value`.

## What happens on ERROR — cleanup flow

On `ereport(elevel >= ERROR)` with no `PG_TRY` between here and `PostgresMain`:

1. `errfinish` runs, formats and emits the message.
2. `pg_re_throw()` longjmps to `PG_exception_stack` (PostgresMain's sigjmp).
3. PostgresMain calls `AbortCurrentTransaction()`.
4. Transaction abort: invokes ResourceOwner callbacks (releases buffer pins,
   relation locks, catcache refs, tuple descriptors, etc.), invalidates
   syscaches, deletes per-transaction memory contexts.
5. Backend returns to the ReadyForQuery state and waits for the next command.

You do **not** write per-call cleanup. Allocate via `palloc` in a context that
will be reset on abort, acquire resources via the appropriate `ResourceOwner`
or registration API (relation_open, LockAcquire, BufferAlloc, etc.), and the
abort path will free everything.

## Recursive errors and ErrorContext

`ErrorContext` is a permanent context kept with ≥ 8KB reserved so that "out of
memory" can itself be reported as an ERROR rather than crashing the backend
[from-readme] (`mmgr/README:253-258`). The error stack has 5 frames
(`ERRORDATA_STACK_SIZE`) before infinite recursion triggers PANIC
[verified-by-code] (`elog.c:154-160`, header comment lines 29-43).

## Quick decision tree

- User typed something wrong → `ereport(ERROR, errcode(spec), errmsg(...))`.
- "Should not happen" invariant violated → `elog(ERROR, "cache lookup failed for relation %u", oid)`.
- Want to warn but continue → `ereport(WARNING, ...)`.
- Debug trace gated by `client_min_messages` / `log_min_messages` →
  `elog(DEBUG1, ...)`.
- Need to attach "while processing X" → push an `ErrorContextCallback`.
- Need to clean up a non-PG resource on error → `PG_TRY`/`PG_FINALLY`,
  and consider FATAL via `PG_ENSURE_ERROR_CLEANUP`.
- Input function reporting "bad value" without aborting xact → `errsave`/`ereturn`.



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/error/elog.c`](../files/src/backend/utils/error/elog.c.md) | — | (the engine) |
| [`src/include/utils/elog.h`](../files/src/include/utils/elog.h.md) | — | (the API) |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-error-code`](../scenarios/add-new-error-code.md)
- [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md)
- [`add-new-utility-statement`](../scenarios/add-new-utility-statement.md)

<!-- /scenarios:auto -->

## Open questions / unverified

- Exact gettext extraction script behavior with multi-line literals
  [unverified] — assumed to follow standard xgettext rules.
- Whether `errbacktrace()` is rate-limited per session [unverified].
- Behavior of `errcontext` callbacks when called from inside `PG_CATCH`
  recovery code [unverified] — header warns recovery section should not
  generate new errors.
