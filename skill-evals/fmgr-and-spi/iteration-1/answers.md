# Iteration 1 — Answers (twice each: baseline then with-skill)

## Eval 1 — Materialize SRF: where state must live

### Answer 1A (baseline, no skill)

For Materialize-mode SRFs you need to put the tuplestore in a memory context
that outlives your function — the executor reads from it after you return.
`CurrentMemoryContext` at function entry is typically a short-lived per-tuple
context, so the tuplestore gets freed before the executor can scan it.

Use the ReturnSetInfo plumbing: cast `fcinfo->resultinfo` to `ReturnSetInfo *`,
check `IsA(rsinfo, ReturnSetInfo)` and that `rsinfo->allowedModes &
SFRM_Materialize` is set. The per-query context lives on
`rsinfo->econtext->ecxt_per_query_memory`. Switch to it, create the
tuplestore and tupdesc there, then put them on `rsinfo->setResult` and
`rsinfo->setDesc`, set `rsinfo->returnMode = SFRM_Materialize`, and return
PG_RETURN_NULL (the Datum return value is ignored).

Modern code uses the helper `InitMaterializedSRF(fcinfo, 0)`, which does the
checks and allocates the tuplestore in the right context for you. After that
you just call tuplestore_putvalues on rsinfo->setResult/setDesc.

### Answer 1B (with skill)

The rule from SKILL.md §1.10 and knowledge/idioms/fmgr.md §8: the tuplestore
and TupleDesc for a Materialize SRF MUST live in
`rsinfo->econtext->ecxt_per_query_memory`, NOT in `CurrentMemoryContext`.
`CurrentMemoryContext` at fmgr entry is usually a per-tuple ExprContext that
the executor resets between tuple cycles, so anything you palloc'd there
vanishes before the caller scans the tuplestore. This is called out in the
skill as "the single most common SRF pitfall"
([verified-by-code] src/backend/utils/fmgr/funcapi.c:100-122).

Use the helper — it handles the context dance:

```c
PG_FUNCTION_INFO_V1(my_mat_srf);
Datum
my_mat_srf(PG_FUNCTION_ARGS)
{
    ReturnSetInfo *rsinfo = (ReturnSetInfo *) fcinfo->resultinfo;
    Datum    values[NCOLS];
    bool     nulls[NCOLS];

    InitMaterializedSRF(fcinfo, 0);   /* allocates tuplestore + tupdesc in
                                         ecxt_per_query_memory and fills
                                         rsinfo->setResult / setDesc */

    /* per row */
    tuplestore_putvalues(rsinfo->setResult, rsinfo->setDesc, values, nulls);

    PG_RETURN_NULL();   /* Materialize ignores the Datum return value */
}
```

Flags: `MAT_SRF_USE_EXPECTED_DESC` to reuse the caller's expectedDesc,
`MAT_SRF_BLESS` to BlessTupleDesc (needed for RECORD)
([verified-by-code] src/include/funcapi.h:296-298).

If you must hand-roll: save oldcxt, switch to
`rsinfo->econtext->ecxt_per_query_memory`, create the tuplestore there
(`tuplestore_begin_heap(true, false, work_mem)`), build the TupleDesc there,
switch back, then `rsinfo->setResult = ts; rsinfo->setDesc = tupdesc;
rsinfo->returnMode = SFRM_Materialize;`. But the helper makes this a one-liner.

---

## Eval 2 — SPI_prepare cached on fn_extra crashes on second call

### Answer 2A (baseline)

Most likely you're storing the SPIPlanPtr without telling SPI to keep it past
SPI_finish. By default a plan from SPI_prepare lives in memory contexts owned
by the current SPI session and gets freed when you call SPI_finish. So on the
next invocation, fn_extra still points at the old plan but the memory is
gone — boom, crash.

Fix: call `SPI_keepplan(plan)` before SPI_finish. That reparents the plan
under a long-lived context (CacheMemoryContext) so it survives. Also make
sure the cache struct you hang off fn_extra is allocated in
`flinfo->fn_mcxt`, not CurrentMemoryContext, because the latter may be a
per-tuple context.

```c
if (fcinfo->flinfo->fn_extra == NULL)
{
    MemoryContext old = MemoryContextSwitchTo(fcinfo->flinfo->fn_mcxt);
    MyCache *c = palloc0(sizeof(*c));
    SPI_connect();
    c->plan = SPI_prepare(sql, nargs, argtypes);
    if (c->plan == NULL) elog(ERROR, "SPI_prepare: %s",
                              SPI_result_code_string(SPI_result));
    SPI_keepplan(c->plan);
    SPI_finish();
    fcinfo->flinfo->fn_extra = c;
    MemoryContextSwitchTo(old);
}
```

On subsequent calls, just SPI_connect, SPI_execute_plan with the cached plan,
consume results (copying anything out via SPI_palloc / SPI_copytuple if
you'll use it past SPI_finish), SPI_finish.

### Answer 2B (with skill)

Classic bug #2 from SKILL.md §2.8 and knowledge/idioms/spi.md §12: a bare
`SPI_prepare` puts the plan in the "SPI Proc" memory context, which
`SPI_finish` deletes. So on the second call, your `fn_extra` cache holds a
dangling pointer to freed memory.

The fix is `SPI_keepplan(plan)` *before* SPI_finish — it reparents the
plan's plancxt under `CacheMemoryContext` and pins the underlying
CachedPlanSources via SaveCachedPlan ([verified-by-code]
src/backend/executor/spi.c:977-1001). It's one-way (saved=true) and
permanent for the plan's lifetime.

Two other related rules from the skill that you should also get right:

1. The cache struct that holds the plan pointer must itself be allocated in
   `fcinfo->flinfo->fn_mcxt`, not `CurrentMemoryContext` — the current
   context at fmgr entry is often a per-tuple ExprContext (SKILL §1.12).
2. fn_extra is "callee-private". Note that `SRF_IS_FIRSTCALL()` literally
   tests fn_extra == NULL, so you cannot share fn_extra between an SRF and a
   plan cache (SKILL §1.9).

Canonical pattern:

```c
typedef struct { SPIPlanPtr plan; } MyCache;

Datum my_func(PG_FUNCTION_ARGS)
{
    MyCache *c = fcinfo->flinfo->fn_extra;

    if (c == NULL)
    {
        MemoryContext old = MemoryContextSwitchTo(fcinfo->flinfo->fn_mcxt);
        c = palloc0(sizeof(*c));
        fcinfo->flinfo->fn_extra = c;
        MemoryContextSwitchTo(old);

        SPI_connect();
        c->plan = SPI_prepare("SELECT ... WHERE id = $1", 1,
                              (Oid[]){ INT4OID });
        if (c->plan == NULL)
            elog(ERROR, "SPI_prepare: %s",
                 SPI_result_code_string(SPI_result));
        SPI_keepplan(c->plan);
        SPI_finish();
    }

    SPI_connect();
    SPI_execute_plan(c->plan, vals, nulls, true /*read_only*/, 0);
    /* read SPI_tuptable; copy any datum you'll return via SPI_palloc /
       SPI_copytuple / SPI_returntuple into the caller's context */
    SPI_finish();

    PG_RETURN_...;
}
```

To free a kept plan later: `SPI_freeplan(plan)` (rare — usually you let it
live as long as the FmgrInfo).

---

## Eval 3 — Looking at SPI_tuptable after a subxact rollback

### Answer 3A (baseline)

You can't. When the subtransaction rolls back, the SPI/executor state and
any tuptables created inside it get cleaned up — there's an AtEOSubXact_SPI
hook that runs on subxact end. So by the time you're in the PG_CATCH block
after RollbackAndReleaseCurrentSubTransaction, SPI_tuptable's contents (or
the tuptable itself) have been freed. Touching it crashes.

The right pattern is to capture the diagnostic data while still inside the
subxact — i.e. inside the PG_CATCH but BEFORE the
RollbackAndReleaseCurrentSubTransaction, except that on a failure your code
never reached the place where you'd read the tuptable. So really the data
you want is in the ErrorData itself: do CopyErrorData() before
FlushErrorState(). The ErrorData has sqlstate, message, detail, context, etc.

```c
PG_CATCH();
{
    MemoryContextSwitchTo(oldctx);
    ErrorData *edata = CopyErrorData();   /* allocate in oldctx */
    FlushErrorState();
    RollbackAndReleaseCurrentSubTransaction();
    /* now safe to look at edata->message, edata->sqlstate, ... */
    ereport(WARNING, (errmsg("user query failed: %s", edata->message)));
    FreeErrorData(edata);
}
PG_END_TRY();
CurrentResourceOwner = oldowner;
```

If you also want partial result rows from before the failure — you can't
really get them. SPI doesn't expose streaming results from a partially
executed query; the tuptable is built at the end. For diagnostics you're
limited to the ErrorData.

### Answer 3B (with skill)

This is the "aborted-subxact rule" from SKILL §2.7 and
knowledge/idioms/spi.md §9. `AtEOSubXact_SPI` (false, mySubid) runs on
subxact rollback ([verified-by-code] src/backend/executor/spi.c:482-572) and
does two things:

- Pops every SPI stack entry whose `connectSubid` matches the dying subxact
  and deletes their memory contexts.
- For surviving SPI frames (one level out), if the in-flight executor call
  started inside the dying subxact (`execSubid >= mySubid`), resets the SPI
  Exec context and frees every tuptable created in this subxact.

So `SPI_tuptable` from the SPI_execute that failed has been freed under you.
Touching it after RollbackAndReleaseCurrentSubTransaction is use-after-free.
SKILL.md §2.8 calls this out explicitly as bug #3.

The diagnostic info you actually have access to is the ErrorData, captured
with CopyErrorData BEFORE FlushErrorState:

```c
MemoryContext oldctx = CurrentMemoryContext;
ResourceOwner oldowner = CurrentResourceOwner;

BeginInternalSubTransaction(NULL);
PG_TRY();
{
    SPI_execute("...user sql...", false, 0);
    /* if we got here, copy any tuptable data into oldctx via SPI_palloc
       BEFORE ReleaseCurrentSubTransaction */
    ReleaseCurrentSubTransaction();
}
PG_CATCH();
{
    MemoryContextSwitchTo(oldctx);
    ErrorData *edata = CopyErrorData();   /* now lives in oldctx */
    FlushErrorState();
    RollbackAndReleaseCurrentSubTransaction();
    /* SPI tuptables from inside the subxact are GONE — do not touch
       SPI_tuptable here. AtEOSubXact_SPI cleaned it. */
    ereport(WARNING,
            (errcode(edata->sqlerrcode),
             errmsg("user query failed: %s", edata->message)));
    FreeErrorData(edata);
}
PG_END_TRY();
CurrentResourceOwner = oldowner;
```

Two corollaries the skill warns about:

- The aborted-subxact rule also forbids continuing SPI work in any SPI
  stack frame opened *inside* the failed subxact — those frames have been
  popped. Only an SPI frame that pre-existed the BeginInternalSubTransaction
  survives.
- This is also why you cannot SPI_commit / SPI_rollback inside a PL
  exception block — see SKILL §2.6 and spi.md §8.

If you genuinely need partial rows, restructure: run the query as a cursor
(SPI_cursor_open) outside the subxact and read it in batches, putting only
the *processing* of each batch (not the fetch) inside a fresh subxact.
