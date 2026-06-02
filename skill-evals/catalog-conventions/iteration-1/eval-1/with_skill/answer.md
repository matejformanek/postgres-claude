# Adding a builtin SQL function `pg_my_frobnitz(int4) returns int4`

End-to-end workflow.

## 1. Write the C implementation

In an appropriate file under `src/backend/...` (e.g. `src/backend/utils/adt/int.c` for int math, or a new file if it's a fresh module), add:

```c
PG_FUNCTION_INFO_V1(pg_my_frobnitz);

Datum
pg_my_frobnitz(PG_FUNCTION_ARGS)
{
    int32   arg = PG_GETARG_INT32(0);
    int32   result = /* ... compute ... */;
    PG_RETURN_INT32(result);
}
```

The C symbol used here (`pg_my_frobnitz`) must match the `prosrc` field of the catalog entry below.

## 2. Pick an OID

From `src/include/catalog/`:

```sh
cd src/include/catalog && ./unused_oids
```

Pick a *random* starting OID in the **8000-9999** range. This range is project policy for in-flight patches to minimize collisions with concurrent submissions. At commit time the committer renumbers it down via `renumber_oids.pl`; don't do that yourself.

## 3. Add the `pg_proc.dat` row

Edit `src/include/catalog/pg_proc.dat`. Place the entry near related existing entries (not at the end of the file). Minimum required fields are `oid`, `descr`, `proname`, `prorettype`, `proargtypes`, `prosrc`:

```perl
{ oid => '8473', descr => 'compute frobnitz of an int',
  proname => 'pg_my_frobnitz', prorettype => 'int4',
  proargtypes => 'int4', prosrc => 'pg_my_frobnitz' },
```

Notes:
- Don't write columns that match their `BKI_DEFAULT` (e.g. `provolatile => 'i'` is the default for immutable; if you want immutable, omit it).
- Don't write `pronargs` — `Catalog.pm`'s `AddDefaultValues()` computes it from `proargtypes`.
- Override `provolatile`, `proisstrict`, `proparallel`, `proretset` etc. only if your function diverges from the default.
- `prorettype` / `proargtypes` use symbolic type names; `BKI_LOOKUP(pg_type)` resolves them.

## 4. Bump `CATALOG_VERSION_NO`

In `src/include/catalog/catversion.h`, bump the constant to today's date in `YYYYMMDDN` format (N=1, or higher if multiple bumps happened the same day). This is mandatory because you added a `.dat` row — otherwise existing data directories built with the prior binary refuse to start against your new binary with a catversion mismatch.

## 5. Verify OID uniqueness

```sh
cd src/include/catalog && ./duplicate_oids
```

Expect empty output, exit code 0. Run after every OID-touching edit.

## 6. Full rebuild

```sh
ninja -C build
```

`genbki.pl` runs at build time and regenerates `postgres.bki`, `pg_proc_d.h`, `syscache_ids.h`, `syscache_info.h`, `system_fk_info.h`. Watch for the `Generating src/backend/catalog/postgres.bki` line — if you don't see it, you have stale headers.

## 7. Re-initdb

A catversion bump means existing data directories won't open. From the build dir:

```sh
rm -rf data && ./tmp_install/.../initdb -D data
```

(or use the `build-and-run` skill / `/setup-pg`).

## 8. Regression test

Add a SQL test exercising the function (e.g. under `src/test/regress/sql/`) and matching expected output. Run:

```sh
meson test -C build --suite regress
```

If you added a row to `pg_proc`, the `opr_sanity` test may flag mismatches (e.g. wrong `provolatile` for a function that calls something volatile). Read those failures carefully — they enforce catalog invariants.

## 9. User-visible docs

Update `doc/src/sgml/func.sgml` (or the relevant section) with a description of the new function. If it introduces a new SQL keyword, also update `src/bin/psql/tab-complete.in.c`.

## Pre-commit gate

- [ ] `./duplicate_oids` clean
- [ ] `CATALOG_VERSION_NO` bumped to today
- [ ] Full clean rebuild succeeds
- [ ] `meson test -C build` green (especially `opr_sanity`)
- [ ] `git grep pg_my_frobnitz` shows expected hits (`.c`, `.dat`, regression test, docs)
- [ ] Docs added

## Common failure modes

1. Forgot to bump catversion — local cluster works (you initdb'd against your new binary), but every other developer's cluster won't start on next pull.
2. OID collision with concurrent patch — `duplicate_oids` catches it; pick a new OID.
3. `prosrc` name doesn't match the C symbol — undefined symbol at function call time.
4. New row breaks `opr_sanity` — typically wrong `provolatile`/`proparallel` for what the impl actually does.

## Why this works (background)

`genbki.pl` parses `pg_proc.h` (schema + `BKI_DEFAULT`s + `BKI_LOOKUP` directives) and `pg_proc.dat` (initial rows) and emits `postgres.bki`, which `initdb` feeds to the bootstrap parser. Your `.dat` row becomes one of the pinned (OID < `FirstUnpinnedObjectId` = 12000) initial `pg_proc` tuples loaded into the template database. Symbolic name resolution (`prorettype => 'int4'`) goes through `BKI_LOOKUP(pg_type)`, looking up `int4` in `pg_type.dat`'s `typname` column.
