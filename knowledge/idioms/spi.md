# SPI — the Server Programming Interface

Long-form notes on the SPI: how it sits on top of the executor, what
its transactional model is, and the unfunny ways it bites back.
Operational quick-reference lives in
`.claude/skills/fmgr-and-spi/SKILL.md`.

All confidence tags `[verified-by-code]` unless otherwise noted, against
`source/` at the pinned commit.

---

## 1. What SPI is

SPI is the C-callable interface that lets a backend extension or PL
language handler run SQL queries inside the running backend, using the
existing executor. PL/pgSQL, PL/Python, PL/Perl etc. are all
implemented on top of it. Outside contrib it's also used by the
referential-integrity triggers in `ri_triggers.c` and a handful of
internal utilities.

The header is `src/include/executor/spi.h` (~200 lines, the entire
public surface); the implementation is `src/backend/executor/spi.c`
(~3400 lines).

## 2. Lifecycle and the stack

```c
SPI_connect();          /* push a new SPI stack frame */
SPI_execute(...);
SPI_finish();           /* pop the frame, free everything in it */
```

`SPI_connect` (really `SPI_connect_ext(0)` —
[verified-by-code] `src/backend/executor/spi.c:94-98`) does:

1. Grows the `_SPI_stack` array if needed (starts at 16, doubles).
   [verified-by-code] lines 106-128.
2. Pushes a new `_SPI_connection`. Sets `connectSubid =
   GetCurrentSubTransactionId()` so subxact cleanup can find it.
3. Creates two memory contexts:
   - "SPI Proc" — parent is `TopTransactionContext` for atomic SPI
     (the default), or `PortalContext` for non-atomic.
   - "SPI Exec" — child of SPI Proc (atomic: parented under
     `TopTransactionContext` directly).
   [verified-by-code] lines 149-167.
4. `CurrentMemoryContext` is switched to "SPI Proc"; the previous one
   is saved in `_SPI_current->savedcxt`. This is what makes
   `SPI_palloc` work after `SPI_finish`.
5. Resets the global `SPI_processed`, `SPI_tuptable`, `SPI_result`;
   the previous values are stashed for restoration.

`SPI_finish` [verified-by-code] lines 182-216:

1. Switches back to `savedcxt`.
2. Deletes "SPI Exec" then "SPI Proc". This auto-frees every
   tuptable and every non-saved plan allocated during the session.
3. Restores the outer SPI_processed / SPI_tuptable / SPI_result.
4. Pops the stack.

Globals `SPI_processed`, `SPI_tuptable`, `SPI_result` are documented
in the source as "a horrible API choice, but it's too late now"
[from-comment] `src/backend/executor/spi.c:40-47`. They are
save-and-restored on every push/pop so nested SPI users see their own
values.

## 3. The three memory contexts in play

When inside SPI, `CurrentMemoryContext` is normally "SPI Proc". Things
palloc'd here die at `SPI_finish`.

"SPI Exec" is reset between SPI executor calls — it holds executor
working state. You don't usually allocate here directly.

`_SPI_current->savedcxt` is the caller's context from before the
SPI_connect. To survive SPI_finish, data must end up here. The
canonical APIs that do this for you:

- `SPI_palloc(size)` → palloc in savedcxt
  [verified-by-code] `src/backend/executor/spi.c:1339-1346`.
- `SPI_repalloc`, `SPI_pfree`, `SPI_datumTransfer` — same family.
- `SPI_copytuple(tuple)` → copy a tuple into savedcxt
  [verified-by-code] lines 1047-1072.
- `SPI_returntuple(tuple, tupdesc)` → produce a HeapTupleHeader Datum
  in savedcxt, suitable for `PG_RETURN_HEAPTUPLEHEADER`
  [verified-by-code] lines 1074-1104.

Forgetting to copy is the #1 leak/use-after-free bug in SPI client
code.

## 4. When to use SPI vs. raw executor

SPI is the *only* officially supported way to run queries from inside
a function. The raw executor API (`CreateQueryDesc` →
`ExecutorStart` → `ExecutorRun` → `ExecutorFinish` →
`ExecutorEnd`) exists, but it requires you to manage snapshots,
ResourceOwners, plan caching, parameter passing, and trigger queues
yourself. Almost no out-of-tree code should do this — the cases that
exist in core are RI triggers and DDL.

If you only need to evaluate an expression (a scalar Const-foldable
thing) you can use `ExecPrepareExpr` / `ExecEvalExpr` directly, no SPI
required. That's appropriate for, e.g., evaluating a partition bound.

## 5. Return codes

Every SPI top-level function returns a small `int` code rather than
throwing. Positive codes are `SPI_OK_*`, negative are `SPI_ERROR_*`
[verified-by-code] `src/include/executor/spi.h:68-100`.

The `SPI_OK_*` codes that come back from `SPI_execute` are command-
specific so a caller can react: `SPI_OK_SELECT` populates
`SPI_tuptable`; `SPI_OK_INSERT` / `UPDATE` / `DELETE` set
`SPI_processed` to the modified row count; `SPI_OK_*_RETURNING`
variants give you both; `SPI_OK_UTILITY` says it was a DDL/DCL
statement [verified-by-code] full list at lines 82-100.

Real ereport-style errors thrown by the executor (constraint
violation, parse failure, division by zero, etc.) are NOT converted to
negative codes — they propagate as ereport(ERROR) and longjmp through
the SPI machinery. The negative `SPI_ERROR_*` codes are for SPI's own
sanity checks: NULL arguments, called-while-disconnected, bad plan
magic, no such relation.

Always log via `SPI_result_code_string(ret)` — it has a giant case
statement covering every code [verified-by-code]
`src/backend/executor/spi.c:1973-2045`.

## 6. Plan caching

```c
SPIPlanPtr  plan = SPI_prepare(sql, nargs, argtypes);
SPI_execute_plan(plan, vals, nulls, read_only, tcount);
```

`SPI_prepare` returns NULL on failure, with the code stored in the
global `SPI_result` (because the return type isn't an int)
[verified-by-code] `src/backend/executor/spi.c:861-901`.

A plan from a bare `SPI_prepare` lives in the SPI Proc context and
dies at SPI_finish. To keep it past that (e.g., to cache in
`fn_extra`):

```c
SPIPlanPtr plan = SPI_prepare(...);
SPI_keepplan(plan);          /* reparent under CacheMemoryContext */
SPI_finish();
/* plan is still valid here */
```

[verified-by-code] `src/backend/executor/spi.c:977-1001`.
`SPI_keepplan` is one-way; once kept, the plan is `saved = true` and
its component `CachedPlanSource`s are pinned via `SaveCachedPlan`.

`SPI_freeplan` releases a kept plan; the plan's `plancxt` (memory
context) is deleted [verified-by-code] lines 1025-1045. Calling it on
a non-saved plan still works because the plan was going to die anyway.

For plans with dynamic parameters, use `SPI_prepare_params` /
`SPI_execute_plan_with_paramlist` to pass a `ParamListInfo` (this is
what PL/pgSQL does so that its plans can use late-bound variables).

The plan is a list of `CachedPlanSource`s — one per statement in the
query string. SPI uses the plancache machinery, which means the plan
can be replanned automatically when underlying objects change (DDL
invalidation). For a single-statement plan you can peek via
`SPI_plan_get_plan_sources` and `SPI_plan_get_cached_plan`
[verified-by-code] lines 2056-2100.

## 7. Cursors

`SPI_cursor_open[_with_args|_with_paramlist|_parse_open]` opens a
prepared plan as a `Portal` you can fetch from incrementally
[verified-by-code] `src/backend/executor/spi.c:1446-1569`.

```c
Portal p = SPI_cursor_open(NULL, plan, vals, nulls, true /*read_only*/);
SPI_cursor_fetch(p, true /*forward*/, 1000);
/* SPI_processed / SPI_tuptable now describe 1000 rows */
SPI_cursor_close(p);
```

The portal-based variants are how you stream a large result without
materializing it; PL/pgSQL `FOR rec IN <query> LOOP` is implemented
this way.

Only "cursor plans" — single-statement read-only SELECTs essentially —
can be opened as cursors. `SPI_is_cursor_plan` enforces this
[verified-by-code] lines 1595-1614, 1911-1948.

## 8. Atomic vs non-atomic, COMMIT/ROLLBACK inside SPI

Default `SPI_connect()` is **atomic** — the SPI session inherits the
caller's transaction and cannot end it. Procedures (CALL) need to
commit/rollback, so they use `SPI_connect_ext(SPI_OPT_NONATOMIC)`
[verified-by-code] lines 100-180, especially `_SPI_current->atomic =
(options & SPI_OPT_NONATOMIC ? false : true)` at line 143.

`SPI_commit()` / `SPI_rollback()` (and `_and_chain` variants):

1. Throw `ERRCODE_INVALID_TRANSACTION_TERMINATION` if `atomic`.
2. Throw the same if any subtransaction is currently open. PL
   exception blocks use subxacts and would be silently undone.
3. Mark the SPI frame `internal_xact = true` so `AtEOXact_SPI` won't
   nuke it.
4. `HoldPinnedPortals()`, `ForgetPortalSnapshots()`,
   `CommitTransactionCommand()` (or `AbortCurrentTransaction()`), then
   `StartTransactionCommand()` to keep going.
[verified-by-code] lines 227-411.

Implication: even with non-atomic SPI, you cannot `SPI_commit` inside
a PL exception block.

## 9. Subxacts and the aborted-subxact rule

The PL exception pattern wraps potentially-failing SPI in a
subtransaction:

```c
MemoryContext oldctx = CurrentMemoryContext;
ResourceOwner oldowner = CurrentResourceOwner;

BeginInternalSubTransaction(NULL);
PG_TRY();
{
    SPI_execute("...", false, 0);
    ReleaseCurrentSubTransaction();
}
PG_CATCH();
{
    MemoryContextSwitchTo(oldctx);
    ErrorData *edata = CopyErrorData();
    FlushErrorState();
    RollbackAndReleaseCurrentSubTransaction();
    /* edata holds the failure; SPI internals were cleaned up by
       AtEOSubXact_SPI on the rollback. */
}
PG_END_TRY();

CurrentResourceOwner = oldowner;
```

When the subxact aborts, `AtEOSubXact_SPI(false, mySubid)` runs
[verified-by-code] `src/backend/executor/spi.c:482-572`:

- Pops every SPI stack entry whose `connectSubid` matches the dying
  subxact, *unless* it's marked `internal_xact` (i.e., it owns the
  SPI_commit/rollback). Memory contexts for popped entries are
  explicitly deleted.
- For the surviving SPI frame (one level out), if its current executor
  call was started inside the dying subxact (`execSubid >= mySubid`),
  resets the SPI Exec context. Same for any tuptables created in this
  subxact.

**The aborted-subxact rule.** Once a subxact has aborted, you cannot
continue running SPI calls in any stack frame that opened *during*
that subxact — they've been popped. If you opened SPI before the
subxact and call SPI again after a rollback, that frame survives, but
any tuptable or executor state from inside the subxact is gone.

This is what people mean when they say "SPI is not for inside an
aborted subxact" — concretely: don't try to consume `SPI_tuptable`
that was populated by an `SPI_execute` whose call started inside the
subxact you just rolled back. The tuptable's memory has been freed
by `AtEOSubXact_SPI`.

PL/pgSQL gets this right by always wrapping a fresh subxact + its own
SPI work + reading results entirely within a single PG_TRY block.

## 10. SPI_register_relation and ENRs

For trigger-table propagation and similar patterns, SPI lets a caller
register an `EphemeralNamedRelation` (a transient table that exists
only for the duration of the SPI call) via `SPI_register_relation` and
unregister via `SPI_unregister_relation`. `SPI_register_trigger_data`
is the convenience for trigger NEW/OLD/transition tables
[verified-by-code] `src/backend/executor/spi.c:3297-3404`. This is how
AFTER ... REFERENCING ... transition tables surface inside trigger
functions written in PL/pgSQL.

## 11. Read-only flag and snapshot semantics

`SPI_execute(sql, read_only, tcount)` and the plan variants take a
`read_only` flag. read_only = true tells SPI to reuse the caller's
active snapshot rather than pushing a new one. This is important for
volatility-sensitive callers (PL/pgSQL `STABLE`/`IMMUTABLE` function
bodies) and lets cursors see consistent data across fetches.

If you write to the database from inside SPI you MUST pass
`read_only = false` — the executor refuses writes under a read-only
snapshot.

## 12. Common bugs in SPI client code

1. **Leaking allocations past SPI_finish.** Memory not copied via
   `SPI_palloc`/`SPI_copytuple` into `savedcxt` is gone after finish.
   Symptom: random crashes or stale data in the caller.
2. **`SPI_prepare` without `SPI_keepplan`** when caching the plan on
   `fn_extra`. Plan dies at finish; `fn_extra` then dangles into the
   next call. Symptom: SIGSEGV on the second invocation of the
   function in a session.
3. **Re-using SPI_tuptable after another SPI_execute.** Each execute
   resets `SPI_tuptable` to its own result; the previous one is
   freed (unless you bumped its refcount via the internals, which
   external callers shouldn't). Copy what you need first.
4. **Forgetting the read_only flag.** Writes need false; reads in
   STABLE/IMMUTABLE functions need true.
5. **Calling SPI after a subxact abort, in a frame that was opened
   inside that subxact.** Use SPI from the outer frame, or re-connect.

## 13. Three things easy to get wrong

(Distilled from §12 for the operational SKILL.)

- Returning palloc'd data past `SPI_finish` without `SPI_palloc` /
  `SPI_copytuple` / `SPI_returntuple`.
- Forgetting `SPI_keepplan` when caching plans across SPI sessions
  (e.g. on `FmgrInfo.fn_extra`).
- Continuing to use SPI state after a subtransaction aborted — the
  executor state and tuptables created inside the failed subxact have
  been deleted by `AtEOSubXact_SPI`.

## 14. Cross-references

- Operational quick-reference: `.claude/skills/fmgr-and-spi/SKILL.md`
- Fmgr side: `knowledge/idioms/fmgr.md`
- Memory contexts: `knowledge/idioms/memory-contexts.md`
- Error reporting and PG_TRY/PG_CATCH: `knowledge/idioms/error-handling.md`
- Manual chapter: <https://www.postgresql.org/docs/current/spi.html> [from-docs]
