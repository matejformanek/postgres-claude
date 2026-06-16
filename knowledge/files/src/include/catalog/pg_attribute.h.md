# pg_attribute.h

- **Source path:** `source/src/include/catalog/pg_attribute.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'attribute' system catalog (pg_attribute)." One row per column (user attnums 1..relnatts, plus negative system attnums). Initial contents generated at compile time by genbki.pl — no `pg_attribute.dat` file. `[from-comment]`

## Catalog definition

- `CATALOG(pg_attribute,1249,AttributeRelationId) BKI_BOOTSTRAP BKI_ROWTYPE_OID(75,AttributeRelation_Rowtype_Id) BKI_SCHEMA_MACRO` `[verified-by-code]`
- `FormData_pg_attribute` / `Form_pg_attribute`.
- Sister struct `FormExtraData_pg_attribute` (`NullableDatum attstattarget; NullableDatum attoptions;`) carries selected varlena fields outside the tuple-descriptor copy. `[verified-by-code]`
- `ATTRIBUTE_FIXED_PART_SIZE` = offsetof(attcollation)+sizeof(Oid) — the part actually copied into tuple descriptors. Per header: "you can't access the variable-length fields except in a real tuple." `[from-comment]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| attrelid | Oid | — | `pg_class` |
| attname | NameData | — | — |
| atttypid | Oid | — | `pg_type` (OPT; 0 for dropped col) |
| attlen | int16 | — | — (copy of pg_type.typlen) |
| attnum | int16 | — | — (negative = system attr) |
| atttypmod | int32 | `BKI_DEFAULT(-1)` | — |
| attndims | int16 | — | — |
| attbyval | bool | — | — (copy of pg_type.typbyval) |
| attalign | char | — | — (copy of pg_type.typalign) |
| attstorage | char | — | — (TYPSTORAGE_* values) |
| attcompression | char | `BKI_DEFAULT('\0')` | — ('\0', 'p'=pglz, 'l'=lz4) |
| attnotnull | bool | — | — |
| atthasdef | bool | `BKI_DEFAULT(f)` | — |
| atthasmissing | bool | `BKI_DEFAULT(f)` | — |
| attidentity | char | `BKI_DEFAULT('\0')` | — (ATTRIBUTE_IDENTITY_*) |
| attgenerated | char | `BKI_DEFAULT('\0')` | — (ATTRIBUTE_GENERATED_*) |
| attisdropped | bool | `BKI_DEFAULT(f)` | — |
| attislocal | bool | `BKI_DEFAULT(t)` | — |
| attinhcount | int16 | `BKI_DEFAULT(0)` | — |
| attcollation | Oid | — | `pg_collation` (OPT) |
| attstattarget | int16 | `BKI_DEFAULT(_null_) BKI_FORCE_NULL` (varlena) | — |
| attacl | aclitem[1] | `BKI_DEFAULT(_null_)` (varlena) | — |
| attoptions | text[1] | `BKI_DEFAULT(_null_)` (varlena) | — |
| attfdwoptions | text[1] | `BKI_DEFAULT(_null_)` (varlena) | — |
| attmissingval | anyarray | `BKI_DEFAULT(_null_)` (varlena) | — |

Per header: varlena fields are NOT present in tuple descriptors. `[from-comment]`

## Key declarations beyond FormData

- **On-disk char constants** (under `EXPOSE_TO_CLIENT_CODE`) — also persisted on disk: `[verified-by-code]`
  - `ATTRIBUTE_IDENTITY_ALWAYS='a'`, `ATTRIBUTE_IDENTITY_BY_DEFAULT='d'`.
  - `ATTRIBUTE_GENERATED_STORED='s'`, `ATTRIBUTE_GENERATED_VIRTUAL='v'`.
- Indexes: `pg_attribute_relid_attnam_index` (unique), `pg_attribute_relid_attnum_index` (unique PK). Syscaches: `ATTNAME`, `ATTNUM`. `[verified-by-code]`
- Header comment block forbids the bare DDL pitfall: "If you change the following, make sure you change the structs for system attributes in catalog/heap.c also. You may need to change catalog/genbki.pl as well." `[from-comment]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_class.h.md` (relnatts invariant ties pg_class to pg_attribute)
- `knowledge/files/src/include/catalog/pg_type.h.md` (typlen/typbyval/typalign duplicated into attribute row)
- `knowledge/files/src/include/catalog/heap.h.md` (system-attr struct copies)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: ATTRIBUTE_IDENTITY_* and ATTRIBUTE_GENERATED_* are on-disk char values]** `pg_attribute.h:230-234` — like RELKIND in pg_class, these single-char constants are written to disk verbatim. No warning comment in the block.
- **[ISSUE-undocumented-invariant: attlen/attbyval/attalign must mirror pg_type]** `pg_attribute.h:58-101` — the long comments on atttypid say "they had better match or Postgres will fail," but the dependency between three separate columns and pg_type is asserted only in prose, not enforced by the catalog. A `[inferred]` consumer (heap_form_tuple) crashes/corrupts on mismatch.

## Tally

`[verified-by-code]=4 [from-comment]=4 [inferred]=1`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/catalog-conventions.md](../../../../idioms/catalog-conventions.md)
