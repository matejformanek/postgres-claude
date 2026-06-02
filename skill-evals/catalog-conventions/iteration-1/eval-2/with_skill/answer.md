# Adding `relhasfrobnitz bool` to `pg_class`

This is a "new column on an existing catalog" change. Workflow:

## 1. Edit `src/include/catalog/pg_class.h`

Add the column to the `CATALOG(pg_class,1259,...)` struct. Since it's a fixed-length boolean — not a varlena, not nullable — it can live in the main struct body (no `#ifdef CATALOG_VARLEN` needed). Place it near related boolean flags like `relhasindex`, `relhasrules`, etc., for cache-line locality and readability.

```c
bool        relhasfrobnitz BKI_DEFAULT(f);
```

The `BKI_DEFAULT(f)` means any `pg_class.dat` row (well — `pg_class` doesn't actually have a `.dat` because rows are populated at bootstrap, but the principle holds for catalogs that do) and any bootstrap-mode tuple creation that doesn't supply this column will get `false`. This is what saves you from touching every existing row.

If new code needs the column publicly visible to frontend tools, you don't need to do anything extra here — `genbki.pl` already emits an `Anum_pg_class_relhasfrobnitz` and the field is part of `FormData_pg_class` automatically.

## 2. Do you need to edit `pg_class.dat`?

`pg_class` has no `pg_class.dat` (its initial rows are created by bootstrap as the catalog tables themselves are built). For catalogs that *do* have a `.dat` (e.g. `pg_proc`, `pg_type`): the `BKI_DEFAULT(f)` lets you skip writing the column on every existing row. You only need to set it on rows where the value differs from the default.

So in the `pg_class` case: no, you don't touch every existing row. The default flows through both bootstrap and runtime tuple creation.

## 3. Wire it into the code that *sets* the column

The default of `false` will apply at table creation in `heap_create_with_catalog` → `InsertPgClassTuple`. If your feature requires the column to be `true` for certain relations, find the right DDL backend (typically in `src/backend/catalog/heap.c` or `src/backend/commands/tablecmds.c`) and emit a `CatalogTupleUpdate` (using `simple_heap_update` semantics) on the pg_class row, then bump invalidation via the standard syscache mechanism (it happens automatically via shared invalidation messages).

## 4. Bump `CATALOG_VERSION_NO`

Mandatory: you added a column to a catalog header. Edit `src/include/catalog/catversion.h` and set it to today's `YYYYMMDDN` (N=1 if no other bump today). Without this, every other developer's local cluster will refuse to start against your new binary.

## 5. Verifications

```sh
cd src/include/catalog && ./duplicate_oids   # still clean
ninja -C build                                # full rebuild — genbki.pl regenerates pg_class_d.h
rm -rf data && ./tmp_install/.../initdb -D data
meson test -C build --suite regress
```

Watch for:
- `pg_class_d.h` regeneration in the build log (`Generating src/backend/catalog/postgres.bki`).
- `Natts_pg_class` rises by 1.
- `Anum_pg_class_relhasfrobnitz` macro becomes available.

## 6. Tests likely to shift

- `opr_sanity` and `type_sanity` may flag invariants.
- `psql` `\d+` output / `pg_dump` if you exposed it.
- Anything that does `SELECT * FROM pg_class` in `src/test/regress/expected/*.out` — the column count changes. You'll need to update those `.out` files.

## On "recompile everyone"

**You cannot avoid recompilation** of anything that accesses `Form_pg_class->...` fields. The C struct layout is the on-disk tuple layout: adding a column changes `sizeof(FormData_pg_class)` and the offset of any field after the new one. Out-of-tree extensions that read `Form_pg_class` *will* need a recompile against the new headers.

What you *can* do is:
- Place the new column at the **end** of the fixed-length section (not in the middle) so offsets of existing fields don't shift. This is the standard pattern and minimizes churn.
- If it were varlena/nullable, place it inside the trailing `#ifdef CATALOG_VARLEN` block — but for a `bool` that doesn't apply.

The `BKI_DEFAULT(f)` only addresses initialization, not ABI compatibility. Extensions still need to rebuild.

## Pre-commit gate

- [ ] `./duplicate_oids` clean (no new OIDs but doesn't hurt)
- [ ] `CATALOG_VERSION_NO` bumped
- [ ] Full clean rebuild
- [ ] `meson test -C build` green, including the regress `.out` updates
- [ ] Docs in `doc/src/sgml/catalogs.sgml` describing the new column
- [ ] No stale references to old `Natts_pg_class` count anywhere

## Common pitfalls

1. **Forgot to bump catversion** — symptom: other devs report "my cluster won't start".
2. **Inserted in the middle of the struct** — gratuitous churn for extensions. Append at the end.
3. **Inserted varlena outside `#ifdef CATALOG_VARLEN`** — N/A for bool, but for varlena/nullable columns this is the silent-garbage failure mode.
4. **Forgot to update expected `.out` files** — many tests select from `pg_class` and will fail.
