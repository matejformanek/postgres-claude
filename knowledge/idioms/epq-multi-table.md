# EPQ multi-table — rowmarks, joins, and non-target rels

When the original query joins multiple tables (e.g.,
`UPDATE a SET x = b.x FROM b WHERE a.id = b.id AND a.cond`),
EPQ recheck has to handle ALL of them: the target rel `a` gets
the conflicting tuple injected, but `b` (and any other joined
rel) must be **re-fetched** by CTID — using rowmarks the planner
attached to the parent ModifyTable. Each non-target rel
referenced in the query carries an `ExecRowMark`/`ExecAuxRowMark`
pair that tells EPQ how to find that rel's current row given the
parent's `origslot`. The recheck plan is structurally identical
to the original; only the leaf scan behavior changes.

Anchors:
- `source/src/backend/executor/execMain.c:2833` —
  EvalPlanQualFetchRowMark [verified-by-code]
- `source/src/backend/executor/execMain.c:3155-3166` —
  relsubs_rowmark array build [verified-by-code]
- `source/src/backend/executor/execMain.c:3168-3184` —
  relsubs_done / blocked per-rel init [verified-by-code]
- `source/src/backend/executor/execMain.c:2845-2867` —
  child-rel partition discriminator [verified-by-code]
- `source/src/backend/executor/execMain.c:2870-2912` —
  ROW_MARK_REFERENCE + FDW RefetchForeignRow path
  [verified-by-code]
- `knowledge/idioms/epq-state-init.md` — companion
- `knowledge/idioms/epq-recheck-flow.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The two slot arrays

```c
TupleTableSlot **relsubs_slot;        /* per-rti: the test slot */
ExecAuxRowMark **relsubs_rowmark;     /* per-rti: how to re-fetch */
bool            *relsubs_done;        /* per-rti: tuple consumed */
bool            *relsubs_blocked;     /* per-rti: don't fetch from here */
```

For a given rti:
- `relsubs_blocked[rti] == true` means "this rel doesn't produce
  tuples during EPQ" — used for result relations (the target
  rel during a DIFFERENT target's recheck) and for rels that
  have already been fully recheck-fetched.
- `relsubs_done[rti] == true` means "we've already produced the
  EPQ tuple for this rel this run; subsequent calls return
  NULL".
- `relsubs_rowmark[rti] != NULL` means "this rel must be
  re-fetched by CTID; here's the rowmark info".

The ExecAuxRowMark / ExecRowMark pair is set up during plan
creation when the planner inserted a `LockRows` node above the
ModifyTable (or for FOR UPDATE/FOR SHARE rows).

## ExecRowMark — what the planner provides

(struct in `execnodes.h`)

```c
typedef struct ExecRowMark
{
    Relation       relation;       /* opened rel (or NULL for foreign) */
    Oid            relid;
    Index          rti;             /* RT index in this query */
    Index          prti;            /* parent RT index (for partitions) */
    Index          rowmarkId;
    RowMarkType    markType;        /* ROW_MARK_EXCLUSIVE / SHARE / REFERENCE / ... */
    LockClauseStrength strength;
    LockWaitPolicy waitPolicy;
    bool           ermActive;
    ItemPointerData curCtid;
    void          *ermExtra;        /* AM-specific */
} ExecRowMark;
```

Variants:
- **`ROW_MARK_EXCLUSIVE` / `ROW_MARK_SHARE`** — `SELECT FOR
  UPDATE / FOR SHARE` style locking. Read-and-lock during normal
  scan.
- **`ROW_MARK_REFERENCE`** — non-locked rel, but plain SELECT
  needs CTID for recheck. Junk attribute carries the CTID.
- **`ROW_MARK_COPY`** — fully copy the row's contents into a junk
  attribute (for foreign or non-CTID-having relations).

The `ExecAuxRowMark` adds the junk attribute numbers used to
extract the row identifier at recheck.

## EvalPlanQualFetchRowMark — re-fetch a non-target row

[verified-by-code `execMain.c:2833-2941`]

```c
bool
EvalPlanQualFetchRowMark(EPQState *epqstate, Index rti, TupleTableSlot *slot)
{
    ExecAuxRowMark *earm = epqstate->relsubs_rowmark[rti - 1];
    ExecRowMark *erm = earm->rowmark;

    if (RowMarkRequiresRowShareLock(erm->markType))
        elog(ERROR, "EvalPlanQual doesn't support locking rowmarks");

    /* Partition discriminator */
    if (erm->rti != erm->prti) {
        Datum tableoid = ExecGetJunkAttribute(epqstate->origslot,
                                              earm->toidAttNo, &isNull);
        if (isNull) return false;
        if (DatumGetObjectId(tableoid) != erm->relid)
            return false;  /* this child wasn't the producer */
    }

    if (erm->markType == ROW_MARK_REFERENCE) {
        /* CTID-based re-fetch */
        datum = ExecGetJunkAttribute(epqstate->origslot, earm->ctidAttNo, &isNull);
        if (isNull) return false;

        if (erm->relation->rd_rel->relkind == RELKIND_FOREIGN_TABLE) {
            fdwroutine = GetFdwRoutineForRelation(erm->relation, false);
            if (!fdwroutine->RefetchForeignRow)
                ereport(ERROR, "cannot lock rows in foreign table");
            fdwroutine->RefetchForeignRow(epqstate->recheckestate, erm, datum, slot, ...);
        } else {
            /* heap_fetch by CTID */
            table_tuple_fetch_row_version(erm->relation, ...);
        }
        return true;
    }
    /* ROW_MARK_COPY — return the copied row directly */
    ...
}
```

Three paths:
1. **`ROW_MARK_REFERENCE` + heap** → fetch by CTID via table-AM.
2. **`ROW_MARK_REFERENCE` + foreign table** → FDW's
   `RefetchForeignRow`.
3. **`ROW_MARK_COPY`** → return the COPY-stashed row from junk.

## Partition-tree discriminator

[verified-by-code `execMain.c:2848-2868`]

When the parent ModifyTable scans an inheritance hierarchy, each
child has its own rti but they share a `prti` (parent RTI).
The `toidAttNo` junk attribute carries the OID of the partition
that produced the row.

At recheck:
```c
if (DatumGetObjectId(tableoid) != erm->relid)
    return false;  /* different child than what produced the row */
```

This is how EPQ knows which leaf of a partitioned table is
being re-fetched. Only the matching child returns a tuple; the
others say "I didn't produce this row".

## Why locking rowmarks aren't supported

```c
if (RowMarkRequiresRowShareLock(erm->markType))
    elog(ERROR, "EvalPlanQual doesn't support locking rowmarks");
```

`SELECT FOR UPDATE` inside an UPDATE's WHERE subquery is unusual
but possible. EPQ refuses to handle it because:
- The lock was acquired during the original scan.
- Re-fetching would need a new lock — possibly waiting again.
- The semantics get murky (what does it mean to "re-acquire
  FOR UPDATE during a row recheck"?).

PG punts with ERROR; the user must rewrite the query.

## Building the relsubs_rowmark array

[verified-by-code `execMain.c:3155-3166`]

```c
epqstate->relsubs_rowmark = palloc0_array(ExecAuxRowMark *, rtsize);
foreach(l, epqstate->arowMarks)
{
    ExecAuxRowMark *earm = (ExecAuxRowMark *) lfirst(l);
    epqstate->relsubs_rowmark[earm->rowmark->rti - 1] = earm;
}
```

The `arowMarks` list comes from the planner's LockRows / SELECT
FOR UPDATE processing. Each entry maps `rti` to junk-attribute
extraction. The array indexed by `rti - 1` gives O(1) lookup.

## Per-rel init at EvalPlanQualStart

[verified-by-code `execMain.c:3168-3184`]

```c
epqstate->relsubs_done = palloc_array(bool, rtsize);
epqstate->relsubs_blocked = palloc0_array(bool, rtsize);

/* Mark result relations blocked */
foreach(l, epqstate->resultRelations) {
    int rtindex = lfirst_int(l);
    epqstate->relsubs_blocked[rtindex - 1] = true;
}

memcpy(epqstate->relsubs_done, epqstate->relsubs_blocked,
       rtsize * sizeof(bool));
```

Initial state:
- Result rels (the UPDATE/DELETE targets) → blocked.
- Other rels (joined tables) → unblocked but done=true initially.

When EvalPlanQual is called for a target rel:
- Sets that rel's blocked=false, done=false (it has a tuple now).
- Other unblocked rels still have done=true initially; scan
  nodes will call `EvalPlanQualFetchRowMark` to pull the real
  row.

## What if a non-target rel disappears

Two cases:
- The row's been deleted (CTID no longer valid) →
  `EvalPlanQualFetchRowMark` returns false → scan returns NULL →
  the JOIN drops the row → WHERE no longer matches → EPQ result
  is NULL → original UPDATE skips this row.
- The row's been updated (not deleted) → CTID still finds A row
  (may be the OLD version if HOT). The fetch returns that
  version. PG's MVCC ensures we see SOME committed version.

## Result rels in multi-target ModifyTable

For partitioned-table UPDATE / MERGE with multiple potentially-
targeted partitions:
- All partitions are in `resultRelations`.
- All are initially `blocked`.
- When EvalPlanQual is called for partition X, X's blocked=false;
  others stay blocked.

Each conflict is scoped to one partition; no cross-partition
EPQ.

## Sharing subplans with the parent

[verified-by-code `execMain.c:3144-3153`]

```c
foreach(l, parentestate->es_plannedstmt->subplans)
{
    Plan *subplan = (Plan *) lfirst(l);
    PlanState *subplanstate = ExecInitNode(subplan, rcestate, 0);
    rcestate->es_subplanstates = lappend(rcestate->es_subplanstates, subplanstate);
}
```

Every subplan in the PlannedStmt is initialized in the recheck
EState. They may or may not be used by the recheck plan tree,
but ExecInitSubPlan expects them all available. Cheap enough
because subplans aren't executed until referenced.

## Common review-time concerns

- **rowmark coverage** must include every non-target rel
  referenced — planner generates them via LockRows / similar.
- **Partition discriminator junk** (`tableoid`) is what tells
  EPQ which child of an inheritance produced the row.
- **FDW row marks require RefetchForeignRow** — not all FDWs
  implement; check `GetForeignRowMarkType`.
- **Locking rowmarks not supported** — `SELECT FOR UPDATE`
  inside an EPQ-relevant subquery raises ERROR.
- **All subplans pre-inited** — even unused ones.
- **PartitionPruneInfo shared** — recheck must initialize same
  Append subplans as parent.

## Invariants

- **[INV-1]** `relsubs_rowmark[rti] != NULL` for every non-
  target rel that needs CTID re-fetch.
- **[INV-2]** Result rels start `relsubs_blocked = true`;
  non-target rels start `relsubs_done = true`.
- **[INV-3]** EvalPlanQual for target X sets X's blocked=false,
  done=false.
- **[INV-4]** ROW_MARK_REFERENCE re-fetches by CTID;
  ROW_MARK_COPY uses junk attribute directly.
- **[INV-5]** Locking rowmarks raise ERROR; EPQ doesn't acquire
  row locks.

## Useful greps

- The fetch + rowmark machinery:
  `grep -n 'EvalPlanQualFetchRowMark\|relsubs_rowmark' source/src/backend/executor/execMain.c | head -10`
- RowMarkType enum:
  `grep -n 'ROW_MARK_EXCLUSIVE\|ROW_MARK_SHARE\|ROW_MARK_REFERENCE\|ROW_MARK_COPY' source/src/include/nodes/plannodes.h | head -10`
- LockRows planner emission:
  `grep -RIn 'LockRows\|create_lockrows_plan' source/src/backend/optimizer | head -10`
- FDW row mark callbacks:
  `grep -RIn 'GetForeignRowMarkType\|RefetchForeignRow' source/src/include/foreign source/src/backend/executor | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2833 | EvalPlanQualFetchRowMark |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2845 | child-rel partition discriminator |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 2870 | ROW_MARK_REFERENCE + FDW RefetchForeignRow path |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 3155 | relsubs_rowmark array build |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | 3168 | relsubs_done / blocked per-rel init |
| [`src/backend/executor/execMain.c`](../files/src/backend/executor/execMain.c.md) | — | full EPQ |
| [`src/backend/optimizer/plan/createplan.c`](../files/src/backend/optimizer/plan/createplan.c.md) | — | LockRows generation |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-hook`](../scenarios/add-new-hook.md)
- [`add-new-plan-node`](../scenarios/add-new-plan-node.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/epq-state-init.md` — EPQState lifecycle.
- `knowledge/idioms/epq-recheck-flow.md` — per-conflict
  re-evaluation entry.
- `knowledge/idioms/heaptuple-update-chain.md` — chain
  followed by CTID re-fetch.
- `knowledge/idioms/fdw-routine-callbacks.md` —
  RefetchForeignRow.
- `knowledge/data-structures/plannerinfo.md` — LockRows /
  rowmarks at plan time.
- `knowledge/data-structures/estate.md` — recheckestate
  setup.
- `knowledge/subsystems/executor.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/executor/execMain.c` — full EPQ.
- `source/src/backend/optimizer/plan/createplan.c` — LockRows
  generation.
