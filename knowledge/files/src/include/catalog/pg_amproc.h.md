# pg_amproc.h

- **Source path:** `source/src/include/catalog/pg_amproc.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "access method procedure" system catalog (`pg_amproc`). Identifies support procedures associated with index operator families/classes. These procedures aren't the implementation of any indexable operator (so they don't fit in pg_amop). [from-comment]

## Catalog definition

- `CATALOG(pg_amproc, 2603, AccessMethodProcedureRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_amproc` typedef; pointer alias `Form_pg_amproc`. [verified-by-code]
- Logical PK is `<amprocfamily, amproclefttype, amprocrighttype, amprocnum>`; oid is a surrogate. [from-comment]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| amprocfamily | Oid | — | `pg_opfamily` |
| amproclefttype | Oid | — | `pg_type` |
| amprocrighttype | Oid | — | `pg_type` |
| amprocnum | int16 | — | — |
| amproc | regproc | — | `pg_proc` |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- "Default" support functions are those where `amproclefttype = amprocrighttype = opclass's opcintype` — these are the ones loaded into the relcache for an index. Non-default entries support cross-type operators; meaning is AM-specific (some AMs ignore them). [from-comment]
- `amprocnum` interpretation is AM-specific — each access method documents its support function numbers (e.g. btree 1=comparison, 2=sortsupport, …). Not enumerated here. [inferred]
- Indexes: `pg_amproc_fam_proc_index` on `(amprocfamily, amproclefttype, amprocrighttype, amprocnum)`, `pg_amproc_oid_index` (PK). [verified-by-code]
- Syscache: `AMPROCNUM` (16). [verified-by-code]
- No function prototypes. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_amop.h` (sibling — operators), `pg_opfamily.h`, `pg_opclass.h`, `access/{nbtree,hash,gist,gin,brin,spgist}/*.h` (per-AM support function number meanings).

## Tally

`[verified-by-code]=5 [from-comment]=2 [inferred]=1`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new built-in scalar data type](../../../../scenarios/add-new-data-type.md)
- [Scenario — Add a new index access method](../../../../scenarios/add-new-index-am.md)
- [Scenario — Add a new operator class for an existing index AM](../../../../scenarios/add-new-operator-class.md)

<!-- scenarios:auto:end -->
