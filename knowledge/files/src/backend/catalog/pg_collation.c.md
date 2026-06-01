# pg_collation.c

- **Source path:** `source/src/backend/catalog/pg_collation.c`
- **Lines:** ~215
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_collation relation." CREATE COLLATION row writer. Each collation has provider (libc/icu/builtin), collctype/collcollate, encoding, deterministic flag.

## Public surface

- `CollationCreate` — insert pg_collation row; check for duplicate (name, encoding, namespace); record deps.
- Aux: lookup by name+encoding (handled mostly via syscache COLLNAMEENCNSP).

## Confidence tag tally

`[inferred]=2`
