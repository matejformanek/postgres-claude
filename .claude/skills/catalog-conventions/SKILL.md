---
name: catalog-conventions
description: Operational checklist for modifying a PostgreSQL system catalog — adding a builtin function, new catalog column, new opclass, etc. Use whenever you edit anything under src/include/catalog/ or add a pg_proc.dat entry.
---

# Catalog modification checklist

Background: `knowledge/idioms/catalog-conventions.md`. This skill is the
hands-on procedure; consult it before/after any change to
`src/include/catalog/*.h` or `*.dat`.

## Before you start

1. **Decide which catalog(s) you touch.** Common patterns:
   - New builtin function → `pg_proc.dat` (+ C function in some backend file).
   - New operator → `pg_operator.dat` + `pg_proc.dat`.
   - New cast → `pg_cast.dat` + `pg_proc.dat`.
   - New type → `pg_type.dat` + I/O funcs in `pg_proc.dat`.
   - New column on existing catalog → edit `pg_X.h`, decide BKI_DEFAULT,
     possibly update every existing row in `pg_X.dat`.
   - New catalog table entirely → new `pg_X.h` + `pg_X.dat` + entries in
     `src/include/catalog/Makefile` / `meson.build` + `headers` list in
     `src/backend/catalog/Makefile`.

2. **Pick OIDs.** From `src/include/catalog/`:
   ```sh
   ./unused_oids
   ```
   Pick a *random* starting OID in **8000-9999** and a contiguous block big
   enough for your patch. Final renumbering down to a tidy range happens
   at commit time via `renumber_oids.pl` — don't do that yourself in
   in-flight work.

## Making the edit

3. **Edit the header (`pg_X.h`)** if the schema changes.
   - Wrap varlena / nullable trailing columns in `#ifdef CATALOG_VARLEN`.
   - Annotate OID-referencing columns with `BKI_LOOKUP(target_catalog)`
     (or `BKI_LOOKUP_OPT` if zero is allowed).
   - Provide `BKI_DEFAULT(val)` for any column the `.dat` files may omit.
   - Public constants (relkinds, prokinds, …) belong inside
     `#ifdef EXPOSE_TO_CLIENT_CODE` so frontend code can read them via
     the generated `pg_X_d.h`.

4. **Edit the data file (`pg_X.dat`)**.
   - Group new entries near related existing ones (not at the end).
   - Always include a `descr` (becomes the `pg_description` row).
   - Use symbolic names for OID references (`prorettype => 'int4'`),
     not numeric OIDs. `BKI_LOOKUP` resolves them.
   - Don't write columns that have a `BKI_DEFAULT` matching your value.
   - Don't write computed columns like `pronargs`.

5. **Write/wire the C implementation.**
   - For a new function: `PG_FUNCTION_INFO_V1(name); Datum name(PG_FUNCTION_ARGS) { ... }`
     in an appropriate `src/backend/.../*.c`. The C symbol must match
     `prosrc` in the dat entry.

## Cache & index plumbing (only when needed)

6. **Adding a new lookup pattern?** Add a `DECLARE_UNIQUE_INDEX` and
   `MAKE_SYSCACHE(NAME, idx, nbuckets)` to the header. Use the syscache
   from C with `SearchSysCacheN` + `ReleaseSysCache`.

7. **Adding a TOAST-eligible catalog?** `DECLARE_TOAST(name, toastoid,
   indexoid)` — pin both OIDs.

## Mandatory verifications (run all of these)

8. **`./duplicate_oids`** — exit code 0, no output. Run from
   `src/include/catalog/`.
   ```sh
   cd src/include/catalog && ./duplicate_oids
   ```

9. **Bump `CATALOG_VERSION_NO`** in
   `src/include/catalog/catversion.h`. Format `YYYYMMDDN` —
   today's date with N=1 (or higher if multiple bumps land same day).
   This is mandatory if you:
   - Added / removed / renamed any catalog column.
   - Added / removed / changed any `.dat` row.
   - Added / removed / renamed any system function or operator.
   - Changed `primnodes.h` / `parsenodes.h` (stored parsetrees).
   - Did anything else that would break a running cluster reading data
     written by the prior binary.

   If you're unsure: bump it. The cost is zero; missing it produces
   confusing "cluster won't start" reports.

10. **Rebuild fully.** `genbki.pl` runs at build time and regenerates
    `postgres.bki`, `pg_X_d.h`, `syscache_ids.h`, `syscache_info.h`,
    `system_fk_info.h`. Forgetting a clean rebuild leaves stale headers.
    With meson:
    ```sh
    ninja -C build
    ```
    Look for `Generating src/backend/catalog/postgres.bki` in the log.

11. **Re-initdb.** Old data directories won't open after a catversion
    bump. From the build dir:
    ```sh
    rm -rf data && ./tmp_install/.../initdb -D data
    ```
    Or use the `build-and-run` skill.

12. **Run catalog-touching regression tests:**
    ```sh
    meson test -C build --suite regress
    ```
    Add a new test exercising the new function/operator/column.
    `make check` works too.

13. **If applicable, update:**
    - `src/test/regress/expected/*.out` — opr_sanity, type_sanity,
      psql_crosstab outputs often shift when you add catalog rows.
    - `doc/src/sgml/func.sgml` (or equivalent) — user-facing docs for
      new functions/operators.
    - `src/bin/psql/tab-complete.in.c` — completion for new SQL keywords.
    - `src/test/modules/test_oat_hooks` etc. if you touched ACL columns.

## Pre-commit gate (don't skip)

- [ ] `./duplicate_oids` clean
- [ ] `CATALOG_VERSION_NO` bumped
- [ ] Full clean rebuild succeeds
- [ ] `meson test -C build` (or `make check-world`) green
- [ ] `git grep` shows no stale references to renamed columns / removed OIDs
- [ ] Docs updated for any user-visible addition

## Common failure modes (in order of frequency)

1. Forgot to bump catversion → reviewer flags it, or worse, lands and
   then breaks every developer's local cluster on next pull.
2. OID collision with a concurrent patch → `duplicate_oids` catches it;
   pick a new OID and rerun.
3. Varlena column outside `CATALOG_VARLEN` → silent garbage reads via
   `Form_pg_X->col`. Always wrap.
4. `BKI_LOOKUP` target name not present in the referenced `.dat` →
   genbki.pl errors clearly; check spelling and that the row exists.
5. New `.dat` row passes build but breaks `opr_sanity` / `type_sanity`
   regression checks → those tests exist precisely to enforce catalog
   invariants; read the failure carefully, it will tell you which
   invariant.
6. Forgot to add `ReleaseSysCache` after a successful `SearchSysCache*`
   in new C code → "cache reference leak" warnings at txn end.

## Reference files (in `source/`)

- `src/include/catalog/README` — pointer to docs
- `src/include/catalog/genbki.h` — macro reference
- `src/include/catalog/catversion.h` — bump target
- `src/include/catalog/duplicate_oids` — uniqueness check script
- `src/include/catalog/unused_oids` — OID picker
- `src/include/catalog/renumber_oids.pl` — committer-side cleanup
- `src/backend/catalog/genbki.pl` + `Catalog.pm` — the generator
- `src/include/access/transam.h:195-197` — `FirstGenbkiObjectId` /
  `FirstUnpinnedObjectId` / `FirstNormalObjectId`
- `src/include/utils/syscache.h` + `src/backend/utils/cache/syscache.c` —
  syscache API and registry

## Upstream docs

- https://www.postgresql.org/docs/current/bki.html
- https://www.postgresql.org/docs/current/system-catalog-declarations.html
- https://www.postgresql.org/docs/current/catalogs.html
