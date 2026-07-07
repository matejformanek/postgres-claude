# Trigger constraint deferral — SET CONSTRAINTS and the AFTER queue

A **deferrable constraint** is one whose enforcement trigger can run
later than the SQL statement that "violated" it — either at the end
of the transaction (DEFERRED) or at an explicit `SET CONSTRAINTS ...
IMMEDIATE`. Internally the deferral is implemented entirely on top
of the AFTER-trigger queue: a deferred trigger is just an AFTER
trigger whose event sits in `afterTriggers.events` past the end of
the query, and gets fired by `AfterTriggerFireDeferred` right before
commit. The per-transaction `SetConstraintState` overrides the
default-deferred / default-immediate setting on a per-trigger basis.

Anchors:
- `source/src/backend/commands/trigger.c:3608-3636` —
  SetConstraintTriggerData + SetConstraintStateData structs
  [verified-by-code]
- `source/src/backend/commands/trigger.c:5796` —
  SetConstraintStateAddItem [verified-by-code]
- `source/src/backend/commands/trigger.c:5826` —
  AfterTriggerSetState (`SET CONSTRAINTS` entry point)
  [verified-by-code]
- `source/src/backend/commands/trigger.c:5329` —
  AfterTriggerFireDeferred (commit-time drain) [verified-by-code]
- `source/src/include/commands/trigger.h:109-110` —
  AFTER_TRIGGER_DEFERRABLE / INITDEFERRED flags [verified-by-code]
- `knowledge/idioms/trigger-transition-tables.md` — companion
- `knowledge/idioms/trigger-during-error.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The four deferral states

A trigger can be in one of four states with respect to deferral:

| pg_trigger.tgdeferrable | pg_trigger.tginitdeferred | Behavior |
|---|---|---|
| false | — | NOT DEFERRABLE — fires immediately, can't be deferred |
| true | false | DEFERRABLE INITIALLY IMMEDIATE — fires at end of stmt by default; SET CONSTRAINTS can defer |
| true | true | DEFERRABLE INITIALLY DEFERRED — fires at commit by default; SET CONSTRAINTS IMMEDIATE can advance |

The flags ride in the `TriggerEvent` bitmask
[verified-by-code `trigger.h:109-110`]:

```c
#define AFTER_TRIGGER_DEFERRABLE    0x00000020
#define AFTER_TRIGGER_INITDEFERRED  0x00000040
```

## SetConstraintStateData — the per-transaction override

[verified-by-code `trigger.c:3627-3634`]

```c
typedef struct SetConstraintStateData
{
    bool        all_isset;       /* SET CONSTRAINTS ALL was seen */
    bool        all_isdeferred;  /* DEFERRED or IMMEDIATE */
    int         numstates;
    int         numalloc;
    SetConstraintTriggerData trigstates[FLEXIBLE_ARRAY_MEMBER];
} SetConstraintStateData;

typedef struct SetConstraintTriggerData
{
    Oid     sct_tgoid;
    bool    sct_tgisdeferred;
} SetConstraintTriggerData;
```

Lives in `afterTriggers.state` (per-transaction). `NULL` means "no
SET CONSTRAINTS run this xact — use each trigger's own
`tginitdeferred` flag". After `SET CONSTRAINTS` runs, the state
either:
- Has `all_isset` true: the per-xact default for every trigger is
  `all_isdeferred`.
- Has explicit `trigstates[]` entries: per-trigger overrides
  layered on top of the ALL default.

## AfterTriggerSetState — implementing SET CONSTRAINTS

[verified-by-code `trigger.c:5826`]

The `SET CONSTRAINTS` utility command runs through this single
entry point. Two forms:

1. **`SET CONSTRAINTS ALL DEFERRED | IMMEDIATE`** —
   `stmt->constraints == NIL`. Discards prior per-trigger entries,
   sets `all_isset = true` and `all_isdeferred` per the keyword.
2. **`SET CONSTRAINTS name [, ...] DEFERRED | IMMEDIATE`** —
   resolves each name to constraint OIDs, walks
   `pg_constraint` for inheritance, finds the underlying
   `pg_trigger` rows, and appends one
   `SetConstraintStateAddItem` call per trigger.

The function refuses to change a NOT-DEFERRABLE trigger's state.

## SetConstraintStateAddItem

[verified-by-code `trigger.c:5795-5817`]

Each call appends one (tgoid, tgisdeferred) pair to the trigstates
array, growing it (`repalloc`) by doubling. The whole thing lives
in TopTransactionContext (so it survives subxacts; see
`trigger-during-error`).

```c
static SetConstraintState
SetConstraintStateAddItem(SetConstraintState state,
                          Oid tgoid, bool tgisdeferred)
{
    if (state->numstates >= state->numalloc) { /* repalloc */ }
    state->trigstates[state->numstates].sct_tgoid = tgoid;
    state->trigstates[state->numstates].sct_tgisdeferred = tgisdeferred;
    state->numstates++;
    return state;
}
```

## How a trigger event becomes "deferred"

When `AfterTriggerSaveEvent` queues an event for an AFTER trigger:
1. It looks at the trigger's `tgdeferrable` / `tginitdeferred`.
2. If the trigger is deferrable, it consults `afterTriggers.state`
   for an override (per-trigger first, then ALL).
3. The resolved "this event should be deferred" decision is
   recorded as an `AFTER_TRIGGER_DEFERRABLE` / `INITDEFERRED` flag
   on the event.

At end-of-query, `AfterTriggerEndQuery` walks the query's local
event list:
- **Immediate** events fire now (this query's statement-end).
- **Deferred** events move to the **transaction-global**
  `afterTriggers.events` list, where they survive until commit.

## AfterTriggerFireDeferred — commit-time drain

[verified-by-code `trigger.c:5329`]

```c
void
AfterTriggerFireDeferred(void)
{
    /* Must not be inside a query */
    Assert(afterTriggers.query_depth == -1);

    events = &afterTriggers.events;
    if (events->head != NULL) {
        PushActiveSnapshot(GetTransactionSnapshot());
        snap_pushed = true;
    }

    afterTriggers.firing_depth++;
    while (afterTriggerMarkEvents(events, NULL, false)) {
        CommandId firing_id = afterTriggers.firing_counter++;
        if (afterTriggerInvokeEvents(events, firing_id, NULL, true))
            break;  /* all fired */
    }

    FireAfterTriggerBatchCallbacks(afterTriggers.batch_callbacks);
    afterTriggers.firing_depth--;
    if (snap_pushed) PopActiveSnapshot();
}
```

Key points:
- Called from `CommitTransaction` BEFORE the commit record is
  written. If a deferred trigger throws ERROR, the transaction
  aborts.
- A new snapshot is pushed for visibility (the original query's
  snapshot may be stale).
- The loop re-runs because a fired trigger can queue NEW deferred
  events at the same level. Each pass gets a fresh
  `firing_counter`.
- xact.c may call this **multiple times** if other pre-commit
  modules queue more triggers between iterations (see header
  comment).

## Foreign keys are the canonical deferrable

PostgreSQL's RI (referential integrity) triggers are deferrable
constraints implemented as system triggers. A
`PRIMARY KEY` / `FOREIGN KEY` declared `DEFERRABLE INITIALLY
DEFERRED` lets you do:

```sql
BEGIN;
INSERT INTO child VALUES (...);   -- FK check deferred
INSERT INTO parent VALUES (...);  -- now parent exists
COMMIT;                            -- AfterTriggerFireDeferred runs FK check, passes
```

Without DEFERRED, the first INSERT would fail at the FK check
firing right after the statement.

## What NOT to defer

[verified-by-code `trigger.c:5045-5050`]

> we do not allow triggers using transition tables to be
> deferrable; they will be fired during AfterTriggerEndQuery,
> after which it's okay to delete the data.

Transition-table tuplestores live in the **subxact's
CurTransactionContext** and are released when the query ends. If
deferral were allowed, the tuplestore would be gone when the
trigger eventually fires. See `trigger-transition-tables`.

Foreign-table triggers are also forbidden from being deferrable
(`trigger.c:3661-3666`): the per-event tuplestore is per-query,
and ordering would break.

## Visibility quirk

Deferred triggers see the post-statement state, NOT the
state-at-time-of-queue. If you UPDATE then DELETE the same row in
a transaction with a DEFERRED FK check, the FK check at commit
fires against the deleted row — which is the correct semantics
but surprises people who think "deferred = use the snapshot from
when I queued you".

## Common review-time concerns

- **DEFERRABLE only matters for AFTER triggers** — BEFORE
  triggers fire immediately, no deferral path.
- **Foreign-table triggers can't be deferrable** —
  `CreateTrigger` rejects them.
- **Transition-table triggers can't be deferrable** —
  tuplestores would be freed before firing.
- **`SET CONSTRAINTS ALL IMMEDIATE` fires queued deferred
  triggers immediately** — including any that would have ERRORed
  at commit. Useful for catching FK violations early.
- **Subxact rollback restores `afterTriggers.state`** — see
  `trigger-during-error` for the trans_stack snapshot machinery.
- **AfterTriggerFireDeferred can be called multiple times** —
  pre-commit modules may queue more events; loop until empty.

## Invariants

- **[INV-1]** Only `tgdeferrable = true` triggers can be deferred;
  `CreateTrigger` rejects `INITDEFERRED` without `DEFERRABLE`.
- **[INV-2]** `AfterTriggerFireDeferred` runs at `query_depth ==
  -1` (between queries) — never mid-statement.
- **[INV-3]** Deferred events live in `afterTriggers.events`
  (xact-global), not in any query-level list.
- **[INV-4]** The per-xact `SetConstraintState` overrides per-
  trigger defaults but never re-enables deferral on a NOT
  DEFERRABLE trigger.
- **[INV-5]** Subxact abort restores the prior `SetConstraintState`
  from `trans_stack[my_level].state` (see
  AfterTriggerEndSubXact).

## Useful greps

- The state struct + add path:
  `grep -n 'SetConstraintStateData\|SetConstraintStateAddItem' source/src/backend/commands/trigger.c | head -10`
- SET CONSTRAINTS entry:
  `grep -n 'AfterTriggerSetState\|ConstraintsSetStmt' source/src/backend/commands/trigger.c | head -10`
- Commit-time drain:
  `grep -n 'AfterTriggerFireDeferred' source/src/backend/access/transam/xact.c | head -5`
- Flag check at event save:
  `grep -n 'AFTER_TRIGGER_DEFERRABLE\|AFTER_TRIGGER_INITDEFERRED' source/src/backend/commands/trigger.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 3608 | SetConstraintTriggerData + SetConstraintStateData structs |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5329 | AfterTriggerFireDeferred (commit-time drain) |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5796 | SetConstraintStateAddItem |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5826 | AfterTriggerSetState (SET CONSTRAINTS entry point) |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | — | whole AFTER trigger machinery |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | — | RI as canonical deferrable-trigger user |
| [`src/include/commands/trigger.h`](../files/src/include/commands/trigger.h.md) | 109 | AFTER_TRIGGER_DEFERRABLE / INITDEFERRED flags |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/trigger-transition-tables.md` — why
  transition-table triggers can't be deferred.
- `knowledge/idioms/trigger-during-error.md` — subxact rollback
  of deferred events + SetConstraintState.
- `knowledge/idioms/commit-sequence.md` — where
  AfterTriggerFireDeferred fits in the pre-commit stages.
- `knowledge/idioms/abort-sequence.md` — AfterTriggerEndXact on
  abort.
- `knowledge/subsystems/transaction-management.md` —
  TopTransactionContext lifetime.
- `knowledge/data-structures/estate.md` — query-level AFTER
  trigger context.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/commands/trigger.c` — the whole AFTER
  trigger machinery.
- `source/src/backend/utils/adt/ri_triggers.c` — RI as
  canonical deferrable-trigger user.
