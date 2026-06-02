# pg_depend.h

- **Source path:** `source/src/include/catalog/pg_depend.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Per-database dependency edges between objects. Header comment: "pg_depend has no preloaded contents, so there is no pg_depend.dat file; dependencies for system-defined objects are loaded into it on-the-fly during initdb. Most built-in objects are pinned anyway, and hence need no explicit entries in pg_depend." Not all dependency pairs are represented — only conditional or hard-to-derive ones. [from-comment]

## Catalog definition

- `CATALOG(pg_depend, 2608, DependRelationId)` — no BKI markings beyond default; per-DB. [verified-by-code] `pg_depend.h:44`
- `FormData_pg_depend` typedef; pointer alias `Form_pg_depend`. [verified-by-code] `pg_depend.h:67,76`
- No `oid` column — composite identification (no PK in the usual sense; two non-unique btree indexes only). [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| classid | Oid | — | `pg_class` (BKI_LOOKUP) |
| objid | Oid | — | — |
| objsubid | int32 | — | — (column number, or 0) |
| refclassid | Oid | — | `pg_class` (BKI_LOOKUP) |
| refobjid | Oid | — | — |
| refobjsubid | int32 | — | — (column number, or 0) |
| deptype | char | — | — (see `DependencyType` in `dependency.h`) |

## Key declarations beyond FormData

- `DECLARE_INDEX(pg_depend_depender_index, 2673, ...)` on (classid, objid, objsubid). [verified-by-code] `pg_depend.h:78`
- `DECLARE_INDEX(pg_depend_reference_index, 2674, ...)` on (refclassid, refobjid, refobjsubid). [verified-by-code] `pg_depend.h:79`
- `deptype` semantics live in `catalog/dependency.h`'s `DependencyType` enum — the char code is **on-disk** (see that header's per-file doc). [from-comment] `pg_depend.h:63-66`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `knowledge/files/src/include/catalog/dependency.h.md` (DependencyType char codes)
- Related: `knowledge/files/src/include/catalog/pg_shdepend.h.md` (cross-DB sibling)

## Tally

`[verified-by-code]=6 [from-comment]=3`
