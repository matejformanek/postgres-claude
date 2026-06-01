# pg_conversion.c

- **Source path:** `source/src/backend/catalog/pg_conversion.c`
- **Lines:** ~155
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_conversion relation." CREATE CONVERSION for client-encoding ↔ server-encoding mappings.

## Public surface

- `ConversionCreate` — insert pg_conversion row, deps on conproc.
- `RemoveConversionById` — called by dependency.c.
- `FindDefaultConversion` — locate the default conversion for an (encoding-from, encoding-to) pair via search_path.

## Confidence tag tally

`[inferred]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
