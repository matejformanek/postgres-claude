# Domain constraints and typcache invalidation

This doc covers two related parts of typcache.c: how domain types'
CHECK / NOT NULL constraints get loaded and refcounted, and how the
whole typcache reacts to catalog changes via four registered
invalidation callbacks.

Domain handling is built on top of the `TypeCacheEntry` lookup path
([[typcache-entry-and-lookup]]). Each domain type has a
`domainData` field pointing to a refcounted `DomainConstraintCache`
that holds the parsed constraint expressions. Callers that need to
evaluate constraints at runtime (e.g., `domain_in`,
`CoerceToDomain` nodes) hold a `DomainConstraintRef` that bumps the
refcount and registers a memory-context callback to drop it on
scope exit.

The invalidation layer is the typcache's contract with the catalog
update machinery: when pg_type, pg_opclass, pg_constraint, or any
relcache invalidation comes in, the four callbacks here mark the
relevant cache entries as stale **without freeing them**, so any
existing pointers to `TypeCacheEntry` (which other modules cache
long-lived) remain valid. The next `lookup_type_cache` call notices
the cleared TCFLAGS and reloads.

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

Domain machinery:
- `source/src/backend/utils/cache/typcache.c:127-144` —
  `DomainConstraintCache` struct (private).
- `source/src/include/utils/typcache.h:160-175` —
  `DomainConstraintRef` struct (caller-facing).
- `source/src/backend/utils/cache/typcache.c:1078-1308` —
  `load_domaintype_info` (the ancestor-walking constraint loader).
- `source/src/backend/utils/cache/typcache.c:1313-1384` —
  `dcs_cmp`, `decr_dcc_refcount`, `dccref_deletion_callback`,
  `prep_domain_constraints`.
- `source/src/backend/utils/cache/typcache.c:1396-1531` —
  `InitDomainConstraintRef`, `UpdateDomainConstraintRef`,
  `DomainHasConstraints`.

Invalidation callbacks:
- `source/src/backend/utils/cache/typcache.c:2383-2422` —
  `InvalidateCompositeTypeCacheEntry`.
- `source/src/backend/utils/cache/typcache.c:2437-2523` —
  `TypeCacheRelCallback` (relcache).
- `source/src/backend/utils/cache/typcache.c:2533-2572` —
  `TypeCacheTypCallback` (pg_type syscache).
- `source/src/backend/utils/cache/typcache.c:2590-2612` —
  `TypeCacheOpcCallback` (pg_opclass syscache).
- `source/src/backend/utils/cache/typcache.c:2628-2646` —
  `TypeCacheConstrCallback` (pg_constraint syscache).

## `DomainConstraintCache` — the per-domain constraint set

[typcache.c:139-144]:

```c
struct DomainConstraintCache
{
    List         *constraints;   /* list of DomainConstraintState nodes */
    MemoryContext dccContext;    /* memory context holding all data */
    long          dccRefCount;   /* number of references to this struct */
};
```

Three observations:

1. **`dccContext` owns everything for this DCC.** The struct itself,
   the list nodes, the parsed `Expr` trees of the CHECK
   constraints, and the `pstrdup`'d constraint names all live in
   `dccContext`. When the refcount hits zero,
   `MemoryContextDelete(dcc->dccContext)` releases the whole thing
   in one shot.

2. **`constraints` is a `List` of `DomainConstraintState` nodes**
   (defined in `execnodes.h`). Each node carries a `constrainttype`
   (`DOM_CONSTRAINT_NOTNULL` or `DOM_CONSTRAINT_CHECK`), a name,
   a `check_expr` (the parsed-and-planned expression tree), and a
   `check_exprstate` slot. The `check_exprstate` is NULL in the
   cached copy — execution-time `ExprState` trees are built per-use
   by `prep_domain_constraints`.

3. **The DCC is only created if the domain has at least one
   constraint** — `load_domaintype_info` keeps `dcc == NULL` until
   it finds a CHECK or NOT NULL [typcache.c:1170-1182]. So
   constraint-less domains pay zero memory cost.

The whole DCC is **immutable after construction** — once
`load_domaintype_info` returns, the DCC's contents never change.
This is what lets multiple `DomainConstraintRef`s safely share a
pointer to the same DCC without any locking.

## `load_domaintype_info` — walking the ancestor chain

[typcache.c:1078-1308] is the meaty constraint loader. The domain
hierarchy is a stack — a CREATE DOMAIN can derive from another
domain, which derives from another, until a non-domain base type is
hit. Constraints from every level apply. So the loader has to walk
the stack:

```c
static void
load_domaintype_info(TypeCacheEntry *typentry)
{
    Oid typeOid = typentry->type_id;
    DomainConstraintCache *dcc = NULL;
    bool notNull = false;
    Relation conRel = table_open(ConstraintRelationId, AccessShareLock);

    for (;;) {
        /* 1. Look up pg_type row for typeOid. */
        tup = SearchSysCache1(TYPEOID, ObjectIdGetDatum(typeOid));
        typTup = (Form_pg_type) GETSTRUCT(tup);

        if (typTup->typtype != TYPTYPE_DOMAIN) {
            /* Not a domain — we've reached the base type. Done. */
            ReleaseSysCache(tup);
            break;
        }

        /* 2. typnotnull on this level? */
        if (typTup->typnotnull) notNull = true;

        /* 3. Scan pg_constraint for CHECKs on this level. */
        scan = systable_beginscan(conRel, ConstraintTypidIndexId, true, NULL, 1, key);
        while (HeapTupleIsValid(conTup = systable_getnext(scan))) {
            if (c->contype != CONSTRAINT_CHECK) continue;

            /* On first constraint, lazily create the dccContext + DCC. */
            if (dcc == NULL) {
                cxt = AllocSetContextCreate(CurrentMemoryContext,
                                            "Domain constraints",
                                            ALLOCSET_SMALL_SIZES);
                dcc = MemoryContextAlloc(cxt, sizeof(*dcc));
                dcc->constraints = NIL;
                dcc->dccContext = cxt;
                dcc->dccRefCount = 0;
            }

            /* Parse conbin, plan the expression, copy into dccContext. */
            check_expr = stringToNode(constring);
            check_expr = expression_planner(check_expr);
            oldcxt = MemoryContextSwitchTo(dcc->dccContext);
            r = makeNode(DomainConstraintState);
            r->constrainttype = DOM_CONSTRAINT_CHECK;
            r->name = pstrdup(NameStr(c->conname));
            r->check_expr = copyObject(check_expr);
            r->check_exprstate = NULL;
            MemoryContextSwitchTo(oldcxt);

            /* Collect for this domain level, to be sorted before merging. */
            ccons[nccons++] = r;
        }
        systable_endscan(scan);

        /* 4. Sort this level's CHECKs by name, then lcons them onto the head. */
        if (nccons > 1) qsort(ccons, nccons, sizeof(...), dcs_cmp);
        while (nccons > 0)
            dcc->constraints = lcons(ccons[--nccons], dcc->constraints);

        /* 5. Continue up the stack. */
        typeOid = typTup->typbasetype;
        ReleaseSysCache(tup);
    }
    table_close(conRel, AccessShareLock);
```

After the loop, if any NOT NULL was seen, a synthetic
`DOM_CONSTRAINT_NOTNULL` is `lcons`'d onto the head of the list
[typcache.c:1259-1293] so it fires before any CHECKs.

Three design choices worth highlighting:

1. **Ancestor constraints come first.** `lcons` (insert-at-head) is
   used inside the loop, so by the time we ascend to the parent
   domain, this level's constraints are at the head; then the
   parent's constraints get `lcons`'d in front of them. End result:
   constraints are applied innermost-first, working outward.

   Wait — re-read: actually the `lcons` is applied *to the
   per-level array* after sorting [typcache.c:1244-1245]. The next
   iteration of the outer loop appends to this growing list via
   `lcons` again, pushing newer (ancestor) constraints to the
   front. The comment at typcache.c:1239-1242 says: "constraints
   of parent domains should be applied earlier". So evaluation
   order is parent → child, which matches the type-narrowing
   semantic where the parent's constraints define the broad bounds
   and the child tightens them.

2. **NOT NULL is `lcons`'d last, so it ends up at the very head.**
   The comment at typcache.c:1289 says "lcons to apply the
   nullness check FIRST". Sensible: skip the CHECK predicates if
   the value is NULL and NOT NULL is required.

3. **Per-level CHECK sort by name** [typcache.c:1236-1237,
   dcs_cmp at 1313-1319]. Within a single domain's set of CHECKs,
   the order would otherwise depend on `systable_beginscan` order
   which is non-deterministic. Sorting by name makes EXPLAIN
   stable and error messages predictable.

The final move is reparenting the `dccContext` into
`CacheMemoryContext` [typcache.c:1299-1304]:

```c
if (dcc) {
    MemoryContextSetParent(dcc->dccContext, CacheMemoryContext);
    typentry->domainData = dcc;
    dcc->dccRefCount++;       /* the typcache's own reference */
}
typentry->flags |= TCFLAGS_CHECKED_DOMAIN_CONSTRAINTS;
```

Before this point, `dccContext` was a child of the *caller's*
context (so OOM aborts would clean it up). At the success point,
it's adopted into `CacheMemoryContext` where it lives until the
refcount hits zero.

## The `DomainConstraintRef` pattern

Callers that need to evaluate domain constraints at runtime have a
problem: the cached `check_exprstate` is NULL (the cache stores plans
only). They need an executable `ExprState` for each CHECK, built via
`ExecInitExpr`, and that ExprState must be freed before the caller's
memory context is reset.

`DomainConstraintRef` [typcache.h:160-175] solves it:

```c
typedef struct DomainConstraintRef
{
    List         *constraints;   /* exposed list (with check_exprstate filled in) */
    MemoryContext refctx;        /* caller's context */
    TypeCacheEntry *tcache;
    bool          need_exprstate;

    /* private */
    DomainConstraintCache *dcc;
    MemoryContextCallback callback;
} DomainConstraintRef;
```

The caller flow:

1. **`InitDomainConstraintRef(type_id, &ref, refctx, true)`**
   [typcache.c:1396-1422]:

   ```c
   ref->tcache = lookup_type_cache(type_id, TYPECACHE_DOMAIN_CONSTR_INFO);
   ref->need_exprstate = true;
   ref->refctx = refctx;
   ref->dcc = NULL;
   ref->callback.func = dccref_deletion_callback;
   ref->callback.arg = ref;
   MemoryContextRegisterResetCallback(refctx, &ref->callback);

   if (ref->tcache->domainData) {
       ref->dcc = ref->tcache->domainData;
       ref->dcc->dccRefCount++;
       ref->constraints = prep_domain_constraints(ref->dcc->constraints,
                                                  ref->refctx);
   } else {
       ref->constraints = NIL;
   }
   ```

   Three things happen:
   - The reset callback is registered **before** the refcount is
     bumped, so that if `prep_domain_constraints` throws, the
     callback fires on the resulting cleanup and the refcount stays
     balanced.
   - `prep_domain_constraints` [typcache.c:1358-1384] flat-copies
     the cached `DomainConstraintState` nodes into `refctx` and
     calls `ExecInitExpr` for each `check_expr` to produce a real
     `ExprState`. The cached list itself is untouched.
   - `ref->constraints` is the **exposed** list with `check_exprstate`
     non-NULL — the caller iterates over this and evaluates each.

2. **`UpdateDomainConstraintRef(&ref)`**
   [typcache.c:1434-1476] — called before each use:

   ```c
   /* (a) Maybe reload cache if invalidated. */
   if ((typentry->flags & TCFLAGS_CHECKED_DOMAIN_CONSTRAINTS) == 0 &&
       typentry->typtype == TYPTYPE_DOMAIN)
       load_domaintype_info(typentry);

   /* (b) If the cached DCC changed, rebuild this ref. */
   if (ref->dcc != typentry->domainData) {
       /* drop old refcount, leak old executable list */
       if (ref->dcc) {
           ref->constraints = NIL;
           ref->dcc = NULL;
           decr_dcc_refcount(dcc);
       }
       /* attach to new DCC */
       dcc = typentry->domainData;
       if (dcc) {
           ref->dcc = dcc;
           dcc->dccRefCount++;
           ref->constraints = prep_domain_constraints(dcc->constraints,
                                                      ref->refctx);
       }
   }
   ```

   The comment at typcache.c:1452-1459 acknowledges the leak: when
   the DCC switches, the old executable list leaks into `refctx`
   until the context resets. The alternative — a child context per
   DCC version — would be over-engineering for what's expected to
   be a very rare event.

3. **The reset callback** [typcache.c:1338-1350]:

   ```c
   static void
   dccref_deletion_callback(void *arg)
   {
       DomainConstraintRef *ref = (DomainConstraintRef *) arg;
       DomainConstraintCache *dcc = ref->dcc;
       if (dcc) {
           ref->constraints = NIL;
           ref->dcc = NULL;
           decr_dcc_refcount(dcc);
       }
   }
   ```

   When `refctx` is reset or deleted, this fires (via the
   `MemoryContextRegisterResetCallback` machinery from
   [[memory-context-api-and-dispatch]]) and balances the refcount.
   The DCC will be freed if this was the last reference.

4. **`decr_dcc_refcount`** [typcache.c:1326-1332]:

   ```c
   static void
   decr_dcc_refcount(DomainConstraintCache *dcc)
   {
       Assert(dcc->dccRefCount > 0);
       if (--(dcc->dccRefCount) <= 0)
           MemoryContextDelete(dcc->dccContext);
   }
   ```

   `MemoryContextDelete(dccContext)` releases the DCC struct, the
   list nodes, the planned `Expr` trees, all of it.

This pattern — refcount + per-caller deletion callback + flat-copy on
attach — is a clean way to share immutable parsed-expression data
across many short-lived executions.

## `DomainHasConstraints` — the fast check

[typcache.c:1487-1531] is a convenience for code that wants to skip
domain-checking when the domain has nothing to check:

```c
bool
DomainHasConstraints(Oid type_id, bool *has_volatile)
{
    typentry = lookup_type_cache(type_id, TYPECACHE_DOMAIN_CONSTR_INFO);
    if (typentry->domainData == NULL) return false;

    if (has_volatile) {
        *has_volatile = false;
        foreach_node(DomainConstraintState, constrstate,
                     typentry->domainData->constraints)
        {
            if (constrstate->constrainttype == DOM_CONSTRAINT_CHECK &&
                contain_volatile_functions((Node *) constrstate->check_expr))
            {
                *has_volatile = true;
                break;
            }
        }
    }
    return true;
}
```

Used by callers like `coerce_to_domain` to decide whether to emit a
`CoerceToDomain` node or skip it.

## The four invalidation callbacks

The typcache registers four cache-inval handlers at first-call init
[typcache.c:422-425]. Each handles a different catalog and applies a
different reset strategy. The unifying principle: **clear `flags`
bits and `tupDesc` (with refcount release), but never free the
`TypeCacheEntry` itself**.

### `TypeCacheRelCallback(arg, relid)` — pg_class relcache

[typcache.c:2437-2523]. Fires when a relcache invalidation happens
for `relid` (or for all relations if `relid == InvalidOid`). Two
paths:

**Targeted (`relid` is specified):**
1. Look up `RelIdToTypeIdCacheHash[relid]` → composite type OID.
2. Look up that type OID in `TypeCacheHash`.
3. Call `InvalidateCompositeTypeCacheEntry(typentry)` —
   release tupdesc refcount, clear `TCFLAGS_OPERATOR_FLAGS`, set
   `tupDesc_identifier = 0`.
4. Walk `firstDomainTypeEntry` linked list; for any domain whose
   `TCFLAGS_DOMAIN_BASE_IS_COMPOSITE` is set, clear
   `TCFLAGS_OPERATOR_FLAGS` (since a composite base type changed,
   the domain's derived operator info may be stale).

**Global (`relid == InvalidOid`):**
- `hash_seq_search` the entire `TypeCacheHash`. For composites:
  `InvalidateCompositeTypeCacheEntry`. For domains-over-composite:
  clear operator flags.

The comment at typcache.c:2432-2435 explains why we can't use
syscache for the relid→typid lookup: the callback can run outside
a transaction (during, e.g., the inval message dispatch in
`InvalidateSystemCachesExtended`), so syscache access is unsafe.
Hence the `RelIdToTypeIdCacheHash` reverse index — pure
in-memory lookup, no transaction context required.

### `TypeCacheTypCallback(arg, cacheid, hashvalue)` — pg_type

[typcache.c:2533-2572]. Fires when a pg_type row changes. The
implementation cleverly uses the matching syshash to scan only
relevant entries:

```c
if (hashvalue == 0)
    hash_seq_init(&status, TypeCacheHash);           /* invalidate all */
else
    hash_seq_init_with_hash_value(&status, TypeCacheHash, hashvalue);

while ((typentry = hash_seq_search(&status)) != NULL) {
    typentry->flags &= ~(TCFLAGS_HAVE_PG_TYPE_DATA |
                         TCFLAGS_CHECKED_DOMAIN_CONSTRAINTS);
    if (hadPgTypeData)
        delete_rel_type_cache_if_needed(typentry);
}
```

The trick depends on `TypeCacheHash` using `type_cache_syshash` as
its hash function [typcache.c:361-366], so the typcache's hash
buckets line up exactly with syscache hashvalues.
`hash_seq_init_with_hash_value` then visits only the typcache
entries whose hash matches the invalidated syscache row.

Note the cleared flags: `TCFLAGS_HAVE_PG_TYPE_DATA` (the subsidiary
fields might have changed) and `TCFLAGS_CHECKED_DOMAIN_CONSTRAINTS`
(typnotnull might've changed on this domain). Operator flags are
NOT cleared here — those depend on pg_opclass, not pg_type.

### `TypeCacheOpcCallback(arg, cacheid, hashvalue)` — pg_opclass

[typcache.c:2590-2612]. Fires when any pg_opclass row changes. Just
walks the whole typcache and clears `TCFLAGS_OPERATOR_FLAGS` from
every entry:

```c
while ((typentry = hash_seq_search(&status)) != NULL) {
    bool hadOpclass = (typentry->flags & TCFLAGS_OPERATOR_FLAGS);
    typentry->flags &= ~TCFLAGS_OPERATOR_FLAGS;
    if (hadOpclass) delete_rel_type_cache_if_needed(typentry);
}
```

The comment at typcache.c:2580-2588 explains: opclass changes are
rare in production, so the unsophisticated "wipe all operator
info" is fine. Cross-type members (pg_amop entries that aren't
the primary opclass operators) aren't cached, so pg_amop and
pg_amproc changes don't need callbacks.

### `TypeCacheConstrCallback(arg, cacheid, hashvalue)` — pg_constraint

[typcache.c:2628-2646]. Fires when any pg_constraint row changes.
The wrinkle: most pg_constraint changes are for **table**
constraints, not domain constraints. But the callback can't tell
from the inval message which kind, so it has to assume the worst:

```c
for (typentry = firstDomainTypeEntry;
     typentry != NULL;
     typentry = typentry->nextDomain)
{
    typentry->flags &= ~TCFLAGS_CHECKED_DOMAIN_CONSTRAINTS;
}
```

The comment at typcache.c:2622-2626 acknowledges this: "we'll do a
lot of useless flushes". But walking only the domain linked-list
(maintained via `firstDomainTypeEntry` and the `nextDomain`
field) means even with no domains in the system, the callback is
O(0). With a handful of domains, it's still O(handful), not O(all
types).

This is also why the domain-list is maintained at lookup time
[typcache.c:509-514, see [[typcache-entry-and-lookup]]] — without
it, this very-frequently-fired callback would have to
`hash_seq_search` the entire typcache.

## `InvalidateCompositeTypeCacheEntry` — the composite reset

[typcache.c:2382-2422] is the shared helper called from
`TypeCacheRelCallback`:

```c
static void
InvalidateCompositeTypeCacheEntry(TypeCacheEntry *typentry)
{
    bool hadTupDescOrOpclass = (typentry->tupDesc != NULL) ||
                               (typentry->flags & TCFLAGS_OPERATOR_FLAGS);

    /* Manually decrement the tupdesc refcount we bumped at load time. */
    if (typentry->tupDesc != NULL) {
        if (--typentry->tupDesc->tdrefcount == 0)
            FreeTupleDesc(typentry->tupDesc);
        typentry->tupDesc = NULL;
        typentry->tupDesc_identifier = 0;          /* change indicator */
    }
    typentry->flags &= ~TCFLAGS_OPERATOR_FLAGS;
    if (hadTupDescOrOpclass)
        delete_rel_type_cache_if_needed(typentry);
}
```

The `tupDesc_identifier = 0` reset is the change signal. Callers
holding a previously-fetched identifier see "0", recognize "the
tupdesc has changed", and reload.

`delete_rel_type_cache_if_needed` removes the entry from
`RelIdToTypeIdCacheHash` if the typcache entry no longer has any
state worth tracking.

## The lazy-reset principle

A unifying theme across all four callbacks: they **only clear
flags**, they don't reload data. The reload is deferred until the
next `lookup_type_cache` call. This means:

- **Callbacks are cheap.** Even global invalidations are just
  bit-flipping over the hash, no syscache reads, no memory
  allocation.
- **Callers see stale data until they ask.** A caller holding
  `typentry->eq_opr` and never re-checking will see the old OID
  forever. That's a feature, not a bug, for code that doesn't
  care about catalog updates (like a long-running array_eq that
  was already mid-execution when the inval arrived).
- **TypeCacheEntry pointers stay valid.** Long-lived holders
  don't need to re-fetch. They just call `lookup_type_cache` again
  with the same flags whenever they want to re-validate.

The composite-type tupdesc release is the only place where actual
memory is freed during invalidation, and even there, the
`TypeCacheEntry` struct itself stays put.

## Invariants

- **`DomainConstraintCache` is immutable after construction.**
  Multiple refs can share a pointer without locking.
- **`dccRefCount` starts at 0**, then gets bumped by 1 for the
  typcache's reference (in `load_domaintype_info`), and by 1 for
  each `DomainConstraintRef` that attaches. Reaching 0 deletes
  the dccContext.
- **`InitDomainConstraintRef` registers the callback BEFORE
  bumping the refcount.** This makes the refcount balanced even if
  `prep_domain_constraints` throws.
- **NOT NULL is always at the head of the constraint list.** CHECKs
  follow, with parent-domain CHECKs ahead of child-domain CHECKs.
- **CHECKs within a single domain level are sorted by name.**
  Stable EXPLAIN, stable error messages.
- **Inval callbacks clear flags but never free `TypeCacheEntry`
  structs.** Other modules' long-lived pointers remain valid.
- **`tupDesc_identifier = 0` is the universal "tupdesc changed"
  signal.** Callers caching derived data should re-check on every
  use.
- **`firstDomainTypeEntry` is maintained on entry creation only.**
  It's not kept in sync with deletions — but typcache entries are
  never deleted, so it doesn't matter.

## Useful greps

```bash
# Find every DomainConstraintRef user:
grep -RnE 'InitDomainConstraintRef|UpdateDomainConstraintRef' \
    source/src/backend

# Trace the four callbacks' registration site:
grep -nE 'CacheRegister(Relcache|Syscache)Callback' \
    source/src/backend/utils/cache/typcache.c

# Inspect domain constraints at runtime:
#   psql:  SELECT typname, typnotnull,
#                 (SELECT array_agg(conname) FROM pg_constraint
#                  WHERE contypid = t.oid) AS checks
#          FROM pg_type t WHERE typtype = 'd';

# See the lcons / ancestor-walking logic:
sed -n '1110,1260p' source/src/backend/utils/cache/typcache.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 127 | DomainConstraintCache struct (private) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 1078 | load_domaintype_info (the ancestor-walking constraint loader) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 1313 | dcs_cmp, decr_dcc_refcount, dccref_deletion_callback, prep_domain_constraints |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 1396 | InitDomainConstraintRef, UpdateDomainConstraintRef, DomainHasConstraints |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2383 | InvalidateCompositeTypeCacheEntry |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2437 | TypeCacheRelCallback (relcache) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2533 | TypeCacheTypCallback (pg_type syscache) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2590 | TypeCacheOpcCallback (pg_opclass syscache) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2628 | TypeCacheConstrCallback (pg_constraint syscache) |
| [`src/include/utils/typcache.h`](../files/src/include/utils/typcache.h.md) | 160 | DomainConstraintRef struct (caller-facing) |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- [[typcache-entry-and-lookup]] — `TypeCacheEntry`, the `flags`
  bitmaps, `lookup_type_cache` flow that loads `domainData` when
  `TYPECACHE_DOMAIN_CONSTR_INFO` is requested.
- [[typcache-record-typmod-and-shared]] — composite type tupdesc
  refcounting that interacts with
  `InvalidateCompositeTypeCacheEntry`.
- [[cache-invalidation-registration]] —
  `CacheRegisterRelcacheCallback`,
  `CacheRegisterSyscacheCallback`, and how the inval queue
  reaches these callbacks.
- [[syscache-invalidation-flow]] — the SI message types and the
  flow that ends in `InvalidateSystemCaches`.
- [[memory-context-api-and-dispatch]] — the reset-callback
  mechanism `DomainConstraintRef` hooks into.
- [[expression-evaluator-flow]] — `ExecInitExpr` is what
  `prep_domain_constraints` calls to build the per-use ExprState
  for each CHECK.
