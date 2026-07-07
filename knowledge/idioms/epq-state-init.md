# EvalPlanQual init — EPQState lifecycle for row-recheck

`EvalPlanQual` is the row-recheck mechanism behind `READ
COMMITTED` UPDATE / DELETE: when our snapshot says "row X
qualifies" but a concurrent xact already locked-and-updated it,
we follow the update chain to the latest version and re-evaluate
the WHERE clause against THAT version. If the re-evaluation
passes, we operate on the new tuple; else we skip the row. The
infrastructure lives in `execMain.c` — `EPQState` carries the
per-target-relation re-evaluation context, including a private
mini-EState that runs the recheck plan tree. Initialization is
two-stage: `EvalPlanQualInit` at ExecInit (cheap, pre-allocates
slot pointers); `EvalPlanQualBegin` lazily creates the
recheck-time state on first need.

Anchors:
- `source/src/backend/executor/execMain.c:2747` —
  EvalPlanQualInit [verified-by-code]
- `source/src/backend/executor/execMain.c:2788` —
  EvalPlanQualSetPlan [verified-by-code]
- `source/src/backend/executor/execMain.c:2804` —
  EvalPlanQualSlot [verified-by-code]
- `source/src/backend/executor/execMain.c:2960` —
  EvalPlanQualBegin [verified-by-code]
- `source/src/backend/executor/execMain.c:3027` —
  EvalPlanQualStart [verified-by-code]
- `source/src/backend/executor/execMain.c:3208` —
  EvalPlanQualEnd [verified-by-code]
- `knowledge/idioms/epq-recheck-flow.md` — companion
- `knowledge/idioms/epq-multi-table.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## Why EPQ exists

```
T1: SELECT FOR UPDATE WHERE x = 5;  -- gets row at v1
T2: UPDATE ... SET x = 5 WHERE id = 17 (which had x=4 at v1);
                                       -- T2 commits
T1: continues to its UPDATE — but the row now has x = 5,
    not the value it saw at v1.
```

At `READ COMMITTED`, T1's snapshot is at start-of-statement; T2
changed the row after. Naive behavior: T1 either ignores the new
version (incorrect — row may not match WHERE anymore) or aborts.

PostgreSQL's choice: T1 fetches the latest tuple version,
re-runs the WHERE clause + JOIN quals against THAT tuple, and:
- If still matches → proceed on the new tuple.
- If no longer matches → skip the row.

This needs to re-evaluate a sub-plan that uses the new tuple's
values in place of the snapshot-time ones — the EPQ machinery.

## EPQState — the recheck context

(struct in `executor.h`)

```c
typedef struct EPQState
{
    /* set by EvalPlanQualInit, fixed for life */
    EState         *parentestate;
    int             epqParam;
    List           *resultRelations;

    /* set / changed by EvalPlanQualSetPlan */
    Plan           *plan;
    List           *arowMarks;

    /* per-tuple input slot for the row currently being re-checked */
    TupleTableSlot *origslot;

    /* dynamically allocated by EvalPlanQualBegin */
    EState         *recheckestate;
    PlanState      *recheckplanstate;
    ExecAuxRowMark **relsubs_rowmark;
    bool           *relsubs_done;
    bool           *relsubs_blocked;
    TupleTableSlot **relsubs_slot;
    List           *tuple_table;
} EPQState;
```

Lifecycle:

```
ExecInitNode
    └── EvalPlanQualInit          /* cheap; allocate slot pointers */

  ... user runs query, conflict detected on a row ...

EvalPlanQual
    ├── EvalPlanQualBegin         /* lazy: create recheckestate */
    │       └── EvalPlanQualStart  /* build the recheck plan state */
    ├── set origslot to the conflicting row
    ├── EvalPlanQualNext           /* run the recheck plan */
    └── return matching tuple or NULL

  ... eventually ...

ExecEndNode
    └── EvalPlanQualEnd            /* tear down recheckestate */
```

## EvalPlanQualInit — the cheap part

[verified-by-code `execMain.c:2747-2779`]

```c
void
EvalPlanQualInit(EPQState *epqstate, EState *parentestate,
                 Plan *subplan, List *auxrowmarks,
                 int epqParam, List *resultRelations)
{
    Index rtsize = parentestate->es_range_table_size;

    epqstate->parentestate = parentestate;
    epqstate->epqParam = epqParam;
    epqstate->resultRelations = resultRelations;

    /*
     * Allocate space to reference a slot for each potential rti — do so now
     * rather than in EvalPlanQualBegin(), as done for other dynamically
     * allocated resources, so EvalPlanQualSlot() can be used to hold tuples
     * that *may* need EPQ later, without forcing the overhead of
     * EvalPlanQualBegin().
     */
    epqstate->tuple_table = NIL;
    epqstate->relsubs_slot = palloc0_array(TupleTableSlot *, rtsize);

    epqstate->plan = subplan;
    epqstate->arowMarks = auxrowmarks;

    /* mark inactive */
    epqstate->origslot = NULL;
    epqstate->recheckestate = NULL;
    /* ... rest NULL */
}
```

Why pre-allocate `relsubs_slot[rtsize]`:
- Callers may want to call `EvalPlanQualSlot` to get a slot for
  a row that *might* need EPQ later — before any conflict
  occurs.
- Avoiding lazy allocation here keeps the slot stable.

The `recheckestate` and related fields stay NULL until a
conflict actually fires EPQ.

## EvalPlanQualBegin — the lazy part

[verified-by-code `execMain.c:2960-2990`]

Called inside EvalPlanQual when a conflict is detected. Either:
1. **First call** — calls `EvalPlanQualStart` to build the
   recheck plan state.
2. **Subsequent call** — resets the prior state (clear
   relsubs_done, relsubs_blocked).

The lazy approach saves the cost of building a full plan state
for queries that don't hit conflicts (the common case).

## EvalPlanQualStart — building the mini-EState

[verified-by-code `execMain.c:3027+`]

```c
static void
EvalPlanQualStart(EPQState *epqstate, Plan *planTree)
{
    EState *parentestate = epqstate->parentestate;
    EState *rcestate;

    /* Build a private EState for the recheck */
    rcestate = CreateExecutorState();
    epqstate->recheckestate = rcestate;

    /* Copy critical fields from parent: snapshot, paramlist, ... */
    rcestate->es_snapshot = parentestate->es_snapshot;
    rcestate->es_query_dsa = parentestate->es_query_dsa;
    /* ... etc ... */

    /* Initialize range table reference + slots */
    /* Set epqstate->relsubs_rowmark, _done, _blocked arrays */
    /* Run ExecInitNode on the recheck plan */
    epqstate->recheckplanstate = ExecInitNode(planTree, rcestate, 0);
}
```

The recheck EState is a SEPARATE executor state with its own
slot table, expression context, range table — but uses the
parent's snapshot, params, and DSA segment.

This isolation lets EPQ recursion compose: if the recheck plan
itself does an UPDATE that conflicts, that nested EPQ gets its
own recheckestate.

## EvalPlanQualSlot — pre-conflict-time slot allocation

[verified-by-code `execMain.c:2804-2824`]

```c
TupleTableSlot *
EvalPlanQualSlot(EPQState *epqstate, Relation relation, Index rti)
{
    TupleTableSlot **slot = &epqstate->relsubs_slot[rti - 1];

    if (*slot == NULL) {
        MemoryContext oldcontext;
        oldcontext = MemoryContextSwitchTo(epqstate->parentestate->es_query_cxt);
        *slot = table_slot_create(relation, &epqstate->tuple_table);
        MemoryContextSwitchTo(oldcontext);
    }
    return *slot;
}
```

Allocated in `parentestate->es_query_cxt` (so it survives the
EPQ tear-down). The slot is what callers stash the
"conflicting row's latest version" into before calling
EvalPlanQualNext.

Note: this can be called WITHOUT EvalPlanQualBegin — the slot
table exists from Init onward.

## EvalPlanQualEnd — tear-down

[verified-by-code `execMain.c:3208+`]

Called from `ExecEndModifyTable` (and similar end-routines):
1. `ExecEndNode(recheckplanstate)` if exists.
2. `FreeExecutorState(recheckestate)`.
3. Drop the slot table.
4. NULL out dynamic fields; keep the static ones.

After EvalPlanQualEnd, the EPQState is "idle" — could be
re-initialized for a new run via SetPlan + a fresh Begin.

## EvalPlanQualSetPlan — for ModifyTable retargeting

[verified-by-code `execMain.c:2788-2796`]

> We used to need this so that ModifyTable could deal with
> multiple subplans. It could now be refactored out of
> existence.

Historically ModifyTable had one subplan per child of inheritance
hierarchies; today there's one subplan total, so SetPlan is
called once. The comment notes it's vestigial.

## epqParam — the recheck trigger

The `epqParam` int is a PARAM_EXEC slot used as a sentinel: when
the recheck plan re-runs, evaluating any expression that
references this param forces re-fetch of the row via
`ExecScanFetch` instead of using the executor's normal scan.

This is how a Var pointing into the target rel gets redirected
to the EPQ slot at recheck time.

## Common review-time concerns

- **EvalPlanQualInit cheap**, EvalPlanQualBegin expensive — the
  split exists for that reason.
- **`relsubs_slot[]` outlives EPQ** — allocated in
  parentestate->es_query_cxt.
- **`recheckestate` is fresh per Begin** — recursion safe.
- **EPQ only at READ COMMITTED** — REPEATABLE READ / SERIALIZABLE
  abort on conflict instead.
- **Don't directly modify EPQState fields** — use the API
  (Init/Begin/Slot/Next/End).
- **`origslot` is the conflicting tuple's parent-relation slot**
  — fetched from the EState's es_epqTupleSlot.

## Invariants

- **[INV-1]** EvalPlanQualInit allocates `relsubs_slot[rtsize]`
  in parentestate->es_query_cxt; persists until query end.
- **[INV-2]** `recheckestate` / `recheckplanstate` are
  lazy-allocated by EvalPlanQualBegin, lazy-freed by
  EvalPlanQualEnd.
- **[INV-3]** EPQ only fires at READ COMMITTED + a tuple-update
  conflict; higher isolation aborts instead.
- **[INV-4]** EvalPlanQualSlot can be called without
  EvalPlanQualBegin (slot table is from Init).
- **[INV-5]** EvalPlanQualSetPlan is vestigial; one subplan per
  EPQ.

## Useful greps

- The Init/Begin family:
  `grep -n '^EvalPlanQualInit\|^EvalPlanQualBegin\|^EvalPlanQualStart\|^EvalPlanQualEnd' source/src/backend/executor/execMain.c | head -10`
- EPQState fields:
  `grep -RIn 'EPQState\|relsubs_slot\|relsubs_rowmark' source/src/include/executor/executor.h | head -15`
- Lifecycle callers:
  `grep -RIn 'EvalPlanQualInit\|EvalPlanQualEnd\|EvalPlanQualBegin' source/src/backend/executor | head -20`
- epqParam:
  `grep -RIn 'epqParam\|ExecScanFetch' source/src/backend/executor | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2747 | EvalPlanQualInit |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2788 | EvalPlanQualSetPlan |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2804 | EvalPlanQualSlot |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2960 | EvalPlanQualBegin |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 3027 | EvalPlanQualStart |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 3208 | EvalPlanQualEnd |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | — | EPQ entry points |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-hook`](../scenarios/add-new-hook.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/epq-recheck-flow.md` —
  EvalPlanQual + EvalPlanQualNext per-tuple recheck.
- `knowledge/idioms/epq-multi-table.md` —
  rowmarks + multi-relation recheck.
- `knowledge/idioms/heaptuple-update-chain.md` —
  the update chain EPQ follows.
- `knowledge/idioms/tuple-locking-modes.md` —
  why conflicts happen.
- `knowledge/data-structures/estate.md` — parent vs recheck
  EState relationship.
- `knowledge/subsystems/executor.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/executor/execMain.c` — EPQ entry points.
