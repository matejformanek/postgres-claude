# Proposed edits — iteration 1 (NOT applied)

## Headline finding

The skill carries an **out-of-date `planner_hook` prototype** in §8. The
example callback signature has 4 parameters:

```
PlannedStmt *
my_planner(Query *parse, const char *query_string,
           int cursorOptions, ParamListInfo boundParams)
```

The real `planner_hook_type` at `source/src/include/optimizer/planner.h:28-32`
has **5** parameters:

```
typedef PlannedStmt *(*planner_hook_type) (Query *parse,
                                           const char *query_string,
                                           int cursorOptions,
                                           ParamListInfo boundParams,
                                           ExplainState *es);
```

An agent copy-pasting from the skill would not compile. This is the most
important single edit. Verified by reading the header directly.

## Other gaps surfaced by grading

1. The skill does not surface `dfmgr.c:297-299` as the actual call site
   that invokes `_PG_init`. Helps an agent answer "when exactly does
   `_PG_init` fire" questions.
2. The skill says "Extensions installed via `shared_preload_libraries`
   (or `session_preload_libraries`)" but never names
   `local_preload_libraries` (the third bucket — local-user only, no
   superuser). Common confusion source.
3. The skill mentions `bgw_extra` only as "up to BGW_EXTRALEN bytes of
   arbitrary blob" but `worker_spi.c:351-357` shows the canonical layout
   (dboid + roleoid + flags) used by `worker_spi_launch`. Worth a
   one-line pointer.
4. The "Hard rules" §6.A bullet on `BackgroundWorkerInitializeConnection`
   names `BGWORKER_BYPASS_ALLOWCONN` / `BGWORKER_BYPASS_ROLELOGINCHECK`
   but doesn't explain when to actually use them. A short example or
   skip.
5. The skill does NOT explain *why* `die` is the right SIGTERM handler
   (vs. a custom `proc_exit(0)`). Eval 3 showed baseline could
   reconstruct the answer from general PG knowledge, but a single
   explicit "why die() and not proc_exit()" sentence would harden
   against regression.
6. The skill does NOT name `ProcessInterrupts()` / `CHECK_FOR_INTERRUPTS()`
   as where the actual SIGTERM cleanup happens. Worth surfacing as the
   loop-body discipline.

## Concrete edit proposals

### Edit 1 — fix the planner_hook example signature (HIGH)

In SKILL.md §8 "Layering hooks on `_PG_init`", replace lines 173-187 with
the current 5-parameter signature. Add `ExplainState *es` to the
parameter list and to both recursive call sites.

**Verification:** `source/src/include/optimizer/planner.h:28-33`.

```c
static planner_hook_type prev_planner_hook = NULL;

static PlannedStmt *
my_planner(Query *parse, const char *query_string,
           int cursorOptions, ParamListInfo boundParams,
           ExplainState *es)
{
    PlannedStmt *result;

    if (prev_planner_hook)
        result = prev_planner_hook(parse, query_string,
                                   cursorOptions, boundParams, es);
    else
        result = standard_planner(parse, query_string,
                                  cursorOptions, boundParams, es);

    /* ... my modifications to result ... */
    return result;
}
```

### Edit 2 — name `local_preload_libraries` alongside the other two (LOW)

In §8 opening paragraph, change "shared_preload_libraries (or
session_preload_libraries)" to "shared_preload_libraries,
session_preload_libraries, or local_preload_libraries" with a
one-sentence note on the difference (timing + privilege scope).

### Edit 3 — explicit "no _PG_fini, library never unloads" note (MED)

Add to §8 a short subsection after the hook example:

> **There is no `_PG_fini`.** PG's dynamic loader (`dfmgr.c:295-299`)
> calls `_PG_init` once when the library is first loaded and never
> calls a teardown function. Libraries loaded into a backend are
> never unloaded. `DROP EXTENSION` removes the SQL-level catalog
> entries (function bindings from the install script) but does NOT
> undo `_PG_init` — your hook is still wired in until the backend
> exits.

**Verification:** `source/src/backend/utils/fmgr/dfmgr.c:295-299`
shows the `_PG_init` dlsym and call, and no symmetric `_PG_fini`
elsewhere in dfmgr.c.

### Edit 4 — annotate why `die` and `SignalHandlerForConfigReload` (MED)

In §6 ("Worker main function skeleton"), add a brief paragraph right
under "Hard rules inside a worker":

> **Why these specific signal handlers?** `die` (in
> `source/src/backend/tcop/postgres.c:3023-3058`) and
> `SignalHandlerForConfigReload` (in
> `source/src/backend/postmaster/interrupt.c:60-65`) both implement the
> only signal-safe pattern: set a flag + `SetLatch(MyLatch)` + return.
> The actual work (`AbortCurrentTransaction`, `ProcessConfigFile`)
> happens in the main loop body when `CHECK_FOR_INTERRUPTS()` or the
> `ConfigReloadPending` check observes the flag — never in the handler
> itself. Calling `proc_exit(0)` straight from a SIGTERM handler would
> (a) skip transaction abort, (b) run signal-unsafe `palloc` / LWLock
> code, and (c) per the `bgw_restart_time` contract, retire the
> worker's slot forever regardless of restart policy.

### Edit 5 — document `bgw_extra` canonical layout pointer (LOW)

In §2 (BackgroundWorker struct), replace the bare comment
`/* bgw_extra: up to BGW_EXTRALEN bytes of arbitrary blob */` with:

```c
/* bgw_extra: up to BGW_EXTRALEN bytes for the launcher to hand the
   worker an arbitrary blob. worker_spi.c packs Oid dboid + Oid roleoid
   + uint32 flags into it; the worker memcpy's them out in main(). */
```

**Verification:** `source/src/test/modules/worker_spi/worker_spi.c:151-157`
(unpacking) and `worker_spi.c:445-454` (packing in launch path).

## Score delta expected if edits applied

iter-1 with_skill: 29/30 (0.967).
After Edit #1: with_skill should hit 30/30 on iter-2 (the missing
prototype assertion).
Edits 2-5 are defensive — they harden against prompts not in this
iteration's set.

## Non-edits

- The §3 flag cheatsheet, §4 start-time list, §5 restart-policy table,
  §7 dynamic-worker API list, and §9 checklist are all verified-correct
  against source (per the [verified-by-code] cites). No changes.
- The `worker_spi.c:362-385` registration cite and `worker_spi.c:134-225`
  main-function cite both match source after re-reading. Keep.
- The two `[unverified]` markers at the bottom (BGWORKER_INTERRUPTIBLE
  recommendation, bgw_notify_pid race) are honestly unverified — leave
  them tagged rather than guessing.
