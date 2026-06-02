# Adding a builtin SQL function `pg_my_frobnitz(int4) returns int4`

## 1. C implementation

Pick an appropriate file under `src/backend/`, e.g. something in `src/backend/utils/adt/`. Write:

```c
#include "postgres.h"
#include "fmgr.h"

PG_FUNCTION_INFO_V1(pg_my_frobnitz);

Datum
pg_my_frobnitz(PG_FUNCTION_ARGS)
{
    int32 arg = PG_GETARG_INT32(0);
    /* compute */
    PG_RETURN_INT32(result);
}
```

## 2. Register it in the catalog

PostgreSQL's builtin functions are declared in `src/include/catalog/pg_proc.dat`. Add an entry there, something like:

```perl
{ oid => 'XXXX', descr => 'compute frobnitz',
  proname => 'pg_my_frobnitz',
  prorettype => 'int4', proargtypes => 'int4',
  prosrc => 'pg_my_frobnitz' },
```

The `prosrc` value must match the C symbol name. You can override defaults like `provolatile`, `proisstrict`, `proparallel` if needed.

## 3. Pick an OID

You need a unique OID. PostgreSQL has scripts in `src/include/catalog/` (I recall something like `unused_oids` and `duplicate_oids`) that help you find and verify a unique OID. Use a value that isn't currently taken. I think there's a convention about a particular range for new patches but I'm not 100% sure of the exact range.

## 4. Bump the catalog version

There's a `catversion.h` somewhere under `src/include/catalog/` with a `CATALOG_VERSION_NO` constant. When you change catalog contents you need to bump this so that existing data directories aren't silently used with a mismatched binary.

## 5. Rebuild

A clean rebuild is required because the build process generates BKI files and `_d.h` headers from the catalog `.dat` files. With meson:

```sh
ninja -C build
```

or with the autoconf path, `make`.

## 6. Re-initdb

Since the catversion changed, your existing data directory won't be usable. You need to run `initdb` again to create a fresh cluster against the new binary.

## 7. Test

Add a regression test under `src/test/regress/` that calls the new function and check the result. Then run `make check` or `meson test`.

## 8. Documentation

Update `doc/src/sgml/func.sgml` to describe the new function in user-facing docs.

## Things to watch out for

- Forgetting to bump catversion is a classic mistake; other devs' clusters will refuse to start.
- OID collisions with other in-flight patches happen.
- The `prosrc` C symbol must exactly match the function name in your `.c` file or you'll get a linker/loader error at call time.
