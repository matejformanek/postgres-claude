# Trigger state during error — rollback of the AFTER queue

When a (sub)transaction aborts, every AFTER-trigger event that
was queued at or below that level must be discarded — and any
DONE / IN-PROGRESS marks set by triggers that *did* fire in the
aborted scope must be un-set, so that re-firing is possible if
control unwinds and the same events get queued again. The
machinery is built around a per-subxact **trans_stack snapshot**
(events list tail + SetConstraintState + query_depth +
firing_counter) plus a `for_each_event_chunk` walk that
selectively clears the AFTER_TRIGGER_DONE / IN_PROGRESS flags.
The same path covers full-transaction abort via
`AfterTriggerEndXact`.

Anchors:
- `source/src/backend/commands/trigger.c:5392` —
  AfterTriggerEndXact [verified-by-code]
- `source/src/backend/commands/trigger.c:5446` —
  AfterTriggerBeginSubXact (snapshot push) [verified-by-code]
- `source/src/backend/commands/trigger.c:5494` —
  AfterTriggerEndSubXact (commit & abort branches) [verified-by-code]
- `source/src/backend/commands/trigger.c:5546-5582` —
  abort-side event-list restore + flag clear [verified-by-code]
- `source/src/backend/commands/trigger.c:3684-3685` —
  AFTER_TRIGGER_DONE / IN_PROGRESS flag bits [verified-by-code]
- `knowledge/idioms/trigger-constraint-deferral.md` — companion
- `knowledge/idioms/trigger-transition-tables.md` — companion
- `.claude/skills/error-handling/SKILL.md` — companion

## Three failure points to handle

1. **Sub-transaction abort** — `ROLLBACK TO SAVEPOINT`. Discard
   events queued by this subxact and any nested subxacts; restore
   prior `SetConstraintState`; reset `query_depth` if subxact ran
   nested queries.
2. **Full transaction abort** — `ROLLBACK` or any unhandled
   ERROR at top level. Drop the event_cxt memory context (frees
   the entire event list at once); reset everything to "no
   transaction in progress".
3. **Repeated abort calls** — `AfterTriggerEndXact` may be
   called more than once if errors stack during xact cleanup
   (`trigger.c:5386-5388`). Idempotent.

## The trans_stack snapshot

[verified-by-code `trigger.c:5446-5486`]

Each subxact entry stores:

```c
typedef struct AfterTriggersTransData
{
    SetConstraintState  state;          /* prior xact's constraint state */
    AfterTriggerEventList events;       /* end-of-events pointer (NOT a copy of events) */
    int                 query_depth;    /* query_depth at subxact start */
    CommandId           firing_counter; /* firing_id boundary */
} AfterTriggersTransData;
```

`AfterTriggerBeginSubXact` pushes:

```c
afterTriggers.trans_stack[my_level].state = NULL;
afterTriggers.trans_stack[my_level].events = afterTriggers.events;
afterTriggers.trans_stack[my_level].query_depth = afterTriggers.query_depth;
afterTriggers.trans_stack[my_level].firing_counter = afterTriggers.firing_counter;
```

The `events` field stores the **list pointers** as they were at
subxact start. On abort, restoring those pointers truncates the
list — discarding everything queued by the subxact in one O(1)
move.

`.state` is initially NULL; it's filled lazily by the first
`SET CONSTRAINTS` inside the subxact (see
`trigger-constraint-deferral`), which does:

```c
if (my_level > 1 &&
    afterTriggers.trans_stack[my_level].state == NULL)
{
    afterTriggers.trans_stack[my_level].state =
        SetConstraintStateCopy(afterTriggers.state);
}
```

So we only pay the copy cost when SET CONSTRAINTS actually
modifies the state inside the subxact.

## AfterTriggerEndSubXact — the abort branch

[verified-by-code `trigger.c:5494-5587`]

```c
void
AfterTriggerEndSubXact(bool isCommit)
{
    if (isCommit) {
        /* discard saved snapshot — nothing to restore */
        state = afterTriggers.trans_stack[my_level].state;
        if (state != NULL) pfree(state);
        /* events queued by this subxact propagate up */
        return;
    }

    /* abort: */

    /* 1. Free query-level storage for queries the subxact opened. */
    while (afterTriggers.query_depth >
           afterTriggers.trans_stack[my_level].query_depth) {
        if (afterTriggers.query_depth < afterTriggers.maxquerydepth)
            AfterTriggerFreeQuery(&afterTriggers.query_stack[afterTriggers.query_depth]);
        afterTriggers.query_depth--;
    }

    /* 2. Truncate global deferred-event list to pre-subxact length. */
    afterTriggerRestoreEventList(&afterTriggers.events,
                                 &afterTriggers.trans_stack[my_level].events);

    /* 3. Restore SetConstraintState if subxact saved one. */
    state = afterTriggers.trans_stack[my_level].state;
    if (state != NULL) {
        pfree(afterTriggers.state);
        afterTriggers.state = state;
    }

    /* 4. Clear DONE/IN_PROGRESS marks for events fired by this subxact. */
    subxact_firing_id = afterTriggers.trans_stack[my_level].firing_counter;
    for_each_event_chunk(event, chunk, afterTriggers.events) {
        AfterTriggerShared evtshared = GetTriggerSharedData(event);
        if (event->ate_flags &
            (AFTER_TRIGGER_DONE | AFTER_TRIGGER_IN_PROGRESS)) {
            if (evtshared->ats_firing_id >= subxact_firing_id)
                event->ate_flags &=
                    ~(AFTER_TRIGGER_DONE | AFTER_TRIGGER_IN_PROGRESS);
        }
    }
}
```

## Why clear the firing flags

A subxact may have FIRED some deferred events (e.g., via a
`SET CONSTRAINTS ... IMMEDIATE` inside the subxact) before
aborting. Those events are marked AFTER_TRIGGER_DONE in the
shared event list. If we leave them DONE after abort, they won't
re-fire at commit — but the side effects they had are rolled
back (rows they wrote, etc.). Conceptually they didn't happen.

The fix: clear DONE / IN_PROGRESS for any event whose
`ats_firing_id >= subxact_firing_id`. Those are exactly the
events fired *during* the aborted subxact. They go back into the
queue to re-fire at the next opportunity.

## firing_counter as the boundary marker

`afterTriggers.firing_counter` is a monotonically increasing
CommandId stamped on each event when it fires (`ats_firing_id`).
The subxact snapshot stores `firing_counter` at subxact start.
Any event with `ats_firing_id >= snapshot` was fired by this
subxact or a child.

This is also why the firing_counter is "mustn't be 0"
(`trigger.c:5111`) — the zero value means "never fired".

## Event-list restoration

[verified-by-code via `afterTriggerRestoreEventList`]

The event list is a linked list of chunks. The trans_stack
stores the (head, tail, tailfree) triple at subxact start;
`afterTriggerRestoreEventList` truncates back to it:
- Frees chunks past the saved tail.
- Resets list pointers.

This is O(chunks-added-by-subxact), not O(events) — the chunks
themselves are the unit of allocation.

## AfterTriggerEndXact — the whole-xact end

[verified-by-code `trigger.c:5392-5438`]

```c
void
AfterTriggerEndXact(bool isCommit)
{
    if (afterTriggers.event_cxt) {
        MemoryContextDelete(afterTriggers.event_cxt);
        afterTriggers.event_cxt = NULL;
        afterTriggers.events.head = NULL;
        afterTriggers.events.tail = NULL;
        afterTriggers.events.tailfree = NULL;
    }

    afterTriggers.trans_stack = NULL;
    afterTriggers.maxtransdepth = 0;
    afterTriggers.query_stack = NULL;
    afterTriggers.maxquerydepth = 0;
    afterTriggers.state = NULL;
    afterTriggers.query_depth = -1;
    afterTriggers.firing_depth = 0;
    /* ... */
}
```

Called from `AbortTransaction` (and `CommitTransaction` after
deferred drain). Drops the entire event_cxt memory context — one
free for the whole event list. Sub-stack fields (trans_stack,
query_stack) are in TopTransactionContext and will be freed by
its eventual reset.

Notable on the abort path: this is called BEFORE
TopTransactionContext is reset, so `afterTriggers.state` etc. are
nulled rather than freed individually.

## Interaction with PG_TRY / PG_CATCH

A trigger function that uses PG_TRY to swallow an ERROR can ONLY
do so safely via a subxact (`BeginInternalSubTransaction` /
`ReleaseCurrentSubTransaction` / `RollbackAndReleaseCurrentSubTransaction`),
because subxact cleanup runs AfterTriggerEndSubXact. A bare
PG_TRY / PG_CATCH that doesn't roll back the subxact leaves the
trigger state inconsistent.

The pattern in PL/pgSQL's `BEGIN ... EXCEPTION WHEN ... END` is
exactly this — it wraps the BEGIN block in an internal subxact.

## Common review-time concerns

- **trans_stack growth doubles** — initial 8 entries, doubles
  via repalloc. Bounded by max subxact nesting; not a hot path.
- **Per-subxact SetConstraintState copy is lazy** — only paid if
  SET CONSTRAINTS runs inside the subxact.
- **Repeated AfterTriggerEndXact is idempotent** — guard on
  `event_cxt != NULL`.
- **Don't queue from within abort cleanup** — by the time
  AfterTriggerEndXact runs, the event_cxt may already be gone.
- **PG_TRY without subxact mishandles AFTER triggers** — use
  internal-subxact pattern.
- **Errors during AfterTriggerFireDeferred abort the xact** —
  the snapshot pushed there is popped by xact cleanup.

## Invariants

- **[INV-1]** Subxact abort restores
  `afterTriggers.events.{head,tail,tailfree}` to the value saved
  at subxact start.
- **[INV-2]** Subxact abort clears DONE / IN_PROGRESS for events
  with `ats_firing_id >= snapshot.firing_counter`.
- **[INV-3]** trans_stack[level].state is NULL unless SET
  CONSTRAINTS modified state inside that subxact.
- **[INV-4]** AfterTriggerEndXact is idempotent across repeated
  abort invocations.
- **[INV-5]** Trigger queue lives in event_cxt
  (sub-context of TopTransactionContext) — single
  MemoryContextDelete reclaims it all on xact end.

## Useful greps

- The abort branch:
  `grep -n 'AfterTriggerEndSubXact\|afterTriggerRestoreEventList' source/src/backend/commands/trigger.c | head -10`
- xact callers:
  `grep -RIn 'AfterTriggerEndXact\|AfterTriggerEndSubXact\|AfterTriggerBeginSubXact' source/src/backend/access/transam/xact.c | head -10`
- Firing-counter / firing-id:
  `grep -n 'firing_counter\|ats_firing_id\|AFTER_TRIGGER_DONE' source/src/backend/commands/trigger.c | head -15`
- PL/pgSQL subxact pattern:
  `grep -n 'BeginInternalSubTransaction\|RollbackAndReleaseCurrentSubTransaction' source/src/pl/plpgsql/src/pl_exec.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | — | AbortTransaction / AbortSubTransaction call sites |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 3684 | AFTER_TRIGGER_DONE / IN_PROGRESS flag bits |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5392 | AfterTriggerEndXact |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5446 | AfterTriggerBeginSubXact (snapshot push) |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5494 | AfterTriggerEndSubXact (commit & abort branches) |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | 5546 | abort-side event-list restore + flag clear |
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | — | full machinery |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/trigger-constraint-deferral.md` —
  SetConstraintState saved here on subxact entry.
- `knowledge/idioms/trigger-transition-tables.md` — transition
  tuplestores freed by resource-owner release on subxact abort.
- `knowledge/idioms/abort-sequence.md` — where
  AfterTriggerEndXact / EndSubXact fit.
- `knowledge/idioms/commit-sequence.md` —
  AfterTriggerFireDeferred + EndXact at COMMIT.
- `knowledge/idioms/subtransaction-as-savepoint.md` —
  BeginInternalSubTransaction pattern.
- `knowledge/data-structures/estate.md` —
  query-level state freed by AfterTriggerFreeQuery.
- `.claude/skills/error-handling/SKILL.md` — companion.
- `source/src/backend/commands/trigger.c` — full machinery.
- `source/src/backend/access/transam/xact.c` —
  AbortTransaction / AbortSubTransaction call sites.
