# pg_opfamily.h

- **Source path:** `source/src/include/catalog/pg_opfamily.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "operator family" system catalog (`pg_opfamily`). One row per (AM, family name, namespace); the container that groups compatible opclasses, operators (`pg_amop`), and support procedures (`pg_amproc`). [from-comment]

## Catalog definition

- `CATALOG(pg_opfamily, 2753, OperatorFamilyRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_opfamily` typedef; pointer alias `Form_pg_opfamily`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| opfmethod | Oid | — | `pg_am` |
| opfname | NameData | — | — |
| opfnamespace | Oid | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| opfowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- Macro `IsBuiltinBooleanOpfamily(opfamily)` (in `EXPOSE_TO_CLIENT_CODE`) — true iff opfamily OID is `BOOL_BTREE_FAM_OID` or `BOOL_HASH_FAM_OID`. Comment notes it does NOT account for non-core opfamilies that might accept boolean. [verified-by-code]
- Indexes: `pg_opfamily_am_name_nsp_index` on `(opfmethod, opfname, opfnamespace)`, `pg_opfamily_oid_index` (PK). [verified-by-code]
- Syscaches: `OPFAMILYAMNAMENSP` (8), `OPFAMILYOID` (8). [verified-by-code]
- No function prototypes. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_opclass.h` (children), `pg_amop.h`, `pg_amproc.h` (membership), `pg_am.h`.

## Tally

`[verified-by-code]=5 [from-comment]=1`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new built-in scalar data type](../../../../scenarios/add-new-data-type.md)
- [Scenario — Add a new index access method](../../../../scenarios/add-new-index-am.md)
- [Scenario — Add a new operator class for an existing index AM](../../../../scenarios/add-new-operator-class.md)

<!-- scenarios:auto:end -->
