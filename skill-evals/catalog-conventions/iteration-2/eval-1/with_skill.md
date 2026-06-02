# Eval 1 — with skill

**Prompt:** Add builtin `pg_my_frobnitz(int4) returns int4`, full
workflow.

## Answer

Workflow for a new builtin function:

### 1. C implementation

Put the C code in an appropriate file under `src/backend/utils/adt/`
(int.c, numeric.c, …) or wherever it fits topically. The function
signature is:

```c
PG_FUNCTION_INFO_V1(pg_my_frobnitz);

Datum
pg_my_frobnitz(PG_FUNCTION_ARGS)
{
    int32 arg = PG_GETARG_INT32(0);
    /* ... compute ... */
    PG_RETURN_INT32(result);
}
```

The C symbol name (`pg_my_frobnitz`) must match the `prosrc` field in
the catalog entry exactly.

### 2. Pick an OID

From `src/include/catalog/`:

```sh
./unused_oids
```

Pick a *random* starting OID in **8000-9999** — this range is reserved
by project convention for in-progress patches and forks (see
`src/include/access/transam.h` around `FirstGenbkiObjectId`), and using
a random start minimises collisions with concurrent patches.
10000-11999 is reserved for genbki.pl auto-assignment; don't touch it.
The committer will renumber your OID down to a tidy low range at commit
time via `renumber_oids.pl` — you don't do that yourself.

### 3. pg_proc.dat entry

In `src/include/catalog/pg_proc.dat`, add a row near related entries
(group with similar int4-arithmetic builtins, not just at the end of
the file):

```
{ oid => '8473', descr => 'frobnitz of an int',
  proname => 'pg_my_frobnitz', prorettype => 'int4',
  proargtypes => 'int4', prosrc => 'pg_my_frobnitz' },
```

Do NOT write:
- `pronargs` — `AddDefaultValues` (in Catalog.pm) computes it from
  `proargtypes`.
- Anything matching `BKI_DEFAULT` in `pg_proc.h`: `provolatile` (default
  `i` = immutable), `proisstrict` (default `t`), `proparallel` (default
  `s` = safe), `prokind` (default `f`), etc. Only write columns where
  you DIVERGE from the default — e.g. a stable function would need
  `provolatile => 's'`.

Use symbolic type names (`int4`), not numeric OIDs — `BKI_LOOKUP`
resolves them.

### 4. Bump catversion

Edit `src/include/catalog/catversion.h` and bump `CATALOG_VERSION_NO`
to `YYYYMMDDN` — today's date with N=1 (or higher if multiple bumps
land same day). This is mandatory because you added a `.dat` row.

### 5. Verify OIDs

```sh
cd src/include/catalog && ./duplicate_oids
```

Must exit 0 with no output. If it complains, pick a different OID.

### 6. Rebuild fully

`genbki.pl` runs at build time and regenerates `postgres.bki`,
`pg_proc_d.h`, `syscache_*.h`. With meson:

```sh
ninja -C build
```

Don't skip — stale generated headers are a common gotcha.

### 7. Re-initdb

Old data directories won't open after a catversion bump:

```sh
rm -rf data && ./tmp_install/.../initdb -D data
```

### 8. Regression tests

```sh
meson test -C build --suite regress
```

Watch for `opr_sanity` / `type_sanity` failures — those tests enforce
catalog invariants and will tell you exactly which invariant you broke.
Add a new regression test exercising `pg_my_frobnitz` in
`src/test/regress/sql/`.

### 9. Docs

Add a row to `doc/src/sgml/func.sgml` in the relevant section for
user-facing documentation.

## Pre-commit gate

- `./duplicate_oids` clean
- `CATALOG_VERSION_NO` bumped
- Full clean rebuild succeeds
- `meson test` green
- `doc/src/sgml/func.sgml` updated
