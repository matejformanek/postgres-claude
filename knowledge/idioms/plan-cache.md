# Plan cache — CachedPlanSource lifecycle, fixed_result, and the staleness traps

`CachedPlanSource` + `CachedPlan` are the two halves of PG's prepared-statement
plan cache. The lifecycle is:

```
PREPARE / Parse → CreateCachedPlan + CompleteCachedPlan
                    ↓
                    plansource on the saved-plans dlist
                    ↓
DDL elsewhere → CacheRegister* callbacks flip is_valid = false
                    ↓
EXECUTE / Bind → GetCachedPlan → RevalidateCachedQuery → re-analyze/re-plan
                    ↓
                    CachedPlan ref-counted, executor scribbles on the copy
                    ↓
DEALLOCATE / Close → DropCachedPlan
```

This file complements `cached-plan-invalidation.md` (the inval pathway)
and `prepared-statement-plancache.md` (the API surface). Here we focus on
three traps that bit sesvars F10 + F11:

1. The `fixed_result` invariant — when a feature that changes result
   types per session must relax this.
2. The `plansource->resultDesc` consumer list — `UtilityTupleDescriptor`
   reads it BEFORE the inner EXECUTE has revalidated.
3. The per-name-vs-per-backend invalidation choice — when your feature's
   "key" is a text name (not an OID), the standard inval callback shape
   doesn't fit; pessimistic per-backend counters work but are strictly
   worse than per-name HTAB invalidation.

Anchors:
- `source/src/backend/utils/cache/plancache.c:148-158` — `InitPlanCache`,
  registers the rel/sys/func callbacks [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:684` —
  `RevalidateCachedQuery` entry point [verified-by-code]
- `source/src/backend/utils/cache/plancache.c:860-885` — the
  `fixed_result` enforcement block [verified-by-code]
- `source/src/include/utils/plancache.h:105-147` — `CachedPlanSource`
  struct definition [verified-by-code]
- `source/src/backend/commands/prepare.c:467-479` —
  `FetchPreparedStatementResultDesc` reads `resultDesc` directly
  [verified-by-code]
- `source/src/backend/tcop/utility.c:2100-2133` — `UtilityTupleDescriptor`
  is the wire-RowDescription consumer [verified-by-code]

## CachedPlanSource lifecycle

A `CachedPlanSource` is created by `CreateCachedPlan` from the raw parse
tree (cheap; no analysis yet), then "completed" by `CompleteCachedPlan`
with the analyzed-and-rewritten query list. `CompleteCachedPlan` is the
moment three durable things happen:

- `plansource->query_list` is set (the analyzed Query nodes).
- `plansource->relationOids` + `invalItems` are computed — the
  invalidation dependencies.
- `plansource->fixed_result` and `plansource->resultDesc` are set
  [verified-by-code `source/src/backend/utils/cache/plancache.c:483-500`].

The plansource is then `SaveCachedPlan`'d, putting it on the
`saved_plan_list` (a global dlist) so the invalidation callbacks can
walk it. PREPARE goes through this whole pipeline; one-shot plans use
the same struct but skip `Save`.

`InitPlanCache` runs once per backend during `InitPostgres` and
registers six callbacks:

```c
CacheRegisterRelcacheCallback(PlanCacheRelCallback, (Datum) 0);
CacheRegisterSyscacheCallback(PROCOID,    PlanCacheObjectCallback, ...);
CacheRegisterSyscacheCallback(TYPEOID,    PlanCacheObjectCallback, ...);
CacheRegisterSyscacheCallback(NAMESPACEOID, PlanCacheSysCallback,   ...);
CacheRegisterSyscacheCallback(OPEROID,    PlanCacheSysCallback,    ...);
CacheRegisterSyscacheCallback(AMOPOPID,   PlanCacheSysCallback,    ...);
CacheRegisterSyscacheCallback(FOREIGNSERVEROID,      PlanCacheSysCallback, ...);
CacheRegisterSyscacheCallback(FOREIGNDATAWRAPPEROID, PlanCacheSysCallback, ...);
```

[verified-by-code `source/src/backend/utils/cache/plancache.c:148-158`]

Note: all three callbacks take `(Datum arg, Oid relid)` or
`(Datum arg, int cacheid, uint32 hashvalue)`. The `Datum arg` is fixed
at registration time — there's no per-plansource arg passed in. Each
callback walks the saved-plan list and matches against
`plansource->relationOids` / `invalItems`. **The callback can't be
called with a string identifier**; see "Per-name vs per-backend
invalidation" below.

`RevalidateCachedQuery` (`plancache.c:684`) [verified-by-code] is what
turns an `is_valid = false` plansource back into a usable one:

1. Re-acquire snapshot if needed.
2. Re-run analyzer + rewriter on the raw parse tree.
3. Re-compute dependencies + `resultDesc`.
4. Set `is_valid = true`; drop the cached gplan if shape changed.

## The `fixed_result` invariant

`CompleteCachedPlan` takes a `fixed_result` bool. PREPARE sets it to
`true`; SPI / other internal callers usually pass `false`. The effect at
revalidation time:

```c
resultDesc = PlanCacheComputeResultDesc(tlist);
if (resultDesc == NULL && plansource->resultDesc == NULL)
{
    /* OK, doesn't return tuples */
}
else if (resultDesc == NULL || plansource->resultDesc == NULL ||
         !equalRowTypes(resultDesc, plansource->resultDesc))
{
    if (plansource->fixed_result)
        ereport(ERROR,
                (errcode(ERRCODE_FEATURE_NOT_SUPPORTED),
                 errmsg("cached plan must not change result type")));
    /* otherwise, replace plansource->resultDesc */
}
```

[verified-by-code `source/src/backend/utils/cache/plancache.c:865-884`]

So:

- `fixed_result = true` + tupdesc change at revalidate → hard ERROR.
- `fixed_result = true` + tupdesc unchanged → no-op.
- `fixed_result = false` + tupdesc change → silently update
  `plansource->resultDesc`.

`FetchPreparedStatementResultDesc` even asserts the invariant:

```c
TupleDesc
FetchPreparedStatementResultDesc(PreparedStatement *stmt)
{
    /*
     * Since we don't allow prepared statements' result tupdescs to
     * change, there's no need to worry about revalidating the cached
     * plan here.
     */
    Assert(stmt->plansource->fixed_result);
    if (stmt->plansource->resultDesc)
        return CreateTupleDescCopy(stmt->plansource->resultDesc);
    else
        return NULL;
}
```

[verified-by-code `source/src/backend/commands/prepare.c:467-479`]

The Assert + the "no need to revalidate" comment together encode the
design assumption: prepared statements have a stable result tupdesc;
clients that read `Describe Statement` get an answer that doesn't lie
when EXECUTE finally runs.

### When fixed_result has to relax

A feature like sesvars (dynamic per-session typed variables) breaks the
assumption: the same PREPARE'd query can return different column types
across sessions, because `@x` has a different type per session. Two
choices:

- **Discriminator at PREPARE time**: when the parse tree contains a
  reference to a feature that can change types, pass
  `fixed_result = false` to `CompleteCachedPlan`. Then revalidation
  silently rebuilds `resultDesc` instead of throwing. Risk: clients
  that called `Describe Statement` and cached the tupdesc will see a
  mismatch at EXECUTE — they need to re-Describe.
- **Per-feature carveout in the enforcement block**: leave
  `fixed_result = true` but add a guard:

  ```c
  if (plansource->fixed_result && !has_session_var(plansource))
      ereport(ERROR, ...);
  ```

  Risk: more surface area, but preserves the invariant for the 99% case.

Sesvars F10 went with option 2 (per-feature guard). Either way, the
client-side surprise (Describe says X, EXECUTE returns Y) is real and
must be documented.

## The `plansource->resultDesc` consumer list

`resultDesc` is read in two notably different paths:

1. **Via `RevalidateCachedQuery` → `GetCachedPlan`** — this is the
   "fresh" read; it has just re-analyzed and rebuilt resultDesc.
2. **Directly, without revalidation** — this is the stale read. The
   canonical consumer is `FetchPreparedStatementResultDesc`
   [verified-by-code `source/src/backend/commands/prepare.c:467-479`],
   which the comment justifies as "we don't allow prepared statements'
   result tupdescs to change, there's no need to worry about
   revalidating".

The path that bit sesvars F11:

```
client sends EXECUTE p
  → UtilityProcessUtility(T_ExecuteStmt)
  → before running, the wire-protocol code calls
    UtilityTupleDescriptor(parsetree) to publish RowDescription
  → UtilityTupleDescriptor → FetchPreparedStatement(stmt->name)
    → FetchPreparedStatementResultDesc(entry)
    → reads plansource->resultDesc DIRECTLY      ← stale read
  → returns the cached resultDesc to the client
  → THEN inner ExecuteQuery runs and calls GetCachedPlan
    → revalidates, rebuilds resultDesc, runs the new plan
  → executor sends tuples shaped per the NEW resultDesc
  → client decodes them against the OLD RowDescription   ← bug
```

[verified-by-code `source/src/backend/tcop/utility.c:2100-2133` for the
`T_ExecuteStmt` case]

### Fix

In `UtilityTupleDescriptor`'s `T_ExecuteStmt` arm, when the feature
that can drift the tupdesc is in play, force a revalidation BEFORE
reading `resultDesc`:

```c
case T_ExecuteStmt:
{
    ExecuteStmt *stmt = (ExecuteStmt *) parsetree;
    PreparedStatement *entry = FetchPreparedStatement(stmt->name, false);
    if (!entry)
        return NULL;
    if (has_session_var(entry->plansource))
    {
        /* force GetCachedPlan to revalidate so resultDesc is fresh,
           then immediately release — we only wanted the side effect */
        CachedPlan *cplan = GetCachedPlan(entry->plansource,
                                          NULL, NULL, NULL);
        ReleaseCachedPlan(cplan, NULL);
    }
    return FetchPreparedStatementResultDesc(entry);
}
```

The `GetCachedPlan` + `ReleaseCachedPlan` pair is the cheapest known way
to force `RevalidateCachedQuery` to run while keeping the existing
direct-read fast path for the 99% case.

## Per-name vs per-backend invalidation

The standard inval callbacks all take either an `Oid` (relcache) or a
`uint32 hashvalue` (syscache) as their identifier. PG syscache entries
are keyed by Oid, so the `hashvalue` is "hash of the Oid", not "hash of
a name". That's the design assumption: invalidation targets a catalog
row identified by Oid, and the plancache callbacks already know how to
match against `relationOids` / `invalItems`.

For a feature whose "thing being invalidated" is a **text name** (not
backed by a pg_* catalog row, so no Oid exists — sesvars '@name', GUCs,
session-local namespaces), the standard shape doesn't fit. Two
strategies:

### (a) Monotonic per-backend counter (pessimistic, simple)

```c
static uint64 sesvar_inval_counter = 0;

void InvalidateSesvars(void) { sesvar_inval_counter++; }

/* on plansource: */
uint64 plansource_counter_at_complete;

/* at RevalidateCachedQuery: */
if (plansource->plansource_counter_at_complete < sesvar_inval_counter)
    plansource->is_valid = false;
```

Pros:
- Trivially implementable; no per-name tracking.
- Cross-session correctness is automatic — the counter is per-backend
  but every backend that touches a sesvar bumps its own counter on the
  relevant DDL/SET.

Cons:
- **Pessimistic**: any sesvar change invalidates ALL plans that
  reference ANY sesvar, even when the changed name is unrelated.
- Plan churn under heavy sesvar use; could be a measurable cost in
  workloads with thousands of saved plans.

Sesvars v1.1 (the AI-implemented branch) chose this.

### (b) Per-name HTAB (precise, requires a backend-local index)

```c
static HTAB *sesvar_dependency_htab;
/* maps sesvar name → list of plansources that depend on it */

void InvalidateSesvar(const char *name)
{
    SesvarDep *dep = hash_search(sesvar_dependency_htab, name, HASH_FIND, ...);
    if (dep)
        foreach plansource in dep->plansources:
            plansource->is_valid = false;
}

/* at CompleteCachedPlan: walk query_list, for each sesvar reference,
   register this plansource against that name in the HTAB. */
```

Pros:
- Precise: only the plans that actually reference `@x` get invalidated
  when `@x` changes.
- Matches the existing `relationOids` / `invalItems` model conceptually.

Cons:
- More code: HTAB management, registration at Complete-time,
  deregistration at DropCachedPlan-time.
- Cross-backend propagation — each backend has to find out about the
  invalidation. The counter approach side-steps this because the SET
  operation itself bumps the local counter; the HTAB approach needs
  shmem inval (a new sinval message kind) or per-backend signalling.

The user's reference sesvars implementation chose this — strictly
better fidelity, paid for in implementation surface.

### Cross-backend propagation, either way

If the "name" can be set in backend A and referenced from a plan in
backend B (sesvars are session-local, so this doesn't apply — but other
features like temp-namespace catalogs do), you need an inval message
that crosses sinvaladt. `CacheInvalidateCustom*` doesn't exist; the
options are:

- Reuse an existing syscache callback by associating the name with an
  Oid (e.g. via a dummy pg_* row). Heavy.
- Add a new sinval message kind. See
  `source/src/backend/storage/ipc/sinvaladt.c`.
- Constrain the feature to be session-local so cross-backend isn't a
  concern.

Sesvars chose the third option.

## Where new invalidation hooks live

When adding a new class of plancache invalidation, the touch points are:

1. **`InitPlanCache`** at
   `source/src/backend/utils/cache/plancache.c:147-158`
   [verified-by-code] — register the callback or initialize the
   counter/HTAB.
2. **The CachedPlanSource struct** at
   `source/src/include/utils/plancache.h:105-147`
   [verified-by-code] — add fields if you need per-plansource state
   (e.g. `has_session_var`, `plansource_counter_at_complete`).
3. **`CompleteCachedPlan`** — set the per-plansource state by analyzing
   the rewritten query list.
4. **`RevalidateCachedQuery`** at
   `source/src/backend/utils/cache/plancache.c:684`
   [verified-by-code] — read the state and flip `is_valid` if the
   discriminator says stale.
5. **`DropCachedPlan`** — clean up any HTAB entries you registered.

Skipping any of these → leaks, stale reads, or missed invalidation.

## Common review-time concerns

- **Did you relax `fixed_result` and update the Assert in
  `FetchPreparedStatementResultDesc`?** If `fixed_result` can be false
  for your feature's plansources, that Assert fires under
  `--enable-cassert`.
- **Did you cover the `UtilityTupleDescriptor` path?** The plan-cache
  comment says "no need to revalidate" but it lies for dynamic-tupdesc
  features. Force a revalidation in the `T_ExecuteStmt` arm.
- **Did you handle generic-vs-custom plan choice?** A plan that's
  invalidated more often will look more expensive on average, biasing
  `choose_custom_plan` toward custom plans. Usually fine; just be aware.
- **Did you register / deregister symmetrically?** Per-name HTAB
  entries must be removed on `DropCachedPlan`; otherwise the HTAB
  grows unboundedly.
- **Is the new state field set on the `newsource` in `CopyCachedPlan`?**
  Look at `plancache.c:1717-1719` for the pattern — every plansource
  field needs to survive copy.

## Invariants

- **[INV-1]** `fixed_result = true` ⇒ tupdesc MUST NOT change across
  revalidations; if it does, ERROR.
- **[INV-2]** `FetchPreparedStatementResultDesc` reads
  `plansource->resultDesc` without revalidating; only safe when
  `fixed_result` truly holds.
- **[INV-3]** Inval callbacks identify by Oid or `uint32 hashvalue`;
  text-keyed features need a side index or a per-backend counter.
- **[INV-4]** Every state field on `CachedPlanSource` must be copied in
  `CopyCachedPlan`.
- **[INV-5]** `InitPlanCache` is the single registration point; one
  call per backend.

## Useful greps

- `grep -n 'plansource->fixed_result\|plansource->resultDesc' source/src/backend/`
- `grep -n 'CacheRegisterSyscacheCallback\|CacheRegisterRelcacheCallback' source/src/backend/utils/cache/plancache.c`
- `grep -n 'FetchPreparedStatementResultDesc\|UtilityTupleDescriptor' source/src/backend/`

## Cross-references

- `knowledge/idioms/prepared-statement-plancache.md` — PREPARE/EXECUTE
  surface; covers the API that creates these plansources
- `knowledge/idioms/cached-plan-invalidation.md` — the DDL → inval
  → revalidate pathway
- `knowledge/idioms/generic-vs-custom-plan.md` — how the plancache
  decides which plan to use; invalidation bias affects this
- `knowledge/idioms/cache-invalidation-registration.md` — sinval-side
  inval registration
- `knowledge/idioms/sinvaladt-broadcast.md` — cross-backend
  propagation
- `source/src/backend/utils/cache/plancache.c` — implementation
- `source/src/include/utils/plancache.h` — struct definitions
- `source/src/backend/commands/prepare.c` — PreparedStatement layer
- `source/src/backend/tcop/utility.c` — UtilityTupleDescriptor

## Open questions / unverified

- Whether `GetCachedPlan` + immediate `ReleaseCachedPlan` is the
  cheapest path to force revalidation [unverified] — works in practice
  for sesvars F11; not benchmarked.
- Whether existing syscache hashvalue dispatch could be repurposed for
  string keys via a synthetic Oid mapping [unverified] — would avoid a
  new sinval message kind but adds catalog coupling.
- Whether `Describe Statement` clients need to re-Describe after a
  silent `resultDesc` replacement [from-comment `source/src/backend/
  utils/cache/plancache.c:861-863`] — the comment assumes parameter
  types don't change, but doesn't address client-side tupdesc caching.
