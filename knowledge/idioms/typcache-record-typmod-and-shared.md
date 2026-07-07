# RECORD typmod registry and the shared parallel-worker variant

The typcache's regular hashtable is keyed by `pg_type.oid`, which works
fine for named composite types (every `CREATE TABLE foo (...)` creates
a pg_type row with a stable OID). But anonymous **record types** — the
ones produced by `ROW(a, b, c)`, `SELECT * FROM (VALUES ...) t(...)`,
`RETURNS TABLE (a int, b text)`, etc. — have no row in pg_type.
Postgres represents them all with `type_id = RECORDOID = 2249` and
disambiguates them with a per-backend `typmod` integer assigned at
first use.

The infrastructure that hands out these typmods, stores the
corresponding `TupleDesc`s, and lets `lookup_rowtype_tupdesc(RECORDOID,
typmod)` reverse-look-them-up lives in typcache.c. There are two layers:

1. **Per-backend** — `RecordCacheArray` indexed by typmod plus a
   `RecordCacheHash` hashtable for finding-by-content.
2. **Parallel-query shared** — `SharedRecordTypmodRegistry` in DSA,
   so parallel workers and the leader see consistent typmods for the
   record types they pass to each other through tuple queues.

This doc covers both. For the per-named-type `TypeCacheEntry` lookup
path, see [[typcache-entry-and-lookup]]. For domain handling and
cache invalidation, see [[typcache-domain-and-invalidation]].

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

- `source/src/backend/utils/cache/typcache.c:161-225` — the four
  record-cache types (`RecordCacheEntry`, `SharedRecordTypmodRegistry`,
  `SharedRecordTableKey`, `SharedRecordTableEntry`,
  `SharedTypmodTableEntry`).
- `source/src/backend/utils/cache/typcache.c:274-313` — module globals
  (`RecordCacheArray`, `RecordCacheHash`, `NextRecordTypmod`,
  `tupledesc_id_counter`).
- `source/src/backend/utils/cache/typcache.c:1817-1837` —
  `ensure_record_cache_typmod_slot_exists` (the array grower).
- `source/src/backend/utils/cache/typcache.c:1846-1922` —
  `lookup_rowtype_tupdesc_internal` (the search path).
- `source/src/backend/utils/cache/typcache.c:1940-2027` —
  the four public `lookup_rowtype_tupdesc*` variants.
- `source/src/backend/utils/cache/typcache.c:2060-2185` —
  `assign_record_type_typmod` and `assign_record_type_identifier`.
- `source/src/backend/utils/cache/typcache.c:2192-2372` —
  `SharedRecordTypmodRegistry{Estimate,Init,Attach}`.
- `source/src/backend/utils/cache/typcache.c:2940-3087` —
  shared-tupledesc helpers (`share_tupledesc`,
  `find_or_make_matching_shared_tupledesc`,
  `shared_record_typmod_registry_detach`).

## Why two storage layers per backend

```c
/* hashtable for recognizing registered record types */
static HTAB *RecordCacheHash = NULL;

typedef struct RecordCacheArrayEntry {
    uint64    id;          /* unique tupdesc identifier */
    TupleDesc tupdesc;
} RecordCacheArrayEntry;

/* array of info about registered record types, indexed by assigned typmod */
static RecordCacheArrayEntry *RecordCacheArray = NULL;
static int32 RecordCacheArrayLen = 0;
static int32 NextRecordTypmod = 0;
```

Two access patterns demand two structures:

- **Lookup by typmod** (`lookup_rowtype_tupdesc(RECORDOID, typmod)`,
  the hot path in record I/O) — `O(1)` array access. The array is
  power-of-2-sized and grown via `pg_nextpower2_32(typmod + 1)`.
- **Lookup by content** (`assign_record_type_typmod(tupDesc)`, "have
  I seen this exact shape before?") — needs a hashtable. The
  `RecordCacheHash` is keyed by `TupleDesc` pointer with a custom
  hash function `record_type_typmod_hash` [typcache.c:2030-2049] that
  uses `hashRowType(tupdesc)` to compute the hash from the shape, and
  `record_type_typmod_compare` that uses `equalRowTypes` to test
  equality.

The two structures share the same `TupleDesc` storage — the hashtable
entry holds a pointer that matches an entry in the array. Both die
at backend exit; there is no inter-backend persistence except via the
shared registry.

`NextRecordTypmod` is the watermark for typmod assignment — the
next value to hand out. Monotonically increasing. Never recycled,
because a process might still hold a `TupleDesc *` referring to an
old typmod.

## `ensure_record_cache_typmod_slot_exists` — the array grower

```c
static void
ensure_record_cache_typmod_slot_exists(int32 typmod)
{
    if (RecordCacheArray == NULL) {
        RecordCacheArray = MemoryContextAllocZero(CacheMemoryContext,
                                                  64 * sizeof(RecordCacheArrayEntry));
        RecordCacheArrayLen = 64;
    }
    if (typmod >= RecordCacheArrayLen) {
        int32 newlen = pg_nextpower2_32(typmod + 1);
        RecordCacheArray = repalloc0_array(RecordCacheArray,
                                           RecordCacheArrayEntry,
                                           RecordCacheArrayLen, newlen);
        RecordCacheArrayLen = newlen;
    }
}
```

Two design points:

- **Initial size 64** [typcache.c:1822-1824] — most backends will
  never use record types at all. 64 is small enough to be cheap if
  unused, big enough to avoid early growth.
- **`repalloc0_array` zero-initializes new slots** — `tupdesc =
  NULL` is the "unused" sentinel.

The array lives in `CacheMemoryContext` so it survives across
transactions; on backend exit it goes away with the rest of
`CacheMemoryContext`.

## `assign_record_type_typmod` — registering a shape

[typcache.c:2060-2139] is the routine called whenever code needs to
"name" an anonymous record type so it can be passed by typmod. The
canonical caller is `BlessTupleDesc` in `tupdesc.c`.

The flow:

```c
void
assign_record_type_typmod(TupleDesc tupDesc)
{
    Assert(tupDesc->tdtypeid == RECORDOID);

    /* 1. First-time init of RecordCacheHash. */

    /* 2. Search for matching shape (HASH_FIND, not HASH_ENTER). */
    recentry = hash_search(RecordCacheHash, &tupDesc, HASH_FIND, &found);
    if (found && recentry->tupdesc != NULL) {
        tupDesc->tdtypmod = recentry->tupdesc->tdtypmod;
        return;       /* shape already known — reuse its typmod */
    }

    /* 3. Not known — manufacture a new entry. */
    oldcxt = MemoryContextSwitchTo(CacheMemoryContext);

    entDesc = find_or_make_matching_shared_tupledesc(tupDesc);  /* parallel path */
    if (entDesc == NULL) {
        /* purely local path: copy the tupdesc, assign next typmod */
        ensure_record_cache_typmod_slot_exists(NextRecordTypmod);
        entDesc = CreateTupleDescCopy(tupDesc);
        entDesc->tdrefcount = 1;
        entDesc->tdtypmod = NextRecordTypmod++;
    } else {
        ensure_record_cache_typmod_slot_exists(entDesc->tdtypmod);
    }

    RecordCacheArray[entDesc->tdtypmod].tupdesc = entDesc;
    RecordCacheArray[entDesc->tdtypmod].id = ++tupledesc_id_counter;

    /* Insert into the hash table */
    recentry = hash_search(RecordCacheHash, &tupDesc, HASH_ENTER, NULL);
    recentry->tupdesc = entDesc;

    tupDesc->tdtypmod = entDesc->tdtypmod;
    MemoryContextSwitchTo(oldcxt);
}
```

Three subtle points:

1. **HASH_FIND first, then HASH_ENTER** — the comment at
   typcache.c:2087-2091 explains: we don't `HASH_ENTER` upfront
   because we need to be sure the `CreateTupleDescCopy` succeeds
   before committing. If the copy throws OOM, we don't want a
   half-initialized hash entry.

2. **`CreateTupleDescCopy(tupDesc)` is a deep copy in
   `CacheMemoryContext`** — the caller's `tupDesc` may be transient
   (e.g., on the stack). We must own our copy permanently.

3. **The shared path** (`find_or_make_matching_shared_tupledesc`) is
   attempted before the local-only path. If we're attached to a
   shared registry, all typmod assignment goes there to keep
   leader/worker views consistent. See "The parallel-query shared
   registry" below.

After `assign_record_type_typmod` returns, the caller's `tupDesc`
has had `tdtypmod` filled in. The caller can now serialize tuples
of this shape using just `(RECORDOID, tdtypmod)` and the receiver
will resolve them via `lookup_rowtype_tupdesc(RECORDOID, tdtypmod)`.

## `lookup_rowtype_tupdesc` — the four flavors

Four public lookup functions:

| Function | Behavior on not-found | TupleDesc lifecycle |
|---|---|---|
| `lookup_rowtype_tupdesc` | `ereport(ERROR)` | refcount bumped; caller must `ReleaseTupleDesc` |
| `lookup_rowtype_tupdesc_noerror` | returns NULL | refcount bumped (if found) |
| `lookup_rowtype_tupdesc_copy` | `ereport(ERROR)` | returns a fresh copy in `CurrentMemoryContext`, no refcount tracking |
| `lookup_rowtype_tupdesc_domain` | ERROR / NULL | refcount bumped; follows domain-over-composite to base |

All four go through `lookup_rowtype_tupdesc_internal`
[typcache.c:1846-1922]:

```c
static TupleDesc
lookup_rowtype_tupdesc_internal(Oid type_id, int32 typmod, bool noError)
{
    if (type_id != RECORDOID) {
        /* Named composite type — use the regular TypeCacheEntry path */
        typentry = lookup_type_cache(type_id, TYPECACHE_TUPDESC);
        return typentry->tupDesc;
    }
    /* type_id == RECORDOID: anonymous record type by typmod */
    if (typmod >= 0) {
        /* (a) Local array hit? */
        if (typmod < RecordCacheArrayLen &&
            RecordCacheArray[typmod].tupdesc != NULL)
            return RecordCacheArray[typmod].tupdesc;

        /* (b) Try the shared typmod registry */
        if (CurrentSession->shared_typmod_registry != NULL) {
            entry = dshash_find(CurrentSession->shared_typmod_table,
                                &typmod, false);
            if (entry != NULL) {
                tupdesc = (TupleDesc) dsa_get_address(CurrentSession->area,
                                                     entry->shared_tupdesc);
                /* import into local cache */
                ensure_record_cache_typmod_slot_exists(typmod);
                RecordCacheArray[typmod].tupdesc = tupdesc;
                RecordCacheArray[typmod].id = ++tupledesc_id_counter;
                dshash_release_lock(CurrentSession->shared_typmod_table, entry);
                return tupdesc;
            }
        }
    }
    /* Nothing matched */
    if (!noError) ereport(ERROR, "record type has not been registered");
    return NULL;
}
```

The "import into local cache" step is important: once we've fetched a
shared TupleDesc, subsequent lookups in this backend bypass the
dshash and hit the array directly. The shared tupdesc's
`tdrefcount = -1` [comment at typcache.c:1900] — refcounting is
disabled because the dsa-backed memory has fixed lifetime tied to
the dsm segment, not to PG's refcount-and-free logic.

The four public variants differ only in error policy and refcount
handling. `_copy` is interesting: when callers need to mutate a
tupdesc (e.g., to set a different `tdtypeid` or tweak attribute
flags), they must copy first because the cached tupdesc is read-only
from the caller's perspective — modifying it would corrupt the cache.

`lookup_rowtype_tupdesc_domain` [typcache.c:1995-2027] handles the
case where a typmod-less domain-over-composite is passed:

```c
if (typentry->typtype == TYPTYPE_DOMAIN)
    return lookup_rowtype_tupdesc_noerror(typentry->domainBaseType,
                                          typentry->domainBaseTypmod,
                                          noError);
```

It recurses on the base type. The comment at typcache.c:1990-1993
explains why this isn't folded into plain `lookup_rowtype_tupdesc`:
callers need to know they're dealing with a domain so they can
apply domain CHECK constraints.

## `assign_record_type_identifier` — change-detection IDs

[typcache.c:2151-2185] hands out `tupDesc_identifier` values:

- **Named composite type**: returns
  `typentry->tupDesc_identifier`. Incremented every time
  `load_typcache_tupdesc` reloads, so callers detect "the underlying
  rowtype changed".
- **Registered RECORD type**: returns `RecordCacheArray[typmod].id`,
  which is stable for the life of the typmod (record types don't
  morph — a new shape gets a new typmod).
- **Anonymous unregistered RECORD**: `++tupledesc_id_counter` —
  always-fresh ID, every call. Caller must register the type to get
  a stable ID.

Use case: a SPI cursor caches a per-tupdesc plan or expression state
tree. To detect when the underlying tupdesc has changed (e.g., after
ALTER TABLE on the composite type), the SPI caches the
`tupDesc_identifier` alongside its plan and re-checks it on every
use. If it differs, invalidate the plan.

`INVALID_TUPLEDESC_IDENTIFIER = 1` [typcache.h:157] is reserved — the
counter starts there and increments to 2 before being handed out.
0 is also reserved (the "not yet determined" sentinel). So valid IDs
start at 2 and grow monotonically.

## The parallel-query shared registry

When a parallel query starts, the leader needs to ensure that any
record types its workers might encounter are visible by the same
typmod. Otherwise leader's typmod 17 might refer to a different
shape than worker's typmod 17, and tuple-passing across the worker
boundary would corrupt the data.

`SharedRecordTypmodRegistry` [typcache.c:181-189] is the answer:

```c
struct SharedRecordTypmodRegistry
{
    dshash_table_handle record_table_handle;   /* hash by tupdesc shape */
    dshash_table_handle typmod_table_handle;   /* hash by typmod */
    pg_atomic_uint32 next_typmod;              /* counter */
};
```

It uses `dshash` (Dynamic Shared Hash, a hash table in DSA segments)
for both indices. The `pg_atomic_uint32 next_typmod` is the shared
counter — workers and leader atomically allocate typmods from it.

### Init (leader) [typcache.c:2214-2305]

The leader calls `SharedRecordTypmodRegistryInit` after creating the
DSM segment for the parallel context:

```c
void
SharedRecordTypmodRegistryInit(SharedRecordTypmodRegistry *registry,
                               dsm_segment *segment,
                               dsa_area *area)
{
    Assert(!IsParallelWorker());

    /* 1. Create both dshash tables in shared memory. */
    record_table = dshash_create(area, &srtr_record_table_params, area);
    typmod_table = dshash_create(area, &srtr_typmod_table_params, NULL);

    /* 2. Seed next_typmod with the leader's local NextRecordTypmod. */
    pg_atomic_init_u32(&registry->next_typmod, NextRecordTypmod);

    /* 3. Copy all entries from leader's RecordCacheArray into shared. */
    for (typmod = 0; typmod < NextRecordTypmod; ++typmod) {
        tupdesc = RecordCacheArray[typmod].tupdesc;
        if (tupdesc == NULL) continue;
        shared_dp = share_tupledesc(area, tupdesc, typmod);
        /* Insert into typmod_table and record_table */
    }

    /* 4. Switch this backend to using the shared registry. */
    CurrentSession->shared_record_table = record_table;
    CurrentSession->shared_typmod_table = typmod_table;
    CurrentSession->shared_typmod_registry = registry;

    /* 5. Register on-detach hook for cleanup. */
    on_dsm_detach(segment, shared_record_typmod_registry_detach, (Datum) 0);
}
```

`share_tupledesc` [typcache.c:2940-2960] is the deep-copy-into-DSA
helper:

```c
static dsa_pointer
share_tupledesc(dsa_area *area, TupleDesc tupdesc, uint32 typmod)
{
    dsa_pointer shared_dp = dsa_allocate(area, TupleDescSize(tupdesc));
    TupleDesc shared_tupdesc = dsa_get_address(area, shared_dp);
    TupleDescCopy(shared_tupdesc, tupdesc);
    shared_tupdesc->tdtypmod = typmod;
    /* shared tupdescs are NOT reference-counted */
    shared_tupdesc->tdrefcount = -1;
    return shared_dp;
}
```

The `tdrefcount = -1` marker says "don't try to bump or release
this — it lives until DSM segment detach".

### Attach (worker) [typcache.c:2313-2372]

Each parallel worker, after attaching to the DSM segment, calls
`SharedRecordTypmodRegistryAttach`:

```c
void
SharedRecordTypmodRegistryAttach(SharedRecordTypmodRegistry *registry)
{
    Assert(IsParallelWorker());
    Assert(NextRecordTypmod == 0);   /* worker must have empty local cache */

    record_table = dshash_attach(CurrentSession->area,
                                 &srtr_record_table_params,
                                 registry->record_table_handle,
                                 CurrentSession->area);
    typmod_table = dshash_attach(CurrentSession->area,
                                 &srtr_typmod_table_params,
                                 registry->typmod_table_handle,
                                 NULL);

    on_dsm_detach(CurrentSession->segment,
                  shared_record_typmod_registry_detach,
                  PointerGetDatum(registry));

    CurrentSession->shared_typmod_registry = registry;
    CurrentSession->shared_record_table = record_table;
    CurrentSession->shared_typmod_table = typmod_table;
}
```

Two important asserts:

1. **`IsParallelWorker()`** — the function is for workers only.
2. **`NextRecordTypmod == 0`** — the worker must have a fresh local
   cache. The comment at typcache.c:2331-2339 explains: if the
   worker had locally-assigned typmods already, they would clash
   with the imported shared ones. Currently parallel workers are
   one-shot (one query then exit); if we ever recycled them, we'd
   need to flush local state between queries.

### `find_or_make_matching_shared_tupledesc` [typcache.c:2961-3066]

When the leader (or worker) calls `assign_record_type_typmod` after
attaching, this function intercepts:

1. **Build a `SharedRecordTableKey { shared=false, u.local_tupdesc=tupdesc }`.**
2. **Look it up in the shared `record_table`.** If found, the
   shared entry's key is `{ shared=true, u.shared_tupdesc=dp }`, and
   we resolve the dsa_pointer to find the TupleDesc that other
   backends know.
3. **If not found, allocate a new typmod atomically:**
   `typmod = pg_atomic_fetch_add_u32(&registry->next_typmod, 1)`.
   Insert into both tables and copy the tupdesc into DSA.

The `SharedRecordTableKey` union [typcache.c:197-205] is the clever
bit: by tagging shared vs. local in the key, the dshash hash and
compare functions [typcache.c:233-272] can transparently handle
"look up the shared entry using a local TupleDesc" — no need to
share the TupleDesc just to look up whether it exists.

```c
static uint32
shared_record_table_hash(const void *a, size_t size, void *arg)
{
    dsa_area *area = arg;
    const SharedRecordTableKey *k = a;
    TupleDesc t = k->shared
                ? (TupleDesc) dsa_get_address(area, k->u.shared_tupdesc)
                : k->u.local_tupdesc;
    return hashRowType(t);
}
```

Both sides of the union end up calling `hashRowType(t)` — the shape
hash is the same regardless of where the tupdesc lives.

### Detach cleanup

`shared_record_typmod_registry_detach` [typcache.c:3072-3087] runs
when the DSM segment detaches:

```c
if (CurrentSession->shared_record_table != NULL) {
    dshash_detach(CurrentSession->shared_record_table);
    CurrentSession->shared_record_table = NULL;
}
if (CurrentSession->shared_typmod_table != NULL) {
    dshash_detach(CurrentSession->shared_typmod_table);
    CurrentSession->shared_typmod_table = NULL;
}
CurrentSession->shared_typmod_registry = NULL;
```

Both leader and worker register the same hook
[typcache.c:2356-2363 worker, 2303-2304 leader]. After detach,
subsequent `assign_record_type_typmod` calls fall back to the
purely-local path; the typmods previously imported from the shared
registry remain in `RecordCacheArray` and are still usable for any
TupleDesc pointers that have been retained.

## Invariants

- **`RecordCacheArray` is monotonic.** `NextRecordTypmod` only
  grows; typmods are never recycled. A `(RECORDOID, typmod)` pair is
  stable for the life of the backend.
- **`tupDesc->tdtypeid == RECORDOID` before `assign_record_type_typmod`**
  — asserted at typcache.c:2067. The function refuses to assign a
  typmod to a named composite type.
- **Shared tupdescs have `tdrefcount == -1`** [typcache.c:1900,
  share_tupledesc]. Refcount tracking is bypassed because lifetime
  is DSM-bound, not refcount-bound.
- **Parallel workers must have empty local cache at attach time**
  [typcache.c:2340]. One-shot worker assumption.
- **`tupledesc_id_counter` is per-process** — IDs are not shared
  across backends. The shared registry imports tupdescs but assigns
  fresh local IDs at import [typcache.c:1906].
- **`assign_record_type_typmod` is the only entry point that ever
  hands out a new typmod** — and it does so atomically (`++` in
  local path or `pg_atomic_fetch_add_u32` in shared path).
- **Lookup falls back gracefully**: array → shared registry → error.
  The shared registry doesn't replace the array; it augments it.

## Useful greps

```bash
# Who calls assign_record_type_typmod? (Usually via BlessTupleDesc.)
grep -RnE 'assign_record_type_typmod|BlessTupleDesc' source/src/backend | head -20

# Who reads tupDesc_identifier for change detection?
grep -RnE 'tupDesc_identifier|tupdesc_identifier' source/src

# Inspect record-cache state at runtime (gdb):
#   (gdb) p NextRecordTypmod
#   (gdb) p RecordCacheArray[0..NextRecordTypmod-1]
#   (gdb) p CurrentSession->shared_typmod_registry

# Find the DSM detach hook registrations:
grep -nE 'shared_record_typmod_registry_detach' \
    source/src/backend/utils/cache/typcache.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 161 | the four record-cache types (RecordCacheEntry, SharedRecordTypmodRegistry, SharedRecordTableKey,... |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 274 | module globals (RecordCacheArray, RecordCacheHash, NextRecordTypmod, tupledesc_id_counter) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 1817 | ensure_record_cache_typmod_slot_exists (the array grower) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 1846 | lookup_rowtype_tupdesc_internal (the search path) |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 1940 | the four public lookup_rowtype_tupdesc variants |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2060 | assign_record_type_typmod and assign_record_type_identifier |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2192 | SharedRecordTypmodRegistry{Estimate,Init,Attach} |
| [`src/backend/utils/cache/typcache.c`](../files/src/backend/utils/cache/typcache.c.md) | 2940 | shared-tupledesc helpers (share_tupledesc, find_or_make_matching_shared_tupledesc,... |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- [[typcache-entry-and-lookup]] — the typed-by-OID path. Named
  composite types go through `lookup_type_cache(type_id,
  TYPECACHE_TUPDESC)` and not through `RecordCacheArray`.
- [[typcache-domain-and-invalidation]] — composite-type invalidation
  (`InvalidateCompositeTypeCacheEntry`) and how it affects cached
  tupdescs.
- [[parallel-context-and-dsm]] — `dsm_segment`, `dsa_area`, and the
  parallel-startup sequence that calls `SharedRecordTypmodRegistryInit`.
- [[parallel-state-propagation]] — what the worker startup sequence
  does just before calling `SharedRecordTypmodRegistryAttach`.
- [[memory-context-api-and-dispatch]] — `CacheMemoryContext` is
  where `RecordCacheArray` and the local cache copies live.
- [[fmgr]] — `RECORDOID` is the type that record_in/record_out etc.
  operate on; understanding the typmod registry is essential to
  reading those functions.
