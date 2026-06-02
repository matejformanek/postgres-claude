# `SearchSysCache1(PROCOID, ...)` — release rules and miss behavior

Two things you need to do, plus an answer on the miss case.

## 1. You MUST call `ReleaseSysCache(tuple)` before returning

Every successful `SearchSysCache*` (the non-`Copy` variants) returns a pinned tuple from the catcache. The pin is reference-counted, and if you don't pair it with `ReleaseSysCache`, the system logs a "cache reference leak" warning at transaction end (the resowner cleanup catches it but complains loudly). Pattern:

```c
HeapTuple   tup;
Form_pg_proc procform;

tup = SearchSysCache1(PROCOID, ObjectIdGetDatum(funcoid));
if (!HeapTupleIsValid(tup))
    ereport(ERROR,
            (errcode(ERRCODE_UNDEFINED_FUNCTION),
             errmsg("function with OID %u does not exist", funcoid)));

procform = (Form_pg_proc) GETSTRUCT(tup);
/* read fields out of procform here */
/* if you need varlena fields (proargnames, etc.), use
 * SysCacheGetAttr while the tuple is still pinned */

ReleaseSysCache(tup);
return result;
```

Key rules:

- The tuple is only valid **between** `SearchSysCache1` and `ReleaseSysCache`. After release, the catcache may evict / invalidate it.
- Any **pointers into the tuple** (e.g. `procform->proname`, or varlena pointers obtained via `SysCacheGetAttr`) become invalid the moment you release. If you need them to outlive the release, either copy them (`pstrdup`, `datumCopy`) or use `SearchSysCacheCopy1` instead — which returns a palloc'd copy in `CurrentMemoryContext` that you free with `heap_freetuple` (or just let the context reset).
- Don't `pfree`/`heap_freetuple` the non-Copy result. It's not your memory.

## 2. Miss behavior

A miss is **not** an error from the syscache's point of view — `SearchSysCache1` returns `NULL` (i.e. an invalid `HeapTuple`). You check with `HeapTupleIsValid(tup)`. It's your job to decide whether the miss is an error in your context:

- If the OID was supposed to exist (e.g. it came from another catalog row that points at this proc), it's a "cache lookup failed for function %u" — by convention `elog(ERROR, "cache lookup failed for function %u", funcoid)` for "should never happen" misses, or `ereport(ERROR, ...)` with `ERRCODE_UNDEFINED_FUNCTION` if it could plausibly be user-triggered.
- If you're just probing existence, use `SearchSysCacheExists1` instead and skip the release/lookup overhead.

## 3. Negative caching is free

The catcache caches misses too (negative entries). So a probe loop or repeated existence check on the same OID won't hammer the heap on every call.

## 4. Cross-backend coherence is automatic

You don't need to worry about another backend updating the row underneath you mid-transaction: shared-invalidation messages from `inval.c` flush entries on catalog mutation, and `AcceptInvalidationMessages` is called at lock acquisition. Within your transaction, you see a stable snapshot of the tuple for the duration of your pin.

## TL;DR

- Yes: pair every successful `SearchSysCache1` with `ReleaseSysCache(tup)` before returning (or before any code path that might `ereport` and longjmp away — though the resowner cleans up on error, the warning still fires in some paths; clean release on the success path is the discipline).
- Miss: `NULL` return, `HeapTupleIsValid` is false; you decide whether to error.
- If you need the tuple beyond the release, use `SearchSysCacheCopy1` (palloc'd copy) instead and free with `heap_freetuple`.
- Use `SearchSysCacheExists1` for pure existence checks.
- Use `GetSysCacheOid1` if you only want the row's OID, not the tuple.
