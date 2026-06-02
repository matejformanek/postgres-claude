# pg_cast.h

- **Source path:** `source/src/include/catalog/pg_cast.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "type casts" system catalog (`pg_cast`). As of Postgres 8.0 it describes both type coercion functions and length coercion functions. [from-comment]

## Catalog definition

- `CATALOG(pg_cast, 2605, CastRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_cast` typedef; pointer alias `Form_pg_cast`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| castsource | Oid | — | `pg_type` |
| casttarget | Oid | — | `pg_type` |
| castfunc | Oid | — | `pg_proc` (OPT, 0 = binary coercible) |
| castcontext | char | — | — |
| castmethod | char | — | — |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `CoercionCodes` enum (on-disk single-char values for `castcontext`): `COERCION_CODE_IMPLICIT 'i'`, `COERCION_CODE_ASSIGNMENT 'a'`, `COERCION_CODE_EXPLICIT 'e'`. Internally remapped to `CoercionContext` (primnodes.h) which sorts by strictness; pg_cast.castcontext letters intentionally do NOT need to sort. [from-comment]
- `CoercionMethod` enum (on-disk values for `castmethod`): `COERCION_METHOD_FUNCTION 'f'`, `COERCION_METHOD_BINARY 'b'`, `COERCION_METHOD_INOUT 'i'`. [verified-by-code]
- Indexes: `pg_cast_oid_index` (PK), `pg_cast_source_target_index` on `(castsource, casttarget)`. [verified-by-code]
- Syscache: `CASTSOURCETARGET` (256). [verified-by-code]
- Function prototype: `CastCreate(...)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_type.h` (cast source/target), `pg_proc.h` (castfunc target), `parser/parse_coerce.c` (consumer).

## Tally

`[verified-by-code]=6 [from-comment]=2`
