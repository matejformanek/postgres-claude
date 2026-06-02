# Eval 2 — libxml2 parser context cleanup (with_skill)

The parser context is a non-PG resource (no ResourceOwner, no MemoryContext
hooks), so per SKILL.md "PG_TRY / PG_CATCH — when to use", this is exactly
the case PG_TRY exists for:

> Use `PG_TRY` only when:
> - You hold a resource that won't be released by transaction abort (e.g. a
>   Python interpreter handle in PL/Python, a libxml2 parser).

Use `PG_FINALLY`, not `PG_CATCH`, because cleanup is symmetric (free on both
success and error) — per SKILL.md "For symmetric cleanup, prefer `PG_FINALLY`
over `PG_CATCH`."

## The pattern

```c
xmlParserCtxtPtr volatile ctxt = NULL;

PG_TRY();
{
    ctxt = xmlNewParserCtxt();
    if (ctxt == NULL)
        ereport(ERROR,
                (errcode(ERRCODE_OUT_OF_MEMORY),
                 errmsg("could not allocate xml parser context")));

    /* parsing work that may call back into PG code and ereport(ERROR) */
    do_parse(ctxt);
}
PG_FINALLY();
{
    if (ctxt != NULL)
        xmlFreeParserCtxt(ctxt);
}
PG_END_TRY();
```

## Why `volatile`

SKILL.md rule under "PG_TRY ... When you do use it":

> Locals modified in TRY and read in CATCH must be `volatile`.

`ctxt` is assigned inside TRY and read inside FINALLY (which runs on the
error path via longjmp), so the compiler may otherwise optimize the
assignment away across the sigsetjmp boundary. `gcc -Wclobbered` is
unreliable here (per `knowledge/idioms/error-handling.md` rule 4).

The `volatile` goes on the pointer itself: `xmlParserCtxtPtr volatile ctxt`.

## Why PG_FINALLY beats PG_CATCH here

- FINALLY always runs and auto-rethrows the original error
  (`knowledge/idioms/error-handling.md` rule 2: "`PG_FINALLY` always runs
  and rethrows"). You don't have to write `PG_RE_THROW()` yourself, and
  you can't accidentally swallow the error.
- CATCH would require you to call `PG_RE_THROW()` explicitly, and SKILL.md
  warns: "PG_CATCH must `PG_RE_THROW()` or call `AbortCurrentTransaction()`
  ... Never swallow silently."
- FINALLY also covers the success path with the same cleanup code — no
  duplication.

## What about FATAL?

**`PG_TRY` / `PG_FINALLY` do NOT catch FATAL.** From SKILL.md:

> `FATAL` is not caught by PG_TRY. Use `PG_ENSURE_ERROR_CLEANUP`
> (`storage/ipc.h`) for FATAL-safe cleanup of process-external resources.

And from `knowledge/idioms/error-handling.md` rule 3:

> `FATAL` is NOT caught. Control exits straight through `proc_exit()`.

For a libxml2 parser context that lives only inside this function call,
this usually doesn't matter — FATAL terminates the backend process, and
the OS reclaims the heap. The libxml2 ctxt is process-local memory; it
disappears with the process.

If you needed to do something like flushing a file or releasing a
cross-process resource (shared memory slot, semaphore), you would wrap
with `PG_ENSURE_ERROR_CLEANUP(cleanup_fn, arg)` from `storage/ipc.h` in
addition to the PG_FINALLY.

## Catch-block discipline (in case you do use PG_CATCH)

SKILL.md: "Keep CATCH minimal — errors inside CATCH recurse on a 5-frame
stack before PANIC." Don't allocate, don't take locks, don't call anything
that can ereport. Just free the resource and rethrow.

`knowledge/idioms/error-handling.md` cites `ERRORDATA_STACK_SIZE = 5` in
`elog.c:154`.
