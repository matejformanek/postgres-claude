# indexing.h

- **Source path:** `source/src/include/catalog/indexing.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"This file provides some definitions to support indexing on system catalogs." [from-comment, indexing.h:3-5]

## Key declarations

- `CatalogIndexState` typedef (opaque to callers; actually a `ResultRelInfo *`).
- API prototypes: `CatalogOpenIndexes`, `CatalogCloseIndexes`, `CatalogTupleInsert`, `CatalogTupleInsertWithInfo`, `CatalogTuplesMultiInsertWithInfo`, `CatalogTupleUpdate`, `CatalogTupleUpdateWithInfo`, `CatalogTupleDelete`. (`MAX_PG_INDEXES` is *not* here — that's per-catalog in the individual headers.)
- The remainder of the file is a long list of `DECLARE_UNIQUE_INDEX(name, oid, oidmacro, decl)` macros, one per catalog system index — these are scanned by genbki.pl to emit index-creation commands in the BKI, and they also produce `#define <NAME>` OID constants in `pg_*_d.h`.

## Tally

`[verified-by-code]=1 [from-comment]=1`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a column to an existing system catalog](../../../../scenarios/add-new-system-catalog-column.md)

<!-- scenarios:auto:end -->
