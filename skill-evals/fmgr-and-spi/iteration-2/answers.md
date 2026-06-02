# Iteration 2 — Answers (baseline + with-skill, post-edits)

The skill text used here is the post-edit version with the five iter-1
refinements applied. Baseline answers are written first, without
consulting SKILL.md.

## Eval 1 — Materialize SRF: where state must live

### Answer 1A (baseline, no skill)

The tuplestore and TupleDesc for a Materialize-mode SRF have to live in
a memory context that survives across executor cycles, because the
executor reads from the tuplestore after your function has returned.
`CurrentMemoryContext` at fmgr entry for an expression call is usually
a per-tuple ExprContext that the executor resets row-by-row, so
allocating there causes a use-after-free or garbage.

The correct context is `rsinfo->econtext->ecxt_per_query_memory`. Cast
`fcinfo->resultinfo` to `ReturnSetInfo *`, switch to that context, build
the tuplestore and TupleDesc there, then set `rsinfo->setResult`,
`rsinfo->setDesc`, and `rsinfo->returnMode = SFRM_Materialize`.

The shorter modern form is to call the helper
`InitMaterializedSRF(fcinfo, 0)` which does the context switch and the
allocation for you. After that you just `tuplestore_putvalues` rows and
`PG_RETURN_NULL()` (Materialize ignores the Datum return value).

### Answer 1B (with skill)

Per SKILL.md §1.10, the tuplestore + TupleDesc for a Materialize-mode
SRF MUST live in `rsinfo->econtext->ecxt_per_query_memory`, NOT
`CurrentMemoryContext` — at fmgr entry the latter is typically a
per-tuple ExprContext that the executor resets between rows, so
anything you palloc'd there vanishes before the caller scans the
tuplestore. The skill flags this as "the single most common SRF
pitfall" ([verified-by-code] `src/backend/utils/fmgr/funcapi.c:100-122`).

Canonical minimal pattern:

```c
PG_FUNCTION_INFO_V1(my_mat_srf);
Datum
my_mat_srf(PG_FUNCTION_ARGS)
{
    ReturnSetInfo *rsinfo = (ReturnSetInfo *) fcinfo->resultinfo;
    Datum    values[NCOLS];
    bool     nulls[NCOLS];

    InitMaterializedSRF(fcinfo, 0);   /* fills rsinfo->setResult & setDesc
                                         in ecxt_per_query_memory */

    /* per row */
    tuplestore_putvalues(rsinfo->setResult, rsinfo->setDesc, values, nulls);

    PG_RETURN_NULL();   /* Materialize ignores the Datum return value */
}
```

Flags ([verified-by-code] `src/include/funcapi.h:296-298`):

| Flag | When to set |
|---|---|
| `MAT_SRF_USE_EXPECTED_DESC` | Use the tupdesc the caller already expects (e.g. `SELECT * FROM srf() AS (...)`). |
| `MAT_SRF_BLESS` | Return type is RECORD and needs a typmod assigned. |

If you hand-roll: save oldcxt, switch to
`rsinfo->econtext->ecxt_per_query_memory`, create the tuplestore there
(`tuplestore_begin_heap(true, false, work_mem)`) and build the
TupleDesc there, switch back, then assign `rsinfo->setResult`,
`rsinfo->setDesc`, `rsinfo->returnMode = SFRM_Materialize`. The helper
turns this into a one-liner.

---

## Eval 2 — SPI_prepare cached on fn_extra segfaults on second call

### Answer 2A (baseline, no skill)

The plan returned by `SPI_prepare` is allocated inside SPI's
session-scoped memory contexts. `SPI_finish` deletes those contexts,
which frees the plan. So on the second call your `fn_extra` is a
dangling pointer.

Fix: call `SPI_keepplan(plan)` BEFORE `SPI_finish`. That reparents the
plan under a long-lived context (CacheMemoryContext) so it survives.
And the cache struct you hang on `fn_extra` must itself be allocated in
`fcinfo->flinfo->fn_mcxt`, not `CurrentMemoryContext`, because the
latter at fmgr entry is often a per-tuple ExprContext that gets reset
between rows.

```c
if (fcinfo->flinfo->fn_extra == NULL)
{
    MemoryContext old = MemoryContextSwitchTo(fcinfo->flinfo->fn_mcxt);
    MyCache *c = palloc0(sizeof(*c));
    fcinfo->flinfo->fn_extra = c;
    MemoryContextSwitchTo(old);

    SPI_connect();
    c->plan = SPI_prepare(sql, nargs, argtypes);
    if (c->plan == NULL)
        elog(ERROR, "SPI_prepare: %s",
             SPI_result_code_string(SPI_result));
    SPI_keepplan(c->plan);
    SPI_finish();
}
```

`SPI_prepare` returns NULL on failure; the actual code is in the global
`SPI_result` because the function returns a pointer.

### Answer 2B (with skill)

Classic bug #2 from SKILL.md §2.8: a bare `SPI_prepare` puts the plan
in the SPI Proc context, which `SPI_finish` deletes. On the second
call `fn_extra` is a dangling pointer — crash.

Fix is `SPI_keepplan(plan)` BEFORE `SPI_finish`. It is one-way
(`saved=true`), reparents the plan's memory context under
`CacheMemoryContext`, and pins the underlying `CachedPlanSource`s via
`SaveCachedPlan` ([verified-by-code]
`src/backend/executor/spi.c:977-1001`).

Two complementary rules from the skill that must be obeyed together,
or you have the same use-after-free with a different shape:

1. The cache struct that holds the plan pointer must be allocated in
   `fcinfo->flinfo->fn_mcxt`, not `CurrentMemoryContext` — the
   current context at fmgr entry is often a per-tuple ExprContext
   (SKILL §1.12).
2. `fn_extra` is callee-private but also reserved by the SRF
   machinery — `SRF_IS_FIRSTCALL()` literally tests
   `fn_extra == NULL`. You cannot share `fn_extra` between an SRF and
   a plan cache (SKILL §1.12 backlink to §1.9).

The full canonical pattern (also in SKILL §2.3 "Cached on `fn_extra`"):

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
    /* read SPI_tuptable; copy datums out via SPI_palloc/SPI_copytuple
       before SPI_finish (SKILL §2.5) */
    SPI_finish();

    PG_RETURN_...;
}
```

Note: `SPI_prepare` returns NULL on failure; the code lands in the
global `SPI_result`. To free a kept plan later: `SPI_freeplan(plan)`
(rare — usually you let it live as long as the FmgrInfo).

---

## Eval 3 — Looking at SPI_tuptable after a subxact rollback

### Answer 3A (baseline, no skill)

When the subxact rolls back, SPI's cleanup hook runs and frees
everything that was allocated inside it — tuptables, executor state,
and any SPI frames that were opened inside the dying subxact. So by
the time you reach the code after
`RollbackAndReleaseCurrentSubTransaction()`, `SPI_tuptable` has been
freed; touching it is use-after-free.

The supported diagnostic channel is the `ErrorData` from the thrown
error. Capture it with `CopyErrorData()` BEFORE `FlushErrorState()`,
allocating in the saved `oldctx` (i.e. switch back to `oldctx`
first). After rollback you can read `edata->message`,
`edata->sqlerrcode`, `edata->detail`, etc.

```c
MemoryContext oldctx = CurrentMemoryContext;
ResourceOwner oldowner = CurrentResourceOwner;

BeginInternalSubTransaction(NULL);
PG_TRY();
{
    SPI_execute("...user sql...", false, 0);
    ReleaseCurrentSubTransaction();
}
PG_CATCH();
{
    MemoryContextSwitchTo(oldctx);
    ErrorData *edata = CopyErrorData();
    FlushErrorState();
    RollbackAndReleaseCurrentSubTransaction();
    /* do NOT touch SPI_tuptable — it's gone */
    ereport(WARNING,
            (errcode(edata->sqlerrcode),
             errmsg("user query failed: %s", edata->message)));
    FreeErrorData(edata);
}
PG_END_TRY();
CurrentResourceOwner = oldowner;
```

If you need partial result rows, you have to `SPI_palloc`/
`SPI_copytuple` them out of the SPI context BEFORE the rollback; you
cannot recover them after.

### Answer 3B (with skill)

This is the aborted-subxact rule from SKILL.md §2.7. `AtEOSubXact_SPI`
([verified-by-code] `src/backend/executor/spi.c:482-572`) is the
cleanup hook the subxact end runs. It does two things:

- Pops every SPI stack entry whose `connectSubid` matches the dying
  subxact and deletes their memory contexts. SPI frames opened
  *inside* the dying subxact are gone — you cannot continue SPI work
  in them.
- For SPI frames that survive (opened in an enclosing (sub)xact), if
  the in-flight executor call started inside the dying subxact it
  resets the SPI Exec context and frees every tuptable created in
  that subxact.

So `SPI_tuptable` from the failed `SPI_execute` has been freed under
you — touching it after `RollbackAndReleaseCurrentSubTransaction` is
use-after-free, as SKILL.md §2.8 bug #3 also calls out.

Per the SKILL §2.7 "capturing diagnostics" paragraph: the supported
channel is `ErrorData` via `CopyErrorData()` BEFORE `FlushErrorState()`,
allocated in the saved `oldctx`. If you need partial *result rows*,
you must `SPI_palloc` / `SPI_copytuple` them out into `oldctx`
BEFORE `ReleaseCurrentSubTransaction` — once the subxact is gone they
cannot be recovered.

Canonical pattern (mirrors §2.7):

```c
MemoryContext oldctx = CurrentMemoryContext;
ResourceOwner oldowner = CurrentResourceOwner;

BeginInternalSubTransaction(NULL);
PG_TRY();
{
    SPI_execute("...user sql...", false, 0);
    /* optional: copy any tuptable data into oldctx via SPI_palloc
       BEFORE Release */
    ReleaseCurrentSubTransaction();
}
PG_CATCH();
{
    MemoryContextSwitchTo(oldctx);
    ErrorData *edata = CopyErrorData();   /* allocated in oldctx */
    FlushErrorState();
    RollbackAndReleaseCurrentSubTransaction();
    /* AtEOSubXact_SPI has freed SPI_tuptable for this subxact — do
       not touch it. */
    ereport(WARNING,
            (errcode(edata->sqlerrcode),
             errmsg("user query failed: %s", edata->message)));
    FreeErrorData(edata);
}
PG_END_TRY();
CurrentResourceOwner = oldowner;
```

Two corollaries the skill flags:

- SPI stack frames opened *inside* the dying subxact have also been
  popped — only an SPI frame that pre-existed
  `BeginInternalSubTransaction` survives.
- This is also why `SPI_commit` / `SPI_rollback` are forbidden inside
  a PL exception block — same root: an open subxact (SKILL §2.6).

If you need partial rows in practice, restructure with a cursor
(`SPI_cursor_open`) opened outside the subxact and fetch in batches,
putting only the per-batch *processing* inside a fresh subxact.
