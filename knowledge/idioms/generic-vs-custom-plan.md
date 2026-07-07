# Generic vs custom plan — the per-execute decision

For a prepared statement (CachedPlanSource), each `EXECUTE`
decides anew whether to **re-use a cached generic plan** or
**plan freshly with the bound params** (custom plan). The
decision is cost-driven: the planner runs custom plans for the
first 5 executes (gathering an average cost), then switches to
the generic plan if it's cheaper-or-equal than the average
custom-plus-planning cost. Knowing the heuristic is essential
for diagnosing surprising plan changes after the 5th execution.

Anchors:
- `source/src/backend/utils/cache/plancache.c:1175` —
  choose_custom_plan [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:1218-1220` —
  the 5-attempts heuristic [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:1225-1229` —
  generic-cost comparison [verified-by-code]
- `knowledge/idioms/prepared-statement-plancache.md` —
  companion
- `knowledge/idioms/cached-plan-invalidation.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The decision function

[verified-by-code `plancache.c:1175-1220`]

```c
static bool
choose_custom_plan(CachedPlanSource *plansource, ParamListInfo boundParams)
{
    /* One-shot plans are always custom */
    if (plansource->is_oneshot)
        return true;

    /* No params → no point in custom (same plan either way) */
    if (boundParams == NULL)
        return false;

    /* Stmt doesn't need revalidation → no point */
    if (!StmtPlanRequiresRevalidation(plansource))
        return false;

    /* GUC forces the decision */
    if (plan_cache_mode == PLAN_CACHE_MODE_FORCE_GENERIC_PLAN)
        return false;
    if (plan_cache_mode == PLAN_CACHE_MODE_FORCE_CUSTOM_PLAN)
        return true;

    /* Cursor-level override */
    if (plansource->cursor_options & CURSOR_OPT_GENERIC_PLAN)
        return false;
    if (plansource->cursor_options & CURSOR_OPT_CUSTOM_PLAN)
        return true;

    /* First 5 executions: always custom (gather cost baseline) */
    if (plansource->num_custom_plans < 5)
        return true;

    /* Compare average custom cost vs generic cost */
    avg_custom_cost = plansource->total_custom_cost /
                       plansource->num_custom_plans;
    if (plansource->generic_cost < avg_custom_cost)
        return false;     /* generic wins */
    return true;          /* custom wins */
}
```

(abstracted)

## The "magic 5"

[verified-by-code `plancache.c:1218-1220`]

```c
/* Generate custom plans until we have done at least 5 (arbitrary) */
if (plansource->num_custom_plans < 5)
    return true;
```

The first 5 executes always run as custom plans. Each one's
cost (planning + execution estimate) is recorded in
`plansource->total_custom_cost`. After 5 samples, the average
becomes the baseline.

Why 5: arbitrary; chosen to balance "enough samples for a
stable average" against "burn 5 plans per query before
generic". Mentioned in code as "arbitrary".

## How custom-plan cost is computed

[from `cached_plan_cost`]

For custom plans, the cost includes:
- **Total cost of the Plan tree** (as estimated by the
  planner).
- **A "planning cost" charge** — non-trivial, since the
  planner ran.

For generic plans:
- **Total cost of the Plan tree** ONLY (planning happened
  once, not per execute).

The comparison: `generic_cost < avg_custom_cost`. Since custom
costs include planning overhead, the generic plan can be
slightly slower on execution and still win.

## When custom wins forever

Custom always wins when:
- `is_oneshot` (protocol-level simple query).
- `boundParams == NULL` (PREPARE'd with no params).
- `plan_cache_mode = force_custom_plan` GUC.
- `CURSOR_OPT_CUSTOM_PLAN` set (PL/pgSQL `DECLARE x CURSOR
  FOR ...`).
- The custom plan is consistently cheaper than the generic
  (e.g., selectivity varies wildly by param).

The last case is the interesting one: with skewed data, a
custom plan with `WHERE id = 1` may produce an IndexScan while
the generic plan picks a SeqScan (since the planner doesn't
know "id = 1" filters to one row).

## When generic wins forever

Generic always wins when:
- No params (`boundParams == NULL`) — there's nothing to plan
  differently.
- `plan_cache_mode = force_generic_plan` GUC.
- `CURSOR_OPT_GENERIC_PLAN` set.
- The data is uniform enough that the planner picks the same
  plan with any param value.

## The "after 5 executes the plan changed" surprise

[user-visible behavior]

A query that ran fast for 5 executes can suddenly slow down on
the 6th if the planner switches to a generic plan that's worse
than the params-specific custom. Common with:
- Skewed indexes (some param values rare, others common).
- Bind-parameter-dependent join orders.
- LIKE / array contains predicates with selective constants.

Workaround: `SET plan_cache_mode = force_custom_plan` for
that session, or `EXPLAIN (GENERIC_PLAN)` to inspect.

## generic_cost — when is it computed?

[from-code]

The generic plan is computed lazily, **only when needed for
the comparison**. So:
- First 5 executes: only custom plans, no generic yet.
- Sixth execute: planner builds the generic plan, computes
  cost, then compares.
- Subsequent executes: generic cost is cached; only the
  custom average updates.

If the generic plan is invalidated by DDL, it's re-planned and
its cost re-computed.

## CURSOR_OPT flags

```c
CURSOR_OPT_GENERIC_PLAN
CURSOR_OPT_CUSTOM_PLAN
```

For PL/pgSQL cursors and SPI-level explicit overrides:

```sql
DECLARE my_cursor CURSOR FOR
SELECT * FROM t WHERE col = $1;     -- GENERIC_PLAN by default
```

```sql
DECLARE my_cursor CURSOR FOR
SELECT * FROM t WHERE col = $1
WITH (custom_plan);                   -- forces custom
```

## plan_cache_mode GUC

```sql
SET plan_cache_mode = 'auto';                  -- default; use heuristic
SET plan_cache_mode = 'force_generic_plan';    -- always generic
SET plan_cache_mode = 'force_custom_plan';     -- always custom
```

Useful for diagnosing "why did my plan change". `auto` is the
adaptive heuristic; the forced modes bypass it.

## Common review-time concerns

- **The 5-execute baseline** matters for benchmarks — make
  sure measurements include the post-5 regime.
- **plan_cache_mode is session-local** — production tuning
  should be per-statement, not global.
- **Generic plan cost can be -1** (not yet computed) — then
  custom wins by default.
- **CURSOR_OPT flags propagate** through SPI / PL/pgSQL.
- **Bind parameter type changes** force a fresh plan
  regardless.
- **Don't compare generic vs custom cost manually** —
  cached_plan_cost includes / excludes planning cost
  correctly.

## Invariants

- **[INV-1]** First 5 executes always custom; baseline
  measurement.
- **[INV-2]** generic_cost includes only execution; custom
  includes planning + execution.
- **[INV-3]** plan_cache_mode GUC overrides the heuristic.
- **[INV-4]** CURSOR_OPT_* overrides the GUC.
- **[INV-5]** is_oneshot / NULL boundParams short-circuit
  the comparison.

## Useful greps

- The decision:
  `grep -n 'choose_custom_plan\|cached_plan_cost' source/src/backend/utils/cache/plancache.c | head -10`
- plan_cache_mode users:
  `grep -RIn 'plan_cache_mode\|PLAN_CACHE_MODE' source/src/backend | head -10`
- CURSOR_OPT flags:
  `grep -n 'CURSOR_OPT_GENERIC_PLAN\|CURSOR_OPT_CUSTOM_PLAN' source/src/include | head -5`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/cache/plancache.c`](../files/src/backend/utils/cache/plancache.c.md) | 1175 | choose_custom_plan |
| [`src/backend/utils/cache/plancache.c`](../files/src/backend/utils/cache/plancache.c.md) | 1218 | the 5-attempts heuristic |
| [`src/backend/utils/cache/plancache.c`](../files/src/backend/utils/cache/plancache.c.md) | 1225 | generic-cost comparison |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/prepared-statement-plancache.md` —
  parent.
- `knowledge/idioms/cached-plan-invalidation.md` —
  invalidation triggers re-planning.
- `knowledge/idioms/cursor-and-portal.md` — cursor options
  flow.
- `knowledge/data-structures/plannerinfo.md` — planner
  invoked.
- `knowledge/subsystems/utils-cache.md` — plancache module.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/utils/cache/plancache.c:1175` —
  choose_custom_plan.
