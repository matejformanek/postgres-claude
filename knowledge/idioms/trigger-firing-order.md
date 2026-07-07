# Trigger firing order — BEFORE / AFTER / INSTEAD OF semantics

PG triggers fire at predictable points around DML operations,
but the **order** matters and the **types** (BEFORE / AFTER /
INSTEAD OF, ROW / STATEMENT) have subtle interactions. Adding a
trigger that fires at the wrong moment, or registering them in
an order that produces unexpected results, is one of the
classic schema-design bugs.

Anchors:
- `source/src/backend/commands/trigger.c` — trigger
  registration + firing [verified-by-code]
- `source/src/include/commands/trigger.h` — public API
- `knowledge/idioms/partition-tuple-routing.md` — companion;
  partitioned-table trigger interaction

## The 3 timings × 2 levels = 6 trigger types

[verified-by-code `trigger.c:225-291`]

| Timing | Level | When fires |
|---|---|---|
| `BEFORE` | `ROW` | Before each affected row; can modify NEW or skip row |
| `AFTER` | `ROW` | After each affected row; effects persist regardless |
| `BEFORE` | `STATEMENT` | Once before the statement; no NEW/OLD access |
| `AFTER` | `STATEMENT` | Once after the statement |
| `INSTEAD OF` | `ROW` | On views; replaces the actual mutation |
| (No `INSTEAD OF STATEMENT`) | — | Not supported |

`INSTEAD OF` triggers only fire on **views** (not base
tables); the trigger replaces the view's row-level mutation
with whatever the function chooses.

## The canonical firing order for a single row INSERT

```
BEFORE STATEMENT trigger
  for each row:
    BEFORE ROW trigger
    INSERT happens (or skipped if BEFORE ROW returned NULL)
    AFTER ROW trigger (deferred)
AFTER STATEMENT trigger
AFTER ROW deferred triggers fire
```

Order within a single timing (e.g. multiple BEFORE ROW
triggers): **alphabetical by trigger name**. So `audit_a`
fires before `audit_b` regardless of CREATE TRIGGER order.

This is a deliberate design decision — explicit ordering via
naming means schema authors control it without depending on
catalog row order.

## BEFORE ROW — can mutate the row

A BEFORE ROW trigger function receives the row in `NEW`
(INSERT/UPDATE) or `OLD` (DELETE) and can:

- **Return NEW** — proceed with the modified value.
- **Return NULL** — skip this row's mutation. Subsequent
  triggers on the same row don't fire either; the statement
  appears to succeed but no row was changed.

The mutation propagates to subsequent triggers — `BEFORE
ROW trigger A` modifies NEW; `BEFORE ROW trigger B` sees A's
modified NEW.

## AFTER ROW — observe, don't modify

AFTER ROW triggers can't change the row (it's already
written). They see the final values. Common uses:

- **Audit logging** — record what changed.
- **Cascade effects** — update related tables.
- **External notifications** — `NOTIFY` based on the change.

The mutation is durable by the time AFTER ROW fires; the
trigger can't undo it short of `RAISE EXCEPTION` which
aborts the statement.

## Deferred AFTER triggers

`CREATE CONSTRAINT TRIGGER ... DEFERRABLE INITIALLY DEFERRED`
makes AFTER ROW triggers fire at **commit** rather than
end-of-statement. Used for:

- **Foreign-key checks** — defer per-row checks until the
  end so cyclic graphs can be inserted in any order.
- **Complex constraints** — defer validation until the
  transaction is complete.

Deferred triggers fire in the order they were queued (which
respects the per-row ordering within the statement that
queued them).

## INSTEAD OF — view mutations

On a view:

```sql
CREATE VIEW employees_v AS SELECT * FROM employees;
CREATE TRIGGER ev_insert
INSTEAD OF INSERT ON employees_v
FOR EACH ROW EXECUTE FUNCTION my_insert_handler();
```

The INSERT against the view fires the trigger; the trigger
function decides what to do (typically INSERT into the
underlying table, possibly modified).

Without an INSTEAD OF trigger, INSERTs / UPDATEs / DELETEs
against most views fail (the view isn't trivially
updatable).

## Partitioned-table trigger interaction

[from companion idiom `partition-tuple-routing.md`]

For a partitioned table with both root-level and child-level
triggers:

- BEFORE root triggers fire first.
- Tuple routed to child partition.
- BEFORE child triggers fire.
- INSERT happens on child.
- AFTER child triggers fire.
- AFTER root triggers fire.

The chain walks the partition tree from root to leaf and
back.

## The TG_event variable in PL/pgSQL

```sql
CREATE FUNCTION audit_trigger() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit (action, new) VALUES ('insert', NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit (action, old, new) VALUES ('update', OLD, NEW);
    -- ...
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

The TG_* variables (`TG_OP`, `TG_TABLE_NAME`, `TG_WHEN`,
`TG_LEVEL`, `TG_ARGV`) describe the trigger context. A
single function can serve as the trigger for multiple
events by dispatching on `TG_OP`.

## TRUNCATE and trigger semantics

TRUNCATE fires:
- BEFORE STATEMENT TRUNCATE triggers.
- TRUNCATE itself.
- AFTER STATEMENT TRUNCATE triggers.

It does NOT fire row-level triggers — TRUNCATE bypasses the
per-row mutation path entirely. This is the "DELETE didn't
fire my trigger" surprise.

If row-level cleanup matters, use DELETE instead of
TRUNCATE, or add a TRUNCATE STATEMENT trigger to handle the
mass-action case.

## Common review-time concerns

- **Order matters; alphabetical by name.** If trigger order
  is critical, use a `_zz_` suffix to control it.
- **BEFORE returning NULL silently skips** — can be a
  surprise if the schema author expected an ERROR.
- **AFTER deferred** + foreign-key cycles — useful but
  delays error to commit time; harder to debug.
- **INSTEAD OF triggers on views** are the way to make
  complex views writable; updatable-views is a separate
  mechanism for simple cases.
- **TRUNCATE bypasses row triggers** — common
  audit-trigger blind spot.

## Invariants

- **[INV-1]** 6 trigger types: 3 timings × 2 levels +
  INSTEAD OF (views only).
- **[INV-2]** Same-timing triggers fire alphabetically by
  name.
- **[INV-3]** BEFORE ROW returning NULL skips the mutation
  AND subsequent triggers on that row.
- **[INV-4]** AFTER triggers can be deferred to commit via
  DEFERRABLE CONSTRAINT TRIGGER.
- **[INV-5]** TRUNCATE fires STATEMENT-level only, NOT
  row-level.

## Useful greps

- The trigger types:
  `grep -n 'TRIGGER_TYPE_BEFORE\|TRIGGER_TYPE_AFTER\|TRIGGER_TYPE_INSTEAD' source/src/backend/commands/trigger.c | head -10`
- The firing entry points:
  `grep -n 'ExecCallTriggerFunc\|AfterTriggerSaveEvent' source/src/backend/commands/trigger.c | head -10`
- BEFORE → AFTER → deferred logic:
  `grep -n 'pg_trigger\.tgdeferrable\|AfterTriggerExecute' source/src/backend/commands/trigger.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/trigger.c`](../files/src/backend/commands/trigger.c.md) | — | trigger registration + firing |
| [`src/include/commands/trigger.h`](../files/src/include/commands/trigger.h.md) | — | public API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/partition-tuple-routing.md` —
  partition + trigger interaction.
- `knowledge/subsystems/contrib-lo.md` — example
  trigger-based auto-cleanup.
- `knowledge/data-structures/tupletableslot.md` — NEW / OLD
  are TupleTableSlots inside the trigger.
- `.claude/skills/executor-and-planner/SKILL.md` —
  trigger invocation in the executor.
- `source/src/backend/commands/trigger.c` —
  implementation.
- `source/src/include/commands/trigger.h` — public API.
