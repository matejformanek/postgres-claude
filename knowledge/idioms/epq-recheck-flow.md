# EvalPlanQual recheck flow — per-conflict row re-evaluation

When a backend at `READ COMMITTED` is about to UPDATE / DELETE a
row, the heap-AM's `heap_update` / `heap_delete` returns
`TM_Updated` if a concurrent committed xact modified the row
between our snapshot acquisition and now. The caller
(`ExecUpdate` / `ExecDelete` in nodeModifyTable.c) then invokes
`EvalPlanQual` with the row's latest version. EvalPlanQual
re-runs the WHERE clause against the new version through the
EPQ recheck plan tree and returns the new tuple if it still
qualifies, or NULL if it doesn't. The recheck plan was set up
at `ExecInit` time; per-call work is just resetting flags +
copying params + one ExecProcNode call.

Anchors:
- `source/src/backend/executor/execMain.c:2678` —
  EvalPlanQual top entry [verified-by-code]
- `source/src/backend/executor/execMain.c:2944` —
  EvalPlanQualNext [verified-by-code]
- `source/src/backend/executor/execMain.c:2960-3017` —
  EvalPlanQualBegin reset path [verified-by-code]
- `source/src/backend/executor/execMain.c:2987-3009` —
  paramExecTypes copy [verified-by-code]
- `source/src/backend/executor/execMain.c:3011-3016` —
  chgParam-driven rescan [verified-by-code]
- `knowledge/idioms/epq-state-init.md` — companion
- `knowledge/idioms/epq-multi-table.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The trigger condition

```c
result = table_tuple_update(resultRelInfo->ri_RelationDesc,
                            tupleid, slot, ...);

if (result == TM_Updated)
{
    /* Concurrent update — re-fetch & re-check */
    TupleTableSlot *epqslot = EvalPlanQual(&node->mt_epqstate, ...);
    if (TupIsNull(epqslot))
        goto skip_row;    /* WHERE no longer matches */
    /* else: epqslot has the matching new version */
    slot = epqslot;
    goto retry_update;
}
```

`TM_Updated` says "the tuple you read was replaced by a newer
version committed since our snapshot". `TM_Deleted` is similar
but the new version is gone. `TM_SelfModified` / `TM_BeingModified`
are different cases handled separately.

## EvalPlanQual — the entry

[verified-by-code `execMain.c:2678-2731`]

```c
TupleTableSlot *
EvalPlanQual(EPQState *epqstate, Relation relation,
             Index rti, TupleTableSlot *inputslot)
{
    EvalPlanQualBegin(epqstate);

    /* Stash the new tuple in the test slot */
    testslot = EvalPlanQualSlot(epqstate, relation, rti);
    if (testslot != inputslot)
        ExecCopySlot(testslot, inputslot);

    /* Mark target rel "has a tuple to re-check" */
    epqstate->relsubs_done[rti - 1] = false;
    epqstate->relsubs_blocked[rti - 1] = false;

    /* Run the recheck plan — expect 0 or 1 result tuples */
    slot = EvalPlanQualNext(epqstate);

    /* Materialize before re-using the EPQ state */
    if (!TupIsNull(slot))
        ExecMaterializeSlot(slot);

    /* Clear test slot, mark "no more re-checks for this rel" */
    ExecClearTuple(testslot);
    epqstate->relsubs_blocked[rti - 1] = true;

    return slot;
}
```

Three discrete steps:
1. **Begin** — lazy-init or reset the recheck plan.
2. **Inject** — copy the new tuple into the per-rel test slot;
   mark this rel as "tuple available" and OTHERS as
   "no tuple available".
3. **Run + materialize** — one ExecProcNode call; result slot
   contents materialized so they don't dangle across cleanup.

## EvalPlanQualNext — the recheck plan execution

[verified-by-code `execMain.c:2944-2954`]

```c
TupleTableSlot *
EvalPlanQualNext(EPQState *epqstate)
{
    MemoryContext oldcontext;
    TupleTableSlot *slot;

    oldcontext = MemoryContextSwitchTo(epqstate->recheckestate->es_query_cxt);
    slot = ExecProcNode(epqstate->recheckplanstate);
    MemoryContextSwitchTo(oldcontext);

    return slot;
}
```

The recheck plan tree was built by EvalPlanQualStart (see
`epq-state-init`). It's structurally identical to the original
target's source plan — same scans, joins, quals — but at each
scan node, if the corresponding `relsubs_blocked[rti] == false`,
the scan reads from `relsubs_slot[rti]` (the EPQ slot) instead
of doing a real scan.

This is the magic: instead of replacing the scan node, the
executor's scan code (`ExecScan`) checks the EPQ slot bookkeeping
on each call and substitutes the EPQ tuple when appropriate.

> In practice, there should never be more than one row... [comment
> at `execMain.c:2941`]

The recheck plan is called with one tuple injected; the plan
either qualifies it (returns the tuple) or filters it out
(returns NULL).

## Reset path in EvalPlanQualBegin

[verified-by-code `execMain.c:2970-3017`]

When Begin is called the second+ time on the same EPQState:

```c
/* Reset relsubs_done to relsubs_blocked baseline */
memcpy(epqstate->relsubs_done, epqstate->relsubs_blocked,
       rtsize * sizeof(bool));

/* Re-copy InitPlan output values from parent */
if (parentestate->es_plannedstmt->paramExecTypes != NIL)
{
    ExecSetParamPlanMulti(rcplanstate->plan->extParam, ...);
    /* copy param values */
    for (i = paramcount - 1; i >= 0; i--) {
        recheckestate->es_param_exec_vals[i].value =
            parentestate->es_param_exec_vals[i].value;
        recheckestate->es_param_exec_vals[i].isnull =
            parentestate->es_param_exec_vals[i].isnull;
    }
}

/* Force rescan of the entire recheck plan tree */
rcplanstate->chgParam = bms_add_member(rcplanstate->chgParam,
                                       epqstate->epqParam);
```

The `epqParam` is added to the recheck plan's `chgParam` — this
signals to `ExecReScan` that ALL scan nodes need to be reset
(starts the recheck fresh).

## Param copy on reset

[verified-by-code `execMain.c:2987-3009`]

The parent's InitPlans (correlated subqueries with PARAM_EXEC
outputs) may have re-evaluated since the last EPQ call. We copy
their current values into the recheck EState's
`es_param_exec_vals` so the recheck plan sees consistent state.

Without this, an InitPlan that updated mid-statement would give
the recheck plan stale params.

## ExecScanFetch / EvalPlanQualFetchRowMark

For non-locked rels referenced by the EPQ plan, scan nodes call
`ExecScanFetch` (or similar table-AM wrapper) which dispatches:
- If `relsubs_done[rti]` — return NULL (don't re-fetch).
- If a rowmark is registered — call `EvalPlanQualFetchRowMark` to
  re-fetch the row from the relation by CTID stored in a junk
  attribute.
- Else — fetch directly via the table AM.

`EvalPlanQualFetchRowMark` (`execMain.c:2833`) implements the
re-fetch: extracts the CTID junk attribute from origslot, then
calls the table-AM's `RefetchForeignRow` (for FDW) or normal
heap fetch.

## Why "at most one tuple"

The recheck plan is essentially the same as the original query's
sub-plan beneath the ModifyTable, but with a single tuple
injected at the target rel's scan position. For typical
single-target UPDATE / DELETE / MERGE, this yields 0 or 1 tuples
after the WHERE clause.

For MERGE with multiple match conditions, the recheck behavior
gets more subtle but still bounded.

## What happens on TM_SelfModified

The row was modified by the SAME xact (e.g., a BEFORE trigger
chained an UPDATE that hit this row). PG raises ERROR — the row
is no longer the one we read. NOT handled via EPQ.

## What happens on TM_BeingModified

Another xact is concurrently modifying but hasn't committed yet.
PG waits for it to commit/abort, then re-fetches the row's new
state. The xact wait happens BEFORE EvalPlanQual; only post-
commit do we EPQ-check.

## Higher isolation levels skip EPQ

At REPEATABLE READ / SERIALIZABLE, TM_Updated → ERROR
("could not serialize access due to concurrent update"). EPQ is
specifically a READ COMMITTED feature.

## EPQ recursion — when recheck itself triggers EPQ

A recheck plan that does its own UPDATE (via writable CTE) can
itself hit TM_Updated. The nested EvalPlanQualInit on the inner
ModifyTable allocates a separate EPQState; recursion bottoms
out when every level either qualifies or NULLs.

## Common review-time concerns

- **EPQ only at READ COMMITTED** — higher isolation aborts.
- **One ExecProcNode call per recheck** — the recheck plan
  returns 0 or 1 tuples.
- **relsubs_blocked is set after the recheck** — so a follow-on
  EvalPlanQual call for a DIFFERENT relation doesn't get this
  rel's tuple.
- **epqParam triggers chgParam** — without this the plan would
  reuse stale scan positions.
- **ExecMaterializeSlot before return** — protects the result
  tuple from EPQ teardown.
- **FDW rows need RefetchForeignRow** — FDWs declare what locks
  they support via GetForeignRowMarkType.

## Invariants

- **[INV-1]** EvalPlanQual is called on `TM_Updated`; not on
  `TM_SelfModified` / `TM_BeingModified` / `TM_Deleted`.
- **[INV-2]** Recheck plan produces at most one tuple (the
  conflicting row + WHERE clause).
- **[INV-3]** `relsubs_blocked[rti] = true` after the recheck
  for that rti.
- **[INV-4]** epqParam added to chgParam triggers full rescan
  of recheck plan on reset.
- **[INV-5]** InitPlan outputs are re-copied from parentestate
  on every Begin (idempotent across nested EPQ calls).

## Useful greps

- EvalPlanQual entry + Next:
  `grep -n '^EvalPlanQual\b\|^EvalPlanQualNext' source/src/backend/executor/execMain.c | head -10`
- TM_Updated callers (the trigger):
  `grep -RIn 'TM_Updated\|TM_Result' source/src/backend/executor/nodeModifyTable.c | head -15`
- chgParam + epqParam:
  `grep -n 'epqParam\|chgParam' source/src/backend/executor/execMain.c | head -15`
- ExecScanFetch dispatch:
  `grep -RIn 'ExecScanFetch' source/src/backend/executor | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2678 | EvalPlanQual top entry |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2944 | EvalPlanQualNext |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2960 | EvalPlanQualBegin reset path |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2987 | paramExecTypes copy |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 3011 | chgParam-driven rescan |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | — | EPQ machinery |
| [`src/backend/executor/nodeModifyTable.c`](../files/src/backend/executor/nodeModifyTable.c.md) | — | caller |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-hook`](../scenarios/add-new-hook.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/epq-state-init.md` — EPQState lifecycle.
- `knowledge/idioms/epq-multi-table.md` — rowmark handling
  for non-target rels in EPQ.
- `knowledge/idioms/heaptuple-update-chain.md` —
  the chain TM_Updated follows.
- `knowledge/idioms/tuple-locking-modes.md` — what produces
  TM_Updated.
- `knowledge/data-structures/estate.md` — parent vs recheck
  EState relationship.
- `knowledge/subsystems/executor.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/executor/execMain.c` — EPQ machinery.
- `source/src/backend/executor/nodeModifyTable.c` — caller.
