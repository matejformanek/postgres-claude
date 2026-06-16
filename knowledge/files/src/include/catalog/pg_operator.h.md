# pg_operator.h

- **Source path:** `source/src/include/catalog/pg_operator.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "operator" system catalog (`pg_operator`). One row per SQL operator (prefix or infix), bridging the operator name to its underlying function and selectivity estimators. [from-comment]

## Catalog definition

- `CATALOG(pg_operator, 2617, OperatorRelationId)` — no special BKI markings (per-DB, not bootstrap). [verified-by-code]
- `FormData_pg_operator` typedef; pointer alias `Form_pg_operator`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| oprname | NameData | — | — |
| oprnamespace | Oid | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| oprowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| oprkind | char | `BKI_DEFAULT(b)` | — |
| oprcanmerge | bool | `BKI_DEFAULT(f)` | — |
| oprcanhash | bool | `BKI_DEFAULT(f)` | — |
| oprleft | Oid | — | `pg_type` (OPT, 0 if prefix) |
| oprright | Oid | — | `pg_type` |
| oprresult | Oid | — | `pg_type` (OPT, 0 for shell op) |
| oprcom | Oid | `BKI_DEFAULT(0)` | `pg_operator` (OPT) |
| oprnegate | Oid | `BKI_DEFAULT(0)` | `pg_operator` (OPT) |
| oprcode | regproc | — | `pg_proc` (OPT, 0 for shell op) |
| oprrest | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| oprjoin | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `oprkind` values are on-disk single-char codes: `'l'` prefix, `'b'` infix. [from-comment]
- Indexes: `pg_operator_oid_index` (PK), `pg_operator_oprname_l_r_n_index` on `(oprname, oprleft, oprright, oprnamespace)`. [verified-by-code]
- Syscaches: `OPEROID` (32), `OPERNAMENSP` (256). [verified-by-code]
- Function prototypes: `OperatorLookup`, `OperatorCreate`, `makeOperatorDependencies`, `OperatorValidateParams`, `OperatorUpd`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_amop.h` (operators wired into opfamilies), `pg_proc.h` (oprcode targets).

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: oprkind char codes are on-disk values]** `pg_operator.h:47` — `oprkind BKI_DEFAULT(b)` with comment "'l' for prefix or 'b' for infix" but no warning that changing the letters breaks on-disk format. Consistent with peers (pg_constraint, pg_am) that share the same gap.

## Tally

`[verified-by-code]=5 [from-comment]=2`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new built-in scalar data type](../../../../scenarios/add-new-data-type.md)
- [Scenario — Add a new built-in operator](../../../../scenarios/add-new-operator.md)
- [Scenario — Add a new built-in operator](../../../../scenarios/add-new-operator.md)

<!-- scenarios:auto:end -->
