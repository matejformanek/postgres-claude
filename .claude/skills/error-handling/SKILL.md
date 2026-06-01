---
name: error-handling
description: PostgreSQL error reporting idioms — ereport vs elog, SQLSTATE, message style, PG_TRY/CATCH. Use whenever writing or editing C code in source/src/backend/ that reports errors, logs messages, or needs longjmp-safe cleanup.
---

# Error handling — actionable rules

Reference doc: `knowledge/idioms/error-handling.md` (read it for the *why*).

## When you write a new error report

1. **Pick `ereport` for user-visible errors, `elog` for "should never happen".**
   `elog(ERROR, "cache lookup failed for relation %u", oid)` is the canonical
   internal-error idiom. `ereport(ERROR, errcode(...), errmsg(...))` is for
   anything the user can trigger.
2. **Always pass an `errcode()`** in `ereport`. Default is `ERRCODE_INTERNAL_ERROR`,
   which is rarely what you want. Pick the most specific SQLSTATE from
   `src/backend/utils/errcodes.txt`. For file/socket errors use
   `errcode_for_file_access()` / `errcode_for_socket_access()` right after the
   syscall (they consume `errno`).
3. **`errmsg` style — no leading capital, no trailing period, no newline,
   one phrase.** Example: `errmsg("relation \"%s\" does not exist", name)`.
4. **`errdetail` / `errhint` / `errcontext` are full sentences** — capital,
   period, may be multi-sentence. `errhint` should be actionable.
5. **Quote identifiers as `\"%s\"`.** Don't quote SQL keywords or numbers.
6. **Don't put SQLSTATE or severity in the message text** — `errcode()` and
   the logger handle them.
7. **Don't concatenate fragments into the format string** — breaks gettext.
   Build via printf args.
8. **Use `errmsg_internal` for messages that should not be translated**
   (developer-only "can't happen" cases). `elog` already does this.

## Picking elevel

- `DEBUG1..DEBUG5` — verbose tracing, gated by `log_min_messages`.
- `LOG` — operational events. Goes to server log, not to client by default.
- `INFO` — explicit user-requested output (e.g. VACUUM VERBOSE).
- `NOTICE` — expected events the user should know about.
- `WARNING` — unexpected non-fatal. Distinct from NOTICE.
- `ERROR` — abort current transaction, longjmp out. Most common choice.
- `FATAL` — terminate this backend process. Used for auth failure, fatal
  startup errors.
- `PANIC` — only if continuing would corrupt shared state (xlog write failure,
  shared memory invariant broken). Postmaster restarts the cluster.

Default to `ERROR`. Use `FATAL`/`PANIC` only with strong justification.

## Critical: `ereport(ERROR)` does not return

It longjmps to the nearest `PG_TRY` or to PostgresMain. **You do not write
cleanup code after it.** Anything reached "after" an ERROR in the source is
dead code from a runtime perspective. Don't `goto cleanup`; let transaction
abort handle memory contexts, locks, buffer pins, etc.

## PG_TRY / PG_CATCH — when to use

Default answer: **don't**. Almost all backend code lets ERROR propagate.

Use `PG_TRY` only when:
- You hold a resource that won't be released by transaction abort (e.g. a
  Python interpreter handle in PL/Python, a libxml2 parser).
- You implement a language that must convert backend ERROR into a host
  exception (PL/pgSQL, SPI re-entry).
- You're at a top-level loop (PostgresMain, bgworker main) and need to
  resume after error.

When you do use it:
- `PG_CATCH` must `PG_RE_THROW()` or call `AbortCurrentTransaction()` /
  `RollbackAndReleaseCurrentSubTransaction()`. Never swallow silently.
- Locals modified in TRY and read in CATCH must be `volatile`.
- Keep CATCH minimal — errors inside CATCH recurse on a 5-frame stack
  before PANIC.
- For symmetric cleanup, prefer `PG_FINALLY` over `PG_CATCH`.
- `FATAL` is not caught by PG_TRY. Use `PG_ENSURE_ERROR_CLEANUP`
  (`storage/ipc.h`) for FATAL-safe cleanup of process-external resources.

## Adding "while doing X" context

Push an `ErrorContextCallback` rather than concatenating the context into the
message. Pop it on normal exit; PG_TRY auto-restores it on error.

```c
ErrorContextCallback cb = { .callback = my_cb, .arg = state,
                            .previous = error_context_stack };
error_context_stack = &cb;
/* work */
error_context_stack = cb.previous;
```

The callback calls `errcontext("processing row %d of \"%s\"", ...)`.

## Soft errors

For input-parsing functions that accept an `ErrorSaveContext *escontext`:
use `errsave(escontext, errcode(...), errmsg(...))` and check the node
afterwards. If `escontext` is NULL, behaves identically to `ereport(ERROR, ...)`.
`ereturn(escontext, dummy_value, ...)` is the shorter form when you have no
post-report cleanup.

## Checklist before committing

- [ ] `errcode()` set explicitly, not relying on default INTERNAL_ERROR.
- [ ] `errmsg` is a string literal (for gettext extraction), lowercase start,
      no period.
- [ ] `errdetail` / `errhint` are complete sentences.
- [ ] Identifiers quoted as `\"%s\"`.
- [ ] No `goto cleanup` after `ereport(ERROR, ...)`.
- [ ] If using `PG_TRY`: catch block rethrows or aborts; modified locals are
      `volatile`.
- [ ] For "should never happen" use `elog`, not `ereport` with hand-written
      `errmsg_internal`.
- [ ] No newlines in `errmsg`.
- [ ] No fragment concatenation.

## When in doubt, cite

Reference live examples by grepping similar paths:
- `src/backend/commands/*.c` for user-facing DDL errors.
- `src/backend/access/heap/heapam.c` for access-method internal errors.
- `src/backend/utils/cache/lsyscache.c` for `elog(ERROR, "cache lookup failed ...")`.
- `src/pl/plpgsql/src/pl_exec.c` for non-trivial `PG_TRY`/`PG_CATCH`.
