# RI_FKey_check — referential integrity verification on INSERT/UPDATE

When you write `INSERT INTO child (parent_id) VALUES (5)`, PostgreSQL
fires a system trigger `RI_FKey_check_ins` (or `_upd` for UPDATE)
on the child table whose body is `RI_FKey_check`. The function
asks: "does a row exist in the parent matching this child's FK
columns?". Two implementations: a **fast path** that probes the
parent's PK unique index directly via the table-AM (added recently,
gated by `ri_fastpath_is_applicable`), and a **SPI-based path** that
runs a parameterized `SELECT 1 FROM parent WHERE pk = $1 FOR KEY
SHARE` query, cached in the SPI plan cache. Both honor MATCH FULL
/ MATCH SIMPLE NULL semantics and use `SnapshotSelf` to skip
checks on dead child rows.

Anchors:
- `source/src/backend/utils/adt/ri_triggers.c:358` —
  RI_FKey_check [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:605` —
  RI_FKey_check_ins (PG_FUNCTION_ARGS wrapper) [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:621` —
  RI_FKey_check_upd [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:464-477` —
  fast-path dispatch [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:485` —
  pk_rel = table_open(..., RowShareLock) [verified-by-code]
- `source/src/backend/utils/adt/ri_triggers.c:500-521` —
  the SPI query string template [verified-by-code]
- `knowledge/idioms/ri-fkey-cascade.md` — companion
- `knowledge/idioms/ri-fkey-setnull-setdefault.md` — companion
- `knowledge/idioms/trigger-constraint-deferral.md` — companion
- `.claude/skills/locking/SKILL.md` — companion

## When does it fire

System triggers `RI_ConstraintTrigger_c_NNNNN` (where NNNNN is
the constraint OID) are auto-created when you declare:
```sql
ALTER TABLE child ADD CONSTRAINT fk FOREIGN KEY (parent_id)
    REFERENCES parent(id);
```

The DDL creates three triggers on `child`:
- `RI_FKey_check_ins` — fires AFTER INSERT.
- `RI_FKey_check_upd` — fires AFTER UPDATE (when FK columns changed).
- Plus three more on `parent` for the DELETE / UPDATE actions
  (see `ri-fkey-cascade`).

All are `INITIALLY IMMEDIATE`; can be `DEFERRABLE` so the actual
firing slides to commit (see `trigger-constraint-deferral`).

## Dead-row skip via SnapshotSelf

[verified-by-code `ri_triggers.c:375-384`]

```c
if (!table_tuple_satisfies_snapshot(trigdata->tg_relation,
                                    newslot, SnapshotSelf))
    return PointerGetDatum(NULL);
```

If the queued child row has been deleted (or further updated)
since the queue entry, skip the check. SnapshotSelf sees all
committed-and-not-deleted rows in the *current* transaction —
exactly the right visibility for "is this version still the
latest?".

This matters for DEFERRED checks: by COMMIT, a row INSERTed and
then UPDATEd in the same xact only needs the latest version
checked.

## NULL semantics — MATCH FULL vs MATCH SIMPLE

[verified-by-code `ri_triggers.c:388-450`]

For multi-column FKs, NULL handling depends on `confmatchtype`:

| Match type | All NULL | Some NULL | None NULL |
|---|---|---|---|
| `FKCONSTR_MATCH_SIMPLE` (default) | pass | pass (any null → pass) | check |
| `FKCONSTR_MATCH_FULL` | pass | ERROR (mixed) | check |
| `FKCONSTR_MATCH_PARTIAL` | — | — | (not implemented) |

The `RI_KEYS_*` enum + `ri_NullCheck` returns one of three
states. MATCH FULL specifically errors on mixed null/non-null —
the SQL spec wants "either fully present or fully absent".

## Fast path — direct PK index probe

[verified-by-code `ri_triggers.c:452-477`]

```c
if (ri_fastpath_is_applicable(riinfo))
{
    if (AfterTriggerIsActive())
        ri_FastPathBatchAdd(riinfo, fk_rel, newslot);
    else
        ri_FastPathCheck(riinfo, fk_rel, newslot);
    return PointerGetDatum(NULL);
}
```

Two sub-paths:
- **Batched** — when called from the AFTER trigger queue,
  buffer entries and probe in groups (amortizes plan cache
  lookup + index open).
- **Per-row** — used by `ALTER TABLE VALIDATE CONSTRAINT`
  scanning every row; no batching, no caching.

The fast path bypasses SPI entirely: opens the PK unique index,
uses `index_beginscan` + `index_getnext_slot`, takes a
KEY-SHARE row lock via `table_tuple_lock`. Saves microseconds
per check on hot OLTP workloads.

Disqualifiers (`ri_fastpath_is_applicable`):
- Partitioned FK or partitioned PK.
- Temporal FK (`hasperiod`).
- Non-default `MATCH` types in some configurations.

## Slow path — the SPI query

[verified-by-code `ri_triggers.c:485-521`]

```c
pk_rel = table_open(riinfo->pk_relid, RowShareLock);
ri_BuildQueryKey(&qkey, riinfo, RI_PLAN_CHECK_LOOKUPPK);

if ((qplan = ri_FetchPreparedPlan(&qkey)) == NULL) {
    /*
     * SELECT 1 FROM [ONLY] <pktable> x WHERE pkatt1 = $1 [AND ...]
     *        FOR KEY SHARE OF x
     */
    /* build query string + types */
    qplan = ri_PlanCheck(...);
}

ri_PerformCheck(...);
```

The query is built ONCE per (constraint, query-shape) pair and
cached in the SPI plan cache (`ri_FetchPreparedPlan`). The
cache key is `RI_PLAN_CHECK_LOOKUPPK` plus the constraint OID.

`FOR KEY SHARE OF x` takes a row-level KEY SHARE lock on the
parent — preventing concurrent DELETE / UPDATE of FK columns
without blocking concurrent UPDATEs of other parent columns.

The `pk_only = "ONLY "` skip for partitioned tables ensures we
search the partition tree, not just the root [`ri_triggers.c:524-525`].

## Temporal FKs — range overlap

[verified-by-code `ri_triggers.c:507-521`]

```sql
ALTER TABLE child ADD CONSTRAINT fk FOREIGN KEY
    (parent_id, valid_range) REFERENCES parent (id, valid_range);
```

For PERIOD FKs, the check query becomes:
```sql
SELECT 1
FROM (
    SELECT pkperiodatt AS r
    FROM ONLY pktable x
    WHERE  pkatt1 = $1 AND pkperiodatt && $n
    FOR KEY SHARE OF x
) x1
HAVING $n <@ range_agg(x1.r)
```

The child's range must be **fully covered** by the union of
matching parent ranges. The `range_agg` aggregate combines
overlapping parent ranges into a single range; `<@` checks
containment.

## ri_PerformCheck — the SPI executor wrapper

[verified-by-code `ri_triggers.c:2628`]

Runs the cached plan with the parameter values from the child
row's FK columns. If the result is empty, raises an FK violation
error. Honors `MATCH FULL` / `SIMPLE` (handled before this point)
and the visibility-snapshot rules.

## Memory + connection lifecycle

```
SPI_connect()
    │
    ├─ table_open(pk_rel, RowShareLock)
    │   │
    │   ├─ ri_FetchPreparedPlan() — cache hit or build
    │   ├─ ri_PerformCheck() — execute, examine SPI_processed
    │   └─ raise FK violation if empty
    │
    ├─ table_close(pk_rel, NoLock)  /* lock until xact end */
    └─ SPI_finish()
```

`NoLock` on close = the RowShareLock stays held until commit,
preventing concurrent FK column changes in the parent.

## Common review-time concerns

- **Trigger function is `tg_event = AFTER ROW INSERT/UPDATE`** —
  fires after each row, queued in afterTriggers.events.
- **FOR KEY SHARE is the key correctness piece** — KEY SHARE
  doesn't block other UPDATEs, only DELETE / KEY UPDATE.
- **Fast-path disqualifiers** — partitioned, temporal, some
  MATCH variants.
- **Cached SPI plan is per-constraint** — DDL on parent
  invalidates via relcache.
- **MATCH FULL mixed-null is a hard ERROR**, not silent pass.
- **SnapshotSelf skip avoids re-checking dead versions** —
  important for DEFERRED + multi-modify-same-row patterns.

## Invariants

- **[INV-1]** `RI_FKey_check` is the body of system triggers
  `RI_FKey_check_ins` / `_upd`.
- **[INV-2]** Pre-check: SnapshotSelf liveness skip + MATCH-FULL
  null check.
- **[INV-3]** Fast path probes PK unique index directly when
  `ri_fastpath_is_applicable`.
- **[INV-4]** Slow path uses SPI cached plan + `FOR KEY SHARE`.
- **[INV-5]** PK relation lock is RowShareLock, held until xact
  end (NoLock on close).

## Useful greps

- The check entry + variants:
  `grep -n '^RI_FKey_check\|RI_FKey_check_ins\|RI_FKey_check_upd' source/src/backend/utils/adt/ri_triggers.c | head -10`
- Fast path:
  `grep -n 'ri_fastpath_is_applicable\|ri_FastPathCheck\|ri_FastPathBatchAdd' source/src/backend/utils/adt/ri_triggers.c | head -10`
- SPI plan cache:
  `grep -n 'ri_FetchPreparedPlan\|ri_BuildQueryKey\|RI_PLAN_CHECK' source/src/backend/utils/adt/ri_triggers.c | head -10`
- NULL handling:
  `grep -n 'ri_NullCheck\|RI_KEYS_\|FKCONSTR_MATCH' source/src/backend/utils/adt/ri_triggers.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 358 | RI_FKey_check |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 464 | fast-path dispatch |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 485 | pk_rel = table_open(..., RowShareLock) |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 500 | the SPI query string template |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 605 | RI_FKey_check_ins (PG_FUNCTION_ARGS wrapper) |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | 621 | RI_FKey_check_upd |
| [`src/backend/utils/adt/ri_triggers.c`](../files/src/backend/utils/adt/ri_triggers.c.md) | — | full RI module |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/ri-fkey-cascade.md` — DELETE / UPDATE
  cascade on parent side.
- `knowledge/idioms/ri-fkey-setnull-setdefault.md` —
  SET NULL / SET DEFAULT actions.
- `knowledge/idioms/trigger-constraint-deferral.md` —
  DEFERRABLE FK timing.
- `knowledge/idioms/fmgr-call-pg-function-args.md` — TriggerData
  unpacking.
- `knowledge/idioms/spi-cache-plan.md` — ri_FetchPreparedPlan
  internals.
- `knowledge/data-structures/ri-constraintinfo.md` —
  RI_ConstraintInfo struct.
- `knowledge/subsystems/constraint-validation.md` — overview.
- `.claude/skills/locking/SKILL.md` — FOR KEY SHARE semantics.
- `.claude/skills/catalog-conventions.md` — pg_constraint +
  pg_trigger entries.
- `source/src/backend/utils/adt/ri_triggers.c` — full RI module.
