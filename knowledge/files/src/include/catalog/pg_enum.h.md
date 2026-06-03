# pg_enum.h

- **Source path:** `source/src/include/catalog/pg_enum.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "enum" system catalog (`pg_enum`) — one row per enum-label, holding the owning enum type, the label string, and a float4 sort position used for ORDER BY of enum values. [verified-by-code]

## Catalog definition

- `CATALOG(pg_enum, 3501, EnumRelationId)` — per-database. [verified-by-code]
- `FormData_pg_enum` typedef; pointer alias `Form_pg_enum`. [verified-by-code]
- Indexes: PKEY on `oid` (3502); UNIQUE on `(enumtypid, enumlabel)` (3503); UNIQUE on `(enumtypid, enumsortorder)` (3534). [verified-by-code]
- Syscaches: `ENUMOID`, `ENUMTYPOIDNAME`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| enumtypid | Oid | BKI_LOOKUP | pg_type |
| enumsortorder | float4 | — | — |
| enumlabel | NameData | — | — |

(No `#ifdef CATALOG_VARLEN` block.)

## Key declarations beyond FormData

- `extern void EnumValuesCreate(Oid enumTypeOid, List *vals)` / `EnumValuesDelete(Oid enumTypeOid)`. [verified-by-code]
- `extern void AddEnumLabel(Oid enumTypeOid, const char *newVal, const char *neighbor, bool newValIsAfter, bool skipIfExists)` — `ALTER TYPE ... ADD VALUE`. [verified-by-code]
- `extern void RenameEnumLabel(Oid, const char *oldVal, const char *newVal)`. [verified-by-code]
- Uncommitted-enum tracking API: `EnumUncommitted(Oid)`, `EstimateUncommittedEnumsSpace()`, `SerializeUncommittedEnums(void *, Size)`, `RestoreUncommittedEnums(void *)`, `AtEOXact_Enum(void)`. These exist so a freshly-ADDed enum value (whose OID isn't yet visible to other snapshots) can be safely used in the same transaction and passed to parallel workers. [inferred]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related backend: `source/src/backend/catalog/pg_enum.c`, `source/src/backend/utils/adt/enum.c`.

## Tally

`[verified-by-code]=12 [inferred]=1`
