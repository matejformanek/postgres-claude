# Prepared statement plancache — caching a query's plan

Every `PREPARE`-d statement (and protocol-level "extended
query") gets a `CachedPlanSource` in the **plan cache** —
holding the parse tree, the analyzed Query, and (optionally) a
ready-to-execute generic Plan. The cache survives across the
prepare/execute cycle, transactions, and even concurrent DDL
(invalidations rebuild rather than discard). Understanding the
plancache lifecycle is essential for any work on PREPARE /
EXECUTE, protocol parse/bind/execute, or PL/pgSQL function
plans.

Anchors:
- `source/src/backend/utils/cache/plancache.c:185` —
  CreateCachedPlan [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:265` —
  CreateCachedPlanForQuery [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:393` —
  CompleteCachedPlan [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:1297` —
  GetCachedPlan [verified-by-code]
- `knowledge/idioms/generic-vs-custom-plan.md` — companion
  (which-plan decision)
- `knowledge/idioms/cached-plan-invalidation.md` — companion
  (DDL → invalidate)
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The two-step build

[verified-by-code `plancache.c:185-450`]

```c
CachedPlanSource *
CreateCachedPlan(RawStmt *raw_parse_tree, const char *query_string, CommandTag commandTag);

void CompleteCachedPlan(CachedPlanSource *plansource,
                        List *querytree_list, ...
                        ParserSetupHook parserSetup, ...);
```

Two steps because **parse + analyze are separate phases**:
1. `CreateCachedPlan` — register the raw parse tree.
2. Caller runs analyze + rewrite (via `pg_analyze_and_rewrite_*`).
3. `CompleteCachedPlan` — register the analyzed Query list,
   record cache invalidation dependencies (relations, types,
   functions touched).

Between the two, the CachedPlanSource is "incomplete" — useful
in PL/pgSQL where the parser config is set up lazily.

## CachedPlanSource — the parse cache

[from `plancache.h`]

```c
typedef struct CachedPlanSource
{
    /* Source text + raw parse tree */
    int                magic;
    Node              *raw_parse_tree;
    const char        *query_string;
    CommandTag         commandTag;

    /* Analyzed form */
    List              *query_list;        /* List of Query */
    List              *relationOids;       /* depended-upon relations */
    List              *invalItems;         /* func/proc/type deps */

    /* Cached plan (generic) */
    struct CachedPlan *gplan;              /* the generic plan, or NULL */
    bool               is_valid;
    bool               is_complete;
    bool               is_saved;
    bool               is_oneshot;

    /* Cost tracking */
    double             generic_cost;
    double             total_custom_cost;
    int                num_custom_plans;

    /* ... ~30 more fields */
} CachedPlanSource;
```

The fields fall into three groups:
- **Source**: raw + analyzed parse trees, query string, tag.
- **Dependency tracking**: relationOids + invalItems for
  invalidation (see `cached-plan-invalidation`).
- **Plan + cost tracking**: gplan + custom-vs-generic
  heuristic state.

## CachedPlan — the actual Plan tree

```c
typedef struct CachedPlan
{
    /* Plan node tree */
    List              *stmt_list;          /* List of PlannedStmt */
    bool               is_oneshot;
    bool               is_saved;
    bool               is_valid;
    int                generation;
    int                refcount;
    MemoryContext      context;
    /* ... */
} CachedPlan;
```

The actual planned form. May be:
- **Generic** — planned with no specific param values (uses
  default selectivity estimates).
- **Custom** — planned with bound params for this specific
  execution.

Cached generic plans persist; custom plans are short-lived
(per-execute).

## GetCachedPlan — the execution-time fetch

[verified-by-code `plancache.c:1297`]

```c
CachedPlan *
GetCachedPlan(CachedPlanSource *plansource, ParamListInfo boundParams,
              ResourceOwner owner, QueryEnvironment *queryEnv);
```

Called at each EXECUTE:
1. Check is_valid (else re-analyze + re-plan).
2. Decide custom vs generic (via `choose_custom_plan`).
3. If custom: plan now with boundParams.
4. If generic: re-use cached gplan (re-plan if it's been
   invalidated since cache).
5. Bump refcount; register with ResourceOwner.
6. Return CachedPlan.

The ResourceOwner tracks the plan reference so it's released
on transaction end / portal close.

## The generic plan cache + ageing

The generic plan is computed lazily on the 6th execute (after
5 custom plans have established a baseline cost). It then
sticks unless invalidated.

After invalidation: the cached gplan is dropped on next
GetCachedPlan call; a fresh one is planned. The
`generation` field bumps to signal "this is a different plan".

## is_oneshot vs is_saved

```c
bool is_oneshot;   /* don't bother caching; just run once */
bool is_saved;     /* lives in CacheMemoryContext, survives xact */
```

- **One-shot**: protocol-level "simple query" without bind
  reuse. Custom plan always; no cache retention.
- **Saved**: PREPARE'd named statement, PL/pgSQL cached plan,
  or extended-protocol unnamed (re-bindable) statement. Lives
  across transactions.
- **Unsaved-but-not-oneshot**: extended-protocol unnamed,
  not-yet-bound. Discarded at end of transaction unless
  promoted to saved.

`SaveCachedPlan(plansource)` promotes unsaved → saved.

## ParamListInfo bind

```c
ParamListInfo boundParams;
```

For PREPARE-d statements with $1, $2, ..., the boundParams
struct holds:
- The Datum value per param slot.
- The isnull flag per slot.
- The type OID per slot.
- (Optional) custom param fetch / hook.

Bound at EXECUTE time; passed to GetCachedPlan; the planner
sees concrete values when choosing custom-vs-generic.

## Use sites

[from-code]

- **Protocol-level PREPARE / EXECUTE** —
  `exec_parse_message` + `exec_bind_message` +
  `exec_execute_message` in `postgres.c`.
- **SQL-level PREPARE / EXECUTE** —
  `PrepareQuery` + `ExecuteQuery` in `commands/prepare.c`.
- **PL/pgSQL plans** — `exec_prepare_plan` in
  `pl/plpgsql/src/pl_exec.c`; each PL statement caches its
  plan.
- **SPI** — `SPI_prepare` + `SPI_execute_plan`.

## Plan-cache memory accounting

Saved plans live in `CacheMemoryContext` (long-lived). The
plan body itself is in its own per-plan context (so dropping
a plan frees a context cleanly).

Re-planning allocates a new context; the old one is reset on
drop.

## Common review-time concerns

- **CreateCachedPlan vs CreateCachedPlanForQuery** — pick the
  one that matches your parse-stage timing.
- **Save before commit** — unsaved plans die at xact end.
- **Custom vs generic decided per-execute** — see
  `generic-vs-custom-plan` companion.
- **Invalidation rebuilds, doesn't discard** —
  `is_valid = false` triggers re-analyze + re-plan on next
  Get.
- **ResourceOwner tracking** — every Get bumps refcount;
  matching ReleaseCachedPlan required.

## Invariants

- **[INV-1]** Two-phase build: Create → analyze → Complete.
- **[INV-2]** Saved plans live in CacheMemoryContext.
- **[INV-3]** is_oneshot → no cache retention; always custom.
- **[INV-4]** GetCachedPlan respects is_valid (re-plans if
  invalid).
- **[INV-5]** Generic plan computed on or after 5 customs;
  re-used unless invalidated.

## Useful greps

- The lifecycle:
  `grep -n 'CreateCachedPlan\|CompleteCachedPlan\|GetCachedPlan\|ReleaseCachedPlan\|SaveCachedPlan' source/src/backend/utils/cache/plancache.c | head -15`
- Callers:
  `grep -RIn 'CreateCachedPlan\|GetCachedPlan' source/src/backend | head -20`
- choose_custom_plan:
  `grep -n 'choose_custom_plan\|cached_plan_cost' source/src/backend/utils/cache/plancache.c | head -5`

## Cross-references

- `knowledge/idioms/generic-vs-custom-plan.md` — the
  decision in choose_custom_plan.
- `knowledge/idioms/cached-plan-invalidation.md` — DDL →
  inval pathway.
- `knowledge/idioms/cursor-and-portal.md` — portal holds
  CachedPlan ref via ResourceOwner.
- `knowledge/idioms/cache-invalidation-registration.md` —
  PlanCacheRelCallback + PlanCacheSysCallback registration.
- `knowledge/data-structures/plannerinfo.md` — the planner
  invoked when re-planning.
- `knowledge/subsystems/utils-cache.md` — plancache module.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/utils/cache/plancache.c` — full
  module.
- `source/src/include/utils/plancache.h` — public API.
