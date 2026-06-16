# pg_class.h

- **Source path:** `source/src/include/catalog/pg_class.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'relation' system catalog (pg_class)." Every relation-shaped object (table, index, sequence, view, matview, composite type, foreign table, partitioned table/index, propgraph) has a row here. `[from-comment]`

## Catalog definition

- `CATALOG(pg_class,1259,RelationRelationId) BKI_BOOTSTRAP BKI_ROWTYPE_OID(83,RelationRelation_Rowtype_Id) BKI_SCHEMA_MACRO` `[verified-by-code]`
- `FormData_pg_class` / `Form_pg_class`. `CLASS_TUPLE_SIZE` = offsetof(relminmxid)+sizeof(TransactionId) (size of fixed part, used when materializing without varlena tail). `[verified-by-code]`
- Note in header: `BKI_DEFAULT` values are only used for rows in `pg_class.dat` (i.e. bootstrap catalogs). `[from-comment]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| relname | NameData | — | — |
| relnamespace | Oid | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| reltype | Oid | — | `pg_type` (OPT) |
| reloftype | Oid | `BKI_DEFAULT(0)` | `pg_type` (OPT) |
| relowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| relam | Oid | `BKI_DEFAULT(heap)` | `pg_am` (OPT) |
| relfilenode | Oid | `BKI_DEFAULT(0)` | — (0 means "mapped" via relmapper.c) |
| reltablespace | Oid | `BKI_DEFAULT(0)` | `pg_tablespace` (OPT) |
| relpages | int32 | `BKI_DEFAULT(0)` | — |
| reltuples | float4 | `BKI_DEFAULT(-1)` | — (-1 = unknown) |
| relallvisible | int32 | `BKI_DEFAULT(0)` | — |
| relallfrozen | int32 | `BKI_DEFAULT(0)` | — |
| reltoastrelid | Oid | `BKI_DEFAULT(0)` | `pg_class` (OPT) |
| relhasindex | bool | `BKI_DEFAULT(f)` | — |
| relisshared | bool | `BKI_DEFAULT(f)` | — |
| relpersistence | char | `BKI_DEFAULT(p)` | — (see RELPERSISTENCE_*) |
| relkind | char | `BKI_DEFAULT(r)` | — (see RELKIND_*) |
| relnatts | int16 | `BKI_DEFAULT(0)` | — (genbki fills) |
| relchecks | int16 | `BKI_DEFAULT(0)` | — |
| relhasrules | bool | `BKI_DEFAULT(f)` | — |
| relhastriggers | bool | `BKI_DEFAULT(f)` | — |
| relhassubclass | bool | `BKI_DEFAULT(f)` | — |
| relrowsecurity | bool | `BKI_DEFAULT(f)` | — |
| relforcerowsecurity | bool | `BKI_DEFAULT(f)` | — |
| relispopulated | bool | `BKI_DEFAULT(t)` | — |
| relreplident | char | `BKI_DEFAULT(n)` | — (see REPLICA_IDENTITY_*) |
| relispartition | bool | `BKI_DEFAULT(f)` | — |
| relrewrite | Oid | `BKI_DEFAULT(0)` | `pg_class` (OPT) |
| relfrozenxid | TransactionId | `BKI_DEFAULT(3)` | — (FirstNormalTransactionId) |
| relminmxid | TransactionId | `BKI_DEFAULT(1)` | — (FirstMultiXactId) |
| relacl | aclitem[1] | `BKI_DEFAULT(_null_)` (varlena) | — |
| reloptions | text[1] | `BKI_DEFAULT(_null_)` (varlena) | — |
| relpartbound | pg_node_tree | `BKI_DEFAULT(_null_)` (varlena) | — |

Header note: the three varlena fields above are not present in a relcache entry's `rd_rel` field. `[from-comment]`

## Key declarations beyond FormData

- **On-disk char constants** (under `#ifdef EXPOSE_TO_CLIENT_CODE`) — changing any letter is an on-disk format break: `[verified-by-code]`
  - `RELKIND_RELATION='r'`, `RELKIND_INDEX='i'`, `RELKIND_SEQUENCE='S'`, `RELKIND_TOASTVALUE='t'`, `RELKIND_VIEW='v'`, `RELKIND_MATVIEW='m'`, `RELKIND_COMPOSITE_TYPE='c'`, `RELKIND_FOREIGN_TABLE='f'`, `RELKIND_PARTITIONED_TABLE='p'`, `RELKIND_PARTITIONED_INDEX='I'`, `RELKIND_PROPGRAPH='g'`.
  - `RELPERSISTENCE_PERMANENT='p'`, `RELPERSISTENCE_UNLOGGED='u'`, `RELPERSISTENCE_TEMP='t'`.
  - `REPLICA_IDENTITY_DEFAULT='d'`, `REPLICA_IDENTITY_NOTHING='n'`, `REPLICA_IDENTITY_FULL='f'`, `REPLICA_IDENTITY_INDEX='i'`.
- Classification macros: `RELKIND_HAS_STORAGE`, `RELKIND_HAS_PARTITIONS`, `RELKIND_HAS_TABLESPACE`, `RELKIND_HAS_TABLE_AM`. `[verified-by-code]`
- Indexes: `pg_class_oid_index` (PK), `pg_class_relname_nsp_index`, `pg_class_tblspc_relfilenode_index`. Syscaches: `RELOID`, `RELNAMENSP`. `[verified-by-code]`
- Prototype: `errdetail_relkind_not_supported(char relkind)`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_attribute.h.md` (relnatts invariant)
- `knowledge/files/src/include/catalog/pg_type.h.md` (reltype, reloftype)
- `knowledge/files/src/include/catalog/heap.h.md` (relcache + heap helpers)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: RELKIND_* / RELPERSISTENCE_* / REPLICA_IDENTITY_* characters are on-disk values]** `pg_class.h:171-198` — these single-character constants are stored verbatim in `pg_class.relkind` / `relpersistence` / `relreplident` and persisted on disk. Changing any letter silently breaks all existing clusters and dumps. The header does not say so — only the underlying skill conventions and `dependency.h`'s analogous block call this out. Worth a one-line warning comment above the block.

## Tally

`[verified-by-code]=8 [from-comment]=3`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/catalog-conventions.md](../../../../idioms/catalog-conventions.md)
