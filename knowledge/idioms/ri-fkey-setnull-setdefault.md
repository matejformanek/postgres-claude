# RI_FKey_setnull / setdefault — the SET NULL / SET DEFAULT actions

`ON DELETE SET NULL` and `ON DELETE SET DEFAULT` (plus their
UPDATE counterparts) run the **same** code path: `ri_set`, with
an `is_set_null` boolean and a tgkind discriminator. The function
builds an `UPDATE child SET fkcol = NULL` (or `DEFAULT`)
`WHERE fkcol = $1` query, caches it via SPI, executes it once per
parent row modification, and — for the SET DEFAULT case only —
runs an extra NO-ACTION recheck because setting to default might
still violate the constraint. The `confdelsetcols` column list
lets `ON DELETE SET NULL (col_a, col_b)` (PG 15+) update only a
subset of FK columns when there are multiple.

Anchors:
- `source/src/backend/utils/adt/ri_triggers.c:1265` —
  RI_FKey_setnull_del [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1280` —
  RI_FKey_setnull_upd [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1295` —
  RI_FKey_setdefault_del [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1310` —
  RI_FKey_setdefault_upd [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1326` — ri_set
  (shared body) [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1394-1411` —
  confdelsetcols subset handling [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:1483-1501` —
  SET DEFAULT NO-ACTION recheck [verified-by-code]
- `knowledge/idioms/ri-fkey-check.md` — companion
- `knowledge/idioms/ri-fkey-cascade.md` — companion
- `.claude/skills/locking/SKILL.md` — companion

## The 4-function fanout

[verified-by-code `ri_triggers.c:1265-1325`]

```c
Datum RI_FKey_setnull_del(PG_FUNCTION_ARGS) {
    ri_CheckTrigger(fcinfo, "RI_FKey_setnull_del", RI_TRIGTYPE_DELETE);
    return ri_set((TriggerData *) fcinfo->context, true,  RI_TRIGTYPE_DELETE);
}

Datum RI_FKey_setnull_upd(PG_FUNCTION_ARGS) {
    ri_CheckTrigger(fcinfo, "RI_FKey_setnull_upd", RI_TRIGTYPE_UPDATE);
    return ri_set((TriggerData *) fcinfo->context, true,  RI_TRIGTYPE_UPDATE);
}

Datum RI_FKey_setdefault_del(PG_FUNCTION_ARGS) {
    ri_CheckTrigger(fcinfo, "RI_FKey_setdefault_del", RI_TRIGTYPE_DELETE);
    return ri_set((TriggerData *) fcinfo->context, false, RI_TRIGTYPE_DELETE);
}

Datum RI_FKey_setdefault_upd(PG_FUNCTION_ARGS) {
    ri_CheckTrigger(fcinfo, "RI_FKey_setdefault_upd", RI_TRIGTYPE_UPDATE);
    return ri_set((TriggerData *) fcinfo->context, false, RI_TRIGTYPE_UPDATE);
}
```

Two booleans (is_set_null + tgkind) generate four distinct query
plan-cache keys.

## ri_set — the shared body

[verified-by-code `ri_triggers.c:1326-1502`]

The structure mirrors RI_FKey_cascade_upd:
1. `ri_FetchConstraintInfo` — get RI_ConstraintInfo.
2. `table_open(fk_rel, RowExclusiveLock)`.
3. `SPI_connect`.
4. Pick a `queryno` from the 4×2 matrix.
5. `ri_FetchPreparedPlan(qkey)` — cache lookup.
6. If miss, build the query string + ri_PlanCheck.
7. `ri_PerformCheck(..., SPI_OK_UPDATE)` — execute.
8. For SET DEFAULT only: extra `ri_restrict(trigdata, true)` call.
9. `SPI_finish` + close fk_rel.

## confdelsetcols — subset SET on DELETE

[verified-by-code `ri_triggers.c:1394-1411`]

PG 15+ syntax:
```sql
ALTER TABLE child ADD FOREIGN KEY (a, b) REFERENCES parent (x, y)
    ON DELETE SET NULL (a);
```

When `riinfo->ndelsetcols != 0`, only those columns are SET to
NULL on parent DELETE:

```c
case RI_TRIGTYPE_DELETE:
    if (riinfo->ndelsetcols != 0) {
        num_cols_to_set = riinfo->ndelsetcols;
        set_cols = riinfo->confdelsetcols;
    } else {
        num_cols_to_set = riinfo->nkeys;
        set_cols = riinfo->fk_attnums;
    }
    break;
```

For UPDATE there's no subset variant — always all FK columns.

## The query template

[verified-by-code `ri_triggers.c:1413-1466`]

```sql
UPDATE [ONLY] <fktable>
   SET fkatt1 = NULL [, fkatt2 = NULL, ...]
 WHERE $1 = fkatt1 [AND $2 = fkatt2, ...]
```

For SET DEFAULT, the literal `DEFAULT` keyword replaces `NULL` in
the SET clause; PG's parser substitutes the column's default
expression at plan time.

The `WHERE` clause uses the parent's OLD key values (`$1`, `$2`)
to find matching child rows. Same `RowExclusiveLock` discipline
as cascade.

## The SET DEFAULT recheck — why it's special

[verified-by-code `ri_triggers.c:1483-1501`]

```c
if (is_set_null)
    return PointerGetDatum(NULL);
else
{
    /*
     * If we just deleted or updated the PK row whose key was equal
     * to the FK columns' default values, and a referencing row exists
     * in the FK table, we would have updated that row to the same
     * values it already had --- and RI_FKey_fk_upd_check_required
     * would hence believe no check is necessary.  So we need to do
     * another lookup now and in case a reference still exists,
     * abort the operation.
     */
    return ri_restrict(trigdata, true);
}
```

Scenario:
- FK column has DEFAULT = 5.
- Parent row with id = 5 is deleted.
- Cascade: SET DEFAULT → child rows that referenced id=5 get
  updated to fk = 5 (same value!).
- Normal RI check thinks "FK didn't change, skip check".
- But parent id = 5 now doesn't exist → constraint violated.

The fix: after SET DEFAULT, explicitly run `ri_restrict`
(NO ACTION) to verify. If the default's referenced row is also
gone, the operation aborts.

SET NULL doesn't need this — NULL always passes FK checks (per
MATCH SIMPLE / FULL).

## Triggers created at FK declaration

For each FK with SET NULL / SET DEFAULT action, ONE trigger is
created on the parent table:
- `ON DELETE SET NULL` → `RI_FKey_setnull_del` trigger.
- `ON UPDATE SET NULL` → `RI_FKey_setnull_upd` trigger.
- (similarly for SET DEFAULT)

A single FK with `ON DELETE SET NULL ON UPDATE CASCADE` creates
both a setnull-del and a cascade-upd trigger.

## Plan cache keys

| Action | Direction | Cache key |
|---|---|---|
| SET NULL | DELETE | RI_PLAN_SETNULL_ONDELETE |
| SET NULL | UPDATE | RI_PLAN_SETNULL_ONUPDATE |
| SET DEFAULT | DELETE | RI_PLAN_SETDEFAULT_ONDELETE |
| SET DEFAULT | UPDATE | RI_PLAN_SETDEFAULT_ONUPDATE |

Combined with the constraint OID, each FK has up to four
distinct cached SPI plans for SET actions.

## Comparison table

| Action | When parent DELETE | When parent UPDATE PK |
|---|---|---|
| CASCADE | child rows DELETEd | child FK columns updated to new PK |
| SET NULL | child FK columns → NULL | child FK columns → NULL |
| SET DEFAULT | child FK columns → DEFAULT (+ recheck) | child FK columns → DEFAULT (+ recheck) |
| RESTRICT | block immediately | block immediately |
| NO ACTION (default) | block at end of stmt or commit | block at end of stmt or commit |

## NULL + the constraint passes free

When child FK columns are set to NULL by these actions:
- MATCH SIMPLE: NULL → constraint passes (don't even check
  parent).
- MATCH FULL: setting only some columns to NULL would be a
  mixed-null violation; PG forbids `SET NULL (col)` for MATCH
  FULL multi-column FKs.

The validator at ALTER TABLE / CREATE TABLE time rejects
incompatible combinations.

## Common review-time concerns

- **One `ri_set` body, 4 entry points** — distinguished by
  is_set_null + tgkind.
- **SET DEFAULT must re-validate** — the default value might
  reference a non-existent parent.
- **`confdelsetcols` only for DELETE** — no equivalent for UPDATE.
- **NULL passes FK check trivially** — no re-validation needed
  for SET NULL.
- **RowExclusiveLock on child** — accumulates with cascades.
- **Plan cache is per (action, direction, constraint)** — 4
  variants × N constraints.

## Invariants

- **[INV-1]** All 4 SET-* triggers share `ri_set` as the body.
- **[INV-2]** SET NULL passes the constraint trivially; no
  recheck.
- **[INV-3]** SET DEFAULT runs `ri_restrict` afterwards to
  catch default → missing parent.
- **[INV-4]** `confdelsetcols` subset only applies on DELETE.
- **[INV-5]** Query template:
  `UPDATE [ONLY] child SET cols = {NULL|DEFAULT} WHERE keys = $`.

## Useful greps

- The 4-fanout + shared body:
  `grep -n '^RI_FKey_setnull_del\|^RI_FKey_setnull_upd\|^RI_FKey_setdefault_del\|^RI_FKey_setdefault_upd\|^ri_set' source/src/backend/utils/adt/ri_triggers.c | head -10`
- The DEFAULT recheck:
  `grep -n 'ri_restrict\|is_set_null' source/src/backend/utils/adt/ri_triggers.c | head -10`
- confdelsetcols handling:
  `grep -n 'confdelsetcols\|ndelsetcols' source/src/backend/utils/adt/ri_triggers.c | head -10`
- Plan cache keys:
  `grep -n 'RI_PLAN_SETNULL\|RI_PLAN_SETDEFAULT' source/src/backend/utils/adt/ri_triggers.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1265 | RI_FKey_setnull_del |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1280 | RI_FKey_setnull_upd |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1295 | RI_FKey_setdefault_del |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1310 | RI_FKey_setdefault_upd |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1326 | ri_set (shared body) |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1394 | confdelsetcols subset handling |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 1483 | SET DEFAULT NO-ACTION recheck |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | — | full RI module |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/ri-fkey-check.md` — child-side check.
- `knowledge/idioms/ri-fkey-cascade.md` — alternative parent-
  side action.
- `knowledge/idioms/trigger-constraint-deferral.md` —
  DEFERRABLE SET actions.
- `knowledge/idioms/spi-cache-plan.md` —
  ri_FetchPreparedPlan internals.
- `knowledge/data-structures/ri-constraintinfo.md` —
  RI_ConstraintInfo + confdelsetcols.
- `knowledge/subsystems/constraint-validation.md` — overview.
- `.claude/skills/locking/SKILL.md` — RowExclusiveLock
  patterns.
- `source/src/backend/utils/adt/ri_triggers.c` — full RI module.
