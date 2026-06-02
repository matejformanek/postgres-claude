# pg_amop.h

- **Source path:** `source/src/include/catalog/pg_amop.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "access method operator" system catalog (`pg_amop`). Identifies the operators associated with each index operator family/class. An entry can be a search operator or an ordering operator, per `amoppurpose`. [from-comment]

## Catalog definition

- `CATALOG(pg_amop, 2602, AccessMethodOperatorRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_amop` typedef; pointer alias `Form_pg_amop`. [verified-by-code]
- Logical PK is `<amopfamily, amoplefttype, amoprighttype, amopstrategy>`; oid is a surrogate. A second unique index on `<amopopr, amoppurpose, amopfamily>` answers "is this operator in this opfamily?". [from-comment]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| amopfamily | Oid | — | `pg_opfamily` |
| amoplefttype | Oid | — | `pg_type` |
| amoprighttype | Oid | — | `pg_type` |
| amopstrategy | int16 | — | — |
| amoppurpose | char | `BKI_DEFAULT(s)` | — |
| amopopr | Oid | — | `pg_operator` |
| amopmethod | Oid | — | `pg_am` |
| amopsortfamily | Oid | `BKI_DEFAULT(0)` | `pg_opfamily` (OPT) |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `amoppurpose` on-disk char codes (in `EXPOSE_TO_CLIENT_CODE`): `AMOP_SEARCH 's'`, `AMOP_ORDER 'o'`. [verified-by-code]
- `amopmethod` is an **intentional denormalization** — a copy of the owning opfamily's `opfmethod` field, kept for lookup speed. [from-comment]
- Indexes: `pg_amop_fam_strat_index` on `(amopfamily, amoplefttype, amoprighttype, amopstrategy)`, `pg_amop_opr_fam_index` on `(amopopr, amoppurpose, amopfamily)`, `pg_amop_oid_index` (PK). [verified-by-code]
- Syscaches: `AMOPSTRATEGY` (64), `AMOPOPID` (64). [verified-by-code]
- No function prototypes; opfamily membership is managed via DDL in `commands/opclasscmds.c`. [inferred]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_opfamily.h`, `pg_opclass.h`, `pg_amproc.h` (sibling — support funcs vs operators), `pg_operator.h`.

## Tally

`[verified-by-code]=5 [from-comment]=3 [inferred]=1`
