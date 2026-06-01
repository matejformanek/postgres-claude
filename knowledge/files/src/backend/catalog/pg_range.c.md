# pg_range.c

- **Source path:** `source/src/backend/catalog/pg_range.c`
- **Lines:** ~120
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_range relation." pg_range stores per-range-type metadata: subtype, subtype opclass, collation, canonicalize function, subdiff function, multirange type OID. Written by CREATE TYPE ... AS RANGE in `commands/typecmds.c`.

## Public surface

- `RangeCreate` — insert pg_range row; record dependencies on subtype/opclass/canonical/subdiff functions.
- `RangeDelete` — remove row.

## Confidence tag tally

`[inferred]=2`
