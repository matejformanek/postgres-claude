# Eval 1 — baseline (no skill)

**Prompt:** Add builtin `pg_my_frobnitz(int4) returns int4`, full
workflow.

## Answer

To add a builtin SQL-visible function in PostgreSQL:

### C code

Pick a backend file that thematically fits (probably
`src/backend/utils/adt/int.c` for int4 stuff, or a new file if you're
adding a family of related functions). Write:

```c
PG_FUNCTION_INFO_V1(pg_my_frobnitz);

Datum
pg_my_frobnitz(PG_FUNCTION_ARGS)
{
    int32 x = PG_GETARG_INT32(0);
    /* ... */
    PG_RETURN_INT32(result);
}
```

The C symbol name has to match what you put in the catalog entry's
`prosrc` field.

### Catalog entry

You need a row in `src/include/catalog/pg_proc.dat`. You'll need to
pick an OID — there's a script `src/include/catalog/unused_oids` that
lists available ranges. Pick one in the high range that hackers
typically use for in-flight patches (I believe around the 6000-9000
band but check current convention). Add an entry like:

```
{ oid => '6789', descr => 'frobnitz function',
  proname => 'pg_my_frobnitz', prorettype => 'int4',
  proargtypes => 'int4', prosrc => 'pg_my_frobnitz',
  provolatile => 'i' },
```

You can override defaults like `provolatile`, `proisstrict`,
`proparallel` if needed.

### Bump catversion

Update `CATALOG_VERSION_NO` in `src/include/catalog/catversion.h`. The
format is a date-based integer (YYYYMMDDN). This is needed any time you
change catalog contents so existing data dirs don't silently break.

### Verify

Run `src/include/catalog/duplicate_oids` to make sure your OID isn't
already taken.

### Rebuild

Do a full rebuild so `genbki.pl` regenerates `postgres.bki` and the
`pg_*_d.h` headers. With meson, `ninja -C build`. With autoconf, `make`
from the top level. After a catversion bump you also need to re-initdb
because old data directories won't load with a different
`CATALOG_VERSION_NO`.

### Test

Run the regression suite (`meson test -C build` or `make check`). Add
a test case for your new function in `src/test/regress/sql/` and the
expected output in `src/test/regress/expected/`. Watch out for failures
in `opr_sanity` — that test checks invariants over `pg_proc`.

### Docs

Document the function in `doc/src/sgml/func.sgml`.
