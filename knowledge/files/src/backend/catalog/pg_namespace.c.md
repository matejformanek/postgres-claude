# pg_namespace.c

- **Source path:** `source/src/backend/catalog/pg_namespace.c`
- **Lines:** ~120
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_namespace relation." Just the catalog-row I/O for schemas. The search-path machinery is in `namespace.c`; this file only writes pg_namespace tuples for CREATE SCHEMA.

## Public surface

- `NamespaceCreate` — insert the pg_namespace row for a new schema. Records owner dep (pg_shdepend), namespace dep on the database (implicit via being a per-DB catalog), extension membership.
- `RenameNamespace`, `AlterSchemaOwner_internal` — for ALTER SCHEMA.

## Confidence tag tally

`[inferred]=2`
