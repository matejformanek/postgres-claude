# pg_description.h

- **Source path:** `source/src/include/catalog/pg_description.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "description" system catalog (`pg_description`) — `COMMENT ON` text for per-database objects. An object is identified by `(objoid, classoid, objsubid)`: the OID of the row that defines it, the OID of the catalog that row lives in, and a column number (for attribute comments) or 0. Initial contents are assembled by genbki.pl from the `*.dat` files of other catalogs (so there is no `pg_description.dat`). [from-comment]

## Catalog definition

- `CATALOG(pg_description, 2609, DescriptionRelationId)` — per-database. [verified-by-code]
- `FormData_pg_description` typedef; pointer alias `Form_pg_description`. [verified-by-code]
- `DECLARE_TOAST(pg_description, 2834, 2835)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_description_o_c_o_index, 2675, ...)` over `(objoid, classoid, objsubid)`. [verified-by-code]
- `DECLARE_FOREIGN_KEY((classoid), pg_class, (oid))` — *not* BKI_LOOKUP because BKI_LOOKUP causes problems for genbki.pl on this column. [from-comment]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| objoid | Oid | — | — (logical FK varies by classoid) |
| classoid | Oid | — (FK declared without BKI_LOOKUP) | pg_class |
| objsubid | int32 | — | — (column number for attributes; 0 otherwise) |
| description | text | BKI_FORCE_NOT_NULL (varlena) | — |

## Key declarations beyond FormData

- None — no macros, no enums, no function prototypes. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companion catalog for shared objects: `pg_shdescription.h.md`.
- Related backend: `source/src/backend/catalog/pg_shdepend.c` (object identification), `source/src/backend/commands/comment.c`.

## Tally

`[verified-by-code]=6 [from-comment]=2`
