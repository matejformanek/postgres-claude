# Eval 2 — baseline (iter-2, no skill)

## PG_TRY / PG_CATCH for libxml2

```c
xmlParserCtxtPtr volatile ctxt = NULL;

ctxt = xmlNewParserCtxt();
if (!ctxt)
    elog(ERROR, "out of memory");

PG_TRY();
{
    /* parsing work */
}
PG_CATCH();
{
    xmlFreeParserCtxt(ctxt);
    PG_RE_THROW();
}
PG_END_TRY();
xmlFreeParserCtxt(ctxt);
```

The `PG_CATCH` block frees the context then re-throws so the error keeps
propagating. The success path also frees it after `PG_END_TRY`.

## volatile

The `ctxt` pointer is modified inside TRY and read inside CATCH, so it must
be `volatile`-qualified. Write as `xmlParserCtxtPtr volatile ctxt` — applies
to the pointer variable itself, not what it points to.

## FATAL

FATAL terminates the backend. PG_TRY / PG_CATCH won't catch it — the longjmp
target is different and the process exits. For libxml2's parser context this
is fine in practice: it's process-local memory and the OS reclaims it when
the backend exits. So no special handling needed for FATAL here.

(If you really needed FATAL-time cleanup of an external resource — shared
memory, on-disk file, child process — you'd register a `before_shmem_exit`
or `on_proc_exit` callback. I don't remember if there's a dedicated macro
for the TRY-style pattern.)
