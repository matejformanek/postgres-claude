# Adding `relhasfrobnitz bool` to `pg_class`

## Header edit

Edit `src/include/catalog/pg_class.h` and add a new field to the `CATALOG(pg_class, ...)` struct. Place it near other similar boolean flags like `relhasindex`. Use a `BKI_DEFAULT(f)` annotation so existing rows and code paths that don't explicitly set it get `false`:

```c
bool   relhasfrobnitz BKI_DEFAULT(f);
```

## Data file

`pg_class` doesn't have a `.dat` file the same way `pg_proc` does — its initial contents come from the bootstrap process when the catalog tables themselves are created. So you don't have to edit a `.dat` for each existing row. For catalogs that do have a `.dat`, the `BKI_DEFAULT` annotation means you don't need to touch every row — only set it where it differs from the default.

## Bump catversion

You changed a catalog schema, so bump `CATALOG_VERSION_NO` in `src/include/catalog/catversion.h`. Existing data directories won't load with a mismatch.

## Rebuild

A full rebuild regenerates `pg_class_d.h` and the BKI files. `Natts_pg_class` will go up by 1.

```sh
ninja -C build
```

Then re-`initdb` because of the catversion bump.

## On recompilation

Anything that uses `Form_pg_class` (the C struct view of a pg_class tuple) is reading the on-disk tuple layout, so adding a column changes the struct size and changes offsets if you inserted in the middle. Conventionally you append at the end of the fixed-length portion to minimize disruption. Out-of-tree extensions reading `Form_pg_class` will need a recompile — there's no way around that, the struct is the tuple format.

## Code paths to update

You'll probably need to update wherever new pg_class rows are written (heap_create_with_catalog in `heap.c`) if your logic wants the column set to something other than the default. Reading is automatic via `pg_class_d.h`'s `Anum_pg_class_relhasfrobnitz`.

## Tests

Many regression tests select * from pg_class or do `\d`-style output; their expected `.out` files will need updates because column count changed.

## Docs

Update `doc/src/sgml/catalogs.sgml` with a row describing the new column.

## Watch out

- Don't forget catversion.
- Don't put a varlena/nullable column outside the `#ifdef CATALOG_VARLEN` block (not relevant for bool, but a common pitfall).
- Update expected regress outputs.
