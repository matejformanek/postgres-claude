# pg_sequence.h

- **Source path:** `source/src/include/catalog/pg_sequence.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "sequence" system catalog (`pg_sequence`) — per-sequence parameters (start / min / max / increment / cache / cycle). The current value lives in the sequence relation's data page, not here. [inferred]

## Catalog definition

- `CATALOG(pg_sequence, 2224, SequenceRelationId)` — per-database, no special BKI flags. [verified-by-code]
- `FormData_pg_sequence` typedef; pointer alias `Form_pg_sequence`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_sequence_seqrelid_index, 5002, ...)` over `seqrelid`. [verified-by-code]
- `MAKE_SYSCACHE(SEQRELID, ..., 32)`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| seqrelid | Oid | BKI_LOOKUP | pg_class |
| seqtypid | Oid | BKI_LOOKUP | pg_type |
| seqstart | int64 | — | — |
| seqincrement | int64 | — | — |
| seqmax | int64 | — | — |
| seqmin | int64 | — | — |
| seqcache | int64 | — | — |
| seqcycle | bool | — | — |

(No `#ifdef CATALOG_VARLEN` block — fixed-width row.)

## Key declarations beyond FormData

- None — no macros, no enums, no function prototypes in the header. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related backend: `source/src/backend/commands/sequence.c` (runtime sequence state lives in the heap relation, not this catalog).

## Tally

`[verified-by-code]=10 [inferred]=1`
