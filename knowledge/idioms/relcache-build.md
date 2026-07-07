# Relcache build — RelationBuildDesc, formrdesc, and the bootstrap chicken-egg

The relcache stores **whole-relation descriptors** (`RelationData`) for
every relation a backend has touched: tuple descriptor, access-method
routines, index info, FK + trigger lists, partition descriptor,
relfilelocator, rd_smgr handle, rules + RLS policies. Where the
catcache caches *tuples* from system catalogs, the relcache caches
*assembled metadata* about a single relation — and one relcache entry
typically depends on hundreds of catcache lookups across `pg_class`,
`pg_attribute`, `pg_index`, `pg_attrdef`, `pg_constraint`, ...

The hard problem: **a relcache build calls SearchSysCache, which opens
system catalogs, which require relcache entries.** PostgreSQL solves
this with two tricks:

1. **`formrdesc`** — hand-built `RelationDesc`s for `pg_class`,
   `pg_attribute`, `pg_proc`, `pg_type` (the four critical local
   catalogs) and a small set of critical indexes. Built from
   compile-time `Desc_pg_class` tables. Marked **nailed** — never
   evicted from the relcache.
2. **The relcache init file** — `pg_internal.init` per database; a
   serialized snapshot of "nailed + frequently-used" relcache entries
   that `RelationCacheInitializePhase3` loads to avoid rebuilding
   from scratch on every backend startup.

This doc walks the `RelationData` struct outline, `RelationBuildDesc`'s
step-by-step assembly, `formrdesc`'s bootstrap-stage hand-build, the
`in_progress_list` invalidation-during-build guard, `RelationClearRelation`
soft eviction, and the three-phase `RelationCacheInitialize*` startup.

Companion docs:
- [[syscache-catcache-internals]] — catcache, the layer relcache builds upon.
- [[syscache-invalidation-flow]] — how relcache invalidations are delivered.
- [[cache-invalidation-registration]] — public `CacheRegister*Callback` API.

## Anchors

- `source/src/backend/utils/cache/relcache.c:1-26` — banner + interface routine summary.
- `source/src/backend/utils/cache/relcache.c:527-740` — `RelationBuildTupleDesc` (pg_attribute scan).
- `source/src/backend/utils/cache/relcache.c:1055-1325` — `RelationBuildDesc` (top-level builder).
- `source/src/backend/utils/cache/relcache.c:1885-2050` — `formrdesc` (the hand-built fallback).
- `source/src/backend/utils/cache/relcache.c:2089-2136` — `RelationIdGetRelation` (the public entry).
- `source/src/backend/utils/cache/relcache.c:2546-2570` — `RelationClearRelation` (eviction).
- `source/src/backend/utils/cache/relcache.c:2585-2891` — `RelationRebuildRelation` (in-place rebuild for refcounted entries).
- `source/src/backend/utils/cache/relcache.c:2938-3000` — `RelationCacheInvalidateEntry` / `RelationCacheInvalidate`.
- `source/src/backend/utils/cache/relcache.c:4004-4400` — `RelationCacheInitialize` / `Phase2` / `Phase3` (startup).
- `source/src/include/utils/rel.h` — `RelationData` struct.

## The RelationData struct (sketch)

```c
/* utils/rel.h (paraphrased) */
struct RelationData {
    RelFileLocator     rd_locator;            /* (spcOid, dbOid, relNumber) */
    SMgrRelation       rd_smgr;               /* opened-on-demand */
    int                rd_refcnt;             /* per-backend pin count */
    ProcNumber         rd_backend;            /* INVALID_PROC for permanent */
    bool               rd_islocaltemp;
    bool               rd_isnailed;           /* formrdesc'd, never evict */
    bool               rd_isvalid;            /* false during rebuild */
    char               rd_indexvalid;
    bool               rd_statvalid;
    SubTransactionId   rd_createSubid;        /* if created in this xact */
    SubTransactionId   rd_newRelfilelocatorSubid;
    SubTransactionId   rd_firstRelfilelocatorSubid;
    SubTransactionId   rd_droppedSubid;
    Form_pg_class      rd_rel;                /* the pg_class tuple's fixed part */
    TupleDesc          rd_att;                /* attribute layout */
    Oid                rd_id;                 /* relation's OID */
    LockInfoData       rd_lockInfo;
    RuleLock          *rd_rules;
    MemoryContext      rd_rulescxt;
    TriggerDesc       *trigdesc;
    RowSecurityDesc   *rd_rsdesc;
    List              *rd_fkeylist;
    PartitionKey       rd_partkey;
    PartitionDesc      rd_partdesc;
    /* index-only fields ... */
    Oid                rd_amhandler;
    TableAmRoutine    *rd_tableam;
    IndexAmRoutine    *rd_indam;
    /* publication info, etc. */
};
```

Critical fields for the build flow: `rd_rel` (the `Form_pg_class`
tuple), `rd_att` (tuple descriptor — most expensive part), `rd_isnailed`
(for formrdesc'd catalogs), `rd_refcnt`, `rd_isvalid`, the various
`rd_*Subid` fields (track in-xact create/drop for sub-xact rollback).

## The lookup entry — RelationIdGetRelation

```c
/* relcache.c:2089 */
Relation RelationIdGetRelation(Oid relationId) {
    AssertCouldGetRelation();
    RelationIdCacheLookup(relationId, rd);            /* hashtable probe */

    if (RelationIsValid(rd)) {
        if (rd->rd_droppedSubid != InvalidSubTransactionId)
            return NULL;                              /* dropped in this xact */
        RelationIncrementReferenceCount(rd);
        if (!rd->rd_isvalid)
            RelationRebuildRelation(rd);              /* invalidated, rebuild in place */
        return rd;
    }

    rd = RelationBuildDesc(relationId, true);         /* build + insert */
    if (RelationIsValid(rd))
        RelationIncrementReferenceCount(rd);
    return rd;
}
```

`RelationIdCache` is a `dynahash` keyed by `Oid` → `Relation`. The
lookup is O(1). The "invalid but cached" case (`!rd_isvalid`)
distinguishes a soft-evicted entry (sinval message arrived but
refcount > 0) from a non-cached entry — rebuild *in place* so the
caller's `Relation` pointer stays valid. [verified-by-code]
(`relcache.c:2110-2113`).

## The full builder — RelationBuildDesc

```c
/* relcache.c:1055 (skeleton) */
Relation RelationBuildDesc(Oid targetRelId, bool insertIt) {
    /* 0. Add to in_progress_list (invalidation-during-build guard) */
    in_progress_offset = in_progress_list_len++;
    in_progress_list[offset].reloid = targetRelId;
retry:
    in_progress_list[offset].invalidated = false;

    /* 1. Fetch pg_class tuple */
    pg_class_tuple = ScanPgRelation(targetRelId, true, false);
    if (!HeapTupleIsValid(pg_class_tuple))
        return NULL;                                  /* relation doesn't exist */

    relp = (Form_pg_class) GETSTRUCT(pg_class_tuple);

    /* 2. Allocate the RelationData + copy pg_class tuple into rd_rel */
    relation = AllocateRelationDesc(relp);
    relation->rd_id = relid;
    relation->rd_refcnt = 0;
    relation->rd_isnailed = false;

    /* 3. Set rd_backend based on persistence */
    switch (relation->rd_rel->relpersistence) {
        case RELPERSISTENCE_TEMP:
            relation->rd_backend = ProcNumberForTempRelations();
            ...
        default:
            relation->rd_backend = INVALID_PROC_NUMBER;
    }

    /* 4. Read pg_attribute: build the TupleDesc */
    RelationBuildTupleDesc(relation);

    /* 5. Initialize AM-specific info */
    if (relation->rd_rel->relkind == RELKIND_INDEX || ... PARTITIONED_INDEX)
        RelationInitIndexAccessInfo(relation);
    else if (RELKIND_HAS_TABLE_AM(relkind) || RELKIND_SEQUENCE)
        RelationInitTableAccessMethod(relation);

    /* 6. Reloptions */
    RelationParseRelOptions(relation, pg_class_tuple);

    /* 7. Optional substructures */
    if (relhasrules)        RelationBuildRuleLock(relation);
    if (relhastriggers)     RelationBuildTriggers(relation);
    if (relrowsecurity)     RelationBuildRowSecurity(relation);

    /* 8. Lock manager state */
    RelationInitLockInfo(relation);

    /* 9. Physical addressing: (spcOid, dbOid, relfilenode) */
    RelationInitPhysicalAddr(relation);
    relation->rd_smgr = NULL;                         /* opened lazily */

    heap_freetuple(pg_class_tuple);

    /* 10. INVALIDATION-DURING-BUILD CHECK */
    if (in_progress_list[offset].invalidated) {
        RelationDestroyRelation(relation, false);
        goto retry;
    }
    in_progress_list_len--;

    /* 11. Insert into hash table */
    if (insertIt)
        RelationCacheInsert(relation, true);

    relation->rd_isvalid = true;
    return relation;
}
```

[verified-by-code] (`relcache.c:1055-1325`).

Step 10 is the **mid-build retry**: while we were running steps 1-9
(each of which can do `SearchSysCache`, which can `AcceptInvalidation-
Messages`, which can deliver a relcache invalidation for *this very
OID*), some inval may have marked our in-progress build dead. If so,
throw away the partial build and retry from step 1. This matches the
catcache `CatCInProgress` stack pattern.

The "between here and the end of this function, don't add code that
does or reasonably could read system catalogs" warning is the
banner constraint after step 10 — we've passed the invalidation check
and any further catalog access would re-open the race.

## Tuple descriptor build — RelationBuildTupleDesc

`RelationBuildTupleDesc` (`relcache.c:527`) opens `pg_attribute` and
scans for every row where `attrelid == relid`. For each:
- Copy the `FormData_pg_attribute` into the new TupleDesc slot.
- Track `has_not_null` for the constraint info.
- Resolve attribute defaults from `pg_attrdef` (lazy — only when
  needed).
- Build `populate_compact_attribute` accelerator entries.

The result is a `TupleDesc` with `tdrefcount = 1` (relcache holds one
reference; catcache may borrow more). This is the dominant cost of a
relcache build because `pg_attribute` is large.

## The bootstrap hand-build — formrdesc

The four critical catalogs **must be relcache-resident before any
catalog scan can run**: `pg_class`, `pg_attribute`, `pg_proc`,
`pg_type`. They are constructed via `formrdesc` using compile-time
data:

```c
/* relcache.c:1885 (skeleton) */
void formrdesc(const char *relationName, Oid relationReltype,
               bool isshared, int natts, const FormData_pg_attribute *attrs)
{
    relation = palloc0_object(RelationData);

    relation->rd_isnailed = true;                     /* nailed-in */
    relation->rd_refcnt = 1;                          /* one phantom pin */
    relation->rd_backend = INVALID_PROC_NUMBER;

    /* Hand-build a Form_pg_class with the minimum needed fields */
    relation->rd_rel = (Form_pg_class) palloc0(CLASS_TUPLE_SIZE);
    namestrcpy(&relation->rd_rel->relname, relationName);
    relation->rd_rel->relnamespace = PG_CATALOG_NAMESPACE;
    relation->rd_rel->reltype = relationReltype;
    relation->rd_rel->relisshared = isshared;
    relation->rd_rel->relpersistence = RELPERSISTENCE_PERMANENT;
    relation->rd_rel->relispopulated = true;
    relation->rd_rel->relkind = RELKIND_RELATION;
    relation->rd_rel->relnatts = natts;
    /* relowner left as zero — flag for Phase3 to fix up from real pg_class */

    /* Build TupleDesc from compile-time attribute array */
    relation->rd_att = CreateTemplateTupleDesc(natts);
    relation->rd_att->tdtypeid = relationReltype;
    for (i = 0; i < natts; i++) {
        memcpy(TupleDescAttr(relation->rd_att, i), &attrs[i], ATTRIBUTE_FIXED_PART_SIZE);
        populate_compact_attribute(relation->rd_att, i);
    }
    TupleDescFinalize(relation->rd_att);

    RelationGetRelid(relation) = TupleDescAttr(relation->rd_att, 0)->attrelid;

    /* These are always mapped (relfilenode lookup goes through relmapper) */
    relation->rd_rel->relfilenode = InvalidRelFileNumber;
    if (IsBootstrapProcessingMode())
        RelationMapUpdateMap(RelationGetRelid(relation),
                             RelationGetRelid(relation),
                             isshared, true);

    RelationInitLockInfo(relation);
    RelationInitPhysicalAddr(relation);

    relation->rd_rel->relam = HEAP_TABLE_AM_OID;
    relation->rd_tableam = GetHeapamTableAmRoutine();
    relation->rd_rel->relhasindex = !IsBootstrapProcessingMode();

    RelationCacheInsert(relation, false);
}
```

[verified-by-code] (`relcache.c:1885-2050`).

Key properties:

1. **`relowner` is intentionally left as 0** — Phase3 checks this and
   knows to read the *real* `pg_class` tuple to fill in fields that
   formrdesc didn't have access to. [from-comment] (`relcache.c:1921-1926`).
2. **`rd_isnailed = true`** + `rd_refcnt = 1`. The nailed flag
   protects against `RelationClearRelation`; the phantom refcount
   prevents in-place rebuild from blowing away the entry while we
   read from it.
3. **`attrs[]` is the source of truth for the tuple descriptor.** The
   data comes from compile-time tables in
   `src/backend/catalog/pg_*.dat` files via genbki.pl into headers
   like `Desc_pg_class`. [from-comment] (`relcache.c:1958-1961`).
4. **Mapped relfilenode.** The four critical catalogs (plus their
   indexes) have `relfilenode = 0` in pg_class and use the
   `relmapper` (`pg_filenode.map`) for the actual file number.
   `RelationMapUpdateMap` populates the initial mapping in bootstrap.
   [verified-by-code] (`relcache.c:1998-2008`).

## Phase 3 — replacing fake entries with real ones

```c
/* relcache.c:4108 (skeleton) */
void RelationCacheInitializePhase3(void) {
    RelationMapInitializePhase3();

    /* Try the init file first; fall back to formrdesc */
    if (!load_relcache_init_file(false)) {
        formrdesc("pg_class",     ...);
        formrdesc("pg_attribute", ...);
        formrdesc("pg_proc",      ...);
        formrdesc("pg_type",      ...);
    }
    if (IsBootstrapProcessingMode()) return;

    /* Load critical indexes (7 local + 6 shared) */
    if (!criticalRelcachesBuilt) {
        load_critical_index(ClassOidIndexId,    RelationRelationId);
        load_critical_index(AttributeRelidNumIndexId, AttributeRelationId);
        load_critical_index(IndexRelidIndexId,  IndexRelationId);
        load_critical_index(OpclassOidIndexId,  OperatorClassRelationId);
        load_critical_index(AccessMethodProcedureIndexId, AccessMethodProcedureRelationId);
        load_critical_index(RewriteRelRulenameIndexId, RewriteRelationId);
        load_critical_index(TriggerRelidNameIndexId, TriggerRelationId);
        criticalRelcachesBuilt = true;
    }
    if (!criticalSharedRelcachesBuilt) {
        load_critical_index(DatabaseNameIndexId, DatabaseRelationId);
        load_critical_index(DatabaseOidIndexId,  DatabaseRelationId);
        load_critical_index(AuthIdRolnameIndexId, AuthIdRelationId);
        load_critical_index(AuthIdOidIndexId,    AuthIdRelationId);
        load_critical_index(AuthMemMemRoleIndexId, AuthMemRelationId);
        load_critical_index(SharedSecLabelObjectIndexId, SharedSecLabelRelationId);
        criticalSharedRelcachesBuilt = true;
    }

    /* Sweep relcache: find faked-up entries (relowner == 0) and replace */
    hash_seq_init(&status, RelationIdCache);
    while ((idhentry = hash_seq_search(&status)) != NULL) {
        relation = idhentry->reldesc;
        if (relation->rd_rel->relowner == InvalidOid) {
            htup = SearchSysCache1(RELOID, ObjectIdGetDatum(relid));
            relp = (Form_pg_class) GETSTRUCT(htup);
            memcpy(relation->rd_rel, relp, CLASS_TUPLE_SIZE);
            ReleaseSysCache(htup);
            restart = true;                           /* hash_seq_search invariant */
        }
        ...
    }
}
```

The `criticalRelcachesBuilt` flag is the **break-the-infinite-recursion
switch**: while false, `systable_beginscan` falls back to heapscan
instead of indexscan for these critical catalogs (because the index
relcache entries don't exist yet); once true, normal indexscans
resume. The "nailed" flag on these indexes is what makes them
unevictable even after the flag flips. [from-comment]
(`relcache.c:4154-4170`).

The `hash_seq_search` "restart" pattern is the standard idiom for
when a callback can invalidate hash entries during iteration — see
[from-comment] (`relcache.c:4242-4247`).

The critical index list (7 local, 6 shared) is hardcoded based on
what `SearchSysCache` needs during a relcache build:
`ClassOidIndexId` for `RELOID` lookups, `AttributeRelidNumIndexId`
for `RelationBuildTupleDesc`'s `pg_attribute` scan, etc.

## In-place rebuild — RelationRebuildRelation

When an inval message arrives for a relation with `refcount > 0`, we
can't `RelationClearRelation` (some caller still holds the pointer).
Instead `RelationRebuildRelation`:

1. Calls `RelationInvalidateRelation` to set `rd_isvalid = false` and
   close `rd_smgr`.
2. Builds a *new* relcache entry via `RelationBuildDesc(.., false)`
   (don't insert).
3. **Swaps the contents** of the old and new entries while preserving:
   - refcount
   - rd_*Subid fields
   - rd_toastoid
   - rd_rel (pg_class fixed part)
   - rd_att (tupledesc — code outside relcache holds pointers into this)
   - rules, partkey, partition descriptor
4. Frees the (now-empty) new entry.

The result: every external pointer to the relcache entry remains
valid, even though its contents are now fresh. [from-comment]
(`relcache.c:2620-2649`).

Index entries get a streamlined `RelationReloadIndexInfo` path; nailed
entries go through `RelationReloadNailed`. [verified-by-code]
(`relcache.c:2606-2618`).

## Invalidation — RelationCacheInvalidateEntry

```c
/* relcache.c:2938 */
void RelationCacheInvalidateEntry(Oid relationId) {
    RelationIdCacheLookup(relationId, relation);
    if (PointerIsValid(relation)) {
        relcacheInvalsReceived++;
        RelationFlushRelation(relation);
    }
}
```

`RelationFlushRelation` either `RelationClearRelation` (refcount = 0)
or marks `rd_isvalid = false` (refcount > 0; will rebuild on next
`RelationIdGetRelation` call). The "soft eviction" of a busy entry
is the bridge: the entry stays in the hash table at the same
address, retains its refcount, but is conceptually stale.

## `in_progress_list` — the invalidation-during-build guard

`in_progress_list` is a per-backend array of `(Oid reloid, bool
invalidated)`. `RelationBuildDesc` pushes onto it at entry and pops
at exit (or at retry). When a relcache invalidation arrives mid-build,
`RelationCacheInvalidateEntry` walks the in-progress list and sets
`invalidated = true` for matching OIDs. The retry check at step 10
catches this and throws away the partial work. [verified-by-code]
(`relcache.c:1092-1102`, `relcache.c:1289-1293`).

## The init file — `pg_internal.init`

Each database has a `pg_internal.init` file in its directory plus a
global `global/pg_internal.init` for shared catalogs. These store a
serialized snapshot of:

- The nailed catalogs' relcache entries (already in formrdesc but
  with correct relowner etc. filled in).
- The nailed indexes' relcache entries.
- Critical opclass info.
- Critical "frequently used" entries — anything that a new backend
  is statistically very likely to need.

`load_relcache_init_file(false)` loads the per-database file;
`load_relcache_init_file(true)` loads the shared file. On success,
phase 3 can skip the formrdesc loop entirely. The file is
**invalidated** by writing a sentinel byte; the writer that performs
a relation-changing DDL drops it. [verified-by-code]
(`relcache.c:4131-4146`).

## Invariants and races

1. **Nailed entries are never evicted.** `formrdesc`'d entries
   (`rd_isnailed = true`) survive `RelationCacheInvalidate(false)`
   sweeps. Critical indexes get the same treatment.
2. **`rd_refcnt > 0` blocks hard eviction.** Soft-evicted entries
   (`rd_isvalid = false`) wait for the next `RelationIdGetRelation`
   call to trigger `RelationRebuildRelation`.
3. **In-place rebuild preserves pointer identity.** External code
   holding a `Relation` retains a valid pointer across inval, even
   if the contents are reconstructed.
4. **`relowner == InvalidOid` is the formrdesc sentinel** for Phase 3
   to identify "needs real pg_class fetch". [from-comment]
   (`relcache.c:1921-1926`).
5. **Mid-build invalidation triggers a retry.** The `in_progress_list`
   ensures we don't return a stale-at-birth entry. [verified-by-code]
   (`relcache.c:1289-1293`).
6. **`criticalRelcachesBuilt` is sticky-true once set.** Subsequent
   `formrdesc` calls would re-clear nailed entries, but the flag
   prevents that path. [from-comment] (`relcache.c:4164-4170`).
7. **Init file is per-database**; the shared file is loaded by every
   backend regardless of database. A relation-changing DDL drops the
   file so the next backend rebuilds from scratch.
8. **`relfilenode = 0` ↔ mapped relation.** The relmapper
   (`pg_filenode.map`) is the source of truth for these — required
   because the four critical catalogs may be VACUUM FULL'd or
   REINDEX'd, which would change their physical filenode without
   touching pg_class (which lives in pg_class itself).

## Useful greps

```bash
# Top-level build/cache APIs:
grep -nE "^RelationIdGetRelation|^RelationBuildDesc|^formrdesc|^RelationClearRelation|^RelationRebuildRelation" \
       source/src/backend/utils/cache/relcache.c

# Three-phase startup:
grep -n "RelationCacheInitialize" source/src/backend/utils/cache/relcache.c

# Critical relcache hardcoded list:
grep -nE "load_critical_index|NUM_CRITICAL" source/src/backend/utils/cache/relcache.c

# Init file:
grep -nE "load_relcache_init_file|write_relcache_init_file|RelCacheInit" \
       source/src/backend/utils/cache/relcache.c

# The in_progress_list dance:
grep -n "in_progress_list" source/src/backend/utils/cache/relcache.c

# Where the nailed flag matters:
grep -n "rd_isnailed" source/src/backend/utils/cache/relcache.c

# Relmapper interaction:
grep -rn "RelationMapUpdateMap\|RelationMapLookup" source/src/backend/
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 1 | banner + interface routine summary |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 527 | RelationBuildTupleDesc (pg_attribute scan) |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 1055 | RelationBuildDesc (top-level builder) |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 1885 | formrdesc (the hand-built fallback) |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 2089 | RelationIdGetRelation (the public entry) |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 2546 | RelationClearRelation (eviction) |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 2585 | RelationRebuildRelation (in-place rebuild for refcounted entries) |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 2938 | RelationCacheInvalidateEntry / RelationCacheInvalidate |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 4004 | RelationCacheInitialize / Phase2 / Phase3 (startup) |
| [`src/backend/utils/cache/relmapper.c`](../files/src/backend/utils/cache/relmapper.c.md) | — | pg_filenode.map mapped-relation indirection |
| [`src/include/utils/rel.h`](../files/src/include/utils/rel.md) | — | RelationData struct |

<!-- /callsites:auto -->

## Cross-references

- [[syscache-catcache-internals]] — catcache layer; relcache builds on hundreds of catcache lookups.
- [[syscache-invalidation-flow]] — how invalidations arrive at `RelationCacheInvalidateEntry`.
- [[cache-invalidation-registration]] — public registration API.
- `knowledge/idioms/catalog-conventions.md` — pg_class / pg_attribute / pg_index conventions.
- `source/src/backend/utils/cache/relmapper.c` — the `pg_filenode.map` mapped-relation indirection.
- `source/src/include/utils/rel.h` — `RelationData` struct.
