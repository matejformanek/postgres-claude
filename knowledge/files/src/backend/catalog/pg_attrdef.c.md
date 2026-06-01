# pg_attrdef.c

- **Source path:** `source/src/backend/catalog/pg_attrdef.c`
- **Lines:** ~330
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_attrdef relation." Per-column DEFAULT expressions are stored as one pg_attrdef row per `(adrelid, adnum)`. This file handles insert/remove and pg_depend wiring (AUTO dep on the column, NORMAL deps on whatever the expression mentions).

## Public surface

- `StoreAttrDefault` (37) — insert a pg_attrdef row carrying the nodeToString'd expression; record deps via `recordDependencyOnExpr`; also flip `pg_attribute.atthasdef = true`.
- `RemoveAttrDefault` (154) — drop default(s) for a column.
- `RemoveAttrDefaultById` (209) — drop one default by its pg_attrdef OID (used by dependency.c).
- `GetAttrDefaultOid` (280), `GetAttrDefaultColumnAddress` (322) — lookups.

## Confidence tag tally

`[verified-by-code]=2 [inferred]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
