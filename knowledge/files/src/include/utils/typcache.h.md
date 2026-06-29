# typcache.h

- **Source path:** `source/src/include/utils/typcache.h`
- **Lines:** 215
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `typcache.c` (impl), `access/tupdesc.h` (TupleDesc), `lib/dshash.h` (shared rowtype registry).

## Purpose

Defines `TypeCacheEntry` (the fat per-type record), the `TYPECACHE_*` flag set telling `lookup_type_cache` what to populate, `DomainConstraintRef` for callers that want to track domain constraints over the long term, and the `SharedRecordTypmodRegistry` opaque type for parallel workers.

## Top-of-file comment

> "Type cache definitions. The type cache exists to speed lookup of certain information about data types that is not directly available from a type's pg_type row." [typcache.h:3-7]

## Public surface

- **Types**: `TypeCacheEntry` (31), `DomainConstraintRef` (165), opaque `DomainConstraintCache`, opaque `SharedRecordTypmodRegistry`.
- **`TYPECACHE_*` bit flags** (138-154): `EQ_OPR`, `LT_OPR`, `GT_OPR`, `CMP_PROC`, `HASH_PROC`, `EQ_OPR_FINFO`, `CMP_PROC_FINFO`, `HASH_PROC_FINFO`, `TUPDESC`, `BTREE_OPFAMILY`, `HASH_OPFAMILY`, `RANGE_INFO`, `DOMAIN_BASE_INFO`, `DOMAIN_CONSTR_INFO`, `HASH_EXTENDED_PROC`, `HASH_EXTENDED_PROC_FINFO`, `MULTIRANGE_INFO`.
- **Constant**: `INVALID_TUPLEDESC_IDENTIFIER ((uint64) 1)` (157) — sentinel for `tupDesc_identifier`.
- **Functions**: `lookup_type_cache(type_id, flags)`, `InitDomainConstraintRef`, `UpdateDomainConstraintRef`, `DomainHasConstraints`, `lookup_rowtype_tupdesc{,_noerror,_copy,_domain}`, `assign_record_type_typmod`, `assign_record_type_identifier`, `compare_values_of_enum`, `SharedRecordTypmodRegistry{Estimate,Init,Attach}`, `AtEOXact_TypeCache`, `AtEOSubXact_TypeCache`.

## Key types

- **`TypeCacheEntry`** (31) — `type_id` must be FIRST (it's the hashtable key) [from-comment, line 33]. Holds pg_type basics, default btree/hash opclass info, the equality/comparison/hash op and proc oids + their pre-set-up FmgrInfos, composite `tupDesc` (reference-counted) + `tupDesc_identifier`, range type fields, multirange type fields, domain base type + typmod, `domainData` (pointer to `DomainConstraintCache`), private `flags` bitmask, `enumData`, `nextDomain` (for the linked domain list).
- **`DomainConstraintRef`** (165) — caller-held handle into a domain's constraints. Includes a `MemoryContextCallback` that releases the typcache's refcount on the constraint set when the caller's context is reset. Required because constraint sets can be invalidated and replaced while a caller still references them. [from-comment, typcache.h:159-164]

## Key invariants

- **Pointer stability** of `TypeCacheEntry`s — guaranteed for the backend's lifetime, mirrored by the impl-file comment. The pointer can be cached anywhere.
- **`tupDesc` for composites is reference-counted.** [from-comment, typcache.h:82-85] Callers that need to hold onto it across cache flushes must use the refcount; `lookup_rowtype_tupdesc_copy` exists for callers that just want a one-shot owned copy.
- **`tupDesc_identifier`** is unique-for-life-of-process and changes whenever the tupdesc does — used to cheaply detect "did this row type change?" without examining the full tupdesc. [from-comment, typcache.h:86-88]
- **`DomainConstraintState`** lives in execnodes.h (not here) because it's an executable expression type. [from-comment, typcache.h:162-163]

## Confidence tag tally

verified-by-code: 2 — from-comment: 5 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [idioms/typcache-domain-and-invalidation.md](../../../../idioms/typcache-domain-and-invalidation.md)
- [idioms/typcache-entry-and-lookup.md](../../../../idioms/typcache-entry-and-lookup.md)
