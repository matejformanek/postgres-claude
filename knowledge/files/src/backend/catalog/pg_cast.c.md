# pg_cast.c

- **Source path:** `source/src/backend/catalog/pg_cast.c`
- **Lines:** ~115
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_cast relation." CREATE CAST / DROP CAST backend. Stores `(castsource, casttarget) → castfunc + castcontext + castmethod` rows.

## Public surface

- `CastCreate` — insert pg_cast row; deps NORMAL on source/target type and on castfunc (if any); INTERNAL on the binary-coercible-only special case.
- Removal goes via the generic dependency.c machinery (`doDeletion` → `RemoveCastById`).

## Confidence tag tally

`[inferred]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
