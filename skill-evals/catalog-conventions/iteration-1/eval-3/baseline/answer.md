# `SearchSysCache1(PROCOID, ...)` — what next

## Release the tuple

Yes, you need to release the cached tuple before returning. The pattern is:

```c
HeapTuple tup = SearchSysCache1(PROCOID, ObjectIdGetDatum(funcoid));
if (!HeapTupleIsValid(tup))
{
    /* handle miss */
}
Form_pg_proc procform = (Form_pg_proc) GETSTRUCT(tup);
/* ... read fields ... */
ReleaseSysCache(tup);
```

If you forget `ReleaseSysCache`, you'll get a "cache reference leak" warning at transaction commit/abort. The cache reference count system tracks this.

## Don't dereference after release

After `ReleaseSysCache`, the tuple pointer is no longer valid — the cache is free to evict it. If you need the data to survive longer than the lookup, either:

- Copy the fields you care about into your own memory (`pstrdup` for strings, etc.) before releasing.
- Use `SearchSysCacheCopy1` instead, which returns a palloc'd copy that you free with `heap_freetuple`.

## Miss behavior

A cache miss returns an invalid HeapTuple — `HeapTupleIsValid(tup)` returns false. It's not raised as an error automatically. You decide what to do:

- If it's a "should never happen" case (e.g. the OID came from another catalog), the convention is `elog(ERROR, "cache lookup failed for function %u", funcoid)`.
- If it's user-triggerable, raise a proper `ereport` with `ERRCODE_UNDEFINED_FUNCTION` and a translatable message.

## Other useful variants

- `SearchSysCacheExists1` — boolean existence probe; no release needed.
- `GetSysCacheOid1` — returns the OID column directly.
- `SearchSysCacheCopy1` — returns a freshly palloc'd copy you must free with `heap_freetuple`.

## Concurrency

The syscache is per-backend but shared-invalidation messages keep it coherent across backends — you don't need to worry about other backends modifying pg_proc behind your back within your transaction.
