# Eval 3 — baseline (no skill)

**Prompt:** `SearchSysCache1(PROCOID, ObjectIdGetDatum(funcoid))`,
read some fields, what do I need to do before returning, and what
happens if the row doesn't exist?

## Answer

### Before returning

If `SearchSysCache1` returned a valid tuple, you have to call
`ReleaseSysCache(tup)` before any return path. Otherwise you'll get
"cache reference leak" warnings at end of transaction — the syscache
keeps a pin on the tuple and you're responsible for releasing it.

```c
HeapTuple tup = SearchSysCache1(PROCOID, ObjectIdGetDatum(funcoid));
if (!HeapTupleIsValid(tup))
    elog(ERROR, "cache lookup failed for function %u", funcoid);

Form_pg_proc proc = (Form_pg_proc) GETSTRUCT(tup);
Oid rettype = proc->prorettype;

ReleaseSysCache(tup);
return rettype;
```

Note that `GETSTRUCT(tup)` (and anything from `SysCacheGetAttr` that
returns a varlena pointing into the tuple) is only valid until the
release call — don't dereference after release. If you need the data
longer, copy it out (pstrdup, datumCopy, …) or use
`SearchSysCacheCopy1` which returns a palloc'd copy of the tuple that
you free with `heap_freetuple` instead.

### If the row doesn't exist

You get an invalid HeapTuple back — `HeapTupleIsValid(tup)` is false.
The syscache itself doesn't raise an error; it's up to you to decide
what to do.

Two conventions in the backend:
- For "this should never happen" callers: `elog(ERROR, "cache lookup
  failed for function %u", funcoid)`. This is the universal wording.
- For lookups that can legitimately miss because of user input:
  `ereport(ERROR, (errcode(ERRCODE_UNDEFINED_FUNCTION), errmsg(...)))`
  so you get a proper SQLSTATE.

If you only care whether the row exists, use
`SearchSysCacheExists1(PROCOID, ObjectIdGetDatum(funcoid))` — it
returns a bool and you don't have to release anything.

### Cross-backend coherence

You don't have to do anything for invalidation in the normal case.
Updates done through `CatalogTupleUpdate` / `heap_update` emit shared
invalidation messages, and other backends invalidate their cached
copies at the next command boundary.
