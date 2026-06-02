# SRF tuple corruption between calls

## Diagnosis
When an SRF is called inside expression evaluation, `CurrentMemoryContext` is the
executor's **per-tuple ExprContext**. That context is reset at the **start** of
each tuple cycle (not the end), so anything you palloc into it gets stomped on
the next call into the node. This matches "Common mistake #4" in SKILL.md:
"Returning per-tuple-context memory across the boundary. The next tuple cycle
resets that context."

## Fix — value-per-call SRFs
Switch into a longer-lived context before building the row. The canonical
pattern uses `multi_call_memory_ctx` from `init_MultiFuncCall`:

```c
FuncCallContext *funcctx;
MemoryContext    oldcxt;

if (SRF_IS_FIRSTCALL())
{
    funcctx = SRF_FIRSTCALL_INIT();
    oldcxt = MemoryContextSwitchTo(funcctx->multi_call_memory_ctx);
    /* allocate per-SRF state here (tupledesc, arrays, etc.) */
    MemoryContextSwitchTo(oldcxt);
}
funcctx = SRF_PERCALL_SETUP();
/* per-row work: short-lived allocs OK in CurrentMemoryContext */
```

For the **returned datum**, if it's a pass-by-reference type and must outlive
the per-tuple context, allocate it in the caller's context (the per-query
context, `econtext->ecxt_per_query_memory`) or copy with `datumCopy` /
`pstrdup`. SKILL.md spells this out: "Either palloc into the caller's context
or `datumCopy` / `pstrdup` / explicit copy."

## Fix — Materialize-mode SRFs (tuplestore)
If you're using `SFRM_Materialize`, build the tuplestore in
`rsinfo->econtext->ecxt_per_query_memory`:

```c
oldcxt = MemoryContextSwitchTo(rsinfo->econtext->ecxt_per_query_memory);
tupstore = tuplestore_begin_heap(true, false, work_mem);
MemoryContextSwitchTo(oldcxt);
```

The tuplestore then survives until end of statement, which is what the
caller expects.

## Why your symptom appears
`CurrentMemoryContext` inside expression eval is the per-tuple context.
The skill's lifetime table (SKILL.md, "Picking the right context") makes
this explicit: "End of one tuple cycle → the executor's per-tuple
ExprContext (usually already CurrentMemoryContext in expression eval)."
You wanted statement lifetime, not tuple lifetime.

## Cites
- SKILL.md "Picking the right context" + Common mistakes #4.
- `knowledge/idioms/memory-contexts.md` "Per-tuple contexts in the executor"
  (resets at the start of each cycle; cites `source/src/backend/utils/mmgr/README:308-368`).
- Canonical switch idiom: `source/src/backend/executor/execMain.c` around
  the `es_query_cxt` switch (referenced from SKILL.md "When in doubt, cite").
