# SRF tuple corruption

The problem: when an SRF is called as an expression, `CurrentMemoryContext`
points at the executor's per-tuple ExprContext. That context is short-lived
and gets reset between tuple cycles, so anything you palloc'd in the previous
call has been freed by the time the next call runs.

## Fix — pick the right context for your SRF style

### Value-per-call

Use `SRF_FIRSTCALL_INIT()` / `SRF_PERCALL_SETUP()`. State that must
survive across calls (your `user_fctx`, tupdesc, accumulator buffers)
goes into `funcctx->multi_call_memory_ctx`, which lives for the query.

```c
if (SRF_IS_FIRSTCALL())
{
    FuncCallContext *funcctx = SRF_FIRSTCALL_INIT();
    MemoryContext    oldcxt  = MemoryContextSwitchTo(funcctx->multi_call_memory_ctx);
    funcctx->user_fctx = palloc0(sizeof(MyState));
    MemoryContextSwitchTo(oldcxt);
}
```

The per-call result Datum itself can be built in CurrentMemoryContext;
`SRF_RETURN_NEXT` handles the copy.

### Materialize mode

Allocate the tuplestore in `rsinfo->econtext->ecxt_per_query_memory`:

```c
ReturnSetInfo *rsinfo = (ReturnSetInfo *) fcinfo->resultinfo;
MemoryContext  oldcxt = MemoryContextSwitchTo(rsinfo->econtext->ecxt_per_query_memory);
tupstore = tuplestore_begin_heap(true, false, work_mem);
MemoryContextSwitchTo(oldcxt);
```

## Crossing the boundary

If you have pass-by-reference data (text, arrays, composites) built in
the short-lived context, copy it before returning: `datumCopy`,
`pstrdup`, or explicit copy into the destination context.
