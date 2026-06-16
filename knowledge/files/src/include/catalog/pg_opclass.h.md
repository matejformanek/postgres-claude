# pg_opclass.h

- **Source path:** `source/src/include/catalog/pg_opclass.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "operator class" system catalog (`pg_opclass`). One row per (AM, opclass name, namespace) combination. Each opclass is a subset of an opfamily that specifies the input data type and (optionally) a distinct stored-key type. [from-comment]

## Catalog definition

- `CATALOG(pg_opclass, 2616, OperatorClassRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_opclass` typedef; pointer alias `Form_pg_opclass`. [verified-by-code]
- Logical PK is `<opcmethod, opcname, opcnamespace>`. At most one row per `<opcmethod, opcintype>` may have `opcdefault = true` (not enforced by index — system catalogs don't have partial indexes). [from-comment]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| opcmethod | Oid | — | `pg_am` |
| opcname | NameData | — | — |
| opcnamespace | Oid | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| opcowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| opcfamily | Oid | — | `pg_opfamily` |
| opcintype | Oid | — | `pg_type` |
| opcdefault | bool | `BKI_DEFAULT(t)` | — |
| opckeytype | Oid | `BKI_DEFAULT(0)` | `pg_type` (OPT) |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `opckeytype = InvalidOid` (the default) means stored index data has the same type as the indexed column. Nonzero indicates an AM-managed conversion to a different stored type; performing it is the AM's responsibility, and not all AMs support it. [from-comment]
- Indexes: `pg_opclass_am_name_nsp_index` on `(opcmethod, opcname, opcnamespace)`, `pg_opclass_oid_index` (PK). [verified-by-code]
- Syscaches: `CLAAMNAMENSP` (8), `CLAOID` (8). [verified-by-code]
- No function prototypes. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_opfamily.h` (parent), `pg_amop.h`, `pg_amproc.h` (members), `commands/opclasscmds.c` (DDL).

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: opcdefault uniqueness not enforced]** `pg_opclass.h:13-17` — comment explicitly notes the "at most one default per (opcmethod, opcintype)" rule isn't enforced by an index because partial indexes aren't allowed on system catalogs. Relies on DDL validation in `opclasscmds.c`. Worth flagging because a corrupt catalog (e.g. extension misuse) could silently violate it.

## Tally

`[verified-by-code]=5 [from-comment]=3`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new built-in scalar data type](../../../../scenarios/add-new-data-type.md)
- [Scenario — Add a new index access method](../../../../scenarios/add-new-index-am.md)
- [Scenario — Add a new operator class for an existing index AM](../../../../scenarios/add-new-operator-class.md)

<!-- scenarios:auto:end -->
