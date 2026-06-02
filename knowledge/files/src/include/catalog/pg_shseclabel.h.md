# pg_shseclabel.h

- **Source path:** `source/src/include/catalog/pg_shseclabel.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

`SECURITY LABEL` storage for shared objects (databases, roles, tablespaces). Shared sibling of `pg_seclabel`; lives in `global/`.

## Catalog definition

- `CATALOG(pg_shseclabel, 3592, SharedSecLabelRelationId) BKI_SHARED_RELATION BKI_ROWTYPE_OID(4066, SharedSecLabelRelation_Rowtype_Id) BKI_SCHEMA_MACRO` — **shared catalog**, fixed rowtype OID, Schema macro emitted. [verified-by-code] `pg_shseclabel.h:30`
- `FormData_pg_shseclabel` typedef; pointer alias `Form_pg_shseclabel`. [verified-by-code] `pg_shseclabel.h:40,44`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| objoid | Oid | — | — (OID of the shared object) |
| classoid | Oid | BKI_LOOKUP | `pg_class` |
| provider | text (varlena) | BKI_FORCE_NOT_NULL | — (under `#ifdef CATALOG_VARLEN`) |
| label | text (varlena) | BKI_FORCE_NOT_NULL | — (under `#ifdef CATALOG_VARLEN`) |

Note: no `objsubid` (shared objects don't have sub-objects); compare `pg_seclabel` which does.

## Key declarations beyond FormData

- `DECLARE_TOAST_WITH_MACRO(pg_shseclabel, 4060, 4061, PgShseclabelToastTable, PgShseclabelToastIndex)` — uses `_WITH_MACRO` variant (typical for shared catalogs whose TOAST must be accessible before relcache is up). [verified-by-code] `pg_shseclabel.h:46`
- `DECLARE_UNIQUE_INDEX_PKEY(pg_shseclabel_object_index, 3593, ...)` on (objoid, classoid, provider). [verified-by-code] `pg_shseclabel.h:48`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_seclabel.h` (per-DB sibling)
- Related backend: `src/backend/commands/seclabel.c`

## Potential issues

- **[ISSUE-question: PK missing objsubid because shared objects can't have sub-objects, but classoid alone isn't enough to distinguish databases vs roles]** `pg_shseclabel.h:48` — the PK includes classoid, so shared objects in different shared catalogs (databases vs roles) don't collide. This is fine, but the omission of `objsubid` compared to `pg_seclabel` deserves a comment. Severity `nit`, type `doc-drift`.

## Tally

`[verified-by-code]=6 [inferred]=2`
