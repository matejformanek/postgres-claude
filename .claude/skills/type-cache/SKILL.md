---
name: type-cache
description: PostgreSQL's per-backend type-info cache — `src/backend/utils/cache/typcache.c` — the `TypeCacheEntry` struct + `lookup_type_cache` + domain constraint caching + RECORD typmod registry + the shared-parallel-worker variant. Loads when the user asks about `typcache` internals, why `lookup_type_cache` might return NULL, how composite types get identified in parallel workers, RECORD types + typmod semantics, domain constraint invalidation, or when investigating a "type doesn't have the expected traits" bug (missing hash/equality/comparison functions). Skip when the ask is about typcache CALLERS (executor, planner — they just call the API), about pg_type catalog rows (that's `catalog-conventions`), or about implementing a new type (that's `add-new-data-type` scenario).
when_to_load: Debug typcache invalidation issues; add typcache flags for a new trait; work with RECORD types + typmod registry; touch domain-constraint caching; understand parallel-worker composite-type identification (shared typcache variant).
companion_skills:
  - catalog-conventions
  - parallel-query
  - memory-contexts
---

# type-cache — the per-backend type info hub

Every backend needs to answer questions about types constantly: does this type have a btree-ordering? An equality operator? A hash function? What are its component fields (for composites)? What constraints (for domains)?

Answering each of these from scratch — parsing `pg_type` + `pg_operator` + `pg_amop` + `pg_amproc` — would require dozens of syscache hits per query. Instead, PG maintains a **per-backend TypeCache**: one `TypeCacheEntry` per referenced type, lazily populated + invalidated via syscache callbacks when catalog changes.

## The file

Single-file subsystem in the backend:

- `src/backend/utils/cache/typcache.c` (~2200 lines) — the whole implementation.
- `src/include/utils/typcache.h` (~180 lines) — the public API + `TypeCacheEntry` struct + flag definitions.

## The `TypeCacheEntry` struct

```c
typedef struct TypeCacheEntry {
    Oid    type_id;
    int16  typlen;
    bool   typbyval;
    char   typalign;
    char   typstorage;
    Oid    typrelid;                    /* for composite */
    char   typtype;
    /* ... base type traits ... */

    /* Cached-on-demand fields (populated lazily) */
    Oid    btree_opf, btree_opintype;
    Oid    hash_opf, hash_opintype;
    Oid    eq_opr;
    Oid    lt_opr;
    Oid    gt_opr;
    Oid    cmp_proc;
    Oid    hash_proc;
    Oid    hash_extended_proc;
    FmgrInfo eq_opr_finfo;
    FmgrInfo cmp_proc_finfo;
    /* ... etc ... */

    /* Composite type support */
    TupleDesc tupDesc;                   /* NULL if not composite */

    /* Domain support */
    DomainConstraintCache *domainData;   /* NULL if not domain */

    /* Range type support */
    /* Multirange type support */

    /* Flags controlling what's been looked up already */
    int flags;
} TypeCacheEntry;
```

## The lookup pattern

```c
TypeCacheEntry *tcache = lookup_type_cache(type_id, flags_wanted);
if (!OidIsValid(tcache->eq_opr))
    ereport(ERROR, ...);
```

The `flags_wanted` bitmap tells the cache which fields to populate:

- `TYPECACHE_EQ_OPR` — populate `eq_opr` + `eq_opr_finfo`.
- `TYPECACHE_LT_OPR` / `TYPECACHE_GT_OPR` — comparison operators.
- `TYPECACHE_CMP_PROC` — btree support-func-1 for the type.
- `TYPECACHE_HASH_PROC` — hash function.
- `TYPECACHE_HASH_EXTENDED_PROC` — 64-bit hash variant.
- `TYPECACHE_BTREE_OPFAMILY` / `TYPECACHE_HASH_OPFAMILY` — the whole opfamily.
- `TYPECACHE_TUPDESC` — composite type's `TupleDesc`.
- `TYPECACHE_DOMAIN_CONSTR_INFO` — domain's `DomainConstraintCache`.
- `TYPECACHE_RANGE_INFO` / `TYPECACHE_MULTIRANGE_INFO` — range-type companions.

Repeatedly asking for flags that are already populated is O(1) — just a hashtable hit + flag check.

## Invalidation

The typcache subscribes to syscache invalidations:

- `TYPEOID` invalidation → clear the affected entry.
- `OPEROID` invalidation → clear all entries (an operator's semantics changed).
- `AMOPOID` / `AMPROCOID` — cache is opfamily-driven; opfamily changes invalidate ALL entries because we can't cheaply identify which types are affected.
- `PROCOID` — for cached FmgrInfos.
- `RELCACHE` invalidation for composite typrelid → clear TupleDesc.

Invalidations are batched and processed at CommandCounterIncrement or transaction boundaries.

## Composite types + TupleDesc

For composite types (row types of tables, `CREATE TYPE AS`, RECORD subtypes):

- `TypeCacheEntry.tupDesc` holds the reference-counted `TupleDesc`.
- Callers `ReleaseTupleDesc` when done — refcount-managed.
- On invalidation (relcache), the old tupDesc gets marked stale but is NOT freed until refcount drops. New lookups get a fresh tupDesc.

## RECORD typmod registry

Anonymous `RECORD` types (SELECT into row, function returning RECORD, etc.) don't have their own catalog entry. Instead, each unique tuple shape gets a **typmod** — an integer assigned during query analysis, mapping to a TupleDesc.

The registry:

- Backend-local for regular queries.
- **Shared for parallel workers** — a hash in DSM so the leader + workers see the same typmod → TupleDesc mapping. This is the `SharedRecordTypmodRegistry` under `typcache.c`.
- Kept alive for the duration of the query.

## Domain support

Domains cache their constraints:

- `DomainConstraintCache` holds the constraint list + expression trees.
- On constraint DDL (CHECK ADD / DROP), the cache invalidates and re-fetches.
- `TYPECACHE_DOMAIN_CONSTR_INFO` flag populates this.
- Constraint-satisfaction functions (`ExecEvalCoerceToDomain`) call typcache lookup then evaluate.

## Parallel-worker interaction

Parallel workers need to see the same type info as the leader. Two mechanisms:

- **Static per-type info** — each worker has its own typcache, populated on-demand. Since catalog is stable across workers within a query, they converge.
- **Anonymous RECORD types** — shared registry (see above) — because the workers can't reconstruct the same typmod → TupleDesc mapping independently.

## Common patch shapes

### Add a new typcache flag / cached trait

- Add flag constant in `include/utils/typcache.h`.
- Add field to `TypeCacheEntry`.
- Extend `lookup_type_cache` to populate on-demand.
- Add invalidation trigger if the trait depends on catalog objects.
- Test with a query using the new trait.

### Debug "typcache says wrong thing about my type"

- Check `pg_type` row directly — is the catalog data correct?
- `pg_amop` / `pg_amproc` — are the operator-class + support-fn rows present?
- Check whether the invalidation callback is being called — set breakpoint on `TypeCacheEntry` clear paths.
- If parallel workers see different results than leader: check the RECORD typmod registry sharing.

### Extend for a new type category

- Range types + multirange types are precedents — they added `TYPECACHE_RANGE_INFO` and `rngelemtype`, `rngcanonical`, `rngsubdiff` etc.
- New composite-shape types (arrays, tuples) already work via `typelem` + inherited traits.

## Pitfalls

- **`lookup_type_cache` may return NULL for `OidIsValid` checks on optional fields** — always check `OidIsValid(tcache->eq_opr)` before use.
- **Repeated lookups with different flags accumulate** — the entry stays alive, flags accumulate. No cleanup between calls.
- **RECORD typmod is query-local** — a portable RECORD value across queries would need re-registration.
- **Parallel workers must NOT populate typcache from stale snapshots** — invalidations propagate at transaction boundaries; a worker mid-transaction sees the leader's snapshot correctly.
- **Domain constraint cache holds expression trees** — those reference `pg_proc` OIDs. If a constraint function is dropped mid-query, the cached expression can crash when evaluated. Rare but real.
- **`TypeCacheEntry.tupDesc` is refcount-managed** — leaking one via `IncrTupleDescRefCount` without matching decref causes memory leaks that surface only under long-running backends.
- **`SharedRecordTypmodRegistry` uses DSA memory** — allocations are bounded by `parallel_workers` × `work_mem`; a query with lots of unique RECORD shapes can OOM the DSA area.
- **`TYPECACHE_HASH_EXTENDED_PROC` was added in PG 11** — extensions targeting older PG need to fall back to `TYPECACHE_HASH_PROC` + 32-bit truncation.
- **Cache thrashing on hot DDL** — a workload doing lots of CREATE/DROP TYPE will invalidate typcache constantly. Not usually a problem, but visible in profiles.

## Related corpus

- **Idioms** (3 direct hits): `typcache-entry-and-lookup`, `typcache-domain-and-invalidation`, `typcache-record-typmod-and-shared`.
- **Subsystem**: `utils-cache` (typcache is one of the caches; parent doc).
- **Data structures**: `tupledesc` (the composite-type descriptor).
- **File doc**: `knowledge/files/src/backend/utils/cache/typcache.c.md`.
- **Related scenario**: `add-new-data-type` (implicitly touches typcache when new-type support-func rows are wired).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/utils/cache/typcache.c
python3 scripts/corpus-chain.py --idiom typcache-entry-and-lookup
```

Surfaces the tight one-file subsystem + 3 typcache-family idioms.

## Boundary

**Use this skill** for `typcache.c` internals.

**Don't use** for:
- **Callers of typcache** — the executor / planner / rewriter just call `lookup_type_cache`. Their skills cover the calling pattern.
- **`pg_type` catalog rows** — `catalog-conventions` for editing catalog.
- **Composite type CREATE / DROP** — `commands/typecmds.c`, not typcache.
- **Domain DDL** — `commands/typecmds.c` for CREATE DOMAIN; typcache only for constraint evaluation at runtime.
- **Range type internals** — `utils/adt/rangetypes.c`.
- **RECORD polymorphism** — the parser + rewriter code, not typcache.
