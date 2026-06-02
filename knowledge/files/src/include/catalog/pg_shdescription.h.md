# pg_shdescription.h

- **Source path:** `source/src/include/catalog/pg_shdescription.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "shared description" system catalog (`pg_shdescription`) — `COMMENT ON` text for cluster-wide objects (databases, roles, tablespaces, …). Like `pg_description`, contents come from the `*.dat` files of other shared catalogs; assembled by genbki.pl at initdb. Identified by `(objoid, classoid)` — no `objsubid` since shared objects have no sub-parts. [from-comment]

## Catalog definition

- `CATALOG(pg_shdescription, 2396, SharedDescriptionRelationId) BKI_SHARED_RELATION` — lives in `global/`. [verified-by-code]
- `FormData_pg_shdescription` typedef; pointer alias `Form_pg_shdescription`. [verified-by-code]
- `DECLARE_TOAST_WITH_MACRO(pg_shdescription, 2846, 2847, PgShdescriptionToastTable, PgShdescriptionToastIndex)` — named-macro toast because shared catalog toast OIDs need to be referenced from elsewhere. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_shdescription_o_c_index, 2397, ...)` over `(objoid, classoid)`. [verified-by-code]
- `DECLARE_FOREIGN_KEY((classoid), pg_class, (oid))` — not BKI_LOOKUP (same genbki.pl reason as pg_description). [from-comment]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| objoid | Oid | — | — (logical FK varies by classoid) |
| classoid | Oid | — (FK without BKI_LOOKUP) | pg_class |
| description | text | BKI_FORCE_NOT_NULL (varlena) | — |

## Key declarations beyond FormData

- None — no macros, no enums, no function prototypes. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Per-DB companion: `pg_description.h.md`.
- Related backend: `source/src/backend/commands/comment.c`.

## Tally

`[verified-by-code]=6 [from-comment]=2`
