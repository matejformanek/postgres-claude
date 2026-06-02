# Eval 2 — with_skill (iter-2)

libxml2 parser context cleanup.

## Use `PG_FINALLY`, not `PG_CATCH`

The skill is explicit: "**Prefer `PG_FINALLY` over `PG_CATCH`** whenever the
cleanup is the same on success and error (the common case). `PG_FINALLY`
auto-rethrows; you can't accidentally swallow the original error."

This is exactly that case — we need to free the parser context on both
success and ERROR. So:

```c
xmlParserCtxtPtr volatile ctxt = NULL;

ctxt = xmlNewParserCtxt();
if (ctxt == NULL)
    ereport(ERROR, (errcode(ERRCODE_OUT_OF_MEMORY),
                    errmsg("could not allocate parser context")));

PG_TRY();
{
    /* parse work that may ereport(ERROR) */
}
PG_FINALLY();
{
    xmlFreeParserCtxt(ctxt);
}
PG_END_TRY();
```

## `volatile` placement

`xmlParserCtxtPtr volatile ctxt` — the pointer itself is the local modified
in TRY (assigned the result of `xmlNewParserCtxt()`) and read in FINALLY.
The skill rule: "Locals modified in TRY and read in CATCH must be `volatile`"
applies equally to FINALLY. The qualifier goes on the pointer, not the
pointee — we don't care if libxml2 mutates what `ctxt` points to, we care
that the compiler doesn't cache `ctxt` itself across the setjmp.

## Auto-rethrow

`PG_FINALLY` automatically re-raises the original error after the cleanup
block runs. You do **not** write `PG_RE_THROW()` inside `PG_FINALLY` —
that's a `PG_CATCH`-only thing.

## FATAL

`FATAL` is **not caught by PG_TRY / PG_CATCH / PG_FINALLY**. The skill says
so explicitly. On FATAL the backend process terminates.

For libxml2's parser context specifically, this is mostly moot: the parser
context is process-local heap memory, and the OS reclaims the entire process
address space when the backend exits. There's nothing to "leak" across
process boundaries. You'd only need FATAL-safe cleanup if the resource were
external to the process (a shared-memory segment, a file on disk that needs
unlinking, a child process to reap, etc.).

If you did need FATAL-safe cleanup, the mechanism is `PG_ENSURE_ERROR_CLEANUP`
declared in `src/include/storage/ipc.h`, which registers a `before_shmem_exit`
callback that runs on FATAL too.

## Recursion limit caveat

If your `PG_FINALLY` block itself raises ERROR, you're now recursing on the
error stack. The stack has a hard limit of 5 frames (`ERRORDATA_STACK_SIZE`
in `src/backend/utils/error/elog.c:154`) before it PANICs the cluster.
Keep FINALLY tiny — just the `xmlFreeParserCtxt(ctxt)` call.
