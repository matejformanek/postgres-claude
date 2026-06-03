# pg_attrdef.h

- **Source path:** `source/src/include/catalog/pg_attrdef.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "attribute defaults" system catalog (`pg_attrdef`). One row per column DEFAULT expression, keyed by (table OID, attnum). [from-comment]

## Catalog definition

- `CATALOG(pg_attrdef, 2604, AttrDefaultRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_attrdef` typedef; pointer alias `Form_pg_attrdef`. [verified-by-code]
- `DECLARE_TOAST(pg_attrdef, 2830, 2831)`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| adrelid | Oid | — | `pg_class` |
| adnum | int16 | — | — (attnum within adrelid) |
| adbin | pg_node_tree | `BKI_FORCE_NOT_NULL` | — (varlena; nodeToString of DEFAULT) |

`adbin` lives in `#ifdef CATALOG_VARLEN`. [verified-by-code]

## Key declarations beyond FormData

- No character enums or on-disk char codes. [verified-by-code]
- Indexes: `pg_attrdef_adrelid_adnum_index` (uniq on `(adrelid, adnum)`), `pg_attrdef_oid_index` (PK). [verified-by-code]
- `DECLARE_FOREIGN_KEY((adrelid, adnum), pg_attribute, (attrelid, attnum))` — single-tuple FK (not array), because each row points at exactly one attribute. [verified-by-code]
- No syscache (lookups are infrequent and done via index scan). [verified-by-code]
- Function prototypes: `StoreAttrDefault`, `RemoveAttrDefault`, `RemoveAttrDefaultById`, `GetAttrDefaultOid`, `GetAttrDefaultColumnAddress`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_attribute.h` (`atthasdef` flag mirrors presence of a pg_attrdef row), `pg_constraint.h` (sibling — constraints vs defaults).

## Tally

`[verified-by-code]=8 [from-comment]=1`
