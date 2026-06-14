# Cached plan invalidation — DDL → re-plan, not discard

The plancache **does NOT discard** cached plans when their
dependencies change — it **marks them stale and re-plans on
next use**. The pathway: a DDL operation registers an
invalidation message → sinvaladt broadcasts it → backends
process it → the plancache's `PlanCacheRelCallback` /
`PlanCacheSysCallback` walk the list of CachedPlanSources and
flip `is_valid = false` on the affected ones → next
GetCachedPlan re-analyzes + re-plans. Knowing this pathway is
essential for any work on cache invalidation, DDL semantics,
or surprising "why did my plan change" diagnoses.

Anchors:
- `source/src/backend/utils/cache/plancache.c:2126` —
  PlanCacheRelCallback [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:2319` —
  PlanCacheSysCallback [verified-by-code]
- `knowledge/idioms/prepared-statement-plancache.md` —
  companion
- `knowledge/idioms/cache-invalidation-registration.md` —
  companion (sinval-side)
- `knowledge/idioms/sinvaladt-broadcast.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The three invalidation callbacks

[verified-by-code `plancache.c:2126, 2319` and `PlanCacheFuncCallback`]

```c
static void PlanCacheRelCallback(Datum arg, Oid relid);
static void PlanCacheFuncCallback(Datum arg, int cacheid, uint32 hashvalue);
static void PlanCacheSysCallback(Datum arg, int cacheid, uint32 hashvalue);
```

Registered in `plancache.c` via `CacheRegisterRelcacheCallback`
+ `CacheRegisterSyscacheCallback`. Each handles a class of
invalidations:

- **Rel** — relation-level changes (CREATE/ALTER/DROP TABLE,
  ALTER TABLE ADD COLUMN, REINDEX, ANALYZE).
- **Func** — pg_proc changes (CREATE/REPLACE FUNCTION,
  ALTER FUNCTION).
- **Sys** — other syscache changes (pg_class, pg_attribute,
  pg_index, pg_opclass, pg_type, pg_constraint, etc.).

## The relation-callback

[verified-by-code `plancache.c:2126`]

```c
static void
PlanCacheRelCallback(Datum arg, Oid relid)
{
    CachedPlanSource *plansource;

    for (plansource = first_saved_plan; plansource; plansource = plansource->next_saved) {
        if (plansource->relationOids and the changed relid match)
            plansource->is_valid = false;
        if (plansource->gplan && (gplan->relationOids matches))
            gplan->is_valid = false;
    }
}
```

(abstracted)

Iterates over every saved CachedPlanSource; for each one, if
its `relationOids` dependency list contains the changed relid
(or the relid == InvalidOid sentinel = "any relation"), flip
the validity flag.

The flip is O(n_saved_plans × n_relids_per_plan); typically
small enough not to matter, but theoretically a hot spot under
massive DDL.

## What triggers each callback

[per `cache-invalidation-registration` companion]

| Action | Callback(s) fired |
|---|---|
| CREATE / DROP TABLE | Rel + Sys (pg_class, pg_attribute) |
| ALTER TABLE ADD COLUMN | Rel + Sys |
| CREATE / DROP INDEX | Rel + Sys (pg_index) |
| ALTER TABLE SET (...) | Rel + Sys (pg_class) |
| REINDEX | Rel |
| VACUUM (no FULL) | none — statistics-only via separate path |
| ANALYZE | Sys (pg_statistic) — stats-stale flag, not full inval |
| CREATE / DROP FUNCTION | Func |
| CREATE / DROP TYPE | Sys (pg_type) |
| GRANT / REVOKE | Sys (pg_class, pg_proc, etc.) |

## The dependency tracking

[per `prepared-statement-plancache`]

When a CachedPlanSource is "completed" (via
`CompleteCachedPlan`), the analyzer records:
- **`relationOids`** — every relation the plan reads/writes.
- **`invalItems`** — every pg_proc / pg_type / pg_opclass /
  etc. entry referenced by an expression.

These are recorded at `Complete`-time, NOT at execute-time.
The callbacks match against these lists to decide which plans
to invalidate.

## Lazy re-plan vs eager discard

The plancache's design: **mark invalid, don't free**.

```c
plansource->is_valid = false;
plansource->gplan->is_valid = false;
```

On next GetCachedPlan:
- The `is_valid = false` triggers `RevalidateCachedQuery`
  which re-analyzes the raw parse tree.
- If the analyze result differs (e.g., a column was dropped),
  the plan changes accordingly.
- If the analyzed Query is the same, only the Plan is
  re-planned.

Why lazy: the invalidation happens at sinval-process time
which is BETWEEN statements; doing the re-plan synchronously
would be expensive AND could fail (e.g., DROP COLUMN makes
some plans uncompilable). Lazy lets the caller see the error
at the natural failure point.

## RevalidateCachedQuery — the recovery

```c
static List *
RevalidateCachedQuery(CachedPlanSource *plansource);
```

When called on an invalid CachedPlanSource:
1. Reset the analyzer / parser state.
2. Re-run `pg_analyze_and_rewrite_*` on the raw parse tree.
3. Re-compute relationOids + invalItems from the new query
   list.
4. Update plansource state: query_list, relationOids,
   invalItems, is_valid = true.
5. If the re-analyzed shape changed: drop the cached gplan
   too.

The re-analyzed query may differ from the original in ways the
client can observe — most commonly, a column added since
PREPARE will not be selected by `SELECT *` (since the analyzed
target list was fixed at PREPARE time, and re-analyze gets the
new column list).

## Why "fixed at PREPARE" can surprise

[user-visible behavior]

```sql
PREPARE p AS SELECT * FROM t;       -- analyzed: SELECT col1, col2
ALTER TABLE t ADD COLUMN col3 int;
EXECUTE p;                            -- still SELECT col1, col2!
```

The re-analyze WILL pick up col3 — but the change can be
surprising if the client expects "p" to mean "current SELECT *
on t". For consistency, `DEALLOCATE p; PREPARE p AS ...;` is
needed.

For protocol-level extended queries: a new `Parse` message
deallocates the prior plan for the same name.

## Cross-backend propagation

The invalidation is **per-backend**. When one backend issues
DDL:
1. The DDL commit emits inval messages via
   `CacheInvalidateRelcacheByRelid` etc.
2. `RegisterInvalidationMessage` queues them in shmem (sinval).
3. On commit, the inval messages broadcast to all backends.
4. Each backend processes them at the next
   `AcceptInvalidationMessages` checkpoint (typically at
   start of next command).
5. Each backend's `PlanCacheRelCallback` fires, marking its
   local plansources invalid.

So a saved plan in backend A is invalidated by a DDL in
backend B; A re-analyzes on next EXECUTE.

## Common review-time concerns

- **Invalidation is lazy** — `is_valid = false` only; re-plan
  on next use.
- **Re-analyze can fail** — DROP COLUMN of a column in the
  plan's targetlist throws an error.
- **SELECT * is re-expanded** on re-analyze — surprising for
  some clients.
- **Statistics-stale != invalid** — ANALYZE doesn't flip
  is_valid; cached plan keeps its old estimates.
- **Adding new callback class** requires symmetric work in
  both Complete (record dependency) and the callback (match
  against dependency list).
- **InvalidOid sentinel** = "any relation"; expensive, use
  sparingly.

## Invariants

- **[INV-1]** is_valid = false; never auto-discard.
- **[INV-2]** Dependencies recorded at Complete-time, matched
  at invalidate-time.
- **[INV-3]** Re-analyze + re-plan happen on next
  GetCachedPlan.
- **[INV-4]** Statistics-stale handled separately (not via
  is_valid).
- **[INV-5]** Cross-backend propagation via sinval messages.

## Useful greps

- The callbacks:
  `grep -n 'PlanCacheRelCallback\|PlanCacheFuncCallback\|PlanCacheSysCallback' source/src/backend/utils/cache/plancache.c | head -10`
- Registration:
  `grep -n 'CacheRegisterRelcacheCallback\|CacheRegisterSyscacheCallback' source/src/backend/utils/cache/plancache.c | head -5`
- RevalidateCachedQuery:
  `grep -n 'RevalidateCachedQuery' source/src/backend/utils/cache/plancache.c | head -5`

## Cross-references

- `knowledge/idioms/prepared-statement-plancache.md` —
  parent.
- `knowledge/idioms/generic-vs-custom-plan.md` —
  re-plan triggers custom-vs-generic re-decision.
- `knowledge/idioms/cache-invalidation-registration.md` —
  the sinval-side; what queues the messages.
- `knowledge/idioms/sinvaladt-broadcast.md` — shmem inval
  propagation.
- `knowledge/idioms/cursor-and-portal.md` — open portals
  pin a CachedPlan; invalidation waits for portal close.
- `knowledge/subsystems/utils-cache.md` — plancache module.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/utils/cache/plancache.c:2126,2319` —
  callbacks.
