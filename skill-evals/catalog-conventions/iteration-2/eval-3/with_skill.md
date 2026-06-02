# Eval 3 — with skill

**Prompt:** `SearchSysCache1(PROCOID, ObjectIdGetDatum(funcoid))`,
read some fields, what do I need to do before returning, and what
happens if the row doesn't exist?

## Answer

### Before returning: release the pin

Every `SearchSysCache*` call that returns a *valid* tuple MUST be
paired with `ReleaseSysCache(tup)` before that path returns. If you
forget, you'll get a "cache reference leak" warning at transaction
end:

```c
HeapTuple tup = SearchSysCache1(PROCOID, ObjectIdGetDatum(funcoid));
if (!HeapTupleIsValid(tup))
    elog(ERROR, "cache lookup failed for function %u", funcoid);

Form_pg_proc proc = (Form_pg_proc) GETSTRUCT(tup);
Oid rettype = proc->prorettype;       /* fixed-size, safe to copy out  */
NameData proname = proc->proname;     /* fixed-size, safe                */
/* anything from SysCacheGetAttr that returns a varlena Datum points
   into the tuple too — copy out before release if you need it longer */

ReleaseSysCache(tup);   /* <-- mandatory */

return rettype;
```

The "valid tuple" qualifier matters: if `HeapTupleIsValid(tup)` is
false, there's nothing to release. You only release after a successful
lookup.

### Pointer lifetime

`Form_pg_proc` (= `GETSTRUCT(tup)`) points directly into the cached
tuple. Anything from `SysCacheGetAttr` that returns a varlena Datum
also points into the tuple. **None of those pointers are valid after
`ReleaseSysCache`.** If you need them past the release:

- Copy scalar values out into locals (as above with `rettype`).
- For strings: `pstrdup(NameStr(proc->proname))`.
- For Datums: `datumCopy(d, typbyval, typlen)`.
- Or use **`SearchSysCacheCopy1`** instead — it returns a palloc'd
  copy of the tuple living in the current memory context, with
  arbitrary lifetime. You then free it with `heap_freetuple(tup)`
  (NOT `ReleaseSysCache` — there's no pin to release).

```c
HeapTuple tup = SearchSysCacheCopy1(PROCOID, ObjectIdGetDatum(funcoid));
/* ... use tup arbitrarily long ... */
heap_freetuple(tup);
```

### What if the row doesn't exist

A miss returns an invalid `HeapTuple` — i.e. `HeapTupleIsValid(tup) ==
false`, or equivalently `tup == NULL` on most paths. This is **not an
error from the syscache itself** — the cache reports "not found", and
the caller decides whether that's an error and what flavor.

Two conventions in the backend:

- **"Should never happen" caller invariant** — use plain `elog`:
  ```c
  elog(ERROR, "cache lookup failed for function %u", funcoid);
  ```
  This is the standard wording. `git grep "cache lookup failed for"`
  shows hundreds of instances.

- **User-triggerable miss** — use `ereport` with a real SQLSTATE so
  client code can react:
  ```c
  ereport(ERROR,
          (errcode(ERRCODE_UNDEFINED_FUNCTION),
           errmsg("function with OID %u does not exist", funcoid)));
  ```

### Other relevant syscache APIs

- **Pure existence check** (don't need the tuple): `SearchSysCacheExists1`.
  Returns bool, no release needed.
- **Just want the OID** of the matching row (e.g. by name): `GetSysCacheOid1`.
- **Multi-key lookups**: `SearchSysCache2/3/4`, with their `…Exists`,
  `…Copy`, `…Attr` variants.

### Cross-backend coherence

You don't need to do anything special for invalidation. Catalog
updates performed through the normal `heap_update` /
`CatalogTupleUpdate` paths emit shared invalidation messages, and
other backends drop their stale syscache entries automatically at the
next command boundary. Manual `CacheInvalidateHeapTuple` calls are
only needed in unusual paths.
