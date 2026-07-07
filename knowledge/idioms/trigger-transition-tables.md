# Trigger transition tables — REFERENCING OLD/NEW TABLE machinery

`CREATE TRIGGER ... REFERENCING OLD TABLE AS oldrows NEW TABLE AS
newrows` lets a statement-level AFTER trigger see all the rows
modified by the firing statement as a *named relation*. The
implementation is a per-query, per-(table-OID, CmdType)
**tuplestore** plus a small `TransitionCaptureState` struct that
the executor threads through every `ExecAR*` call. The tuplestore
fills as rows are modified; when the AFTER trigger fires after the
query, the PL handler sees the tuplestore as a relation it can
SELECT from.

Anchors:
- `source/src/include/commands/trigger.h:56-84` —
  TransitionCaptureState struct [verified-by-code]
- `source/src/backend/commands/trigger.c:4980` —
  MakeTransitionCaptureState [verified-by-code]
- `source/src/backend/commands/trigger.c:5045-5050` —
  "transition tables can't be deferrable" comment [verified-by-code]
- `source/src/include/commands/trigger.h:185-251` —
  ExecAR* signatures taking TransitionCaptureState [verified-by-code]
- `knowledge/idioms/trigger-constraint-deferral.md` — companion
- `knowledge/idioms/trigger-during-error.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The data flow

```
ExecModifyTable / nodeModifyTable
    │
    │  for each row affected:
    │  ExecARInsertTriggers / ExecARDeleteTriggers / ExecARUpdateTriggers
    │      │
    │      │  uses TransitionCaptureState passed in
    │      ▼
    │  AfterTriggerSaveEvent
    │      │
    │      ├── queues the AFTER trigger event
    │      └── tuplestore_puttupleslot(tcs_*_private->{old,new}_tuplestore, slot)
    │
    │  ... query ends ...
    │
    ▼
AfterTriggerEndQuery
    │
    │  afterTriggerInvokeEvents()
    │      │
    │      ▼
    │  AfterTriggerExecute → trigger function called
    │      │
    │      ▼
    │  PL handler exposes tuplestore as `oldrows` / `newrows`
    │  (e.g., plpgsql treats them as ROW-type variables /
    │  relations the trigger function can SELECT from)
```

## TransitionCaptureState — the per-caller handle

[verified-by-code `trigger.h:56-84`]

```c
typedef struct TransitionCaptureState
{
    bool        tcs_delete_old_table;
    bool        tcs_update_old_table;
    bool        tcs_update_new_table;
    bool        tcs_insert_new_table;

    TupleTableSlot *tcs_original_insert_tuple;

    struct AfterTriggersTableData *tcs_insert_private;
    struct AfterTriggersTableData *tcs_update_private;
    struct AfterTriggersTableData *tcs_delete_private;
} TransitionCaptureState;
```

The four `tcs_*_table` bools are passed-through copies of
TriggerDesc flags; they tell the caller "does ANY trigger on this
relation want this transition table?". The `tcs_*_private`
pointers reference the shared `AfterTriggersTableData` (one per
(relid, cmdtype)) where the tuplestore actually lives.

`tcs_original_insert_tuple` is an optimization for the
partition-routing path — see "the conversion-bypass trick" below.

## MakeTransitionCaptureState

[verified-by-code `trigger.c:4980`]

```c
TransitionCaptureState *
MakeTransitionCaptureState(TriggerDesc *trigdesc, Oid relid, CmdType cmdType);
```

Called once per `ModifyTable` plan node, per relation. Decides
which of the four transition tables are needed based on:
- `cmdType` — INSERT / UPDATE / DELETE / MERGE.
- `trigdesc->trig_{insert,update,delete}_{old,new}_table`
  — true if at least one trigger on the rel wants that direction.

Returns NULL if no transition table is needed (the common case).

Then for each direction needed, it calls
`GetAfterTriggersTableData(relid, cmdtype)` to find-or-create the
**shared** `AfterTriggersTableData` (one per (relid, cmdtype) per
query). The tuplestore is allocated lazily inside that struct in
**CurTransactionContext** (the subxact's), managed by the subxact's
resource owner.

```c
oldcxt = MemoryContextSwitchTo(CurTransactionContext);
saveResourceOwner = CurrentResourceOwner;
CurrentResourceOwner = CurTransactionResourceOwner;

if (need_old_upd && upd_table->old_tuplestore == NULL)
    upd_table->old_tuplestore = tuplestore_begin_heap(false, false, work_mem);
/* ... three more directions ... */

CurrentResourceOwner = saveResourceOwner;
MemoryContextSwitchTo(oldcxt);
```

## The four directions

| Direction | Filled by | Visible in trigger as |
|---|---|---|
| `delete_old` | DELETE | `OLD TABLE` (on DELETE trigger) |
| `update_old` | UPDATE | `OLD TABLE` (on UPDATE trigger) |
| `update_new` | UPDATE | `NEW TABLE` (on UPDATE trigger) |
| `insert_new` | INSERT | `NEW TABLE` (on INSERT trigger) |

MERGE uses all four (it can route any row through INSERT, UPDATE,
or DELETE). INSERT triggers see only new; DELETE only old; UPDATE
sees both.

## Sharing across the same kind of operation

[verified-by-code `trigger.c:4973-4977`]

> Per SQL spec, all operations of the same kind
> (INSERT/UPDATE/DELETE) on the same table during one query
> should share one transition table.

A single UPDATE statement that modifies 1000 rows fires the
statement-level AFTER trigger ONCE, with a tuplestore containing
all 1000 (old, new) pairs. Two UPDATE statements in different
queries get separate tuplestores. The (relid, cmdtype) key in
`AfterTriggersTableData` enforces this.

## MERGE shares with INSERT/UPDATE/DELETE

[verified-by-code `trigger.c:5040-5043`]

> MERGE must use the same AfterTriggersTableData structs as
> INSERT, UPDATE, and DELETE, so that any MERGE'd tuples are
> added to the same tuplestores as tuples from any INSERT, UPDATE,
> or DELETE commands running in the same top-level command (e.g.,
> in a writable CTE).

Writable CTEs can mix MERGE with plain INSERT inside one
top-level command; the spec requires the AFTER trigger to see ALL
the rows, regardless of which sub-statement routed them. The
key-on-(relid, cmdtype) lookup handles this transparently.

## The conversion-bypass trick

When inserting through a partitioned-table root with tuple
routing, the inserter converts the row from root format to leaf
format. If we then store it in a transition tuplestore in root
format, we'd have to convert *back*.

`tcs_original_insert_tuple` solves this: when the inserting code
already has the root-format tuple in hand, it sets this slot
field on the TCS; AfterTriggerSaveEvent stores that one directly,
skipping the back-conversion.

## Why transition tables can't be deferrable

[verified-by-code `trigger.c:5045-5050`]

> the AfterTriggersTableData list, as well as the tuplestores,
> are allocated in the current (sub)transaction's
> CurTransactionContext, and the tuplestores are managed by the
> (sub)transaction's resource owner. This is sufficient lifespan
> because we do not allow triggers using transition tables to be
> deferrable; they will be fired during AfterTriggerEndQuery,
> after which it's okay to delete the data.

If a transition-table trigger were DEFERRED, the trigger would
fire at COMMIT — but by then `AfterTriggerFreeQuery` has already
called `tuplestore_end` on every tuplestore. There would be
nothing to read.

CreateTrigger enforces this at DDL time.

## Cleanup at end-of-query

[verified-by-code `trigger.c:5265-5302`]

`AfterTriggerFreeQuery` walks `qs->tables` and for each
`AfterTriggersTableData`:
1. `tuplestore_end(old_tuplestore)` / `new_tuplestore`.
2. `ExecDropSingleTupleTableSlot(storeslot)` if a slot was
   allocated for reading.
3. Frees the list cells.

All allocated in CurTransactionContext, so even if the cleanup
errors out, the next subxact-end reset reclaims everything.

## Common review-time concerns

- **Statement-level triggers only** — REFERENCING ... is rejected
  on row-level triggers by parse-time check.
- **Transition tables are tuplestores, not relations** — a
  trigger function selects from them, but there's no
  catalog-visible relation.
- **work_mem cap** — tuplestores spill to disk past `work_mem`;
  large UPDATEs can hit disk.
- **Same (relid, cmdtype) shared** — be aware when reading the
  code: one writable CTE can fill from multiple sites.
- **`tcs_original_insert_tuple` is per-CALL** — partition routing
  sets it, then the next call's caller must reset it.
- **No subxact rollback hook** — if a subxact that filled the
  tuplestore aborts, the tuplestore is freed via resource owner
  release; the trigger never fires (its events also get rolled
  back).

## Invariants

- **[INV-1]** TCS is per-caller; the underlying
  AfterTriggersTableData (and tuplestore) is per-(relid, cmdtype)
  per-query.
- **[INV-2]** Tuplestores live in subxact's
  CurTransactionContext; managed by subxact resource owner.
- **[INV-3]** Transition-table triggers cannot be deferrable
  (CreateTrigger rejects).
- **[INV-4]** Transition-table triggers fire at
  AfterTriggerEndQuery, NOT at deferral time.
- **[INV-5]** One MERGE shares tuplestores with INSERT / UPDATE /
  DELETE in the same top-level command.

## Useful greps

- The struct + maker:
  `grep -n 'TransitionCaptureState\|MakeTransitionCaptureState' source/src/include/commands/trigger.h source/src/backend/commands/trigger.c | head -10`
- Call sites in executor:
  `grep -RIn 'MakeTransitionCaptureState\|transition_capture' source/src/backend/executor/nodeModifyTable.c | head -10`
- Tuplestore allocation:
  `grep -n 'tuplestore_begin_heap.*work_mem' source/src/backend/commands/trigger.c | head -5`
- Free path:
  `grep -n 'AfterTriggerFreeQuery' source/src/backend/commands/trigger.c | head -5`
- ExecAR* signatures:
  `grep -n 'TransitionCaptureState' source/src/include/commands/trigger.h | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 4980 | MakeTransitionCaptureState |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5045 | "transition tables can't be deferrable" comment |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | — | full module |
| [`src/backend/executor/nodeModifyTable.c`](../files/src/backend/executor/nodeModifyTable.c.md) | — | ExecAR call sites |
| [`src/include/commands/trigger.h`](../files/src/include/commands/trigger.h.md) | 56 | TransitionCaptureState struct |
| [`src/include/commands/trigger.h`](../files/src/include/commands/trigger.h.md) | 185 | ExecAR signatures taking TransitionCaptureState |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/trigger-constraint-deferral.md` — why
  transition triggers can't be deferred.
- `knowledge/idioms/trigger-during-error.md` — subxact-abort path
  releases tuplestores via resource owner.
- `knowledge/idioms/partition-tuple-routing.md` —
  `tcs_original_insert_tuple` bypass.
- `knowledge/data-structures/tupletableslot.md` — slot returned
  for transition-table reads.
- `knowledge/data-structures/estate.md` — query-scoped trigger
  state.
- `knowledge/subsystems/tuplestore.md` — the backing store.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/commands/trigger.c` — full module.
- `source/src/backend/executor/nodeModifyTable.c` — ExecAR* call
  sites.
