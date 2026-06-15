# TypeCacheEntry and `lookup_type_cache`

The type cache is a backend-local hashtable keyed by type OID that
stores per-type information the planner and executor need but that
isn't directly in the `pg_type` row — the default btree/hash opclass,
the equality/comparison/hash operator OIDs, pre-built `FmgrInfo`
structs, the composite type's `TupleDesc`, range subtype info, domain
base type, and a couple of bitmap-set fast paths for arrays/records.

`lookup_type_cache(type_id, flags)` is the single entry point. Callers
pass `TYPECACHE_*` flag bits to say which fields they need, and the
cache fills them in lazily on first request — opclass lookups,
operator lookups, and `fmgr_info` setup are expensive, so we don't
pay for what nobody asked for.

This doc covers the entry struct, the lookup flow, lazy-fill bookkeeping,
the secondary relid→typid map, and the in-progress crash-safety
pattern. For RECORD typmods and the shared registry used by parallel
workers, see [[typcache-record-typmod-and-shared]]. For domain
constraints and invalidation callbacks, see
[[typcache-domain-and-invalidation]].

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

- `source/src/include/utils/typcache.h:31-135` — `TypeCacheEntry`
  struct definition.
- `source/src/include/utils/typcache.h:138-154` — the 16 `TYPECACHE_*`
  flag bits.
- `source/src/backend/utils/cache/typcache.c:1-41` — banner, design
  notes ("typcache entries are good permanently allows caching pointers
  to them in long-lived places").
- `source/src/backend/utils/cache/typcache.c:78-119` — module globals
  and the private TCFLAGS_* bitmap.
- `source/src/backend/utils/cache/typcache.c:389-960` —
  `lookup_type_cache`, the workhorse.
- `source/src/backend/utils/cache/typcache.c:962-1067` —
  `load_typcache_tupdesc`, `load_rangetype_info`,
  `load_multirangetype_info` (the per-section loaders called from
  `lookup_type_cache`).
- `source/src/backend/utils/cache/typcache.c:3093-3220` —
  `insert_rel_type_cache_if_needed`,
  `delete_rel_type_cache_if_needed`, `finalize_in_progress_typentries`,
  `AtEOXact_TypeCache`.

## The struct (one row per type OID)

`TypeCacheEntry` [typcache.h:31-135] is a fat struct — about 30 fields
worth of cached per-type state. The fields fall into seven groups:

```c
typedef struct TypeCacheEntry
{
    /* hash key + cached hash value (must be first) */
    Oid    type_id;
    uint32 type_id_hash;

    /* (1) Subsidiary pg_type data copied at first touch */
    int16  typlen;
    bool   typbyval;
    char   typalign, typstorage, typtype;
    Oid    typrelid, typsubscript, typelem, typarray, typcollation;

    /* (2) Opfamily info, lazily filled */
    Oid    btree_opf, btree_opintype;
    Oid    hash_opf, hash_opintype;
    Oid    eq_opr, lt_opr, gt_opr, cmp_proc;
    Oid    hash_proc, hash_extended_proc;

    /* (3) Pre-built fmgr lookups, lazily filled */
    FmgrInfo eq_opr_finfo;
    FmgrInfo cmp_proc_finfo;
    FmgrInfo hash_proc_finfo;
    FmgrInfo hash_extended_proc_finfo;

    /* (4) Composite type's tupdesc + change-counter */
    TupleDesc tupDesc;
    uint64    tupDesc_identifier;     /* monotonic, changes on every refresh */

    /* (5) Range / multirange info */
    struct TypeCacheEntry *rngelemtype;
    Oid       rng_opfamily, rng_collation;
    FmgrInfo  rng_cmp_proc_finfo, rng_canonical_finfo, rng_subdiff_finfo;
    struct TypeCacheEntry *rngtype;   /* multirange's underlying range */

    /* (6) Domain info */
    Oid       domainBaseType;
    int32     domainBaseTypmod;
    DomainConstraintCache *domainData;

    /* (7) Bookkeeping */
    int       flags;                  /* TCFLAGS_* bitmap */
    struct TypeCacheEnumData    *enumData;
    struct TypeCacheEntry       *nextDomain;
} TypeCacheEntry;
```

Key design property documented at typcache.c:19-23:

> Once created, a type cache entry lives as long as the backend does, so
> there is no need for a call to release a cache entry. If the type is
> dropped, the cache entry simply becomes wasted storage. This is not
> expected to happen often, and assuming that typcache entries are good
> permanently allows caching pointers to them in long-lived places.

This permanence is what enables fields like `rngelemtype` (a pointer to
*another* `TypeCacheEntry`) to be stored as long-lived pointers without
fragile refcounting. The cache entries themselves never move and never
get freed — only their *contents* get invalidated via the flag bits.

## The two flag bitmaps

`TypeCacheEntry.flags` uses two overlapping namespaces:

**Public `TYPECACHE_*` bits** [typcache.h:138-154] — the **input**
flags callers pass to `lookup_type_cache(type_id, flags)`. These say
"please make sure these fields are filled":

| Bit | Meaning |
|---|---|
| `TYPECACHE_EQ_OPR` (0x1) | `eq_opr` |
| `TYPECACHE_LT_OPR` (0x2) | `lt_opr` |
| `TYPECACHE_GT_OPR` (0x4) | `gt_opr` |
| `TYPECACHE_CMP_PROC` (0x8) | `cmp_proc` |
| `TYPECACHE_HASH_PROC` (0x10) | `hash_proc` |
| `TYPECACHE_EQ_OPR_FINFO` (0x20) | `eq_opr_finfo` |
| `TYPECACHE_CMP_PROC_FINFO` (0x40) | `cmp_proc_finfo` |
| `TYPECACHE_HASH_PROC_FINFO` (0x80) | `hash_proc_finfo` |
| `TYPECACHE_TUPDESC` (0x100) | `tupDesc` (composite types) |
| `TYPECACHE_BTREE_OPFAMILY` (0x200) | `btree_opf`/`btree_opintype` |
| `TYPECACHE_HASH_OPFAMILY` (0x400) | `hash_opf`/`hash_opintype` |
| `TYPECACHE_RANGE_INFO` (0x800) | range-type fields |
| `TYPECACHE_DOMAIN_BASE_INFO` (0x1000) | `domainBaseType`/`Typmod` |
| `TYPECACHE_DOMAIN_CONSTR_INFO` (0x2000) | `domainData` |
| `TYPECACHE_HASH_EXTENDED_PROC` (0x4000) | extended hash |
| `TYPECACHE_HASH_EXTENDED_PROC_FINFO` (0x8000) | extended hash finfo |
| `TYPECACHE_MULTIRANGE_INFO` (0x10000) | `rngtype` |

**Private `TCFLAGS_*` bits** [typcache.c:99-119] — the **state**
flags `lookup_type_cache` maintains internally, recording which work
has already been done and what data is currently valid:

| Bit | Meaning |
|---|---|
| `TCFLAGS_HAVE_PG_TYPE_DATA` | subsidiary fields (typlen, typbyval, …) are valid |
| `TCFLAGS_CHECKED_BTREE_OPCLASS` | we've looked up default btree opclass (may not exist) |
| `TCFLAGS_CHECKED_HASH_OPCLASS` | we've looked up default hash opclass |
| `TCFLAGS_CHECKED_EQ_OPR` / `_LT_OPR` / `_GT_OPR` | we've resolved eq/lt/gt |
| `TCFLAGS_CHECKED_CMP_PROC` / `_HASH_PROC` / `_HASH_EXTENDED_PROC` | per-proc |
| `TCFLAGS_CHECKED_ELEM_PROPERTIES` | array-element-has-equality etc. derived |
| `TCFLAGS_HAVE_ELEM_EQUALITY` / `_COMPARE` / `_HASHING` / `_EXTENDED_HASHING` | actual results |
| `TCFLAGS_CHECKED_FIELD_PROPERTIES` | record-field-has-equality etc. derived |
| `TCFLAGS_HAVE_FIELD_EQUALITY` / `_COMPARE` / `_HASHING` / `_EXTENDED_HASHING` | results |
| `TCFLAGS_CHECKED_DOMAIN_CONSTRAINTS` | domain's constraint set is loaded |
| `TCFLAGS_DOMAIN_BASE_IS_COMPOSITE` | domain over a composite type (cached fact) |

The bitmask `TCFLAGS_OPERATOR_FLAGS` [typcache.c:122-125] is
`~(HAVE_PG_TYPE_DATA | CHECKED_DOMAIN_CONSTRAINTS | DOMAIN_BASE_IS_COMPOSITE)`
— i.e., all the operator/proc checks. Used when invalidating after
opclass change: "wipe everything operator-related, keep the basic
pg_type and domain data".

## `lookup_type_cache` — the lookup flow

`lookup_type_cache(type_id, flags)` [typcache.c:389-960] is structured
as a long sequence of "if you need X and it's not cached, go fetch it"
blocks. On hot paths (cache hit, requested fields already valid), it's
just a hash lookup and a flag-bit AND. On a cold-cache miss, it may
chain through several syscache lookups.

The skeleton:

```c
TypeCacheEntry *
lookup_type_cache(Oid type_id, int flags)
{
    /* 1. First-call init: create TypeCacheHash, RelIdToTypeIdCacheHash,
     *    register four cache-invalidation callbacks. */

    /* 2. Register this OID in the in_progress_list (crash-safety). */

    /* 3. Hash lookup. If hit: typentry is fresh. If miss: SearchSysCache(TYPEOID),
     *    HASH_ENTER, copy pg_type fields, set TCFLAGS_HAVE_PG_TYPE_DATA,
     *    thread into firstDomainTypeEntry list if it's a domain. */

    /* 4. If TCFLAGS_HAVE_PG_TYPE_DATA was cleared by an inval since last call,
     *    re-fetch from pg_type. */

    /* 5. For each TYPECACHE_X bit in flags, check the corresponding
     *    TCFLAGS_CHECKED_X bit. If unset, do the work and set the flag. */

    /* 6. insert_rel_type_cache_if_needed() — secondary index upkeep. */

    return typentry;
}
```

### First-call init [typcache.c:395-439]

The first call ever to `lookup_type_cache` in a backend creates two
hash tables and registers four invalidation callbacks:

```c
TypeCacheHash = hash_create("Type information cache", 64,
                            &ctl, HASH_ELEM | HASH_FUNCTION);
RelIdToTypeIdCacheHash = hash_create("Map from relid to OID of cached composite type",
                                     64, &ctl, HASH_ELEM | HASH_BLOBS);

CacheRegisterRelcacheCallback(TypeCacheRelCallback, (Datum) 0);
CacheRegisterSyscacheCallback(TYPEOID, TypeCacheTypCallback, (Datum) 0);
CacheRegisterSyscacheCallback(CLAOID, TypeCacheOpcCallback, (Datum) 0);
CacheRegisterSyscacheCallback(CONSTROID, TypeCacheConstrCallback, (Datum) 0);
```

Note that `type_cache_syshash` [typcache.c:361-366] is installed as
the custom hash function for `TypeCacheHash`. Why: it computes the
same hash that the syscache would compute, so
`hash_seq_init_with_hash_value(TypeCacheHash, hashvalue)` can scan
only the entries that could possibly match a given syscache
invalidation message. Without that match, the inval callbacks would
have to scan the entire table on every pg_type update.

The four callbacks correspond to the four catalog tables this cache
depends on. See [[typcache-domain-and-invalidation]] for what each
one does on inval.

### `in_progress_list` — crash-safety [typcache.c:226-228, 443-455]

```c
static Oid *in_progress_list;
static int  in_progress_list_len;
static int  in_progress_list_maxlen;

/* In lookup_type_cache, after possible hash table init: */
if (in_progress_list_len >= in_progress_list_maxlen) {
    /* grow */
}
in_progress_offset = in_progress_list_len++;
in_progress_list[in_progress_offset] = type_id;
```

The list records every type currently being filled in by an active
`lookup_type_cache` call. Why this matters: `lookup_type_cache` can
recurse (e.g., a range type calls `lookup_type_cache(subtype)`), and
along the way, an `ereport(ERROR)` could fire (out of memory, missing
opclass, etc.) leaving a partly-filled cache entry behind.

The secondary `RelIdToTypeIdCacheHash` is *supposed* to mirror
"every cache entry has its `typrelid → type_id` registered if it's
composite", and the assert in `delete_rel_type_cache_if_needed`
[typcache.c:3163] checks "either the secondary entry exists, or this
type is in progress". So `is_in_progress` is the get-out-of-jail card
for the assert during recursive lookups.

`AtEOXact_TypeCache` and `AtEOSubXact_TypeCache`
[typcache.c:3210-3219] call `finalize_in_progress_typentries`
[typcache.c:3191-3207] which sweeps the list and ensures every
in-progress entry has its secondary mapping in place even if the
parent transaction aborted mid-lookup.

### The opclass lookup cascade [typcache.c:558-630]

When any of the equality/comparison flags are requested, the function
first ensures the **default opfamily** info is loaded:

```c
if ((flags & (TYPECACHE_EQ_OPR | ...)) &&
    !(typentry->flags & TCFLAGS_CHECKED_BTREE_OPCLASS))
{
    opclass = GetDefaultOpClass(type_id, BTREE_AM_OID);
    if (OidIsValid(opclass)) {
        typentry->btree_opf = get_opclass_family(opclass);
        typentry->btree_opintype = get_opclass_input_type(opclass);
    } else {
        typentry->btree_opf = typentry->btree_opintype = InvalidOid;
    }
    /* Reset operator-derived bits — they may now be incorrect */
    typentry->flags &= ~(TCFLAGS_CHECKED_EQ_OPR | ...);
    typentry->flags |= TCFLAGS_CHECKED_BTREE_OPCLASS;
}
```

Two subtleties:

1. **If we look up eq but there's no btree opclass, we also force
   `TYPECACHE_HASH_OPFAMILY`** [typcache.c:598-601]:

   ```c
   if ((flags & (TYPECACHE_EQ_OPR | TYPECACHE_EQ_OPR_FINFO)) &&
       !(typentry->flags & TCFLAGS_CHECKED_EQ_OPR) &&
       typentry->btree_opf == InvalidOid)
       flags |= TYPECACHE_HASH_OPFAMILY;
   ```

   Equality can come from either the btree (`BTEqualStrategyNumber`)
   or hash (`HTEqualStrategyNumber`) opclass. Most types have both; if
   btree is missing we need hash to satisfy the eq request.

2. **Re-checking on every call.** If `TCFLAGS_CHECKED_BTREE_OPCLASS`
   is set, the block is skipped — we trust the cached opclass. If
   the inval callback (`TypeCacheOpcCallback`, see below) ever sees a
   `pg_opclass` change, it clears all `TCFLAGS_OPERATOR_FLAGS`, which
   includes `TCFLAGS_CHECKED_BTREE_OPCLASS`, forcing re-lookup.

### Array / record equality awareness [typcache.c:658-664]

A subtle special case: if the equality operator resolves to
`ARRAY_EQ_OP` or `RECORD_EQ_OP`, we additionally check that the
contained element/field types themselves have equality:

```c
if (eq_opr == ARRAY_EQ_OP &&
    !array_element_has_equality(typentry))
    eq_opr = InvalidOid;
else if (eq_opr == RECORD_EQ_OP &&
         !record_fields_have_equality(typentry))
    eq_opr = InvalidOid;
```

Without this check, `lookup_type_cache(some_array_of_X)` for an X
that has no `=` operator would report "yes, this type has eq, it's
`array_eq`" — and `array_eq` would then fail at runtime trying to
call the missing element-type comparison. The comment at
typcache.c:652-657 calls this out.

The `array_element_has_equality` machinery
[typcache.c:1534-1593] recursively `lookup_type_cache`s the element
type (which is why we need the in_progress_list for the recursive
calls). Results are cached via the `TCFLAGS_HAVE_ELEM_EQUALITY` /
`TCFLAGS_HAVE_FIELD_EQUALITY` bits — once derived, never recomputed
until invalidated.

### FmgrInfo pre-build [typcache.c:73-79 banner + scattered]

When `TYPECACHE_EQ_OPR_FINFO` is requested, the cache pre-fills
`typentry->eq_opr_finfo`:

```c
fmgr_info_cxt(typentry->eq_opr, &typentry->eq_opr_finfo,
              CacheMemoryContext);
```

The pre-built `FmgrInfo` lives in `CacheMemoryContext` (process-
lifetime), so it survives across queries and transactions. This is
the entire point of the cache for index-support routines like
`array_eq`, `record_cmp`, `hash_array`: they can't leak memory and
they want to call `FunctionCall1(&finfo, …)` directly with no
per-call setup. The cache holds the warm `FmgrInfo`.

`load_rangetype_info` [typcache.c:998-1050] does the same for
`rng_cmp_proc_finfo`, `rng_canonical_finfo`, `rng_subdiff_finfo`.

### The composite type path [typcache.c:962-993]

`load_typcache_tupdesc` is invoked when `TYPECACHE_TUPDESC` is
requested for a composite type:

```c
rel = relation_open(typentry->typrelid, AccessShareLock);
typentry->tupDesc = RelationGetDescr(rel);
typentry->tupDesc->tdrefcount++;        /* manual bump — NOT IncrTupleDescRefCount */
typentry->tupDesc_identifier = ++tupledesc_id_counter;
relation_close(rel, AccessShareLock);
```

Three things to note:

1. **The tupdesc is shared with the relcache.** `RelationGetDescr`
   returns the relcache's tupdesc; the type cache just borrows it
   with a manual refcount bump.

2. **The refcount bump is NOT entered in `CurrentResourceOwner`**
   [comment at typcache.c:976-979]. The reference can outlive the
   query that triggered the lookup, so per-query resource ownership
   would be wrong. The refcount is manually balanced in
   `InvalidateCompositeTypeCacheEntry` (see
   [[typcache-domain-and-invalidation]]).

3. **`tupDesc_identifier` is a monotonic counter** — every time we
   reload the tupdesc, we mint a new unique ID. Callers who cache
   data derived from the tupdesc can check `tupDesc_identifier` to
   see if it changed (a comparison cheaper than tupdesc equality).
   See `assign_record_type_identifier` in
   [[typcache-record-typmod-and-shared]].

### The domain-type list [typcache.c:509-514]

When a new entry is created for a domain type, it's threaded into a
singly-linked list:

```c
if (typentry->typtype == TYPTYPE_DOMAIN) {
    typentry->nextDomain = firstDomainTypeEntry;
    firstDomainTypeEntry = typentry;
}
```

This list is used by `TypeCacheConstrCallback`
[typcache.c:2628-2646] to walk only the domains during pg_constraint
invalidation — far cheaper than `hash_seq_search` over the full
TypeCacheHash. Domains are rare in production workloads but
pg_constraint invalidations are frequent (every table constraint
change fires one), so this list pays off.

## `RelIdToTypeIdCacheHash` — the reverse index

The secondary map [typcache.c:87-93]:

```c
typedef struct RelIdToTypeIdCacheEntry
{
    Oid relid;             /* the relation OID */
    Oid composite_typid;   /* the matching composite type OID */
} RelIdToTypeIdCacheEntry;
```

Why exists: `TypeCacheRelCallback(relid)` needs to invalidate the
typcache entry whose `typrelid == relid`. With only `TypeCacheHash`
keyed by type OID, we'd have to scan every entry. The reverse map
gives O(1) lookup from relid to type OID.

But only **composite** types with **active state** need entries.
`insert_rel_type_cache_if_needed` [typcache.c:3093-3119] guards the
insert:

```c
if (typentry->typtype != TYPTYPE_COMPOSITE) return;
if ((typentry->flags & TCFLAGS_HAVE_PG_TYPE_DATA) ||
    (typentry->flags & TCFLAGS_OPERATOR_FLAGS) ||
    typentry->tupDesc != NULL)
{
    /* HASH_ENTER */
}
```

— and `delete_rel_type_cache_if_needed` [typcache.c:3127-3183]
removes it when all three drops to false. This is what keeps the
reverse map from holding stale entries for never-used composite
types.

The comment at typcache.c:2432-2435 explains why we can't just use
the syscache to find the type by relid during inval: "the code can
be called outside of transaction", so syscache isn't available.

## Invariants

- **`type_id` is the hash key and must be the first field.**
  `MemSet(typentry, 0, sizeof(TypeCacheEntry))` happens at creation
  but `type_id` is then re-set to the actual OID. The hash table
  uses `sizeof(Oid)` keysize.
- **TypeCacheEntry pointers are stable** for the life of the
  backend. Other modules' caches can store them long-lived.
- **`tupDesc_identifier` of 0 means "not yet determined"; 1
  (`INVALID_TUPLEDESC_IDENTIFIER`) is also reserved**
  [typcache.h:157]. Valid IDs start at 2.
- **`typtype` and `typrelid` are treated as constant** — the
  comment at typcache.c:540-541 says "many of these fields shouldn't
  ever change, particularly typtype, but copy 'em anyway" on reload.
- **`TCFLAGS_CHECKED_X` means "we tried"; the value of the field
  may still be `InvalidOid`** — e.g. a type with no btree opclass
  gets `TCFLAGS_CHECKED_BTREE_OPCLASS` set but `btree_opf = InvalidOid`.
  Caller must check the field, not just the flag.
- **`in_progress_list` is finalized at end of (sub)transaction**
  via `AtEOXact_TypeCache` / `AtEOSubXact_TypeCache`. If lookup
  errors out, the list is left until then.
- **`firstDomainTypeEntry` is the head of the linked-list of all
  domain-type entries** — used by `TypeCacheConstrCallback` and the
  domain-over-composite invalidation walk in `TypeCacheRelCallback`.

## Useful greps

```bash
# Find every TYPECACHE_* flag caller and what they request:
grep -RnE 'lookup_type_cache\(' source/src/backend | head -50

# Discover which subsystems hold long-lived TypeCacheEntry pointers:
grep -RnE 'TypeCacheEntry \*' source/src/include source/src/backend/utils

# Spot the four cache-invalidation registrations:
grep -nE 'CacheRegister(Relcache|Syscache)Callback' \
    source/src/backend/utils/cache/typcache.c

# Inspect what the typcache costs at runtime:
#   psql -c 'SELECT * FROM pg_backend_memory_contexts WHERE name LIKE '%type%';'
#   gdb> p TypeCacheHash->hctl->nentries
```

## Cross-references

- [[typcache-record-typmod-and-shared]] — `RecordCacheArray` keyed by
  typmod, `assign_record_type_typmod`, the parallel-worker shared
  registry (`SharedRecordTypmodRegistry`).
- [[typcache-domain-and-invalidation]] — domain constraint loading
  (`load_domaintype_info`), the four cache-inval callbacks, the
  `DomainConstraintCache` refcounting and the
  `DomainConstraintRef`-via-MemoryContextCallback pattern.
- [[cache-invalidation-registration]] — the `CacheRegisterXxxCallback`
  framework this module hooks into.
- [[sinvaladt-broadcast]] — how cache invalidation messages reach this
  backend.
- [[memory-context-api-and-dispatch]] — `CacheMemoryContext` is where
  the typcache lives.
- [[fmgr]] — `FmgrInfo` and `fmgr_info_cxt` semantics; the typcache
  is one of the biggest holders of pre-built `FmgrInfo` structs.
- [[catalog-conventions]] — `GetDefaultOpClass`, `get_opclass_family`,
  `get_opfamily_member` are the underlying opclass lookups.
