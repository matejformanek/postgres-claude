# pg_proc.h

- **Source path:** `source/src/include/catalog/pg_proc.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'procedure' system catalog (pg_proc)." One row per SQL-callable routine (function, procedure, aggregate, window function). `[from-comment]`

## Catalog definition

- `CATALOG(pg_proc,1255,ProcedureRelationId) BKI_BOOTSTRAP BKI_ROWTYPE_OID(81,ProcedureRelation_Rowtype_Id) BKI_SCHEMA_MACRO` `[verified-by-code]`
- `FormData_pg_proc` / `Form_pg_proc`.
- Note: `proargtypes` is technically variable-length (`oidvector`) but is laid out before the `CATALOG_VARLEN` boundary so direct C-struct access is permitted. `[from-comment]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| proname | NameData | — | — |
| pronamespace | Oid | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| proowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| prolang | Oid | `BKI_DEFAULT(internal)` | `pg_language` |
| procost | float4 | `BKI_DEFAULT(1)` | — |
| prorows | float4 | `BKI_DEFAULT(0)` | — |
| provariadic | Oid | `BKI_DEFAULT(0)` | `pg_type` (OPT) |
| prosupport | regproc | `BKI_DEFAULT(0)` | `pg_proc` (OPT) |
| prokind | char | `BKI_DEFAULT(f)` | — (PROKIND_*) |
| prosecdef | bool | `BKI_DEFAULT(f)` | — |
| proleakproof | bool | `BKI_DEFAULT(f)` | — |
| proisstrict | bool | `BKI_DEFAULT(t)` | — |
| proretset | bool | `BKI_DEFAULT(f)` | — |
| provolatile | char | `BKI_DEFAULT(i)` | — (PROVOLATILE_*) |
| proparallel | char | `BKI_DEFAULT(s)` | — (PROPARALLEL_*) |
| pronargs | int16 | — | — (genbki fills) |
| pronargdefaults | int16 | `BKI_DEFAULT(0)` | — |
| prorettype | Oid | — | `pg_type` |
| proargtypes | oidvector | `BKI_FORCE_NOT_NULL` | `pg_type` |
| proallargtypes | Oid[1] | `BKI_DEFAULT(_null_)` (varlena) | `pg_type` |
| proargmodes | char[1] | `BKI_DEFAULT(_null_)` (varlena) | — (PROARGMODE_*) |
| proargnames | text[1] | `BKI_DEFAULT(_null_)` (varlena) | — |
| proargdefaults | pg_node_tree | `BKI_DEFAULT(_null_)` (varlena) | — |
| protrftypes | Oid[1] | `BKI_DEFAULT(_null_)` (varlena) | `pg_type` |
| prosrc | text | `BKI_FORCE_NOT_NULL` (varlena) | — |
| probin | text | `BKI_DEFAULT(_null_)` (varlena) | — |
| prosqlbody | pg_node_tree | `BKI_DEFAULT(_null_)` (varlena) | — |
| proconfig | text[1] | `BKI_DEFAULT(_null_)` (varlena) | — |
| proacl | aclitem[1] | `BKI_DEFAULT(_null_)` (varlena) | — |

## Key declarations beyond FormData

- **On-disk char constants** (under `EXPOSE_TO_CLIENT_CODE`): `[verified-by-code]`
  - `PROKIND_FUNCTION='f'`, `PROKIND_AGGREGATE='a'`, `PROKIND_WINDOW='w'`, `PROKIND_PROCEDURE='p'`.
  - `PROVOLATILE_IMMUTABLE='i'`, `PROVOLATILE_STABLE='s'`, `PROVOLATILE_VOLATILE='v'`.
  - `PROPARALLEL_SAFE='s'`, `PROPARALLEL_RESTRICTED='r'`, `PROPARALLEL_UNSAFE='u'`.
  - `PROARGMODE_IN='i'`, `PROARGMODE_OUT='o'`, `PROARGMODE_INOUT='b'`, `PROARGMODE_VARIADIC='v'`, `PROARGMODE_TABLE='t'`. Header explicitly says these must agree with `FunctionParameterMode` enum in parsenodes.h. `[from-comment]`
- TOAST + indexes: `DECLARE_TOAST(pg_proc, 2836, 2837)`; PK `pg_proc_oid_index`, unique `pg_proc_proname_args_nsp_index`. Syscaches: `PROCOID`, `PROCNAMEARGSNSP`. `[verified-by-code]`
- Function prototypes: `ProcedureCreate` (long signature), `function_parse_error_transpose`, `oid_array_to_list`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_type.h.md` (prorettype/proargtypes target)
- `knowledge/files/src/include/catalog/pg_language.h.md` (prolang target)
- `knowledge/files/src/include/catalog/pg_namespace.h.md` (pronamespace target)

## Potential issues

- **[ISSUE-undocumented-invariant: PROKIND/PROVOLATILE/PROPARALLEL/PROARGMODE chars are on-disk values]** `pg_proc.h:155-190` — single-char enums persisted in catalog rows; changing letters breaks on-disk compatibility. Only PROARGMODE has a cross-reference comment (to parsenodes.h enum); the other three lack any stability note.
- **[ISSUE-undocumented-invariant: proargtypes layout pun]** `pg_proc.h:92-97` — header comment says "we allow direct access to proargtypes" because it's the first varlena and falls at a fixed C-struct offset. This is a fragile invariant — if anyone ever inserts a fixed-length nullable column between `prorettype` and `proargtypes`, every reader using `proc->proargtypes` quietly reads garbage. Worth an assertion-style note.

## Tally

`[verified-by-code]=4 [from-comment]=3`
