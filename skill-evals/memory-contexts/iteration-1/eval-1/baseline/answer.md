# SRF tuple corruption between calls

The problem is that inside an expression context, CurrentMemoryContext is
a short-lived per-tuple context that gets reset between rows. Your tuple
pointer is dangling.

For an SRF you want to use the SRF helper macros. On first call, use
`SRF_FIRSTCALL_INIT()` to get a `FuncCallContext`, and switch into
`funcctx->multi_call_memory_ctx` before doing any allocations that need
to persist across calls (state, tupledesc, etc). On each subsequent
call use `SRF_PERCALL_SETUP()`. The multi-call memory context lives for
the duration of the SRF, not just one tuple cycle.

For Materialize-mode SRFs that build a tuplestore, allocate the
tuplestore in the per-query memory context, available as
`rsinfo->econtext->ecxt_per_query_memory`. That way it survives across
all calls in the statement.

If you absolutely need to return pass-by-reference data, either copy it
into the caller's context with datumCopy or allocate it there directly
with a MemoryContextSwitchTo.

The general rule: per-tuple ExprContext is for transient scratch, not
for things the caller will hold onto.
