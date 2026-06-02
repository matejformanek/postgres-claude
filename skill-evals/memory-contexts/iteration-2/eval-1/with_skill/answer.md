# SRF tuple corruption — what's happening and the right pattern

## Why corruption

Inside an SRF that's evaluated as an expression, `CurrentMemoryContext`
is the executor's **per-tuple ExprContext**. That context is **reset at
the start of each tuple cycle** (not the end) — see SKILL.md "Picking
the right context" lifetime table and `knowledge/idioms/memory-contexts.md`.
So anything you palloc'd in the previous call has been freed by the
time the consumer touches it on the next call. That's your corruption.

Cite: `source/src/backend/executor/execExprInterp.c` and
`source/src/backend/utils/mmgr/README` (lines ~308-368) document the
"reset at start" timing.

## Canonical patterns

Two flavors of SRF, two contexts.

### Value-per-call (ValuePerCall mode)

Use the `funcctx->multi_call_memory_ctx` set up by `SRF_FIRSTCALL_INIT()`.
That context lives across all calls of the SRF for one query.

```c
Datum
my_srf(PG_FUNCTION_ARGS)
{
    FuncCallContext *funcctx;
    MemoryContext    oldcxt;

    if (SRF_IS_FIRSTCALL())
    {
        funcctx = SRF_FIRSTCALL_INIT();
        oldcxt  = MemoryContextSwitchTo(funcctx->multi_call_memory_ctx);
        /* allocate user_fctx, tupdesc, anything that must survive calls */
        funcctx->user_fctx = palloc0(sizeof(MyState));
        MemoryContextSwitchTo(oldcxt);
    }
    funcctx = SRF_PERCALL_SETUP();

    /* per-call result tuple in CurrentMemoryContext (per-tuple) is fine —
       SRF_RETURN_NEXT will datumCopy it across the boundary for us */
    ...
    SRF_RETURN_NEXT(funcctx, result);
}
```

### Materialize mode (tuplestore)

Allocate the tuplestore and tupdesc in
`rsinfo->econtext->ecxt_per_query_memory` so they survive the per-tuple
resets:

```c
ReturnSetInfo *rsinfo = (ReturnSetInfo *) fcinfo->resultinfo;
MemoryContext  per_query_ctx = rsinfo->econtext->ecxt_per_query_memory;
MemoryContext  oldcxt = MemoryContextSwitchTo(per_query_ctx);

tupstore = tuplestore_begin_heap(true, false, work_mem);
rsinfo->returnMode = SFRM_Materialize;
rsinfo->setResult  = tupstore;
rsinfo->setDesc    = tupdesc;
MemoryContextSwitchTo(oldcxt);
```

## Moving pass-by-reference data across the boundary

If you build a `text *` or composite Datum in a short-lived context and
need it to outlive the cycle, **copy it**: `datumCopy()`, `pstrdup()`,
or an explicit memcpy into the target context. (SKILL.md "Common
mistakes" #4.)

## The switch idiom

```c
MemoryContext oldcxt = MemoryContextSwitchTo(target_cxt);
... do work ...
MemoryContextSwitchTo(oldcxt);
```

Cite: SKILL.md "The switch idiom"; precedent in
`source/src/backend/executor/execMain.c` around `es_query_cxt`.
