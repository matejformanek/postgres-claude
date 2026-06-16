# pg_am.h

- **Source path:** `source/src/include/catalog/pg_am.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "access method" system catalog (`pg_am`). One row per index or table access method (btree, hash, gist, gin, brin, spgist, heap, …). [from-comment]

## Catalog definition

- `CATALOG(pg_am, 2601, AccessMethodRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_am` typedef; pointer alias `Form_pg_am`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| amname | NameData | — | — |
| amhandler | regproc | — | `pg_proc` |
| amtype | char | — | — |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `amtype` on-disk char codes (in `EXPOSE_TO_CLIENT_CODE`): `AMTYPE_INDEX 'i'`, `AMTYPE_TABLE 't'`. Changing these letters is an on-disk format break. [verified-by-code]
- Indexes: `pg_am_name_index` on `amname`, `pg_am_oid_index` (PK). [verified-by-code]
- Syscaches: `AMNAME` (4), `AMOID` (4). [verified-by-code]
- No function prototypes declared (creation routed through `CommandAM` in DDL code, not via a header-declared `AccessMethodCreate`). [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_opclass.h`, `pg_opfamily.h`, `pg_amop.h`, `pg_amproc.h` (opclass/opfamily layered above pg_am), `access/amapi.h` and `access/tableam.h` (handler API the `amhandler` regproc returns).

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: amtype char codes are on-disk values]** `pg_am.h:65-66` — `AMTYPE_INDEX 'i'` and `AMTYPE_TABLE 't'` are stored verbatim in pg_am rows; the header doesn't warn that changing the letters is a catalog format break.

## Tally

`[verified-by-code]=6 [from-comment]=1`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new index access method](../../../../scenarios/add-new-index-am.md)

<!-- scenarios:auto:end -->
