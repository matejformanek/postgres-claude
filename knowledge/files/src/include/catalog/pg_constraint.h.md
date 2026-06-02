# pg_constraint.h

- **Source path:** `source/src/include/catalog/pg_constraint.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "constraint" system catalog (`pg_constraint`). One row per CHECK / NOT NULL / PRIMARY KEY / UNIQUE / FOREIGN KEY / EXCLUSION / TRIGGER constraint on a relation or domain. [from-comment]

## Catalog definition

- `CATALOG(pg_constraint, 2606, ConstraintRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_constraint` typedef; pointer alias `Form_pg_constraint`. [verified-by-code]
- `DECLARE_TOAST(pg_constraint, 2832, 2833)`. [verified-by-code]
- `(conname, connamespace)` is **deliberately not unique** — global uniqueness would force a global lock for unnamed constraints. Uniqueness is enforced per-relation/per-domain by an index on `(conrelid, contypid, conname)`. [from-comment]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| conname | NameData | — | — |
| connamespace | Oid | — | `pg_namespace` |
| contype | char | — | — |
| condeferrable | bool | — | — |
| condeferred | bool | — | — |
| conenforced | bool | — | — |
| convalidated | bool | — | — |
| conrelid | Oid | — | `pg_class` (OPT; 0 for domain/assertion) |
| contypid | Oid | — | `pg_type` (OPT; 0 unless domain constraint) |
| conindid | Oid | — | `pg_class` (OPT; supporting index) |
| conparentid | Oid | — | `pg_constraint` (OPT; partition parent) |
| confrelid | Oid | — | `pg_class` (OPT; FK referenced table) |
| confupdtype | char | — | — (FK ON UPDATE action) |
| confdeltype | char | — | — (FK ON DELETE action) |
| confmatchtype | char | — | — (FK match type) |
| conislocal | bool | — | — |
| coninhcount | int16 | — | — |
| connoinherit | bool | — | — |
| conperiod | bool | — | — |
| conkey | int16[1] | — | — (varlena; conrelid attnums) |
| confkey | int16[1] | — | — (varlena; confrelid attnums) |
| conpfeqop | Oid[1] | — | `pg_operator` (varlena; PK=FK eq ops) |
| conppeqop | Oid[1] | — | `pg_operator` (varlena; PK=PK eq ops) |
| conffeqop | Oid[1] | — | `pg_operator` (varlena; FK=FK eq ops) |
| confdelsetcols | int16[1] | — | — (varlena; ON DELETE SET subset) |
| conexclop | Oid[1] | — | `pg_operator` (varlena; exclusion ops) |
| conbin | pg_node_tree | — | — (varlena; CHECK expression) |

Varlena columns live in `#ifdef CATALOG_VARLEN`. [verified-by-code]

## Key declarations beyond FormData

- `contype` on-disk char codes (in `EXPOSE_TO_CLIENT_CODE`): `CONSTRAINT_CHECK 'c'`, `CONSTRAINT_FOREIGN 'f'`, `CONSTRAINT_NOTNULL 'n'`, `CONSTRAINT_PRIMARY 'p'`, `CONSTRAINT_UNIQUE 'u'`, `CONSTRAINT_TRIGGER 't'`, `CONSTRAINT_EXCLUSION 'x'`. [verified-by-code]
- `confupdtype`/`confdeltype` use `FKCONSTR_ACTION_*` and `confmatchtype` uses `FKCONSTR_MATCH_*` — both defined in `parsenodes.h`, not here. [from-comment]
- `ConstraintCategory` enum: `CONSTRAINT_RELATION`, `CONSTRAINT_DOMAIN`, `CONSTRAINT_ASSERTION` (future expansion). [verified-by-code]
- Indexes: `pg_constraint_conname_nsp_index`, `pg_constraint_conrelid_contypid_conname_index` (uniq per-rel name), `pg_constraint_contypid_index`, `pg_constraint_oid_index` (PK), `pg_constraint_conparentid_index`. [verified-by-code]
- Syscache: `CONSTROID` (16). [verified-by-code]
- `DECLARE_ARRAY_FOREIGN_KEY_OPT((conrelid, conkey), pg_attribute, (attrelid, attnum))` — note: conkey may contain zero (InvalidAttrNumber) for whole-row Var. [verified-by-code]
- `DECLARE_ARRAY_FOREIGN_KEY((confrelid, confkey), pg_attribute, (attrelid, attnum))`. [verified-by-code]
- Function prototypes: `CreateConstraintEntry`, `ConstraintNameIsUsed`, `ConstraintNameExists`, `ChooseConstraintName`, `findNotNullConstraintAttnum`, `findNotNullConstraint`, `findDomainNotNullConstraint`, `extractNotNullColumn`, `AdjustNotNullInheritance`, `RelationGetNotNullConstraints`, `RemoveConstraintById`, `RenameConstraintById`, `AlterConstraintNamespaces`, `ConstraintSetParentConstraint`, `get_relation_constraint_oid`, `get_relation_constraint_attnos`, `get_domain_constraint_oid`, `get_relation_idx_constraint_oid`, `get_primary_key_attnos`, `DeconstructFkConstraintRow`, `FindFKPeriodOpers`, `check_functional_grouping`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_attrdef.h` (sibling — column defaults), `parsenodes.h` (`FKCONSTR_ACTION_*`, `FKCONSTR_MATCH_*`), `pg_class.h`, `pg_type.h`.

## Tally

`[verified-by-code]=10 [from-comment]=2`
