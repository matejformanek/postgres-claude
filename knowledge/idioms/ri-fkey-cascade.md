# RI_FKey_cascade_del / _upd — CASCADE action implementation

When a parent row is deleted (or its key updated) with the FK
declared `ON DELETE CASCADE` / `ON UPDATE CASCADE`, PostgreSQL
fires `RI_FKey_cascade_del` / `RI_FKey_cascade_upd` as the
AFTER-trigger body on the parent. Each runs an SPI-cached
`DELETE FROM child WHERE fk = $1` or `UPDATE child SET fk = $newval
WHERE fk = $oldval`. The cascaded DML re-enters the executor,
which can recursively fire more cascade triggers (deletes
cascading further down a chain). The whole thing rides on the
AFTER-trigger queue + SPI plan cache; there's no special
"cascade scheduler" — just normal trigger machinery.

Anchors:
- `source/src/backend/utils/adt/ri_triggers.c:1046` —
  RI_FKey_cascade_del [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1148` —
  RI_FKey_cascade_upd [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1087-1116` —
  cascade-DELETE query template [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1194-1238` —
  cascade-UPDATE query template [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1068, 1172` —
  fk_rel = table_open(..., RowExclusiveLock) [verified-by-code]
- `knowledge/idioms/ri-fkey-check.md` — companion
- `knowledge/idioms/ri-fkey-setnull-setdefault.md` — companion
- `.claude/skills/locking/SKILL.md` — companion

## When does it fire

DDL:
```sql
ALTER TABLE child ADD FOREIGN KEY (parent_id)
    REFERENCES parent(id) ON DELETE CASCADE ON UPDATE CASCADE;
```

creates two **additional** system triggers on the **parent**:
- `RI_ConstraintTrigger_a_NNNNN` — RI_FKey_cascade_del
  (AFTER DELETE).
- `RI_ConstraintTrigger_a_NNNNN+1` — RI_FKey_cascade_upd
  (AFTER UPDATE, when PK columns changed).

The `_a_` (action) prefix vs `_c_` (check) distinguishes parent-
side from child-side triggers.

## RI_FKey_cascade_del — the DELETE side

[verified-by-code `ri_triggers.c:1046-1139`]

```c
Datum
RI_FKey_cascade_del(PG_FUNCTION_ARGS)
{
    ri_CheckTrigger(fcinfo, "RI_FKey_cascade_del", RI_TRIGTYPE_DELETE);
    riinfo = ri_FetchConstraintInfo(trigdata->tg_trigger,
                                    trigdata->tg_relation, true);

    fk_rel = table_open(riinfo->fk_relid, RowExclusiveLock);
    pk_rel = trigdata->tg_relation;
    oldslot = trigdata->tg_trigslot;

    SPI_connect();

    ri_BuildQueryKey(&qkey, riinfo, RI_PLAN_CASCADE_ONDELETE);
    if ((qplan = ri_FetchPreparedPlan(&qkey)) == NULL) {
        /*
         * DELETE FROM [ONLY] <fktable> WHERE $1 = fkatt1 [AND ...]
         */
        /* build query string */
        qplan = ri_PlanCheck(querybuf.data, riinfo->nkeys, queryoids,
                             &qkey, fk_rel, pk_rel);
    }

    ri_PerformCheck(riinfo, &qkey, qplan,
                    fk_rel, pk_rel,
                    oldslot, NULL,
                    false,
                    true,       /* must detect new rows */
                    SPI_OK_DELETE);

    SPI_finish();
    table_close(fk_rel, RowExclusiveLock);
    return PointerGetDatum(NULL);
}
```

The query is a parameterized DELETE on the child. The `$1`
parameter takes the parent's old key value (from
`trigdata->tg_trigslot`). Execution via SPI; result code must be
`SPI_OK_DELETE`.

## RI_FKey_cascade_upd — the UPDATE side

[verified-by-code `ri_triggers.c:1148-1256`]

```c
/*
 * UPDATE [ONLY] <fktable> SET fkatt1 = $1 [, ...]
 *        WHERE $n = fkatt1 [AND ...]
 *
 * $1..$nkeys  = new PK values (the SET targets)
 * $nkeys+1..  = old PK values (the WHERE quals)
 */
```

Both old (from `oldslot`) and new (from `newslot`) values are
passed. The UPDATE rewrites every child row's FK columns to point
at the new key. Uses `RowExclusiveLock` on the FK table.

The cascade UPDATE assumes there's an **assignment cast** from
the PK type to the FK type [comment at `ri_triggers.c:1199-1201`];
this is a parse-time check.

## "must detect new rows" — Snapshot semantics

[verified-by-code `ri_triggers.c:1130, 1247`]

The `detectNewRows = true` parameter to `ri_PerformCheck` tells
the SPI execution to use a fresh snapshot — see new child rows
inserted by **earlier triggers in the same firing cycle**.

If a BEFORE-INSERT trigger added a child row after the parent
DELETE was queued, the cascade must reach it. Without
`detectNewRows`, the cascade would use the original DML's
snapshot and miss the new row.

## Recursive cascading

If `child` itself has children (grandchild table), and the
grandchild's FK is also CASCADE, then `RI_FKey_cascade_del`'s
DELETE on child fires another `RI_FKey_cascade_del` on
grandchild. The AFTER-trigger queue handles the depth-first
recursion correctly because every cascading DELETE goes through
the normal executor + trigger machinery.

The query depth grows linearly with the cascade chain. Each
level is a separate query stack frame in `afterTriggers`.

## The locking ladder

| Level | Lock on parent | Lock on child |
|---|---|---|
| User DELETE FROM parent WHERE id = 5 | RowExclusiveLock (the DELETE) | (none yet) |
| RI_FKey_cascade_del fires | (already held) | RowExclusiveLock |
| Cascade DELETE FROM child WHERE fk = 5 | (already held) | (already held) |
| RI_FKey_cascade_del on child's children | — | RowExclusiveLock down the chain |

Locks accumulate; nothing released until xact end.

## Plan cache invalidation

`ri_FetchPreparedPlan` caches by `(RI_PLAN_CASCADE_ONDELETE,
constraint_oid)`. Cache invalidates when:
- Constraint is dropped.
- Parent or child relation is dropped / altered (relcache
  invalidation).
- ALTER CONSTRAINT changes match type or referenced columns.

After invalidation, the next firing rebuilds + re-caches.

## Difference from SET NULL / SET DEFAULT

| Action | Effect on child | Function |
|---|---|---|
| CASCADE | DELETE / UPDATE child rows | RI_FKey_cascade_del / _upd |
| SET NULL | UPDATE child rows: fk = NULL | RI_FKey_setnull_del / _upd |
| SET DEFAULT | UPDATE child rows: fk = DEFAULT | RI_FKey_setdefault_del / _upd |
| RESTRICT | Block (immediate, no defer) | RI_FKey_restrict_del / _upd |
| NO ACTION | Block (default, deferable) | (check at end) |

Cascade is the only one that performs DELETEs on the child;
others UPDATE or block.

## SET DEFAULT to a non-existent default

If `ON DELETE SET DEFAULT` is declared and the default value
doesn't reference an existing parent row, the cascade UPDATE
fails the FK check it just triggered (the SET DEFAULT → UPDATE
→ child's RI_FKey_check fires → no matching parent → ERROR).

This is intentional per SQL spec: the cascade tries the action,
then the normal RI check validates the result.

## EXPLAIN visibility

`EXPLAIN (ANALYZE) DELETE FROM parent WHERE id IN (1,2,3);`
does NOT show the cascade DELETEs. They run in a nested
trigger-internal SPI plan that isn't visible to the top-level
EXPLAIN.

Use `auto_explain.log_nested_statements = on` or trace
`pg_stat_statements` to see them. The "Trigger time" line in
EXPLAIN ANALYZE output aggregates total cascade time.

## Common review-time concerns

- **Cascade fires AFTER ROW** — runs once per parent row deleted.
- **Recursive cascades go through full trigger machinery** —
  no special unwinding.
- **`detectNewRows = true`** is the snapshot-progress signal.
- **Cascade can fire the check side** — e.g., SET DEFAULT to a
  bad value re-triggers RI_FKey_check, may ERROR.
- **Lock accumulation** — long cascade chains hold many
  RowExclusiveLocks until commit.
- **Plan cache rebuild on DDL** — relcache invalidation is the
  trigger.
- **EXPLAIN ANALYZE hides nested DML** — separate tracing needed.

## Invariants

- **[INV-1]** Cascade triggers fire AFTER each parent row
  modification; one trigger invocation per row.
- **[INV-2]** Cascade DELETE: `DELETE FROM ONLY <child> WHERE
  fk = $1` (partitioned parent omits ONLY).
- **[INV-3]** Cascade UPDATE: assignment cast from PK to FK
  type must exist.
- **[INV-4]** `detectNewRows = true` — cascade sees rows added
  by earlier triggers in the same cycle.
- **[INV-5]** Cascade recursion uses the normal AFTER-trigger
  queue, depth-first via SPI nesting.

## Useful greps

- The cascade functions:
  `grep -n '^RI_FKey_cascade_del\|^RI_FKey_cascade_upd\|RI_PLAN_CASCADE' source/src/backend/utils/adt/ri_triggers.c | head -10`
- Query templates:
  `grep -n 'DELETE FROM\|UPDATE %s%s SET' source/src/backend/utils/adt/ri_triggers.c | head -10`
- detectNewRows callers:
  `grep -n 'detectNewRows\|must detect new rows' source/src/backend/utils/adt/ri_triggers.c | head -10`
- The parent-side trigger creation:
  `grep -n 'createForeignKeyActionTriggers\|RI_FKey_cascade' source/src/backend/commands/tablecmds.c source/src/backend/utils/adt/ri_triggers.c | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/commands/tablecmds.c`](../files/src/backend/commands/tablecmds.c.md) | — | ALTER TABLE ADD FK creates the triggers |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1046 | RI_FKey_cascade_del |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1068 | fk_rel = table_open(..., RowExclusiveLock) |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1087 | cascade-DELETE query template |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1148 | RI_FKey_cascade_upd |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1194 | cascade-UPDATE query template |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | — | full RI module |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/ri-fkey-check.md` — child-side check the
  cascade may re-trigger.
- `knowledge/idioms/ri-fkey-setnull-setdefault.md` —
  alternative parent-side actions.
- `knowledge/idioms/trigger-constraint-deferral.md` —
  DEFERRABLE FK with cascade.
- `knowledge/idioms/spi-cache-plan.md` —
  ri_FetchPreparedPlan internals.
- `knowledge/data-structures/ri-constraintinfo.md` —
  RI_ConstraintInfo struct.
- `knowledge/subsystems/constraint-validation.md` — overview.
- `.claude/skills/locking/SKILL.md` — RowExclusiveLock
  accumulation patterns.
- `source/src/backend/utils/adt/ri_triggers.c` — full RI module.
- `source/src/backend/commands/tablecmds.c` — ALTER TABLE ADD
  FK creates the triggers.
