# pg_range.h

- **Source path:** `source/src/include/catalog/pg_range.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "range type" system catalog (`pg_range`) — per-range-type subtype, subtype opclass, optional canonicalization and subdiff functions, and the constructor regprocs for range and matching multirange. [verified-by-code]

## Catalog definition

- `CATALOG(pg_range, 3541, RangeRelationId)` — per-database, no special BKI flags. [verified-by-code]
- `FormData_pg_range` typedef; pointer alias `Form_pg_range`. [verified-by-code]
- Indexes: PKEY on `rngtypid` (3542); UNIQUE on `rngmultitypid` (2228). [verified-by-code]
- Syscaches: `RANGETYPE`, `RANGEMULTIRANGE`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| rngtypid | Oid | BKI_LOOKUP | pg_type |
| rngsubtype | Oid | BKI_LOOKUP | pg_type |
| rngmultitypid | Oid | BKI_LOOKUP | pg_type |
| rngcollation | Oid | BKI_DEFAULT(0), BKI_LOOKUP_OPT | pg_collation |
| rngsubopc | Oid | BKI_LOOKUP | pg_opclass |
| rngconstruct2 | regproc | BKI_LOOKUP | pg_proc |
| rngconstruct3 | regproc | BKI_LOOKUP | pg_proc |
| rngmltconstruct0 | regproc | BKI_LOOKUP | pg_proc |
| rngmltconstruct1 | regproc | BKI_LOOKUP | pg_proc |
| rngmltconstruct2 | regproc | BKI_LOOKUP | pg_proc |
| rngcanonical | regproc | BKI_LOOKUP_OPT | pg_proc |
| rngsubdiff | regproc | BKI_LOOKUP_OPT | pg_proc |

(No `#ifdef CATALOG_VARLEN` block.)

## Key declarations beyond FormData

- `extern void RangeCreate(...)` — inserts a row given all twelve column values plus subtype OID and constructor regprocs. [verified-by-code]
- `extern void RangeDelete(Oid rangeTypeOid)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related backend: `source/src/backend/catalog/pg_range.c`, `source/src/backend/utils/adt/rangetypes.c`, `source/src/backend/utils/adt/multirangetypes.c`.

## Tally

`[verified-by-code]=15`
