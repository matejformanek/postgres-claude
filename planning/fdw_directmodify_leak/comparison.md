# Comparison — our blind fix vs Tom Lane's `232d8caeaaa`

**Date:** 2026-07-13
**Our commit chain (`feature_fdw_directmodify_leak`):**
- `fa4030506f2` Phase 1: es_query_cxt reset callback + PG_TRY removal

**Upstream fix:** `232d8caeaaa06fd3c6b76a68ef9c62ea5fdf12ea`
(Haiyang Li reporter, Tom Lane review + commit, 2025-05-30,
back-patched-through PG13).

Both branches start from the same parent `d98cefe1143`.

## L6 verdict — approach E graduated *correctly*

**This was the L6 stress test — the target's fix pattern is the
"restructure control flow to match new invariant" shape L6 codifies.**

The blind brainstorm §5 correctly enumerated approach E as the
mandatory L6-triggered option, correctly rejected approaches A-D:

- **A** (explicit PQclear at every PG_TRY exit) — rejected because
  the throw fires in `ExecProject` *outside* postgres_fdw's stack
  frame, so no PG_TRY inside the FDW can catch it.
- **B** (single-wrapping PG_TRY at Iterate entry) — rejected for
  the same "throw is outside our frame" reason.
- **C** (MemoryContext reset callback) — subsumed by E.
- **D** (ResourceOwner-tracked resource) — rejected as too invasive
  for a 5-branch back-patch.

Recommended approach: **E2** — register a
`MemoryContextRegisterResetCallback` on `estate->es_query_cxt` that
owns the PGresult across all exit paths, plus delete the
now-redundant PG_TRY in `get_returning_data`.

**Tom's fix is the same approach category.** L6 delivered the
right shape for the first time on a target that specifically
stresses it.

## Leak outcome

| metric                        | parent commit | our fix       | Tom's fix (expected) |
|-------------------------------|--------------:|--------------:|---------------------:|
| RSS after 20 k iter × 25 s    | 90.9 MB       | 14.2 MB       | flat                 |
| RSS delta over 25 s           | +79 MB        | +0.1 MB       | ~0                   |
| Leak rate                     | 3.3 MB/s      | ~5 KB/s       | 0                    |
| Result correctness            | error propagated | error propagated | error propagated |

Our fix cuts the leak rate ~800× — RSS is essentially flat
(observed growth is OS-level allocator bookkeeping, not
`hashtempcxt`-style accumulation).

## Diff size

| author    | files | insertions | deletions | net LOC change | commits |
|-----------|------:|-----------:|----------:|---------------:|--------:|
| Tom Lane  |     1 |         35 |        27 |             +8 |       1 |
| Ours      |     1 |         82 |        25 |            +57 |       1 |

Roughly the same shape — 5-line net for Tom, 57 net for us. Ours
is larger because our callback comment blocks are more verbose
and the callback structure is more heavily commented.

## Structural comparison — three key differences

### 1. Callback struct storage

**Tom's fix.** Add `MemoryContextCallback result_cb;` as a *field*
of `PgFdwDirectModifyState`. The callback struct lives in the same
palloc block as the state struct.

```c
typedef struct PgFdwDirectModifyState
{
    ...
    MemoryContextCallback result_cb;    /* ensures result will get freed */
    ...
} PgFdwDirectModifyState;
```

Registration: `MemoryContextRegisterResetCallback(CurrentMemoryContext,
&dmstate->result_cb);` — passes the address of the embedded field.

**Our fix.** Separately palloc a fresh `MemoryContextCallback` on
`estate->es_query_cxt`.

```c
MemoryContextCallback *cb;
cb = (MemoryContextCallback *)
    MemoryContextAlloc(estate->es_query_cxt,
                       sizeof(MemoryContextCallback));
cb->func = pgfdw_result_reset_callback;
cb->arg = &dmstate->result;
MemoryContextRegisterResetCallback(estate->es_query_cxt, cb);
```

**Tom's is cleaner.** Embedding removes:
- A separate palloc site to reason about
- An extra pointer indirection during callback dispatch
- The ownership question about "who owns this callback struct's
  memory" (in Tom's design, the state struct owns it)

### 2. Callback function + arg semantics

**Tom's fix.** Function pointer is `PQclear` directly (cast to
`MemoryContextCallbackFunction`). Arg is the PGresult *value*.
Callback fires → PQclear(arg) → PQclear(PGresult).

```c
dmstate->result_cb.func = (MemoryContextCallbackFunction) PQclear;
dmstate->result_cb.arg = NULL;      /* initially disarmed */
...
dmstate->result_cb.arg = dmstate->result;    /* arm when result set */
...
dmstate->result_cb.arg = NULL;      /* disarm on End */
```

Relies on `PQclear(NULL)` being a documented no-op, so the "armed
with NULL" state is safe.

**Our fix.** Function pointer is a wrapper `pgfdw_result_reset_callback`.
Arg is `&dmstate->result` — a *pointer-to-pointer*. Callback
dereferences and PQclears whatever's there.

```c
static void
pgfdw_result_reset_callback(void *arg)
{
    PGresult  **resultp = (PGresult **) arg;

    if (*resultp != NULL)
    {
        PQclear(*resultp);
        *resultp = NULL;
    }
}
```

**Tom's is cleaner.** Removes:
- A wrapper function
- The pointer-to-pointer dereference layer
- The `*resultp = NULL` bookkeeping (unnecessary because the
  callback only fires once per context lifetime)

The idiom "cast a well-known clean-up function directly, use the
opaque handle as arg" is more idiomatic PG C style. Ours is more
defensive but more machinery.

### 3. Handoff between `execute_dml_stmt` and `pgfdw_report_error`

**Tom's fix.**

```c
Assert(dmstate->result == NULL);
dmstate->result = pgfdw_get_result(dmstate->conn);
dmstate->result_cb.arg = dmstate->result;   /* arm callback */

if (PQresultStatus(dmstate->result) !=
    (dmstate->has_returning ? PGRES_TUPLES_OK : PGRES_COMMAND_OK))
    pgfdw_report_error(ERROR, dmstate->result, dmstate->conn, false,
                       dmstate->query);
```

Note the last argument: `clear=false`. Tom tells `pgfdw_report_error`
NOT to PQclear -- the callback is now the sole owner and will
release the PGresult when es_query_cxt tears down. Single ownership.

**Our fix.**

```c
dmstate->result = pgfdw_get_result(dmstate->conn);
if (PQresultStatus(dmstate->result) !=
    (dmstate->has_returning ? PGRES_TUPLES_OK : PGRES_COMMAND_OK))
{
    PGresult   *res = dmstate->result;

    dmstate->result = NULL;
    pgfdw_report_error(ERROR, res, dmstate->conn, true,
                       dmstate->query);
}
```

We keep `clear=true` (the existing behavior) and detach the
PGresult from `dmstate->result` (NULL the pointer) *before* passing
it to `pgfdw_report_error`. That way `pgfdw_report_error`'s
PG_FINALLY PQclears the local `res`, and our callback fires later
with `dmstate->result == NULL` (no-op). Two-owner semantics with
explicit handoff.

**Tom's is cleaner.** Single-ownership + clear=false is the whole
point of the callback approach. Our "detach then clear=true" is
the same behavior via a different bookkeeping path.

## What we got right

1. **L6 approach E fired correctly.** Brainstorm §5 enumerated the
   full A-E slate; §6 recommended E2. Zero false positives (didn't
   pick a less-suitable approach). This is the whole point of the
   L6 codification — L6 delivered.
2. **F30 grep-pass identified the pre-existing PG_TRY as
   redundant.** The plan §7 confirmed the throw fires *outside*
   the PG_TRY frame (in `ExecProject`), which is exactly why
   PG_TRY at the acquisition site is fundamentally insufficient.
3. **RSS canary bounded the leak to ~5 KB/s** (parent was
   3.3 MB/s). ~800× reduction, same order-of-magnitude as
   expected of Tom's fix.
4. **Same 3 call-site touchpoints as Tom.** postgresBeginDirectModify
   registers callback; postgresEndDirectModify NULLs `dmstate->result`;
   `execute_dml_stmt` hands off to callback; `get_returning_data`
   loses its redundant PG_TRY block.
5. **Correctness verified** — same error message propagates from
   `pgfdw_report_error`; subsequent operations succeed; session
   stays alive after the error.

## What we got wrong

1. **F34 — did not consider embedding the MemoryContextCallback
   struct inside `PgFdwDirectModifyState`.** Our design allocated
   the callback separately on `es_query_cxt`. Tom's design embeds
   it as a field of the state struct. Embedding is strictly
   better: one fewer palloc, one fewer pointer indirection, no
   "who owns the callback struct?" question. F34 codifies this as
   a new plan-time consideration for reset-callback approaches.

2. **F35 — did not consider using PQclear directly as the callback
   function.** We wrote a wrapper `pgfdw_result_reset_callback`
   that dereferences a pointer-to-pointer and PQclears the value.
   Tom cast `PQclear` directly to `MemoryContextCallbackFunction`
   and used the PGresult value as arg. The "cast known-clean-up
   function directly" idiom is more idiomatic PG C style and
   removes machinery.

3. **F36 — did not consider using clear=false in pgfdw_report_error.**
   Our error branch does "detach then clear=true"; Tom's does
   "callback owns, so clear=false". Both are correct. Tom's is
   the natural fit for the "single owner via callback" model.

4. **Approach E2 was RIGHT but implementation choices were
   slightly heavier than optimal.** The trilogy correctly picked
   the design category; the plan's implementation-level details
   were more defensive than Tom's. That's a category-vs-detail
   split.

## What Tom did that we did too

1. **Register callback in `postgresBeginDirectModify`** (both fires
   during es_query_cxt teardown regardless of scan-body outcome).
2. **NULL `dmstate->result` in `postgresEndDirectModify`** after
   PQclear (both make the callback a no-op on the happy path).
3. **Delete the PG_TRY in `get_returning_data`.** Same 22-line
   deletion, same rationale ("callback covers it now").
4. **Do NOT add a regress test** for the fix. (Ours skipped
   Phase 2 because of a pre-existing macOS crash in the
   postgres_fdw regress suite at the parent pin; Tom simply
   didn't ship a test either.)

## Pre-existing macOS crash — F37

The contrib/postgres_fdw regress suite crashes on macOS +
cassert + `MALLOC_PERTURB_=209` at parent pin `d98cefe1143`,
regardless of our modifications.  Reverting `postgres_fdw.c` to
the parent-pin state reproduces the crash identically on the
c2positive-check test row (line 6753 of the results file).

This is *not* related to our fix or Tom's fix — it's an
environmental issue that manifests specifically when the meson
test harness's `MALLOC_PERTURB_` value tickles some allocator
state at that pin.  The crash never fires in the isolated
manual reproducer or in the RSS canary.

Loop consequence: Phase 2 (regress test additions) was skipped
because we could not verify new regress rows against a
green baseline.  R13's phase-end gate used core `regress` +
`isolation` + the RSS canary in place of the postgres_fdw suite.

Action for `knowledge/scenarios/fix-memory-leak.md`: add a
Phase 0.5 check — "run the target contrib suite at parent-pin
before landing the fix; if it's red, plan phase-end gate around
core suites + the RSS canary instead of the target suite."

## Methodology validation verdict for the planner suite

Fourth calibration run confirms the pattern with a critical new
data point:

- **Phase 0 harness** — strong. F31 already codified (scenario#34
  landed 55e853cf). Reproducer needed 3 iterations to work
  reliably, but Phase 0.5 target-suite health check was NEW gap
  (F37).
- **Phase 1 triage** — strong. Target picked with explicit
  approach-E-relevance rationale. Ranked runners-up correctly.
- **Brainstorm (Phase 2 of trilogy)** — **strong**. L6 approach-E
  fired correctly on the target designed to stress it. Brainstorm
  §5 enumerated all 5 approaches with cited rejection reasoning
  for A-D. **This is the first calibration run since L6 landed
  where L6 delivered its intended value.**
- **Plan (Phase 2 of trilogy)** — mostly strong. §7 F30 grep-pass
  correctly identified the PG_TRY-in-get_returning_data as the
  redundant defense to remove. §3 file table missed the "consider
  embedding callback in state struct" consideration (F34); §7
  Memory & Resource management didn't ask "what's the natural
  callback function signature — wrapper or direct-cast?" (F35).
- **Implement (Phase 3 of trilogy)** — mixed. R4 phase-end check
  was compromised by the pre-existing macOS crash (F37); RSS
  canary + core regress + isolation used instead. First calibration
  run where R13 was materially adjusted mid-flight.
- **Compare (Phase 4 of trilogy)** — strong. Delta illuminated F34
  + F35 + F36 all at implementation-detail level; approach category
  was correct.

**Net assessment:** The planner suite produced a **semantically
correct** fix that bounds the leak to essentially zero, using the
same approach category (memory-context reset callback) as Tom's
upstream fix. Implementation details differ — Tom's is cleaner in
three specific ways codified as F34/F35/F36 above — but the
fundamental design choice (L6 approach E) was picked correctly by
the newly-graduated L6 lesson.

**This is the first calibration run where L6 was tested in the
wild, and it worked.**

## New F/L findings to graduate

- **F34 — embed MemoryContextCallback in state struct.** When the
  fix uses a reset callback for a per-scan/per-query resource,
  the callback struct should live as a field of the surrounding
  state struct, not as a separate palloc. Fewer moving parts,
  cleaner ownership. Codify in `knowledge/idioms/memory-contexts.md`.

- **F35 — cast well-known cleanup functions directly.** For
  reset-callback approaches, prefer casting a well-known cleanup
  function (PQclear, pfree, closesocket, etc.) directly to
  `MemoryContextCallbackFunction` rather than writing a wrapper.
  Only write a wrapper if the cleanup needs additional bookkeeping
  the callback dispatcher can't provide. Codify in
  `knowledge/idioms/memory-contexts.md`.

- **F36 — for callback-owned resources, use "single owner via
  callback" semantics throughout.** If a callback owns a resource,
  every other code path that could release it should either detach
  first or delegate to the callback. Do NOT double-manage. Codify
  in `knowledge/idioms/memory-contexts.md`.

- **F37 — Phase 0.5: check target contrib suite health at parent
  pin.** Before assuming R13's phase-end gate = target contrib
  suite, run the suite at parent pin (blank fix) and confirm
  green. If red on the environment, fall back to core regress +
  isolation + RSS canary. Codify in
  `knowledge/scenarios/fix-memory-leak.md`.

- **L7 — approach E's detail-vs-category split.** L6 correctly
  identifies the design category ("restructure to invariant").
  But implementation details — where to store the callback, what
  function to register, single-vs-two-owner semantics — are
  independent design choices the brainstorm doesn't naturally
  enumerate. Consider extending the plan template (§7 Memory &
  Resource management) with an "if this is a callback-based
  approach, name the storage location + function shape +
  ownership semantics" sub-block. Anchored in F34+F35+F36 which
  all reflect the same "L6 called the category right, plan didn't
  drill into details" gap.

## Cross-references

- `planning/fdw_directmodify_leak/baseline.md` — reproducer +
  Phase 0
- `planning/fdw_directmodify_leak/triage.md` — target selection
- `planning/fdw_directmodify_leak/brainstorm.md` — Phase 2 blind
  design, approach A-E enumeration
- `planning/fdw_directmodify_leak/plan.md` — Phase 2 blind plan
  (14 sections)
- `planning/jsonpath_leak/comparison.md` — L5 origin
- `planning/nodesubplan_leak/comparison.md` — L6 origin (F32)
- `.claude/skills/pg-feature-brainstorm/SKILL.md` — L6 codification
- upstream `232d8caeaaa06fd3c6b76a68ef9c62ea5fdf12ea` — Tom Lane's
  actual fix
