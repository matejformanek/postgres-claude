# pg_transform.h

- **Source path:** `source/src/include/catalog/pg_transform.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "transform" system catalog (`pg_transform`) — type↔language transforms registered via `CREATE TRANSFORM FOR <type> LANGUAGE <lang>`, holding the from-SQL and to-SQL conversion functions. [inferred]

## Catalog definition

- `CATALOG(pg_transform, 3576, TransformRelationId)` — per-database. [verified-by-code]
- `FormData_pg_transform` typedef; pointer alias `Form_pg_transform`. [verified-by-code]
- Indexes: PKEY on `oid` (3574); UNIQUE on `(trftype, trflang)` (3575). [verified-by-code]
- Syscaches: `TRFOID`, `TRFTYPELANG`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| trftype | Oid | BKI_LOOKUP | pg_type |
| trflang | Oid | BKI_LOOKUP | pg_language |
| trffromsql | regproc | BKI_LOOKUP_OPT | pg_proc |
| trftosql | regproc | BKI_LOOKUP_OPT | pg_proc |

(No `#ifdef CATALOG_VARLEN` block.)

## Key declarations beyond FormData

- None — no macros, no enums, no function prototypes. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related backend: `source/src/backend/commands/typecmds.c` (CREATE TRANSFORM handling).

## Tally

`[verified-by-code]=8 [inferred]=1`
