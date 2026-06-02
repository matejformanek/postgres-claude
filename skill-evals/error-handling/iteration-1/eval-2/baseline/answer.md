# Eval 2 — libxml2 parser context cleanup (baseline)

Use PG_TRY / PG_CATCH around the parsing work, and free the context in the
catch block. Something like:

```c
xmlParserCtxtPtr ctxt = xmlNewParserCtxt();
PG_TRY();
{
    do_parse(ctxt);
}
PG_CATCH();
{
    xmlFreeParserCtxt(ctxt);
    PG_RE_THROW();
}
PG_END_TRY();
xmlFreeParserCtxt(ctxt);  /* success path */
```

You need `PG_RE_THROW()` so the original error keeps propagating. I think
there's also `PG_FINALLY` which would consolidate the two free calls but
I don't remember if it works in combination with PG_CATCH or instead of it.

## volatile

I vaguely recall that variables modified in PG_TRY and read in PG_CATCH
need `volatile` because longjmp can clobber non-volatile locals. So
probably `volatile xmlParserCtxtPtr ctxt`. Not 100% sure where the
volatile goes syntactically.

## FATAL

I think FATAL is different from ERROR — it terminates the backend so the
PG_CATCH might not run? I'd have to check. There's probably a separate
mechanism for FATAL-safe cleanup but I don't remember the name. Possibly
on_proc_exit callbacks or some PG_ENSURE_* macro.

Honestly for libxml2 specifically, if FATAL fires and the process dies,
the OS frees the heap so the libxml2 ctxt is gone anyway — process-local
memory. So it probably doesn't matter for this case.
