# pg_conversion.h

- **Source path:** `source/src/include/catalog/pg_conversion.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "conversion" system catalog (`pg_conversion`). One row per character-set encoding conversion (e.g. UTF8 → LATIN1), pointing at the C function that performs it. [from-comment]

## Catalog definition

- `CATALOG(pg_conversion, 2607, ConversionRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_conversion` typedef; pointer alias `Form_pg_conversion`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| conname | NameData | — | — |
| connamespace | Oid | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| conowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| conforencoding | int32 | — | `encoding` (BKI_LOOKUP — pseudo, resolved by genbki) |
| contoencoding | int32 | — | `encoding` (BKI_LOOKUP — pseudo) |
| conproc | regproc | — | `pg_proc` |
| condefault | bool | `BKI_DEFAULT(t)` | — |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- The `encoding` lookup is a pseudo-catalog handled by genbki to map encoding names (UTF8, SQL_ASCII, etc.) to numeric IDs from `pg_wchar.h`. [inferred]
- Indexes: `pg_conversion_default_index` on `(connamespace, conforencoding, contoencoding, oid)`, `pg_conversion_name_nsp_index` on `(conname, connamespace)`, `pg_conversion_oid_index` (PK). [verified-by-code]
- Syscaches: `CONDEFAULT` (8), `CONNAMENSP` (8), `CONVOID` (8). [verified-by-code]
- Function prototypes: `ConversionCreate(...)`, `FindDefaultConversion(...)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_proc.h` (conproc target), `mb/pg_wchar.h` (encoding IDs).

## Tally

`[verified-by-code]=5 [from-comment]=1 [inferred]=1`
